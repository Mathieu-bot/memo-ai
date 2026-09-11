#!/bin/sh
set -e

# Ensure the local fallback storage directory exists (used when B2 is
# not configured, e.g. local/demo deployments). The database directory
# is created by SQLite/init_db on demand.
mkdir -p /data/uploads

# Create tables on first run (idempotent).
python init_db.py

exec "$@"