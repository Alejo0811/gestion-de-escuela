//go:build !windows

package main

import (
	"fmt"
	"os"
)

func openBrowser(address string) error {
	return fmt.Errorf("El lanzador está destinado a Windows: %s", address)
}
func controlPressed() bool  { return false }
func showError(text string) { fmt.Fprintln(os.Stderr, text) }
