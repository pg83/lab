// Stream a protected Unix management socket over an existing SSH session.
package main

import (
	"fmt"
	"io"
	"net"
	"os"
)

func main() {
	if len(os.Args) != 2 {
		fmt.Fprintln(os.Stderr, "usage: socket-relay /path/to/management.sock")
		os.Exit(2)
	}
	c, err := net.DialUnix("unix", nil, &net.UnixAddr{Name: os.Args[1], Net: "unix"})
	if err != nil {
		fmt.Fprintln(os.Stderr, err)
		os.Exit(1)
	}
	defer c.Close()
	go func() {
		io.Copy(c, os.Stdin)
		c.CloseWrite()
	}()
	if _, err := io.Copy(os.Stdout, c); err != nil {
		fmt.Fprintln(os.Stderr, err)
		os.Exit(1)
	}
}
