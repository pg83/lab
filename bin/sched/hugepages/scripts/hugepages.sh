#!/bin/sh
set -xue

sysctl vm.compact_memory=1
sysctl vm.nr_hugepages=2048
sysctl vm.nr_hugepages
