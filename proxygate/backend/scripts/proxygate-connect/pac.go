package main

import (
	"strings"
)

// domainMatcher checks whether a hostname should be routed through the proxy.
type domainMatcher struct {
	exact    map[string]bool // exact domain matches
	wildcard map[string]bool // suffix matches (*.domain)
}

func newDomainMatcher(domains []string, includeWildcard bool) *domainMatcher {
	m := &domainMatcher{
		exact:    make(map[string]bool),
		wildcard: make(map[string]bool),
	}
	for _, d := range domains {
		d = strings.ToLower(strings.TrimSpace(d))
		if d == "" {
			continue
		}
		m.exact[d] = true
		if includeWildcard {
			// Also match all subdomains: *.example.com
			m.wildcard["."+d] = true
		}
	}
	return m
}

func (m *domainMatcher) count() int {
	return len(m.exact)
}

// matches returns true if the host (with optional :port) should be proxied.
func (m *domainMatcher) matches(host string) bool {
	// Strip port if present
	if idx := strings.LastIndex(host, ":"); idx > 0 {
		host = host[:idx]
	}
	host = strings.ToLower(host)

	// Exact match
	if m.exact[host] {
		return true
	}

	// Wildcard/subdomain match: check if host ends with .domain
	for suffix := range m.wildcard {
		if strings.HasSuffix(host, suffix) {
			return true
		}
	}

	return false
}
