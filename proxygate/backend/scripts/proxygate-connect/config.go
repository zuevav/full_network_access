package main

import (
	"encoding/json"
	"fmt"
	"io"
	"net/http"
	"time"
)

// ConnectConfig is the server-provided configuration.
type ConnectConfig struct {
	Domains         []string `json:"domains"`
	IncludeWildcard bool     `json:"include_wildcard"`
	ServerHost      string   `json:"server_host"`
	ServerPorts     []int    `json:"server_ports"`
	ProxyUser       string   `json:"proxy_user"`
	ProxyPass       string   `json:"proxy_pass"`
}

// fetchConfig downloads configuration from the ProxyGate server.
func fetchConfig(server, token string) (*ConnectConfig, error) {
	url := fmt.Sprintf("https://%s/api/connect-config/%s", server, token)

	client := &http.Client{Timeout: 15 * time.Second}
	resp, err := client.Get(url)
	if err != nil {
		return nil, fmt.Errorf("HTTP request failed: %w", err)
	}
	defer resp.Body.Close()

	if resp.StatusCode != 200 {
		body, _ := io.ReadAll(io.LimitReader(resp.Body, 1024))
		return nil, fmt.Errorf("server returned %d: %s", resp.StatusCode, string(body))
	}

	var cfg ConnectConfig
	if err := json.NewDecoder(resp.Body).Decode(&cfg); err != nil {
		return nil, fmt.Errorf("failed to decode config: %w", err)
	}

	if len(cfg.Domains) == 0 {
		return nil, fmt.Errorf("server returned empty domain list")
	}
	if cfg.ServerHost == "" {
		cfg.ServerHost = server
	}
	if len(cfg.ServerPorts) == 0 {
		cfg.ServerPorts = []int{443, 8443}
	}

	return &cfg, nil
}
