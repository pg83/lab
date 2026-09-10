// SPDX-License-Identifier: MIT
package main

import (
	"context"
	"crypto/rand"
	"encoding/binary"
	"net/netip"
	"os"
	"testing"
	"time"

	"golang.zx2c4.com/wireguard/tun/tuntest"
)

// Opt-in network test: keys stay in an external file, and all IP traffic uses
// an in-memory TUN. This does not alter host routes or require CAP_NET_ADMIN.
func TestLiveProton(t *testing.T) {
	path := os.Getenv("PROTON_LIVE_CONFIG")
	if path == "" {
		t.Skip("explicit live configuration required")
	}
	f, err := os.Open(path)
	if err != nil {
		t.Fatal(err)
	}
	defer f.Close()
	c, err := readConfig(f, os.Getenv("PROTON_LIVE_ENDPOINT"))
	if err != nil {
		t.Fatal(err)
	}
	ctx, cancel := context.WithCancel(context.Background())
	tunnel := tuntest.NewChannelTUN()
	done := make(chan struct{})
	var serveErr error
	go func() { defer close(done); serveErr = serve(ctx, tunnel.TUN(), c, false, 15*time.Second) }()
	defer func() {
		cancel()
		select {
		case <-done:
		case <-time.After(7 * time.Second):
			t.Error("shutdown timeout")
		}
	}()
	sourceIP := netip.MustParsePrefix(c.addresses[0]).Addr()
	if !sourceIP.Is4() {
		t.Fatal("live DNS probe requires an IPv4 Interface Address")
	}
	source := sourceIP.As4()
	for _, destination := range []string{"10.2.0.1", "1.1.1.1"} {
		target := netip.MustParseAddr(destination).As4()
		dns := []byte{0, 0, 1, 0, 0, 1, 0, 0, 0, 0, 0, 0, 7, 'e', 'x', 'a', 'm', 'p', 'l', 'e', 3, 'c', 'o', 'm', 0, 0, 1, 0, 1}
		if _, err := rand.Read(dns[:2]); err != nil {
			t.Fatal(err)
		}
		packet := make([]byte, 28+len(dns))
		packet[0] = 0x45
		packet[8] = 64
		packet[9] = 17
		binary.BigEndian.PutUint16(packet[2:4], uint16(len(packet)))
		copy(packet[12:16], source[:])
		copy(packet[16:20], target[:])
		var sum uint32
		for i := 0; i < 20; i += 2 {
			sum += uint32(binary.BigEndian.Uint16(packet[i : i+2]))
		}
		for sum > 65535 {
			sum = (sum & 65535) + (sum >> 16)
		}
		binary.BigEndian.PutUint16(packet[10:12], ^uint16(sum))
		binary.BigEndian.PutUint16(packet[20:22], 45678)
		binary.BigEndian.PutUint16(packet[22:24], 53)
		binary.BigEndian.PutUint16(packet[24:26], uint16(8+len(dns)))
		copy(packet[28:], dns)
		timeout := time.NewTimer(18 * time.Second)
		retry := time.NewTicker(2 * time.Second)
		defer timeout.Stop()
		defer retry.Stop()
		send := tunnel.Outbound
		received := false
		for !received {
			select {
			case send <- packet:
				send = nil
			case <-retry.C:
				send = tunnel.Outbound
			case <-done:
				t.Fatalf("transport stopped: %v", serveErr)
			case <-timeout.C:
				t.Fatalf("no tunneled DNS answer from %s", destination)
			case p := <-tunnel.Inbound:
				if len(p) < 40 || p[0]>>4 != 4 || p[9] != 17 {
					continue
				}
				if [4]byte(p[12:16]) != target || [4]byte(p[16:20]) != source {
					continue
				}
				off := int(p[0]&15) * 4
				if off < 20 {
					continue
				}
				if len(p) < off+20 || binary.BigEndian.Uint16(p[off:]) != 53 || binary.BigEndian.Uint16(p[off+2:]) != 45678 {
					continue
				}
				d := p[off+8:]
				if d[0] != dns[0] || d[1] != dns[1] {
					continue
				}
				if d[2]&128 == 0 || d[3]&15 != 0 || binary.BigEndian.Uint16(d[6:8]) == 0 {
					t.Fatalf("invalid DNS response from %s", destination)
				}
				t.Logf("authenticated tunnel: DNS answer from %s, answers=%d", destination, binary.BigEndian.Uint16(d[6:8]))
				received = true
			}
		}
		timeout.Stop()
		retry.Stop()
	}
}
