#!/bin/bash
set -e

echo "Waiting for database..."
while ! pg_isready -h db -p 5432 -U ${POSTGRES_USER:-app} > /dev/null 2>&1; do
    sleep 2
done
echo "Database ready!"

echo "Running migrations..."
alembic upgrade head || echo "Migration warning"

mkdir -p /app/uploads
exec "$@"
