// SPDX-License-Identifier: MIT
package main

import (
	"bytes"
	"context"
	"crypto/ecdh"
	"crypto/rand"
	"crypto/tls"
	"encoding/base64"
	"encoding/binary"
	"encoding/hex"
	"errors"
	"fmt"
	"io"
	"net"
	"net/http/httptest"
	"net/netip"
	"strings"
	"testing"
	"time"

	"golang.zx2c4.com/wireguard/conn"
	"golang.zx2c4.com/wireguard/device"
	"golang.zx2c4.com/wireguard/tun/tuntest"
)

const sample = `[Interface]
PrivateKey = AQEBAQEBAQEBAQEBAQEBAQEBAQEBAQEBAQEBAQEBAQE=
Address = 10.2.0.2/32, fd00::2/128
DNS = 10.2.0.1
[Peer]
PublicKey = AgICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgI=
AllowedIPs = 0.0.0.0/0, ::/0
Endpoint = 192.0.2.1:51820
`

func requireLoopback(t *testing.T) {
	t.Helper()
	lo, err := net.InterfaceByName("lo")
	if err == nil && lo.Flags&net.FlagUp == 0 {
		t.Skip("loopback is down in this build sandbox; run transport tests with loopback up")
	}
}

func TestConfig(t *testing.T) {
	c, err := readConfig(strings.NewReader(sample), "192.0.2.1:443")
	if err != nil {
		t.Fatal(err)
	}
	if c.sources() != "10.2.0.2,fd00::2" || c.mtu != 1320 || c.keepalive != 25 {
		t.Fatalf("wrong address extraction or defaults")
	}
	ipc := c.ipc()
	for _, want := range []string{"endpoint=192.0.2.1:443\n", "allowed_ip=0.0.0.0/0\n", "allowed_ip=::/0\n", "private_key=" + strings.Repeat("01", 32) + "\n"} {
		if !strings.Contains(ipc, want) {
			t.Fatal("missing IPC field")
		}
	}
	if strings.Contains(ipc, "51820") {
		t.Fatal("exported UDP endpoint leaked into Stealth config")
	}
}

func TestConfigRejectsUnsafeOrInvalidInput(t *testing.T) {
	for _, tc := range []struct{ name, config, endpoint string }{
		{"missing TLS endpoint", sample, ""},
		{"hostname", sample, "example.com:443"},
		{"zero port", sample, "192.0.2.1:0"},
		{"extra peer", sample + "[Peer]\n", "192.0.2.1:443"},
		{"shell hook", strings.Replace(sample, "[Interface]", "[Interface]\nPostUp = do-not-run", 1), "192.0.2.1:443"},
		{"bad key", strings.Replace(sample, "AQEBAQEBAQEBAQEBAQEBAQEBAQEBAQEBAQEBAQEBAQE=", "SECRET", 1), "192.0.2.1:443"},
		{"missing addresses", strings.Replace(sample, "Address = 10.2.0.2/32, fd00::2/128\n", "", 1), "192.0.2.1:443"},
		{"bad prefix", strings.Replace(sample, "10.2.0.2/32", "10.2.0.2/99", 1), "192.0.2.1:443"},
		{"duplicate key", strings.Replace(sample, "[Interface]", "[Interface]\nPrivateKey = SECRET", 1), "192.0.2.1:443"},
	} {
		t.Run(tc.name, func(t *testing.T) {
			_, err := readConfig(strings.NewReader(tc.config), tc.endpoint)
			if err == nil || strings.Contains(err.Error(), "SECRET") {
				t.Fatal("expected rejection without echoing secret values")
			}
		})
	}
}

// Local TLS/TunSafe-to-UDP relay for an actual WireGuard peer. This is an
// independent framing decoder, not a mock of the client's Stealth bind.
func relayTLS(t *testing.T, udpEndpoint string) (string, <-chan string) {
	t.Helper()
	certServer := httptest.NewTLSServer(nil)
	certConfig := certServer.TLS.Clone()
	certServer.Close()
	hello := make(chan string, 1)
	certConfig.GetConfigForClient = func(h *tls.ClientHelloInfo) (*tls.Config, error) {
		hello <- h.ServerName
		return nil, nil
	}
	ln, err := tls.Listen("tcp", "127.0.0.1:0", certConfig)
	if err != nil {
		t.Fatal(err)
	}
	t.Cleanup(func() { ln.Close() })
	go func() {
		stream, err := ln.Accept()
		if err != nil {
			return
		}
		defer stream.Close()
		stream.SetDeadline(time.Now().Add(10 * time.Second))
		udp, err := net.Dial("udp", udpEndpoint)
		if err != nil {
			t.Error(err)
			return
		}
		defer udp.Close()
		udp.SetDeadline(time.Now().Add(10 * time.Second))
		go func() {
			buf := make([]byte, 65535)
			for {
				n, err := udp.Read(buf[2:])
				if err != nil {
					return
				}
				binary.BigEndian.PutUint16(buf, uint16(n))
				if _, err := stream.Write(buf[:n+2]); err != nil {
					return
				}
			}
		}()
		var prefix [8]byte
		var counter uint64
		for {
			var header [2]byte
			if _, err := io.ReadFull(stream, header[:]); err != nil {
				return
			}
			size := int(binary.BigEndian.Uint16(header[:]) & 0x3fff)
			packet := make([]byte, size)
			if _, err := io.ReadFull(stream, packet); err != nil {
				return
			}
			switch header[0] >> 6 {
			case 0:
				if len(packet) >= 16 && binary.LittleEndian.Uint32(packet) == 4 {
					copy(prefix[:], packet[:8])
					counter = binary.LittleEndian.Uint64(packet[8:16])
				}
			case 2:
				h := make([]byte, 16)
				copy(h, prefix[:])
				binary.LittleEndian.PutUint64(h[8:], counter+1)
				packet = append(h, packet...)
				counter++
			default:
				t.Error("unknown TunSafe frame")
				return
			}
			if _, err := udp.Write(packet); err != nil {
				return
			}
		}
	}()
	return ln.Addr().String(), hello
}

func TestStealthWireGuardRoundTrip(t *testing.T) {
	requireLoopback(t)
	clientKey, err := ecdh.X25519().GenerateKey(rand.Reader)
	if err != nil {
		t.Fatal(err)
	}
	serverKey, err := ecdh.X25519().GenerateKey(rand.Reader)
	if err != nil {
		t.Fatal(err)
	}
	serverTun := tuntest.NewChannelTUN()
	serverStates := make(chan device.HandshakeState)
	server := device.NewDevice(serverTun.TUN(), conn.NewStdNetBind(func(int) int { return 0 }), device.NewLogger(device.LogLevelError, "server: "), serverStates, "10.2.0.1")
	go func() {
		for {
			select {
			case <-serverStates:
			case <-server.Wait():
				return
			}
		}
	}()
	defer server.Close()
	err = server.IpcSet(fmt.Sprintf("private_key=%x\nlisten_port=0\npublic_key=%x\nallowed_ip=10.2.0.2/32\n", serverKey.Bytes(), clientKey.PublicKey().Bytes()))
	if err != nil {
		t.Fatal(err)
	}
	if err := server.Up(); err != nil {
		t.Fatal(err)
	}
	ipc, err := server.IpcGet()
	if err != nil {
		t.Fatal(err)
	}
	var port string
	for _, line := range strings.Split(ipc, "\n") {
		if strings.HasPrefix(line, "listen_port=") {
			port = strings.TrimPrefix(line, "listen_port=")
		}
	}
	endpoint, hello := relayTLS(t, "127.0.0.1:"+port)
	c := config{
		privateKey: hex.EncodeToString(clientKey.Bytes()), publicKey: hex.EncodeToString(serverKey.PublicKey().Bytes()),
		endpoint: netip.MustParseAddrPort(endpoint), addresses: []string{"10.2.0.2/32"}, allowedIPs: []string{"10.2.0.1/32"}, keepalive: 1,
	}
	clientTun := tuntest.NewChannelTUN()
	ctx, cancel := context.WithCancel(context.Background())
	result := make(chan error, 1)
	go func() { result <- serve(ctx, clientTun.TUN(), c, false, 5*time.Second) }()
	defer func() {
		cancel()
		select {
		case err := <-result:
			if err != nil {
				t.Error(err)
			}
		case <-time.After(5 * time.Second):
			t.Error("shutdown blocked")
		}
	}()
	send := func(ch chan []byte, p []byte) {
		t.Helper()
		select {
		case ch <- p:
		case <-time.After(5 * time.Second):
			t.Fatal("TUN send timeout")
		}
	}
	receive := func(ch chan []byte, want []byte) {
		t.Helper()
		select {
		case p := <-ch:
			if !bytes.Equal(p, want) {
				t.Fatal("packet changed in transit")
			}
		case <-time.After(5 * time.Second):
			t.Fatal("TUN receive timeout")
		}
	}
	clientIP, serverIP := netip.MustParseAddr("10.2.0.2"), netip.MustParseAddr("10.2.0.1")
	for range 3 { // Exercises successive counters and compact TunSafe frames.
		p := tuntest.Ping(serverIP, clientIP)
		send(clientTun.Outbound, p)
		receive(serverTun.Inbound, p)
		p = tuntest.Ping(clientIP, serverIP)
		send(serverTun.Outbound, p)
		receive(clientTun.Inbound, p)
	}
	select {
	case sni := <-hello:
		if sni == "" {
			t.Fatal("missing camouflage SNI")
		}
	default:
		t.Fatal("TLS handshake was not observed")
	}
}

func TestStealthHandshakeDeadline(t *testing.T) {
	requireLoopback(t)
	// TLS succeeds, but the local UDP peer never answers the WireGuard handshake.
	blackhole, err := net.ListenPacket("udp", "127.0.0.1:0")
	if err != nil {
		t.Fatal(err)
	}
	defer blackhole.Close()
	endpoint, _ := relayTLS(t, blackhole.LocalAddr().String())
	c, err := readConfig(strings.NewReader(sample), endpoint)
	if err != nil {
		t.Fatal(err)
	}
	result := make(chan error, 1)
	go func() {
		result <- serve(context.Background(), tuntest.NewChannelTUN().TUN(), c, false, 300*time.Millisecond)
	}()
	select {
	case err := <-result:
		if err == nil || !strings.Contains(err.Error(), "first WireGuard handshake") {
			t.Fatalf("expected authentication deadline, got %v", err)
		}
	case <-time.After(5 * time.Second):
		t.Fatal("deadline/shutdown blocked")
	}
}

func TestStealthConnectionFailure(t *testing.T) {
	requireLoopback(t)
	ln, err := net.Listen("tcp", "127.0.0.1:0")
	if err != nil {
		t.Fatal(err)
	}
	endpoint := ln.Addr().String()
	ln.Close()
	c, err := readConfig(strings.NewReader(sample), endpoint)
	if err != nil {
		t.Fatal(err)
	}
	err = serve(context.Background(), tuntest.NewChannelTUN().TUN(), c, false, time.Second)
	var opErr *net.OpError
	if !errors.As(err, &opErr) {
		t.Fatalf("expected transport failure, got %v", err)
	}
}

func TestKeyValidation(t *testing.T) {
	if _, err := keyHex(base64.StdEncoding.EncodeToString(make([]byte, 32))); err == nil {
		t.Fatal("accepted zero key")
	}
}
