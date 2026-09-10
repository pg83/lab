// SPDX-License-Identifier: MIT
package main

import (
	"bytes"
	"context"
	"encoding/binary"
	"io"
	"net"
	"testing"
	"time"
)

func TestSOCKSConnect(t *testing.T) {
	requireLoopback(t)
	for _, tc := range []struct {
		name, address string
		wire          []byte
	}{
		{"IPv4", "192.0.2.1:443", []byte{1, 192, 0, 2, 1}},
		{"domain", "example.com:443", append([]byte{3, 11}, []byte("example.com")...)},
		{"IPv6", "[2001:db8::1]:443", append([]byte{4}, net.ParseIP("2001:db8::1").To16()...)},
	} {
		t.Run(tc.name, func(t *testing.T) {
			echo, err := net.Listen("tcp", "127.0.0.1:0")
			if err != nil {
				t.Fatal(err)
			}
			defer echo.Close()
			go func() {
				c, err := echo.Accept()
				if err != nil {
					return
				}
				defer c.Close()
				c.SetDeadline(time.Now().Add(5 * time.Second))
				b, _ := io.ReadAll(c) // Reply only after client half-close.
				c.Write(append([]byte("reply:"), b...))
			}()
			listener, err := net.Listen("tcp", "127.0.0.1:0")
			if err != nil {
				t.Fatal(err)
			}
			ctx, cancel := context.WithCancel(context.Background())
			done := make(chan error, 1)
			seen := make(chan string, 1)
			go func() {
				done <- serveSOCKS(ctx, listener, func(ctx context.Context, network, address string) (net.Conn, error) {
					seen <- address
					return (&net.Dialer{}).DialContext(ctx, network, echo.Addr().String())
				})
			}()
			defer func() {
				cancel()
				select {
				case err := <-done:
					if err != nil {
						t.Error(err)
					}
				case <-time.After(5 * time.Second):
					t.Error("SOCKS shutdown blocked")
				}
			}()
			client, err := net.Dial("tcp", listener.Addr().String())
			if err != nil {
				t.Fatal(err)
			}
			defer client.Close()
			client.SetDeadline(time.Now().Add(5 * time.Second))
			client.Write([]byte{5, 1, 0})
			var method [2]byte
			if _, err := io.ReadFull(client, method[:]); err != nil || method != [2]byte{5, 0} {
				t.Fatalf("method: %v %v", method, err)
			}
			request := append([]byte{5, 1, 0}, tc.wire...)
			request = binary.BigEndian.AppendUint16(request, 443)
			client.Write(append(request, []byte("payload")...))
			var reply [10]byte
			if _, err := io.ReadFull(client, reply[:]); err != nil || reply[1] != 0 || reply[3] != 1 {
				t.Fatalf("CONNECT: %v %v", reply, err)
			}
			client.(*net.TCPConn).CloseWrite()
			response, err := io.ReadAll(client)
			if err != nil || string(response) != "reply:payload" {
				t.Fatalf("relay: %q %v", response, err)
			}
			if address := <-seen; address != tc.address {
				t.Fatalf("dialed %s, wanted %s", address, tc.address)
			}
		})
	}
}

func TestSOCKSRejectsUnsupportedRequests(t *testing.T) {
	for _, command := range []byte{2, 3} {
		server, client := net.Pipe()
		done := make(chan struct{})
		go func() {
			defer close(done)
			defer server.Close()
			handleSOCKS(context.Background(), server, func(context.Context, string, string) (net.Conn, error) {
				t.Error("unsupported request reached dialer")
				return nil, net.ErrClosed
			})
		}()
		client.SetDeadline(time.Now().Add(2 * time.Second))
		client.Write([]byte{5, 1, 0})
		var method [2]byte
		io.ReadFull(client, method[:])
		client.Write([]byte{5, command, 0, 1})
		response, err := io.ReadAll(client)
		client.Close()
		<-done
		if err != nil || !bytes.Equal(response, []byte{5, 7, 0, 1, 0, 0, 0, 0, 0, 0}) {
			t.Fatalf("unsupported command response %v: %v", response, err)
		}
	}
}
