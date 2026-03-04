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
	listenAddr    = envOr("TLS_PROXY_LISTEN", ":443")
	backupAddr    = envOr("TLS_PROXY_BACKUP", ":8443")
	proxyBackend  = envOr("TLS_PROXY_BACKEND", "127.0.0.1:3128")
	webBackend    = envOr("TLS_PROXY_WEB", "127.0.0.1:8445")
	certFile      = envOr("TLS_PROXY_CERT", "/etc/letsencrypt/live/fna.zetit.ru/fullchain.pem")
	keyFile       = envOr("TLS_PROXY_KEY", "/etc/letsencrypt/live/fna.zetit.ru/privkey.pem")
	whitelistFile = envOr("TLS_PROXY_WHITELIST", "/etc/3proxy/allowed_ips.txt")
)

// Global whitelist instance
var whitelist = &whitelistHolder{}

func envOr(key, fallback string) string {
	if v := os.Getenv(key); v != "" {
		return v
	}
	return fallback
}

// IP whitelist holder with hot-reload via SIGHUP
type whitelistHolder struct {
	mu  sync.RWMutex
	ips map[string]bool
}

func (w *whitelistHolder) load() {
	ips := make(map[string]bool)
	f, err := os.Open(whitelistFile)
	if err != nil {
		log.Printf("Whitelist file not found (%s), requiring auth for all IPs", whitelistFile)
		w.mu.Lock()
		w.ips = ips
		w.mu.Unlock()
		return
	}
	defer f.Close()
	scanner := bufio.NewScanner(f)
	for scanner.Scan() {
		line := strings.TrimSpace(scanner.Text())
		if line != "" && !strings.HasPrefix(line, "#") {
			ips[line] = true
		}
	}
	w.mu.Lock()
	w.ips = ips
	w.mu.Unlock()
	log.Printf("Whitelist loaded: %d IPs", len(ips))
}

func (w *whitelistHolder) contains(ip string) bool {
	w.mu.RLock()
	defer w.mu.RUnlock()
	return w.ips[ip]
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

// --- ServerHello fragmentation for DPI bypass ---

// serverFragmentingConn wraps a net.Conn and fragments the first N Write() calls
// into small chunks. DPI (TSPU) inspects the first 3-5 TCP segments to extract
// server certificate info. Fragmenting ServerHello + Certificate into 3-byte
// chunks means DPI needs 20+ segments to reconstruct — it gives up after 3-5.
type serverFragmentingConn struct {
	net.Conn
	mu        sync.Mutex
	remaining int // number of writes left to fragment
	fragSize  int // bytes per fragment
}

func (c *serverFragmentingConn) Write(p []byte) (int, error) {
	c.mu.Lock()
	if c.remaining <= 0 {
		c.mu.Unlock()
		return c.Conn.Write(p)
	}
	c.remaining--
	c.mu.Unlock()

	// Fragment this write into small TCP segments
	total := 0
	for total < len(p) {
		end := total + c.fragSize
		if end > len(p) {
			end = len(p)
		}
		n, err := c.Conn.Write(p[total:end])
		total += n
		if err != nil {
			return total, err
		}
		// Small jitter between fragments to look like natural network delay
		time.Sleep(time.Duration(1+rand.Intn(3)) * time.Millisecond)
	}
	return total, nil
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
// NOTE: CONNECT responses MUST NOT include a body — the tunnel starts immediately after
// the header terminator (\r\n\r\n). Any body bytes would corrupt the tunneled TLS handshake.
// Headers-only padding is safe since HTTP clients ignore extra headers in CONNECT 200 responses.
func buildPaddedResponse() []byte {
	var sb strings.Builder
	sb.WriteString("HTTP/1.1 200 Connection established\r\n")

	// Server header — rotated per connection
	sb.WriteString(fmt.Sprintf("Server: %s\r\n", serverNames[rand.Intn(len(serverNames))]))

	// Date header
	sb.WriteString(fmt.Sprintf("Date: %s\r\n", time.Now().UTC().Format(http.TimeFormat)))

	// Random subset of extra headers (3-5 headers, shuffled) — no Content-Type/Content-Length
	count := 3 + rand.Intn(3)
	perm := rand.Perm(len(extraHeaders))
	if count > len(perm) {
		count = len(perm)
	}
	for _, idx := range perm[:count] {
		h := extraHeaders[idx]
		sb.WriteString(fmt.Sprintf("%s: %s\r\n", h.key, expandTemplate(h.val)))
	}

	// End of headers — NO body for CONNECT responses
	sb.WriteString("\r\n")

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

func handleCONNECT(clientConn net.Conn, host string, extraHeaders string) {
	backend, err := net.DialTimeout("tcp", proxyBackend, 10*time.Second)
	if err != nil {
		clientConn.Write([]byte("HTTP/1.1 502 Bad Gateway\r\n\r\n"))
		return
	}
	defer backend.Close()

	if tc, ok := backend.(*net.TCPConn); ok {
		tc.SetNoDelay(true)
	}

	// Forward CONNECT to 3proxy with any auth headers from client
	connectReq := fmt.Sprintf("CONNECT %s HTTP/1.1\r\nHost: %s\r\n%s\r\n", host, host, extraHeaders)
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

	// Send buffered data (may be nil for h2 direct relay)
	if len(firstBytes) > 0 {
		if _, err := backend.Write(firstBytes); err != nil {
			return
		}
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
		// Read remaining headers, extract Proxy-Authorization for forwarding to 3proxy
		var proxyAuth string
		for {
			line, err := reader.ReadString('\n')
			if err != nil || strings.TrimSpace(line) == "" {
				break
			}
			if strings.HasPrefix(strings.ToLower(strings.TrimSpace(line)), "proxy-authorization:") {
				proxyAuth = strings.TrimSpace(line) + "\r\n"
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

		// IP whitelist check: whitelisted IPs pass without auth,
		// non-whitelisted must provide Proxy-Authorization
		clientIP, _, _ := net.SplitHostPort(conn.RemoteAddr().String())
		if !whitelist.contains(clientIP) && proxyAuth == "" {
			conn.Write([]byte("HTTP/1.1 407 Proxy Authentication Required\r\nProxy-Authenticate: Basic realm=\"ProxyGate\"\r\n\r\n"))
			return
		}

		// Remove deadline for relay
		conn.SetReadDeadline(time.Time{})
		handleCONNECT(conn, target, proxyAuth)
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

// --- TLS configuration with DPI-resistant features ---

var cipherSuites = []uint16{
	tls.TLS_ECDHE_ECDSA_WITH_AES_128_GCM_SHA256,
	tls.TLS_ECDHE_RSA_WITH_AES_128_GCM_SHA256,
	tls.TLS_ECDHE_ECDSA_WITH_AES_256_GCM_SHA384,
	tls.TLS_ECDHE_RSA_WITH_AES_256_GCM_SHA384,
	tls.TLS_ECDHE_ECDSA_WITH_CHACHA20_POLY1305,
	tls.TLS_ECDHE_RSA_WITH_CHACHA20_POLY1305,
}

func makeTLSConfig(holder *certHolder) *tls.Config {
	return &tls.Config{
		GetCertificate: holder.getCertificate,
		MinVersion:     tls.VersionTLS12,
		NextProtos:     []string{"http/1.1"},
		CipherSuites:   cipherSuites,
		// Randomize cipher suite order per connection to defeat TLS fingerprinting
		GetConfigForClient: func(hello *tls.ClientHelloInfo) (*tls.Config, error) {
			shuffled := make([]uint16, len(cipherSuites))
			copy(shuffled, cipherSuites)
			rand.Shuffle(len(shuffled), func(i, j int) {
				shuffled[i], shuffled[j] = shuffled[j], shuffled[i]
			})
			return &tls.Config{
				GetCertificate: holder.getCertificate,
				MinVersion:     tls.VersionTLS12,
				NextProtos:     []string{"http/1.1"},
				CipherSuites:   shuffled,
			}, nil
		},
	}
}

func listenTLS(addr string, tlsConf *tls.Config, wg *sync.WaitGroup) net.Listener {
	// Listen on dual-stack (IPv4+IPv6)
	ln, err := net.Listen("tcp", addr)
	if err != nil {
		log.Fatalf("Failed to listen on %s: %v", addr, err)
	}

	wg.Add(1)
	go func() {
		defer wg.Done()
		for {
			rawConn, err := ln.Accept()
			if err != nil {
				if strings.Contains(err.Error(), "use of closed") {
					return
				}
				continue
			}
			go func(rc net.Conn) {
				// Enable TCP_NODELAY so each Write() goes as a separate TCP segment
				if tc, ok := rc.(*net.TCPConn); ok {
					tc.SetNoDelay(true)
				}

				// Wrap in serverFragmentingConn — fragments the first 10 TLS writes
				// (ServerHello + Certificate chain) into 3-byte TCP segments.
				// DPI inspects first 3-5 segments; with 3-byte fragments,
				// certificate data doesn't appear until segment 20+.
				fragConn := &serverFragmentingConn{
					Conn:      rc,
					remaining: 10,
					fragSize:  3,
				}

				// Manual TLS handshake on the fragmenting conn
				tlsConn := tls.Server(fragConn, tlsConf)
				tlsConn.SetDeadline(time.Now().Add(15 * time.Second))
				if err := tlsConn.Handshake(); err != nil {
					tlsConn.Close()
					return
				}
				tlsConn.SetDeadline(time.Time{})

				handleConnection(tlsConn)
			}(rawConn)
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

	whitelist.load()

	tlsConf := makeTLSConfig(holder)

	var listenWg sync.WaitGroup

	ln1 := listenTLS(listenAddr, tlsConf, &listenWg)
	log.Printf("Listening on %s (primary)", listenAddr)

	ln2 := listenTLS(backupAddr, tlsConf, &listenWg)
	log.Printf("Listening on %s (backup)", backupAddr)

	log.Printf("CONNECT -> %s | HTTP/WS -> %s | ALPN: http/1.1 | ServerHello fragmentation: 3B/segment", proxyBackend, webBackend)

	// Signal handling
	sigCh := make(chan os.Signal, 1)
	signal.Notify(sigCh, syscall.SIGTERM, syscall.SIGINT, syscall.SIGHUP)

	for sig := range sigCh {
		switch sig {
		case syscall.SIGHUP:
			log.Println("SIGHUP: reloading TLS certificates and whitelist...")
			if err := holder.load(); err != nil {
				log.Printf("Failed to reload certs: %v", err)
			} else {
				log.Println("TLS certificates reloaded")
			}
			whitelist.load()
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
