#!/bin/sh
# Keep the scheduler's log history and publish the same poll to Prometheus.
exec timeout -s KILL 120s smart_metrics
