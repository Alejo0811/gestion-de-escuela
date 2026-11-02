package main

import (
	"io"
	"net/http"
	"net/http/httptest"
	"net/url"
	"path/filepath"
	"strings"
	"testing"
)

func TestURLValidation(t *testing.T) {
	for _, bad := range []string{"http://example.com", "javascript:alert(1)", "https://user:pass@example.com", "https://example.com/?token=private", "https://example.com/#secret", "https://example.com/login", "https://"} {
		if _, err := validURL(bad); err == nil {
			t.Errorf("accepted %q", bad)
		}
	}
	if got, err := validURL(" https://escuela.example.com/ "); err != nil || got != "https://escuela.example.com" {
		t.Fatal(got, err)
	}
}

func TestWizardSavesOnlyAddress(t *testing.T) {
	file := filepath.Join(t.TempDir(), "launcher.json")
	saved := make(chan struct{})
	handler := configHandler(file, "127.0.0.1:3210", "secret-nonce", "", saved)
	send := func(token, origin, host string) *httptest.ResponseRecorder {
		body := url.Values{"token": {token}, "url": {"https://my-school.example.com"}}
		req := httptest.NewRequest(http.MethodPost, "http://127.0.0.1:3210/", strings.NewReader(body.Encode()))
		req.Header.Set("Content-Type", "application/x-www-form-urlencoded")
		req.Header.Set("Origin", origin)
		req.Host = host
		recorder := httptest.NewRecorder()
		handler.ServeHTTP(recorder, req)
		return recorder
	}
	for _, r := range []*httptest.ResponseRecorder{send("wrong", "http://127.0.0.1:3210", "127.0.0.1:3210"), send("secret-nonce", "https://attacker.example", "127.0.0.1:3210"), send("secret-nonce", "http://127.0.0.1:3210", "attacker.example")} {
		if r.Code != 403 {
			t.Fatalf("CSRF accepted: %d", r.Code)
		}
	}
	response := send("secret-nonce", "http://127.0.0.1:3210", "127.0.0.1:3210")
	if response.Code != 303 || response.Header().Get("Location") != "https://my-school.example.com" {
		t.Fatal(response)
	}
	config, err := readSettings(file)
	if err != nil || config.URL != "https://my-school.example.com" {
		t.Fatal(config, err)
	}
	select {
	case <-saved:
	default:
		t.Fatal("did not complete")
	}
	if err = saveSettings(file, "https://updated.example.com"); err != nil {
		t.Fatal(err)
	}
	config, err = readSettings(file)
	if err != nil || config.URL != "https://updated.example.com" {
		t.Fatal(config, err)
	}
}

func TestWizardEscapesAndHidesUnrelatedPaths(t *testing.T) {
	handler := configHandler(filepath.Join(t.TempDir(), "config.json"), "127.0.0.1:3210", "nonce", "https://example.com/?x=\"<script>", make(chan struct{}))
	req := httptest.NewRequest("GET", "http://127.0.0.1:3210/", nil)
	req.Host = "127.0.0.1:3210"
	response := httptest.NewRecorder()
	handler.ServeHTTP(response, req)
	body, _ := io.ReadAll(response.Result().Body)
	if strings.Contains(string(body), "<script>") {
		t.Fatal("unescaped configuration")
	}
	req.URL.Path = "/launcher.json"
	response = httptest.NewRecorder()
	handler.ServeHTTP(response, req)
	if response.Code != 404 {
		t.Fatal("configuration exposed")
	}
}
