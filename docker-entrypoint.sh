#!/bin/sh
set -e

# Create tables and seed initial data on first run (idempotent).
python init_db.py

exec "$@"