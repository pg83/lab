package main

import (
	"context"
	"errors"
	"flag"
	"fmt"
	"os"
	"os/exec"
	"os/signal"
	"strconv"
	"strings"
	"syscall"
	"time"

	clientv3 "go.etcd.io/etcd/client/v3"
	"go.etcd.io/etcd/client/v3/concurrency"
)

const (
	defaultTTL           = 10
	defaultDialTimeout   = 2 * time.Second
	defaultKeepAliveTime = 2 * time.Second
	defaultKeepAliveTO   = 6 * time.Second
	defaultStopTimeout   = 10 * time.Second
	unlockTimeout        = 5 * time.Second
)

type options struct {
	lockName    string
	command     []string
	ttl         int
	stopTimeout time.Duration
}

type acquiredLock struct {
	session *concurrency.Session
	mutex   *concurrency.Mutex
}

type acquireResult struct {
	lock *acquiredLock
	err  error
}

func usage(fs *flag.FlagSet) {
	fmt.Fprintf(fs.Output(), "usage: etcd_lock [options] <lock-name> -- <command> [args...]\n")
	fs.PrintDefaults()
}

func parseOptions(args []string) (options, error) {
	var out options
	fs := flag.NewFlagSet("etcd_lock", flag.ContinueOnError)
	fs.SetOutput(os.Stderr)
	fs.IntVar(&out.ttl, "ttl", defaultTTL, "etcd lease TTL in seconds")
	fs.DurationVar(&out.stopTimeout, "stop-timeout", defaultStopTimeout, "grace period when forwarding an external signal")
	fs.Usage = func() { usage(fs) }

	if err := fs.Parse(args); err != nil {
		return out, err
	}

	rest := fs.Args()
	if len(rest) < 3 || rest[1] != "--" {
		fs.Usage()
		return out, errors.New("lock name, --, and command are required")
	}
	if out.ttl <= 0 {
		return out, errors.New("ttl must be positive")
	}
	if out.stopTimeout < 0 {
		return out, errors.New("stop-timeout must not be negative")
	}

	out.lockName = rest[0]
	out.command = append([]string(nil), rest[2:]...)
	return out, nil
}

func envDuration(name string, fallback time.Duration) (time.Duration, error) {
	raw := os.Getenv(name)
	if raw == "" {
		return fallback, nil
	}

	d, err := time.ParseDuration(raw)
	if err != nil {
		return 0, fmt.Errorf("%s: %w", name, err)
	}
	return d, nil
}

func clientConfig(ctx context.Context) (clientv3.Config, error) {
	rawEndpoints := os.Getenv("ETCDCTL_ENDPOINTS")
	if rawEndpoints == "" {
		rawEndpoints = "127.0.0.1:2379"
	}

	endpoints := make([]string, 0, 3)
	for _, endpoint := range strings.Split(rawEndpoints, ",") {
		if endpoint = strings.TrimSpace(endpoint); endpoint != "" {
			endpoints = append(endpoints, endpoint)
		}
	}
	if len(endpoints) == 0 {
		return clientv3.Config{}, errors.New("ETCDCTL_ENDPOINTS contains no endpoints")
	}

	dialTimeout, err := envDuration("ETCDCTL_DIAL_TIMEOUT", defaultDialTimeout)
	if err != nil {
		return clientv3.Config{}, err
	}
	keepAliveTime, err := envDuration("ETCDCTL_KEEPALIVE_TIME", defaultKeepAliveTime)
	if err != nil {
		return clientv3.Config{}, err
	}
	keepAliveTimeout, err := envDuration("ETCDCTL_KEEPALIVE_TIMEOUT", defaultKeepAliveTO)
	if err != nil {
		return clientv3.Config{}, err
	}

	username := os.Getenv("ETCDCTL_USER")
	password := os.Getenv("ETCDCTL_PASSWORD")
	if password == "" {
		if user, pass, ok := strings.Cut(username, ":"); ok {
			username, password = user, pass
		}
	}

	return clientv3.Config{
		Context:              ctx,
		Endpoints:            endpoints,
		DialTimeout:          dialTimeout,
		DialKeepAliveTime:    keepAliveTime,
		DialKeepAliveTimeout: keepAliveTimeout,
		Username:             username,
		Password:             password,
	}, nil
}

func acquire(ctx context.Context, client *clientv3.Client, name string, ttl int) (*acquiredLock, error) {
	session, err := concurrency.NewSession(
		client,
		concurrency.WithTTL(ttl),
		concurrency.WithContext(ctx),
	)
	if err != nil {
		return nil, err
	}

	mutex := concurrency.NewMutex(session, name)
	if err := mutex.Lock(ctx); err != nil {
		session.Orphan()
		return nil, err
	}

	return &acquiredLock{session: session, mutex: mutex}, nil
}

func commandEnv(lock *acquiredLock) []string {
	env := make([]string, 0, len(os.Environ())+2)
	for _, item := range os.Environ() {
		if strings.HasPrefix(item, "ETCD_LOCK_KEY=") || strings.HasPrefix(item, "ETCD_LOCK_REV=") {
			continue
		}
		env = append(env, item)
	}

	return append(
		env,
		"ETCD_LOCK_KEY="+lock.mutex.Key(),
		"ETCD_LOCK_REV="+strconv.FormatInt(lock.mutex.Header().Revision, 10),
	)
}

func startCommand(argv []string, env []string) (*exec.Cmd, <-chan error, error) {
	cmd := exec.Command(argv[0], argv[1:]...)
	cmd.Env = env
	cmd.Stdin = os.Stdin
	cmd.Stdout = os.Stdout
	cmd.Stderr = os.Stderr
	cmd.SysProcAttr = &syscall.SysProcAttr{
		Setpgid:   true,
		Pdeathsig: syscall.SIGKILL,
	}

	if err := cmd.Start(); err != nil {
		return nil, nil, err
	}

	done := make(chan error, 1)
	go func() { done <- cmd.Wait() }()
	return cmd, done, nil
}

func signalGroup(cmd *exec.Cmd, sig syscall.Signal) error {
	err := syscall.Kill(-cmd.Process.Pid, sig)
	if errors.Is(err, syscall.ESRCH) {
		return nil
	}
	return err
}

func waitCode(err error) int {
	if err == nil {
		return 0
	}

	var exitErr *exec.ExitError
	if !errors.As(err, &exitErr) {
		return 1
	}

	status, ok := exitErr.Sys().(syscall.WaitStatus)
	if !ok {
		return 1
	}
	if status.Signaled() {
		return 128 + int(status.Signal())
	}
	return status.ExitStatus()
}

func signalNumber(sig os.Signal) syscall.Signal {
	if value, ok := sig.(syscall.Signal); ok {
		return value
	}
	return syscall.SIGTERM
}

func release(lock *acquiredLock) {
	ctx, cancel := context.WithTimeout(context.Background(), unlockTimeout)
	err := lock.mutex.Unlock(ctx)
	cancel()
	if err != nil && !errors.Is(err, concurrency.ErrSessionExpired) {
		fmt.Fprintf(os.Stderr, "etcd_lock: unlock: %v\n", err)
	}
	lock.session.Orphan()
}

func stopForSignal(cmd *exec.Cmd, done <-chan error, lockDone <-chan struct{}, sig syscall.Signal, timeout time.Duration) error {
	if err := signalGroup(cmd, sig); err != nil {
		fmt.Fprintf(os.Stderr, "etcd_lock: signal command: %v\n", err)
	}

	timer := time.NewTimer(timeout)
	defer timer.Stop()

	select {
	case err := <-done:
		return err
	case <-lockDone:
		fmt.Fprintln(os.Stderr, "etcd_lock: lease lost during command shutdown; killing command")
	case <-timer.C:
		fmt.Fprintln(os.Stderr, "etcd_lock: command ignored signal; killing command")
	}

	if err := signalGroup(cmd, syscall.SIGKILL); err != nil {
		fmt.Fprintf(os.Stderr, "etcd_lock: kill command: %v\n", err)
	}
	return <-done
}

func run(args []string) int {
	opts, err := parseOptions(args)
	if err != nil {
		fmt.Fprintf(os.Stderr, "etcd_lock: %v\n", err)
		return 2
	}

	signals := make(chan os.Signal, 2)
	signal.Notify(signals, syscall.SIGINT, syscall.SIGTERM, syscall.SIGHUP, syscall.SIGQUIT)
	defer signal.Stop(signals)

	ctx, cancel := context.WithCancel(context.Background())
	defer cancel()

	cfg, err := clientConfig(ctx)
	if err != nil {
		fmt.Fprintf(os.Stderr, "etcd_lock: config: %v\n", err)
		return 2
	}
	client, err := clientv3.New(cfg)
	if err != nil {
		fmt.Fprintf(os.Stderr, "etcd_lock: client: %v\n", err)
		return 1
	}
	defer client.Close()

	acquired := make(chan acquireResult, 1)
	go func() {
		lock, acquireErr := acquire(ctx, client, opts.lockName, opts.ttl)
		acquired <- acquireResult{lock: lock, err: acquireErr}
	}()

	var lock *acquiredLock
	select {
	case result := <-acquired:
		if result.err != nil {
			fmt.Fprintf(os.Stderr, "etcd_lock: acquire %s: %v\n", opts.lockName, result.err)
			return 1
		}
		lock = result.lock
	case sig := <-signals:
		cancel()
		fmt.Fprintf(os.Stderr, "etcd_lock: interrupted while acquiring %s\n", opts.lockName)
		return 128 + int(signalNumber(sig))
	}

	// Lock() can return just before the keepalive stream reports that the
	// session died. Never start a command for a lock already known to be lost.
	select {
	case <-lock.session.Done():
		fmt.Fprintf(os.Stderr, "etcd_lock: lease lost before command start for %s\n", opts.lockName)
		return 1
	default:
	}

	cmd, commandDone, err := startCommand(opts.command, commandEnv(lock))
	if err != nil {
		fmt.Fprintf(os.Stderr, "etcd_lock: start %s: %v\n", opts.command[0], err)
		release(lock)
		return 1
	}

	select {
	case commandErr := <-commandDone:
		release(lock)
		return waitCode(commandErr)

	case <-lock.session.Done():
		fmt.Fprintf(os.Stderr, "etcd_lock: lease lost for %s; killing command\n", opts.lockName)
		if err := signalGroup(cmd, syscall.SIGKILL); err != nil {
			fmt.Fprintf(os.Stderr, "etcd_lock: kill command: %v\n", err)
		}
		<-commandDone
		return 1

	case sig := <-signals:
		sigNumber := signalNumber(sig)
		stopForSignal(cmd, commandDone, lock.session.Done(), sigNumber, opts.stopTimeout)
		release(lock)
		return 128 + int(sigNumber)
	}
}

func main() {
	os.Exit(run(os.Args[1:]))
}
