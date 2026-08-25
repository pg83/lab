package main

import (
	"os"
	"os/exec"
	"syscall"
	"testing"
	"time"
)

func TestParseOptions(t *testing.T) {
	opts, err := parseOptions([]string{
		"--ttl=17",
		"--stop-timeout=3s",
		"/lock/test",
		"--",
		"command",
		"arg",
	})
	if err != nil {
		t.Fatal(err)
	}
	if opts.ttl != 17 || opts.stopTimeout != 3*time.Second {
		t.Fatalf("unexpected options: %+v", opts)
	}
	if opts.lockName != "/lock/test" {
		t.Fatalf("unexpected lock name: %q", opts.lockName)
	}
	if len(opts.command) != 2 || opts.command[0] != "command" || opts.command[1] != "arg" {
		t.Fatalf("unexpected command: %q", opts.command)
	}
}

func TestClientConfigFromEnvironment(t *testing.T) {
	t.Setenv("ETCDCTL_ENDPOINTS", "127.0.0.1:1, 127.0.0.1:2")
	t.Setenv("ETCDCTL_DIAL_TIMEOUT", "4s")
	t.Setenv("ETCDCTL_KEEPALIVE_TIME", "5s")
	t.Setenv("ETCDCTL_KEEPALIVE_TIMEOUT", "6s")
	t.Setenv("ETCDCTL_USER", "user:pass")
	t.Setenv("ETCDCTL_PASSWORD", "")

	cfg, err := clientConfig(t.Context())
	if err != nil {
		t.Fatal(err)
	}
	if len(cfg.Endpoints) != 2 || cfg.Endpoints[1] != "127.0.0.1:2" {
		t.Fatalf("unexpected endpoints: %q", cfg.Endpoints)
	}
	if cfg.DialTimeout != 4*time.Second || cfg.DialKeepAliveTime != 5*time.Second || cfg.DialKeepAliveTimeout != 6*time.Second {
		t.Fatalf("unexpected durations: %+v", cfg)
	}
	if cfg.Username != "user" || cfg.Password != "pass" {
		t.Fatalf("unexpected credentials: %q/%q", cfg.Username, cfg.Password)
	}
}

func TestWaitCode(t *testing.T) {
	cmd := exec.Command("sh", "-c", "exit 7")
	if code := waitCode(cmd.Run()); code != 7 {
		t.Fatalf("got exit code %d, want 7", code)
	}
}

func TestSignalCommandGroup(t *testing.T) {
	cmd, done, err := startCommand([]string{"sh", "-c", "exec sleep 300"}, os.Environ())
	if err != nil {
		t.Fatal(err)
	}
	if err := signalGroup(cmd, syscall.SIGKILL); err != nil {
		t.Fatal(err)
	}

	select {
	case err := <-done:
		if code := waitCode(err); code != 128+int(syscall.SIGKILL) {
			t.Fatalf("got exit code %d, want %d", code, 128+int(syscall.SIGKILL))
		}
	case <-time.After(5 * time.Second):
		t.Fatal("command group did not stop")
	}
}
