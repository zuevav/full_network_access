package main

import (
	"flag"
	"fmt"
	"log"
	"os"
	"os/signal"
	"syscall"
)

var (
	version = "0.7.0"
)

func main() {
	token := flag.String("token", "", "Access token from ProxyGate server")
	server := flag.String("server", "", "ProxyGate server hostname (e.g. fna.zetit.ru)")
	listen := flag.String("listen", "127.0.0.1:8800", "Local proxy listen address")
	fragSize := flag.Int("frag", 2, "ClientHello fragment size in bytes")
	showVersion := flag.Bool("version", false, "Show version and exit")
	flag.Parse()

	if *showVersion {
		fmt.Printf("proxygate-connect v%s\n", version)
		os.Exit(0)
	}

	if *token == "" || *server == "" {
		fmt.Fprintf(os.Stderr, "Usage: proxygate-connect -token=TOKEN -server=HOST\n\n")
		fmt.Fprintf(os.Stderr, "  -token    Access token from ProxyGate server\n")
		fmt.Fprintf(os.Stderr, "  -server   ProxyGate server hostname\n")
		fmt.Fprintf(os.Stderr, "  -listen   Local proxy address (default 127.0.0.1:8800)\n")
		fmt.Fprintf(os.Stderr, "  -frag     ClientHello fragment size (default 2)\n")
		os.Exit(1)
	}

	log.SetFlags(log.Ldate | log.Ltime | log.Lmsgprefix)
	log.SetPrefix("[proxygate] ")

	log.Printf("proxygate-connect v%s", version)
	log.Printf("Server: %s | Fragment size: %d bytes", *server, *fragSize)

	// Fetch configuration from server
	cfg, err := fetchConfig(*server, *token)
	if err != nil {
		log.Fatalf("Failed to fetch config: %v", err)
	}
	log.Printf("Config loaded: %d domains, ports %v", len(cfg.Domains), cfg.ServerPorts)

	// Build domain matcher from config
	matcher := newDomainMatcher(cfg.Domains, cfg.IncludeWildcard)
	log.Printf("Domain matcher ready: %d patterns", matcher.count())

	// Start local proxy
	proxy := newLocalProxy(*listen, cfg, matcher, *fragSize)
	go func() {
		if err := proxy.start(); err != nil {
			log.Fatalf("Proxy failed: %v", err)
		}
	}()
	log.Printf("Local proxy listening on %s", *listen)
	log.Printf("Configure your browser: PROXY %s", *listen)

	// Wait for signal
	sigCh := make(chan os.Signal, 1)
	signal.Notify(sigCh, syscall.SIGTERM, syscall.SIGINT)
	<-sigCh
	log.Println("Shutting down...")
	proxy.stop()
}
