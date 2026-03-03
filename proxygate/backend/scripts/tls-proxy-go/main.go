package main

import (
	"bufio"
	"crypto/tls"
	"fmt"
	"io"
	"log"
	"math/rand"
	"net"
	"net/http"
	"os"
	"os/signal"
	"strings"
	"sync"
	"syscall"
	"time"
)

// Config from environment
var (
	listenAddr  = envOr("TLS_PROXY_LISTEN", ":443")
	backupAddr  = envOr("TLS_PROXY_BACKUP", ":8443")
	proxyBackend = envOr("TLS_PROXY_BACKEND", "127.0.0.1:3128")
	webBackend  = envOr("TLS_PROXY_WEB", "127.0.0.1:8445")
	certFile    = envOr("TLS_PROXY_CERT", "/etc/letsencrypt/live/fna.zetit.ru/fullchain.pem")
	keyFile     = envOr("TLS_PROXY_KEY", "/etc/letsencrypt/live/fna.zetit.ru/privkey.pem")
)

func envOr(key, fallback string) string {
	if v := os.Getenv(key); v != "" {
		return v
	}
	return fallback
}

// TLS certificate holder with hot-reload via SIGHUP
type certHolder struct {
	mu   sync.RWMutex
	cert *tls.Certificate
}

func (h *certHolder) load() error {
	cert, err := tls.LoadX509KeyPair(certFile, keyFile)
	if err != nil {
		return err
	}
	h.mu.Lock()
	h.cert = &cert
	h.mu.Unlock()
	return nil
}

func (h *certHolder) getCertificate(*tls.ClientHelloInfo) (*tls.Certificate, error) {
	h.mu.RLock()
	defer h.mu.RUnlock()
	return h.cert, nil
}

// --- Padding: realistic HTTP response disguise ---

var serverNames = []string{
	"nginx/1.24.0", "nginx/1.25.3", "cloudflare", "Apache/2.4.58",
	"nginx", "Microsoft-IIS/10.0", "LiteSpeed",
}

var extraHeaders = []struct{ key, val string }{
	{"ETag", `"%%HEX%%"`},
	{"Cache-Control", "max-age=%%AGE%%"},
	{"Vary", "Accept-Encoding"},
	{"Age", "%%SMALL%%"},
	{"X-Cache", "%%CACHE%%"},
	{"CF-Ray", "%%RAY%%"},
	{"X-Request-Id", "%%HEX%%"},
	{"Accept-Ranges", "bytes"},
	{"X-Powered-By", "Express"},
	{"Via", "1.1 vegur"},
	{"X-Content-Type-Options", "nosniff"},
}

var cacheVals = []string{"HIT", "MISS", "DYNAMIC", "BYPASS"}

func randomHex(n int) string {
	const hex = "0123456789abcdef"
	b := make([]byte, n)
	for i := range b {
		b[i] = hex[rand.Intn(16)]
	}
	return string(b)
}

func expandTemplate(s string) string {
	s = strings.ReplaceAll(s, "%%HEX%%", randomHex(32))
	s = strings.ReplaceAll(s, "%%AGE%%", fmt.Sprintf("%d", rand.Intn(86400)))
	s = strings.ReplaceAll(s, "%%SMALL%%", fmt.Sprintf("%d", rand.Intn(3600)))
	s = strings.ReplaceAll(s, "%%CACHE%%", cacheVals[rand.Intn(len(cacheVals))])
	s = strings.ReplaceAll(s, "%%RAY%%", fmt.Sprintf("%s-FRA", randomHex(16)))
	return s
}

// buildPaddedResponse creates a realistic-looking HTTP 200 response for CONNECT disguise.
func buildPaddedResponse() []byte {
	var sb strings.Builder
	sb.WriteString("HTTP/1.1 200 Connection established\r\n")

	// Server header — rotated per connection
	sb.WriteString(fmt.Sprintf("Server: %s\r\n", serverNames[rand.Intn(len(serverNames))]))

	// Date header
	sb.WriteString(fmt.Sprintf("Date: %s\r\n", time.Now().UTC().Format(http.TimeFormat)))

	// Content-Type
	r := rand.Intn(100)
	switch {
	case r < 70:
		sb.WriteString("Content-Type: text/html; charset=utf-8\r\n")
	case r < 90:
		sb.WriteString("Content-Type: application/json\r\n")
	default:
		sb.WriteString("Content-Type: text/plain\r\n")
	}

	// Random subset of extra headers (4-7 headers, shuffled)
	count := 4 + rand.Intn(4)
	perm := rand.Perm(len(extraHeaders))
	if count > len(perm) {
		count = len(perm)
	}
	for _, idx := range perm[:count] {
		h := extraHeaders[idx]
		sb.WriteString(fmt.Sprintf("%s: %s\r\n", h.key, expandTemplate(h.val)))
	}

	// Body padding — looks like HTML or JSON (5-50KB)
	padSize := 5000 + rand.Intn(45000)
	sb.WriteString(fmt.Sprintf("Content-Length: %d\r\n", padSize))
	sb.WriteString("\r\n")

	if rand.Intn(100) < 70 {
		// HTML body
		sb.WriteString("<!DOCTYPE html><html lang=\"en\"><head><meta charset=\"utf-8\">")
		sb.WriteString("<title>Loading</title></head><body>")
		for sb.Len() < padSize+200 { // +200 for headers already written
			sb.WriteString(fmt.Sprintf("<div class=\"c-%s\"><span>%s</span></div>",
				randomHex(4), randomHex(20+rand.Intn(60))))
		}
		sb.WriteString("</body></html>")
	} else {
		// JSON body
		sb.WriteString(`{"status":"ok","data":{`)
		first := true
		for sb.Len() < padSize+200 {
			if !first {
				sb.WriteByte(',')
			}
			first = false
			sb.WriteString(fmt.Sprintf(`"f_%s":"%s"`, randomHex(4), randomHex(20+rand.Intn(80))))
		}
		sb.WriteString("}}")
	}

	return []byte(sb.String())
}

// --- Connection handling ---

const bufSize = 65536

func relay(a, b net.Conn, wg *sync.WaitGroup) {
	defer wg.Done()
	buf := make([]byte, bufSize)
	io.CopyBuffer(a, b, buf)
	// Signal the other direction to stop
	if tc, ok := a.(*net.TCPConn); ok {
		tc.CloseWrite()
	}
}

func handleCONNECT(clientConn net.Conn, host string) {
	backend, err := net.DialTimeout("tcp", proxyBackend, 10*time.Second)
	if err != nil {
		clientConn.Write([]byte("HTTP/1.1 502 Bad Gateway\r\n\r\n"))
		return
	}
	defer backend.Close()

	if tc, ok := backend.(*net.TCPConn); ok {
		tc.SetNoDelay(true)
	}

	// Forward CONNECT to 3proxy
	connectReq := fmt.Sprintf("CONNECT %s HTTP/1.1\r\nHost: %s\r\n\r\n", host, host)
	if _, err := backend.Write([]byte(connectReq)); err != nil {
		clientConn.Write([]byte("HTTP/1.1 502 Bad Gateway\r\n\r\n"))
		return
	}

	// Read 3proxy response
	br := bufio.NewReader(backend)
	resp, err := http.ReadResponse(br, nil)
	if err != nil {
		clientConn.Write([]byte("HTTP/1.1 502 Bad Gateway\r\n\r\n"))
		return
	}
	resp.Body.Close()

	if resp.StatusCode == 200 {
		// Timing jitter: 10-80ms
		time.Sleep(time.Duration(10+rand.Intn(70)) * time.Millisecond)

		// Send padded response to disguise CONNECT from DPI
		padded := buildPaddedResponse()
		if _, err := clientConn.Write(padded); err != nil {
			return
		}

		// Bidirectional relay
		var wg sync.WaitGroup
		wg.Add(2)
		go relay(clientConn, backend, &wg)
		go relay(backend, clientConn, &wg)
		wg.Wait()
	} else {
		// Forward error response
		clientConn.Write([]byte(fmt.Sprintf("HTTP/1.1 %d %s\r\n\r\n", resp.StatusCode, resp.Status)))
	}
}

func handleHTTP(clientConn net.Conn, firstBytes []byte) {
	backend, err := net.DialTimeout("tcp", webBackend, 10*time.Second)
	if err != nil {
		clientConn.Write([]byte("HTTP/1.1 502 Bad Gateway\r\n\r\n"))
		return
	}
	defer backend.Close()

	if tc, ok := backend.(*net.TCPConn); ok {
		tc.SetNoDelay(true)
	}

	// Send buffered data
	if _, err := backend.Write(firstBytes); err != nil {
		return
	}

	// Bidirectional relay
	var wg sync.WaitGroup
	wg.Add(2)
	go relay(clientConn, backend, &wg)
	go relay(backend, clientConn, &wg)
	wg.Wait()
}

func handleConnection(conn net.Conn) {
	defer conn.Close()

	conn.SetReadDeadline(time.Now().Add(30 * time.Second))

	reader := bufio.NewReaderSize(conn, bufSize)

	// Peek first line to detect CONNECT vs HTTP
	firstLine, err := reader.ReadString('\n')
	if err != nil {
		return
	}

	if strings.HasPrefix(strings.ToUpper(strings.TrimSpace(firstLine)), "CONNECT ") {
		// Read remaining headers
		var headers strings.Builder
		headers.WriteString(firstLine)
		for {
			line, err := reader.ReadString('\n')
			headers.WriteString(line)
			if err != nil || strings.TrimSpace(line) == "" {
				break
			}
		}

		// Parse target host:port
		parts := strings.Fields(firstLine)
		if len(parts) < 2 {
			conn.Write([]byte("HTTP/1.1 400 Bad Request\r\n\r\n"))
			return
		}
		target := parts[1]
		if !strings.Contains(target, ":") {
			target += ":443"
		}

		// Remove deadline for relay
		conn.SetReadDeadline(time.Time{})
		handleCONNECT(conn, target)
	} else {
		// Regular HTTP — pass everything to nginx
		// Inject X-Real-IP / X-Forwarded-For so nginx sees real client IP
		clientIP, _, _ := net.SplitHostPort(conn.RemoteAddr().String())
		ipHeaders := fmt.Sprintf("X-Real-IP: %s\r\nX-Forwarded-For: %s\r\n", clientIP, clientIP)

		// Reconstruct: request line + injected headers + rest of request
		buffered := make([]byte, reader.Buffered())
		n, _ := reader.Read(buffered)
		allData := make([]byte, 0, len(firstLine)+len(ipHeaders)+n)
		allData = append(allData, []byte(firstLine)...)
		allData = append(allData, []byte(ipHeaders)...)
		allData = append(allData, buffered[:n]...)

		// Remove deadline for relay
		conn.SetReadDeadline(time.Time{})
		handleHTTP(conn, allData)
	}
}

func makeTLSConfig(holder *certHolder) *tls.Config {
	return &tls.Config{
		GetCertificate: holder.getCertificate,
		MinVersion:     tls.VersionTLS12,
		NextProtos:     []string{"http/1.1"},
		CipherSuites: []uint16{
			tls.TLS_ECDHE_ECDSA_WITH_AES_128_GCM_SHA256,
			tls.TLS_ECDHE_RSA_WITH_AES_128_GCM_SHA256,
			tls.TLS_ECDHE_ECDSA_WITH_AES_256_GCM_SHA384,
			tls.TLS_ECDHE_RSA_WITH_AES_256_GCM_SHA384,
			tls.TLS_ECDHE_ECDSA_WITH_CHACHA20_POLY1305,
			tls.TLS_ECDHE_RSA_WITH_CHACHA20_POLY1305,
		},
	}
}

func listenTLS(addr string, tlsConf *tls.Config, wg *sync.WaitGroup) net.Listener {
	// Listen on dual-stack (IPv4+IPv6)
	ln, err := net.Listen("tcp", addr)
	if err != nil {
		log.Fatalf("Failed to listen on %s: %v", addr, err)
	}
	tlsLn := tls.NewListener(ln, tlsConf)

	wg.Add(1)
	go func() {
		defer wg.Done()
		for {
			conn, err := tlsLn.Accept()
			if err != nil {
				if strings.Contains(err.Error(), "use of closed") {
					return
				}
				continue
			}
			go handleConnection(conn)
		}
	}()

	return ln
}

func main() {
	log.SetFlags(log.Ldate | log.Ltime | log.Lmsgprefix)
	log.SetPrefix("[tls-proxy] ")

	holder := &certHolder{}
	if err := holder.load(); err != nil {
		log.Fatalf("Failed to load TLS cert: %v", err)
	}

	tlsConf := makeTLSConfig(holder)

	var listenWg sync.WaitGroup

	ln1 := listenTLS(listenAddr, tlsConf, &listenWg)
	log.Printf("Listening on %s (primary)", listenAddr)

	ln2 := listenTLS(backupAddr, tlsConf, &listenWg)
	log.Printf("Listening on %s (backup)", backupAddr)

	log.Printf("CONNECT -> %s | HTTP/WS -> %s | ALPN: http/1.1", proxyBackend, webBackend)

	// Signal handling
	sigCh := make(chan os.Signal, 1)
	signal.Notify(sigCh, syscall.SIGTERM, syscall.SIGINT, syscall.SIGHUP)

	for sig := range sigCh {
		switch sig {
		case syscall.SIGHUP:
			log.Println("SIGHUP: reloading TLS certificates...")
			if err := holder.load(); err != nil {
				log.Printf("Failed to reload certs: %v", err)
			} else {
				log.Println("TLS certificates reloaded")
			}
		case syscall.SIGTERM, syscall.SIGINT:
			log.Println("Shutting down...")
			ln1.Close()
			ln2.Close()
			listenWg.Wait()
			log.Println("Stopped.")
			return
		}
	}
}
