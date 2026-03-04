package main

import (
	"bufio"
	"encoding/base64"
	"encoding/json"
	"fmt"
	"io"
	"log"
	"net"
	"net/http"
	"strings"
	"sync"
	"sync/atomic"
	"time"
)

// localProxy is an HTTP CONNECT proxy that runs on localhost.
// It intercepts CONNECT requests for configured domains and tunnels them
// through the ProxyGate server with ClientHello fragmentation.
type localProxy struct {
	listenAddr string
	cfg        *ConnectConfig
	matcher    *domainMatcher
	fragSize   int
	listener   net.Listener
	proxyAuth  string // base64-encoded user:pass for 3proxy

	activeConns atomic.Int64
}

func newLocalProxy(listen string, cfg *ConnectConfig, matcher *domainMatcher, fragSize int) *localProxy {
	auth := base64.StdEncoding.EncodeToString(
		[]byte(fmt.Sprintf("%s:%s", cfg.ProxyUser, cfg.ProxyPass)),
	)
	return &localProxy{
		listenAddr: listen,
		cfg:        cfg,
		matcher:    matcher,
		fragSize:   fragSize,
		proxyAuth:  auth,
	}
}

func (p *localProxy) start() error {
	ln, err := net.Listen("tcp", p.listenAddr)
	if err != nil {
		return fmt.Errorf("listen %s: %w", p.listenAddr, err)
	}
	p.listener = ln

	for {
		conn, err := ln.Accept()
		if err != nil {
			if strings.Contains(err.Error(), "use of closed") {
				return nil
			}
			continue
		}
		go p.handleClient(conn)
	}
}

func (p *localProxy) stop() {
	if p.listener != nil {
		p.listener.Close()
	}
}

func (p *localProxy) handleClient(conn net.Conn) {
	defer conn.Close()

	conn.SetReadDeadline(time.Now().Add(30 * time.Second))
	reader := bufio.NewReader(conn)

	// Read first line
	firstLine, err := reader.ReadString('\n')
	if err != nil {
		return
	}

	// Handle status endpoint for browser extension
	if strings.HasPrefix(firstLine, "GET /__proxygate_status") {
		p.handleStatus(conn)
		return
	}

	// Only handle CONNECT
	if !strings.HasPrefix(strings.ToUpper(strings.TrimSpace(firstLine)), "CONNECT ") {
		conn.Write([]byte("HTTP/1.1 405 Method Not Allowed\r\n\r\n"))
		return
	}

	// Read remaining headers
	for {
		line, err := reader.ReadString('\n')
		if err != nil || strings.TrimSpace(line) == "" {
			break
		}
	}

	// Parse target
	parts := strings.Fields(firstLine)
	if len(parts) < 2 {
		conn.Write([]byte("HTTP/1.1 400 Bad Request\r\n\r\n"))
		return
	}
	target := parts[1]
	host := target
	if idx := strings.LastIndex(host, ":"); idx > 0 {
		host = host[:idx]
	}

	// Check if domain matches our proxy list
	if !p.matcher.matches(target) {
		// Direct connect — don't proxy, just tunnel directly
		p.handleDirect(conn, target)
		return
	}

	conn.SetReadDeadline(time.Time{})
	p.activeConns.Add(1)
	defer p.activeConns.Add(-1)

	// Connect to ProxyGate server with TLS + ClientHello fragmentation
	serverConn, err := tlsDialWithFallback(p.cfg.ServerHost, p.cfg.ServerPorts, p.fragSize)
	if err != nil {
		log.Printf("Failed to connect to server for %s: %v", host, err)
		conn.Write([]byte("HTTP/1.1 502 Bad Gateway\r\n\r\n"))
		return
	}
	defer serverConn.Close()

	// Send CONNECT request with auth to 3proxy (through Go TLS proxy)
	connectReq := fmt.Sprintf(
		"CONNECT %s HTTP/1.1\r\nHost: %s\r\nProxy-Authorization: Basic %s\r\n\r\n",
		target, host, p.proxyAuth,
	)
	if _, err := serverConn.Write([]byte(connectReq)); err != nil {
		conn.Write([]byte("HTTP/1.1 502 Bad Gateway\r\n\r\n"))
		return
	}

	// Read server response
	br := bufio.NewReader(serverConn)
	resp, err := http.ReadResponse(br, nil)
	if err != nil {
		conn.Write([]byte("HTTP/1.1 502 Bad Gateway\r\n\r\n"))
		return
	}
	resp.Body.Close()

	if resp.StatusCode != 200 {
		conn.Write([]byte(fmt.Sprintf("HTTP/1.1 %d %s\r\n\r\n", resp.StatusCode, resp.Status)))
		return
	}

	// Tell client the tunnel is established
	conn.Write([]byte("HTTP/1.1 200 Connection established\r\n\r\n"))

	// Bidirectional relay
	var wg sync.WaitGroup
	wg.Add(2)
	go func() {
		defer wg.Done()
		io.Copy(serverConn, conn)
	}()
	go func() {
		defer wg.Done()
		io.Copy(conn, serverConn)
	}()
	wg.Wait()
}

// handleDirect tunnels non-matching domains directly (without going through server).
func (p *localProxy) handleDirect(conn net.Conn, target string) {
	if !strings.Contains(target, ":") {
		target += ":443"
	}

	remote, err := net.DialTimeout("tcp", target, 10*time.Second)
	if err != nil {
		conn.Write([]byte("HTTP/1.1 502 Bad Gateway\r\n\r\n"))
		return
	}
	defer remote.Close()

	conn.SetReadDeadline(time.Time{})
	conn.Write([]byte("HTTP/1.1 200 Connection established\r\n\r\n"))

	var wg sync.WaitGroup
	wg.Add(2)
	go func() {
		defer wg.Done()
		io.Copy(remote, conn)
	}()
	go func() {
		defer wg.Done()
		io.Copy(conn, remote)
	}()
	wg.Wait()
}

// handleStatus responds to /__proxygate_status for the browser extension.
func (p *localProxy) handleStatus(conn net.Conn) {
	domains := make([]string, 0, len(p.matcher.exact))
	for d := range p.matcher.exact {
		domains = append(domains, d)
	}
	status := struct {
		Status  string   `json:"status"`
		Version string   `json:"version"`
		Server  string   `json:"server"`
		Domains []string `json:"domains"`
		Active  int64    `json:"active_connections"`
	}{
		Status:  "running",
		Version: version,
		Server:  p.cfg.ServerHost,
		Domains: domains,
		Active:  p.activeConns.Load(),
	}
	body, _ := json.Marshal(status)

	resp := fmt.Sprintf(
		"HTTP/1.1 200 OK\r\nContent-Type: application/json\r\nAccess-Control-Allow-Origin: *\r\nContent-Length: %d\r\nConnection: close\r\n\r\n%s",
		len(body), body,
	)
	conn.Write([]byte(resp))
}
