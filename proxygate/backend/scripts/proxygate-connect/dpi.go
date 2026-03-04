package main

import (
	"math/rand"
	"net"
	"sync"
	"time"
)

// fragmentingConn wraps a net.Conn and fragments the first Write() call
// (the TLS ClientHello) into tiny TCP segments to defeat DPI.
//
// How it works:
// - TCP_NODELAY is enabled, so each Write() becomes a separate TCP segment
// - The ClientHello (~250 bytes) is split into fragments of `fragSize` bytes (default 2)
// - This produces 125+ TCP segments instead of 1
// - SNI (at offset ~43+) doesn't appear until segment 22+ with 2-byte fragments
// - TSPU/DPI gives up after inspecting 3-5 segments → connection passes through
// - After the first Write(), all subsequent writes pass through normally
type fragmentingConn struct {
	net.Conn
	mu            sync.Mutex
	fragSize      int
	firstWriteDone bool
}

func newFragmentingConn(conn net.Conn, fragSize int) *fragmentingConn {
	// Enable TCP_NODELAY so each small Write() goes as its own TCP segment
	if tc, ok := conn.(*net.TCPConn); ok {
		tc.SetNoDelay(true)
	}
	return &fragmentingConn{
		Conn:     conn,
		fragSize: fragSize,
	}
}

func (c *fragmentingConn) Write(p []byte) (int, error) {
	c.mu.Lock()
	if c.firstWriteDone {
		c.mu.Unlock()
		return c.Conn.Write(p)
	}
	c.firstWriteDone = true
	c.mu.Unlock()

	// Fragment the ClientHello into tiny TCP segments
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
		// Random jitter 1-5ms between fragments to mimic natural network variation
		time.Sleep(time.Duration(1+rand.Intn(5)) * time.Millisecond)
	}
	return total, nil
}
