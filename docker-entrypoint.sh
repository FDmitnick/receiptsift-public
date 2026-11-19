#!/bin/sh
set -eu

mkdir -p /app/data
chown -R receiptsift:receiptsift /app/data

exec gosu receiptsift "$@"
