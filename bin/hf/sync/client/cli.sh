#!/usr/bin/env sh

D=$(dirname ${0})

export PYTHONPATH=${D}:${PYTHONPATH}
export REQUESTS_CA_BUNDLE=/etc/ssl/cert.pem

exec python3 ${D}/huggingface_hub/commands/huggingface_cli.py "${@}"
