package main

import (
	"crypto/tls"
	"fmt"
	"math/rand"
	"net"
	"time"
)

// tlsDial connects to the server with TLS, using ClientHello fragmentation.
// It randomizes cipher suite order to defeat TLS fingerprinting.
func tlsDial(host string, port int, fragSize int) (net.Conn, error) {
	addr := fmt.Sprintf("%s:%d", host, port)

	// TCP connect
	rawConn, err := net.DialTimeout("tcp", addr, 10*time.Second)
	if err != nil {
		return nil, fmt.Errorf("TCP dial %s: %w", addr, err)
	}

	// Wrap in fragmenting conn — will fragment the ClientHello
	fragConn := newFragmentingConn(rawConn, fragSize)

	// Randomized cipher suites to defeat fingerprinting
	ciphers := []uint16{
		tls.TLS_ECDHE_ECDSA_WITH_AES_128_GCM_SHA256,
		tls.TLS_ECDHE_RSA_WITH_AES_128_GCM_SHA256,
		tls.TLS_ECDHE_ECDSA_WITH_AES_256_GCM_SHA384,
		tls.TLS_ECDHE_RSA_WITH_AES_256_GCM_SHA384,
		tls.TLS_ECDHE_ECDSA_WITH_CHACHA20_POLY1305,
		tls.TLS_ECDHE_RSA_WITH_CHACHA20_POLY1305,
	}
	rand.Shuffle(len(ciphers), func(i, j int) {
		ciphers[i], ciphers[j] = ciphers[j], ciphers[i]
	})

	tlsConf := &tls.Config{
		ServerName:   host,
		MinVersion:   tls.VersionTLS12,
		NextProtos:   []string{"http/1.1"},
		CipherSuites: ciphers,
	}

	tlsConn := tls.Client(fragConn, tlsConf)
	tlsConn.SetDeadline(time.Now().Add(15 * time.Second))
	if err := tlsConn.Handshake(); err != nil {
		tlsConn.Close()
		return nil, fmt.Errorf("TLS handshake with %s: %w", addr, err)
	}
	tlsConn.SetDeadline(time.Time{})

	return tlsConn, nil
}

// tlsDialWithFallback tries each port in order, returning the first successful connection.
func tlsDialWithFallback(host string, ports []int, fragSize int) (net.Conn, error) {
	var lastErr error
	for _, port := range ports {
		conn, err := tlsDial(host, port, fragSize)
		if err != nil {
			lastErr = err
			continue
		}
		return conn, nil
	}
	return nil, fmt.Errorf("all ports failed, last error: %w", lastErr)
}
