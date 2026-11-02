// EscuelaTenis opens the user's shared private application. No club data or
// credentials are embedded in the executable or stored in its configuration.
package main

import (
	"context"
	"crypto/rand"
	"crypto/subtle"
	_ "embed"
	"encoding/hex"
	"encoding/json"
	"errors"
	"fmt"
	"html/template"
	"net"
	"net/http"
	"net/url"
	"os"
	"path/filepath"
	"strings"
	"sync"
	"time"
)

//go:embed setup.html
var setupHTML string

type settings struct {
	URL string `json:"url"`
}

func validURL(raw string) (string, error) {
	u, err := url.Parse(strings.TrimSpace(raw))
	if err != nil || u.Scheme != "https" || u.Hostname() == "" || u.User != nil || u.RawQuery != "" || u.Fragment != "" || (u.Path != "" && u.Path != "/") {
		return "", errors.New("Introduce la dirección HTTPS de tu aplicación, sin contraseñas, rutas ni parámetros.")
	}
	if strings.ContainsAny(raw, "\r\n\t") {
		return "", errors.New("La dirección contiene caracteres no válidos.")
	}
	u.Path = ""
	return u.String(), nil
}

func readSettings(path string) (settings, error) {
	var config settings
	data, err := os.ReadFile(path)
	if err != nil {
		return config, err
	}
	if len(data) > 4096 {
		return config, errors.New("Configuración demasiado grande")
	}
	if err = json.Unmarshal(data, &config); err != nil {
		return config, err
	}
	config.URL, err = validURL(config.URL)
	return config, err
}

func saveSettings(path, address string) error {
	address, err := validURL(address)
	if err != nil {
		return err
	}
	if err = os.MkdirAll(filepath.Dir(path), 0700); err != nil {
		return err
	}
	data, _ := json.Marshal(settings{URL: address})
	file, err := os.CreateTemp(filepath.Dir(path), "launcher-*.tmp")
	if err != nil {
		return err
	}
	name := file.Name()
	defer os.Remove(name)
	if _, err = file.Write(data); err != nil {
		file.Close()
		return err
	}
	if err = file.Close(); err != nil {
		return err
	}
	// On Windows Rename replaces an existing regular file on the same volume.
	return os.Rename(name, path)
}

func configHandler(configPath, address, token, previous string, saved chan struct{}) http.Handler {
	var once sync.Once
	view := template.Must(template.New("setup").Parse(setupHTML))
	return http.HandlerFunc(func(w http.ResponseWriter, r *http.Request) {
		w.Header().Set("Cache-Control", "no-store")
		w.Header().Set("X-Content-Type-Options", "nosniff")
		w.Header().Set("Content-Security-Policy", "default-src 'none'; style-src 'unsafe-inline'; form-action 'self'; frame-ancestors 'none'; base-uri 'none'")
		if r.Host != address {
			http.Error(w, "Origen no permitido", http.StatusForbidden)
			return
		}
		if r.URL.Path != "/" {
			http.NotFound(w, r)
			return
		}
		if r.Method == "GET" {
			w.Header().Set("Content-Type", "text/html; charset=utf-8")
			view.Execute(w, map[string]string{"Token": token, "URL": previous})
			return
		}
		if r.Method != "POST" {
			w.Header().Set("Allow", "GET, POST")
			http.Error(w, "Método no permitido", 405)
			return
		}
		if r.Header.Get("Origin") != "http://"+address {
			http.Error(w, "Origen no permitido", 403)
			return
		}
		r.Body = http.MaxBytesReader(w, r.Body, 8192)
		if err := r.ParseForm(); err != nil {
			http.Error(w, "Formulario no válido", 400)
			return
		}
		if subtle.ConstantTimeCompare([]byte(r.PostForm.Get("token")), []byte(token)) != 1 {
			http.Error(w, "Formulario no válido", 403)
			return
		}
		target, err := validURL(r.PostForm.Get("url"))
		if err != nil {
			http.Error(w, err.Error()+" Usa Atrás para corregirla.", 400)
			return
		}
		if err := saveSettings(configPath, target); err != nil {
			http.Error(w, "No se ha podido guardar la dirección en tu perfil de Windows.", 500)
			return
		}
		http.Redirect(w, r, target, http.StatusSeeOther)
		once.Do(func() { close(saved) })
	})
}

func configure(path, previous string) error {
	listener, err := net.Listen("tcp4", "127.0.0.1:0")
	if err != nil {
		return err
	}
	tokenBytes := make([]byte, 32)
	if _, err := rand.Read(tokenBytes); err != nil {
		listener.Close()
		return err
	}
	saved := make(chan struct{})
	address := listener.Addr().String()
	server := &http.Server{Handler: configHandler(path, address, hex.EncodeToString(tokenBytes), previous, saved), ReadHeaderTimeout: 5 * time.Second, ReadTimeout: 10 * time.Second, WriteTimeout: 10 * time.Second, IdleTimeout: 10 * time.Second}
	done := make(chan error, 1)
	go func() { done <- server.Serve(listener) }()
	if err := openBrowser("http://" + address); err != nil {
		server.Close()
		return err
	}
	select {
	case <-saved:
		// Give the browser time to receive its redirect before closing the wizard.
		time.Sleep(350 * time.Millisecond)
	case <-time.After(10 * time.Minute):
	case err := <-done:
		if err != http.ErrServerClosed {
			return err
		}
	}
	ctx, cancel := context.WithTimeout(context.Background(), 3*time.Second)
	defer cancel()
	return server.Shutdown(ctx)
}

func run() error {
	if len(os.Args) > 1 && os.Args[1] == "--self-test" {
		dir, err := os.MkdirTemp("", "escuela-selftest-")
		if err != nil {
			return err
		}
		defer os.RemoveAll(dir)
		file := filepath.Join(dir, "launcher.json")
		if err = saveSettings(file, "https://example.com"); err != nil {
			return err
		}
		if _, err = readSettings(file); err != nil {
			return err
		}
		// Exercise replacing an existing config on native Windows too.
		if err = saveSettings(file, "https://example.org"); err != nil {
			return err
		}
		config, err := readSettings(file)
		if err != nil {
			return err
		}
		if config.URL != "https://example.org" {
			return errors.New("No se actualizó la configuración")
		}
		return nil
	}
	root, err := os.UserConfigDir()
	if err != nil {
		return err
	}
	file := filepath.Join(root, "EscuelaTenis", "launcher.json")
	config, loadErr := readSettings(file)
	change := len(os.Args) > 1 && os.Args[1] == "--configurar"
	if loadErr != nil || change || controlPressed() {
		return configure(file, config.URL)
	}
	return openBrowser(config.URL)
}

func main() {
	if err := run(); err != nil {
		if len(os.Args) > 1 && os.Args[1] == "--self-test" {
			fmt.Fprintln(os.Stderr, err)
			os.Exit(1)
		}
		showError("No se ha podido abrir Escuela de Tenis.\n\n" + err.Error())
		os.Exit(1)
	}
}
