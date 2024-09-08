#!/usr/bin/env sh

set -xue

cd /dev

rm -rf links.tmp
mkdir links.tmp
devlinkinto links.tmp
rm -rf links
mv links.tmp links
