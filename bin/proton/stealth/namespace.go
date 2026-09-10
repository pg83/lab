// SPDX-License-Identifier: MIT
package main

import (
	"context"
	"errors"
	"fmt"
	"log"
	"net"
	"net/netip"
	"os"
	"os/exec"
	"os/signal"
	"runtime"
	"strconv"
	"strings"
	"syscall"
	"time"

	"golang.org/x/sys/unix"
	"golang.zx2c4.com/wireguard/conn"
	"golang.zx2c4.com/wireguard/tun"
)

func reexecSOCKS(address string, endpoint netip.AddrPort) error {
	local, err := netip.ParseAddrPort(address)
	if err != nil || !local.Addr().IsLoopback() || local.Port() == 0 {
		return errors.New("-socks requires a numeric loopback IP and nonzero port")
	}
	if _, err := exec.LookPath("ip"); err != nil {
		return fmt.Errorf("namespace setup requires iproute2: %w", err)
	}
	listener, err := net.ListenTCP("tcp", net.TCPAddrFromAddrPort(local))
	if err != nil {
		return err
	}
	defer listener.Close()
	dialer := net.Dialer{Timeout: 5 * time.Second}
	transport, err := dialer.Dial("tcp", endpoint.String())
	if err != nil {
		return fmt.Errorf("opening Proton transport before netns: %w", err)
	}
	defer transport.Close()
	listenerFile, err := listener.File()
	if err != nil {
		return err
	}
	defer listenerFile.Close()
	transportFile, err := transport.(*net.TCPConn).File()
	if err != nil {
		return err
	}
	defer transportFile.Close()
	for _, f := range []*os.File{listenerFile, transportFile} {
		if _, err := unix.FcntlInt(f.Fd(), unix.F_SETFD, 0); err != nil {
			return err
		}
	}
	parent, err := os.Readlink("/proc/self/ns/net")
	if err != nil {
		return err
	}
	executable, err := os.Executable()
	if err != nil {
		return err
	}
	args := append([]string{executable}, os.Args[1:]...)
	args = append(args, "-socks-fd", strconv.Itoa(int(listenerFile.Fd())), "-transport-fd", strconv.Itoa(int(transportFile.Fd())), "-parent-netns", parent)
	// setns/unshare affects the calling OS thread, not all Go runtime threads.
	// Exec on this locked thread replaces the runtime, keeping the PID and FDs.
	runtime.LockOSThread()
	if err := unix.Unshare(unix.CLONE_NEWNET); err != nil {
		return fmt.Errorf("creating VPN network namespace: %w", err)
	}
	return syscall.Exec(executable, args, os.Environ())
}

func configureNamespace(iface string, c config) error {
	ip := func(args ...string) error {
		out, err := exec.Command("ip", args...).CombinedOutput()
		if err != nil {
			return fmt.Errorf("ip %s: %w: %s", strings.Join(args, " "), err, out)
		}
		return nil
	}
	if err := ip("link", "set", "lo", "up"); err != nil {
		return err
	}
	has4, has6 := false, false
	for _, addr := range c.addresses {
		p := netip.MustParsePrefix(addr)
		has4 = has4 || p.Addr().Is4()
		has6 = has6 || p.Addr().Is6()
		args := []string{"addr", "add", addr, "dev", iface}
		if p.Addr().Is6() {
			args = append(args, "nodad")
		}
		if err := ip(args...); err != nil {
			return err
		}
	}
	if err := ip("link", "set", iface, "up"); err != nil {
		return err
	}
	for _, prefix := range c.allowedIPs {
		p := netip.MustParsePrefix(prefix)
		if p.Addr().Is4() && has4 || p.Addr().Is6() && has6 {
			family := "-4"
			if p.Addr().Is6() {
				family = "-6"
			}
			if err := ip(family, "route", "replace", prefix, "dev", iface); err != nil {
				return err
			}
		}
	}
	return nil
}

func runSOCKSNamespace(listenerFD, transportFD int, parent, iface string, c config, verbose bool, timeout time.Duration) error {
	current, err := os.Readlink("/proc/self/ns/net")
	if err != nil {
		return err
	}
	if parent == "" || current == parent || listenerFD < 3 || transportFD < 3 || listenerFD == transportFD {
		return errors.New("SOCKS worker requires inherited sockets and a fresh network namespace")
	}
	if len(c.dns) == 0 {
		return errors.New("SOCKS mode requires DNS in the WireGuard config")
	}
	lf := os.NewFile(uintptr(listenerFD), "socks-listener")
	listener, err := net.FileListener(lf)
	lf.Close()
	if err != nil {
		return err
	}
	defer listener.Close()
	addr, ok := listener.Addr().(*net.TCPAddr)
	if !ok || !addr.IP.IsLoopback() {
		return errors.New("inherited SOCKS listener must be on loopback")
	}
	tf := os.NewFile(uintptr(transportFD), "proton-transport")
	transport, err := net.FileConn(tf)
	tf.Close()
	if err != nil {
		return err
	}
	defer transport.Close()
	tcp, ok := transport.(*net.TCPConn)
	if !ok || tcp.RemoteAddr().String() != c.endpoint.String() {
		return errors.New("inherited transport does not match Proton endpoint")
	}
	t, err := tun.CreateTUN(iface, c.mtu)
	if err != nil {
		return err
	}
	if err := configureNamespace(iface, c); err != nil {
		t.Close()
		return err
	}
	ctx, cancel := signal.NotifyContext(context.Background(), os.Interrupt, syscall.SIGTERM)
	defer cancel()
	dnsDialer := &net.Dialer{Timeout: 5 * time.Second}
	dialer := &net.Dialer{Resolver: &net.Resolver{
		PreferGo: true,
		Dial: func(ctx context.Context, network, _ string) (net.Conn, error) {
			return dnsDialer.DialContext(ctx, network, net.JoinHostPort(c.dns[0], "53"))
		},
	}}
	ready := make(chan struct{})
	socksDone := make(chan error, 1)
	go func() {
		select {
		case <-ctx.Done():
			socksDone <- nil
			return
		case <-ready:
		}
		log.Printf("SOCKS5 ready on %s, VPN namespace %s", listener.Addr(), current)
		socksDone <- serveSOCKS(ctx, listener, dialer.DialContext)
		cancel()
	}()
	factory := func(ch chan<- error) conn.Bind {
		bind := stealthBind(ch, verbose).(*conn.StdNetBindTcp)
		available := true
		bind.SetDialTCP(func(address string) (*net.TCPConn, error) {
			if !available || address != c.endpoint.String() {
				return nil, errors.New("inherited Proton socket exhausted; restart required")
			}
			available = false
			return tcp, nil
		})
		return bind
	}
	err = serveWithBind(ctx, t, c, verbose, timeout, factory, func() { close(ready) })
	cancel()
	listener.Close()
	socksErr := <-socksDone
	if err != nil {
		return err
	}
	return socksErr
}
