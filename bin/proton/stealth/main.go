// SPDX-License-Identifier: MIT
package main

import (
	"bufio"
	"context"
	"encoding/base64"
	"encoding/hex"
	"errors"
	"flag"
	"fmt"
	"io"
	"log"
	"net/netip"
	"os"
	"os/signal"
	"strconv"
	"strings"
	"syscall"
	"time"

	"golang.zx2c4.com/wireguard/conn"
	"golang.zx2c4.com/wireguard/conn/server_name_utils"
	"golang.zx2c4.com/wireguard/device"
	"golang.zx2c4.com/wireguard/tun"
)

type config struct {
	privateKey, publicKey, presharedKey string
	endpoint                            netip.AddrPort
	addresses, allowedIPs, dns          []string
	mtu, keepalive                      int
}

func keyHex(value string) (string, error) {
	b, err := base64.StdEncoding.DecodeString(value)
	if err != nil || len(b) != 32 {
		return "", errors.New("expected a base64-encoded 32-byte key")
	}
	var nonzero byte
	for _, v := range b {
		nonzero |= v
	}
	if nonzero == 0 {
		return "", errors.New("zero key is not allowed")
	}
	return hex.EncodeToString(b), nil
}

// Only the declarative subset of a single-peer wg-quick config is supported.
// In particular, shell hooks and routing directives must not be silently ignored.
func readConfig(r io.Reader, endpoint string) (config, error) {
	c := config{mtu: 1320, keepalive: 25}
	var err error
	c.endpoint, err = netip.ParseAddrPort(endpoint)
	if err != nil || c.endpoint.Port() == 0 || c.endpoint.Addr().IsUnspecified() || c.endpoint.Addr().Zone() != "" {
		return c, errors.New("-endpoint must specify the Stealth server's numeric IP:TCP-port (not the exported UDP port)")
	}
	section := ""
	sections := make(map[string]bool)
	seen := make(map[string]bool)
	s := bufio.NewScanner(r)
	for line := 1; s.Scan(); line++ {
		text, _, _ := strings.Cut(s.Text(), "#")
		text = strings.TrimSpace(text)
		if text == "" {
			continue
		}
		if text == "[Interface]" || text == "[Peer]" {
			section = text
			if sections[section] {
				return c, fmt.Errorf("line %d: expected exactly one Interface and one Peer", line)
			}
			sections[section] = true
			continue
		}
		k, v, ok := strings.Cut(text, "=")
		if !ok || section == "" {
			return c, fmt.Errorf("line %d: invalid config syntax", line)
		}
		k, v = strings.TrimSpace(k), strings.TrimSpace(v)
		field := section + k
		if seen[field] {
			return c, fmt.Errorf("line %d: duplicate field", line)
		}
		seen[field] = true
		err = nil
		switch field {
		case "[Interface]PrivateKey":
			c.privateKey, err = keyHex(v)
		case "[Peer]PublicKey":
			c.publicKey, err = keyHex(v)
		case "[Peer]PresharedKey":
			c.presharedKey, err = keyHex(v)
		case "[Interface]Address", "[Peer]AllowedIPs":
			for _, value := range strings.Split(v, ",") {
				p, e := netip.ParsePrefix(strings.TrimSpace(value))
				if e != nil {
					err = errors.New("invalid IP prefix")
					break
				}
				if section == "[Interface]" {
					c.addresses = append(c.addresses, p.String())
				} else {
					c.allowedIPs = append(c.allowedIPs, p.Masked().String())
				}
			}
		case "[Interface]DNS":
			for _, value := range strings.Split(v, ",") {
				a, e := netip.ParseAddr(strings.TrimSpace(value))
				if e != nil {
					err = errors.New("DNS must contain IP addresses")
					break
				}
				c.dns = append(c.dns, a.String())
			}
		case "[Interface]MTU":
			c.mtu, err = strconv.Atoi(v)
			if err != nil || c.mtu < 576 || c.mtu > 9000 {
				err = errors.New("MTU must be between 576 and 9000")
			}
		case "[Peer]PersistentKeepalive":
			c.keepalive, err = strconv.Atoi(v)
			if err != nil || c.keepalive < 1 || c.keepalive > 65535 {
				err = errors.New("PersistentKeepalive must be between 1 and 65535 for this supervised client")
			}
		case "[Peer]Endpoint":
			// Always overridden by the explicit Stealth endpoint flag.
		default:
			err = errors.New("unsupported field (routing and shell hooks belong outside this process)")
		}
		if err != nil {
			// Do not include input values: they can contain private keys.
			return c, fmt.Errorf("line %d: %w", line, err)
		}
	}
	if err := s.Err(); err != nil {
		return c, fmt.Errorf("reading config: %w", err)
	}
	if c.privateKey == "" || c.publicKey == "" || len(c.addresses) == 0 || len(c.allowedIPs) == 0 {
		return c, errors.New("config requires Interface PrivateKey/Address and Peer PublicKey/AllowedIPs")
	}
	return c, nil
}

func (c config) sources() string {
	ips := make([]string, 0, len(c.addresses))
	for _, p := range c.addresses {
		ips = append(ips, netip.MustParsePrefix(p).Addr().String())
	}
	return strings.Join(ips, ",")
}

func (c config) ipc() string {
	var b strings.Builder
	fmt.Fprintf(&b, "private_key=%s\nreplace_peers=true\npublic_key=%s\nendpoint=%s\npersistent_keepalive_interval=%d\nreplace_allowed_ips=true\n", c.privateKey, c.publicKey, c.endpoint, c.keepalive)
	if c.presharedKey != "" {
		fmt.Fprintf(&b, "preshared_key=%s\n", c.presharedKey)
	}
	for _, prefix := range c.allowedIPs {
		fmt.Fprintf(&b, "allowed_ip=%s\n", prefix)
	}
	return b.String()
}

func stealthBind(errors chan<- error, verbose bool) conn.Bind {
	quiet := func(string, ...any) {}
	l := &conn.Logger{Errorf: log.Printf, Verbosef: quiet}
	if verbose {
		l.Verbosef = log.Printf
	}
	return conn.CreateStdNetBind("tls", server_name_utils.ServerNameTop, l, errors, func(int) int { return 0 })
}

// NewDevice starts its TUN readers immediately. Hold both packets and link
// events until the TLS endpoint and peer are configured and the device is up.
type startupTUN struct {
	tun.Device
	configured <-chan struct{}
}

func (t startupTUN) Read(b []byte, offset int) (int, error) {
	<-t.configured
	return t.Device.Read(b, offset)
}

func (t startupTUN) Events() <-chan tun.Event {
	<-t.configured
	return t.Device.Events()
}

func serve(ctx context.Context, t tun.Device, c config, verbose bool, timeout time.Duration) error {
	return serveWithBind(ctx, t, c, verbose, timeout, func(ch chan<- error) conn.Bind {
		return stealthBind(ch, verbose)
	}, nil)
}

func serveWithBind(ctx context.Context, t tun.Device, c config, verbose bool, timeout time.Duration, makeBind func(chan<- error) conn.Bind, onReady func()) error {
	transportErrors := make(chan error)
	handshakes := make(chan device.HandshakeState)
	failure := make(chan error, 1)
	ready := make(chan struct{}, 1)
	done := make(chan struct{})
	// Proton sends synchronously on both channels, including while closing.
	// Keep draining until Device.Close has completed to avoid a shutdown deadlock.
	go func() {
		for {
			select {
			case <-done:
				return
			case err := <-transportErrors:
				select {
				case failure <- fmt.Errorf("Stealth transport: %w", err):
				default:
				}
			case state := <-handshakes:
				if state == device.HandshakeFail {
					select {
					case failure <- errors.New("WireGuard handshake failed"):
					default:
					}
				}
				if state == device.HandshakeSuccess {
					select {
					case ready <- struct{}{}:
					default:
					}
				}
			}
		}
	}()
	defer close(done)
	level := device.LogLevelError
	if verbose {
		level = device.LogLevelVerbose
	}
	configured := make(chan struct{})
	d := device.NewDevice(startupTUN{t, configured}, makeBind(transportErrors), device.NewLogger(level, "proton-stealth: "), handshakes, c.sources())
	defer d.Close()
	if err := d.IpcSet(c.ipc()); err != nil {
		close(configured)
		return fmt.Errorf("configuring WireGuard: %w", err)
	}
	err := d.Up()
	close(configured)
	if err != nil {
		return fmt.Errorf("starting WireGuard: %w", err)
	}
	timer := time.NewTimer(timeout)
	defer timer.Stop()
	for {
		select {
		case <-ctx.Done():
			return nil
		case err := <-failure:
			return err
		case <-d.Wait():
			return errors.New("TUN device closed")
		case <-ready:
			timer.Stop()
			log.Print("WireGuard handshake succeeded over Stealth")
			if onReady != nil {
				onReady()
				onReady = nil
			}
		case <-timer.C:
			return errors.New("timed out waiting for the first WireGuard handshake")
		}
	}
}

func run() error {
	path := flag.String("config", "", "single-peer Proton WireGuard config file")
	iface := flag.String("interface", "pst0", "TUN interface to create")
	endpoint := flag.String("endpoint", "", "Stealth endpoint IP:TCP-port; required, overrides config Endpoint")
	check := flag.Bool("check", false, "validate config without opening TUN or connecting")
	verbose := flag.Bool("verbose", false, "enable WireGuard and TLS diagnostics")
	timeout := flag.Duration("handshake-timeout", 45*time.Second, "deadline for the first authenticated WireGuard handshake")
	socks := flag.String("socks", "", "host loopback IP:port; serve SOCKS5 CONNECT in a private VPN namespace")
	listenerFD := flag.Int("socks-fd", -1, "internal: inherited SOCKS listener")
	transportFD := flag.Int("transport-fd", -1, "internal: inherited Proton TCP connection")
	parentNS := flag.String("parent-netns", "", "internal: network namespace before reexec")
	flag.Parse()
	if *path == "" || flag.NArg() != 0 || *timeout <= 0 || *iface == "" || len(*iface) > 15 || strings.ContainsAny(*iface, "/: \t\n%") {
		return errors.New("specify -config and a valid -interface (1-15 characters), with a positive handshake timeout")
	}
	f, err := os.Open(*path)
	if err != nil {
		return err
	}
	c, err := readConfig(f, *endpoint)
	f.Close()
	if err != nil {
		return err
	}
	log.Printf("interface=%s endpoint=%s address=%s DNS=%s MTU=%d", *iface, c.endpoint, strings.Join(c.addresses, ","), strings.Join(c.dns, ","), c.mtu)
	if *check {
		return nil
	}
	if *socks != "" {
		if *listenerFD < 0 && *transportFD < 0 && *parentNS == "" {
			return reexecSOCKS(*socks, c.endpoint)
		}
		return runSOCKSNamespace(*listenerFD, *transportFD, *parentNS, *iface, c, *verbose, *timeout)
	}
	if *listenerFD >= 0 || *transportFD >= 0 || *parentNS != "" {
		return errors.New("inherited descriptors require -socks")
	}
	ctx, stop := signal.NotifyContext(context.Background(), os.Interrupt, syscall.SIGTERM)
	defer stop()
	t, err := tun.CreateTUN(*iface, c.mtu)
	if err != nil {
		return fmt.Errorf("opening TUN: %w", err)
	}
	log.Print("TUN created; configure its addresses, routes and DNS externally")
	return serve(ctx, t, c, *verbose, *timeout)
}

func main() {
	log.SetFlags(log.LstdFlags)
	if err := run(); err != nil {
		log.Print(err)
		os.Exit(1)
	}
}
