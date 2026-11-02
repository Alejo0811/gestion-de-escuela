package main

import (
	"fmt"
	"syscall"
	"unsafe"
)

var shellExecute = syscall.NewLazyDLL("shell32.dll").NewProc("ShellExecuteW")
var messageBox = syscall.NewLazyDLL("user32.dll").NewProc("MessageBoxW")
var keyState = syscall.NewLazyDLL("user32.dll").NewProc("GetAsyncKeyState")

func openBrowser(address string) error {
	target, err := syscall.UTF16PtrFromString(address)
	if err != nil {
		return err
	}
	verb, _ := syscall.UTF16PtrFromString("open")
	result, _, _ := shellExecute.Call(0, uintptr(unsafe.Pointer(verb)), uintptr(unsafe.Pointer(target)), 0, 0, 1)
	if result <= 32 {
		return fmt.Errorf("Windows no pudo abrir el navegador (código %d)", result)
	}
	return nil
}

func controlPressed() bool { result, _, _ := keyState.Call(0x11); return result&0x8000 != 0 }

func showError(text string) {
	title, _ := syscall.UTF16PtrFromString("Escuela de Tenis")
	body, _ := syscall.UTF16PtrFromString(text)
	messageBox.Call(0, uintptr(unsafe.Pointer(body)), uintptr(unsafe.Pointer(title)), 0x10)
}
