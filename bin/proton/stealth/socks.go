// SPDX-License-Identifier: MIT
package main

import (
	"context"
	"encoding/binary"
	"errors"
	"fmt"
	"io"
	"log"
	"net"
	"strconv"
	"sync"
	"time"
)

type socksDial func(context.Context, string, string) (net.Conn, error)

func serveSOCKS(ctx context.Context, listener net.Listener, dial socksDial) error {
	ctx, cancel := context.WithCancel(ctx)
	stop := context.AfterFunc(ctx, func() { listener.Close() })
	defer stop()
	defer listener.Close()
	var clients sync.WaitGroup
	defer clients.Wait()
	defer cancel()
	limit := make(chan struct{}, 256)
	for {
		client, err := listener.Accept()
		if err != nil {
			if ctx.Err() != nil {
				return nil
			}
			return err
		}
		select {
		case limit <- struct{}{}:
		default:
			client.Close()
			continue
		}
		clients.Add(1)
		go func() {
			defer clients.Done()
			defer func() { <-limit }()
			defer client.Close()
			stop := context.AfterFunc(ctx, func() { client.Close() })
			defer stop()
			// Malformed requests and disconnected clients only affect this stream.
			if err := handleSOCKS(ctx, client, dial); err != nil && ctx.Err() == nil && !errors.Is(err, io.EOF) && !errors.Is(err, net.ErrClosed) {
				log.Printf("SOCKS request: %v", err)
			}
		}()
	}
}

func handleSOCKS(ctx context.Context, client net.Conn, dial socksDial) error {
	client.SetDeadline(time.Now().Add(10 * time.Second))
	var greeting [2]byte
	if _, err := io.ReadFull(client, greeting[:]); err != nil {
		return err
	}
	if greeting[0] != 5 || greeting[1] == 0 {
		return errors.New("invalid SOCKS5 greeting")
	}
	methods := make([]byte, int(greeting[1]))
	if _, err := io.ReadFull(client, methods); err != nil {
		return err
	}
	noAuth := false
	for _, method := range methods {
		noAuth = noAuth || method == 0
	}
	if !noAuth {
		_, err := client.Write([]byte{5, 255})
		return err
	}
	if _, err := client.Write([]byte{5, 0}); err != nil {
		return err
	}
	var request [4]byte
	if _, err := io.ReadFull(client, request[:]); err != nil {
		return err
	}
	if request[0] != 5 || request[2] != 0 {
		return errors.New("invalid SOCKS5 request")
	}
	if request[1] != 1 {
		return socksReply(client, 7, nil) // CONNECT only, like the existing TCP exit.
	}
	var host string
	switch request[3] {
	case 1, 4:
		n := 4
		if request[3] == 4 {
			n = 16
		}
		ip := make([]byte, n)
		if _, err := io.ReadFull(client, ip); err != nil {
			return err
		}
		host = net.IP(ip).String()
	case 3:
		var size [1]byte
		if _, err := io.ReadFull(client, size[:]); err != nil {
			return err
		}
		if size[0] == 0 {
			return socksReply(client, 8, nil)
		}
		name := make([]byte, int(size[0]))
		if _, err := io.ReadFull(client, name); err != nil {
			return err
		}
		host = string(name)
	default:
		return socksReply(client, 8, nil)
	}
	var port [2]byte
	if _, err := io.ReadFull(client, port[:]); err != nil {
		return err
	}
	client.SetDeadline(time.Now().Add(20 * time.Second))
	dialCtx, cancel := context.WithTimeout(ctx, 15*time.Second)
	remote, err := dial(dialCtx, "tcp", net.JoinHostPort(host, strconv.Itoa(int(binary.BigEndian.Uint16(port[:])))))
	cancel()
	if err != nil {
		_ = socksReply(client, 4, nil)
		return fmt.Errorf("SOCKS dial: %w", err)
	}
	defer remote.Close()
	stop := context.AfterFunc(ctx, func() { remote.Close() })
	defer stop()
	if err := socksReply(client, 0, remote.LocalAddr()); err != nil {
		return err
	}
	client.SetDeadline(time.Time{})
	done := make(chan struct{})
	go func() {
		_, err := io.Copy(remote, client)
		if c, ok := remote.(interface{ CloseWrite() error }); ok && err == nil {
			c.CloseWrite()
		} else {
			remote.Close()
		}
		close(done)
	}()
	_, err = io.Copy(client, remote)
	if c, ok := client.(interface{ CloseWrite() error }); ok {
		c.CloseWrite()
	}
	client.Close()
	remote.Close()
	<-done
	return err
}

func socksReply(w io.Writer, code byte, addr net.Addr) error {
	ip := net.IPv4zero.To4()
	port := 0
	if tcp, ok := addr.(*net.TCPAddr); ok {
		ip, port = tcp.IP, tcp.Port
	}
	kind := byte(4)
	if v4 := ip.To4(); v4 != nil {
		ip, kind = v4, 1
	} else {
		ip = ip.To16()
	}
	b := append([]byte{5, code, 0, kind}, ip...)
	b = binary.BigEndian.AppendUint16(b, uint16(port))
	_, err := w.Write(b)
	return err
}
