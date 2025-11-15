#!/bin/bash
# Backend Entrypoint Script
# This script handles database migrations before starting the application

set -e

echo "========================================="
echo "  Backend Service Initialization"
echo "========================================="

# Wait for database to be ready
echo " Waiting for PostgreSQL to be ready..."
while ! pg_isready -h db -p 5432 -U ${POSTGRES_USER:-app} > /dev/null 2>&1; do
    echo "   Database is not ready yet, waiting..."
    sleep 2
done
echo " Database is ready!"

# Check if this is the first time setup
echo ""
echo " Checking database initialization status..."

# Run Alembic migrations
echo ""
echo " Running database migrations..."
if alembic upgrade head; then
    echo " Database migrations completed successfully!"
else
    echo " Database migration failed!"
    echo "   Trying to initialize database from scratch..."
    
    # If migration fails, try to create initial revision
    if [ ! -d "alembic/versions" ] || [ -z "$(ls -A alembic/versions)" ]; then
        echo "   No migrations found, creating initial migration..."
        alembic revision --autogenerate -m "Initial migration"
    fi
    
    # Try upgrade again
    if alembic upgrade head; then
        echo " Database initialized successfully!"
    else
        echo "  Migration failed, but will continue startup..."
        echo "   Please check database connection and schema manually"
    fi
fi

# Create uploads directory if it doesn't exist
echo ""
echo " Checking uploads directory..."
mkdir -p /app/uploads
chmod 777 /app/uploads
echo " Uploads directory ready"

# Log startup information
echo ""
echo "========================================="
echo "  Starting Application Server"
echo "========================================="
echo "Environment: ${DEBUG:-false}"
echo "Log Level: ${LOG_LEVEL:-INFO}"
echo "Database: ${DATABASE_URL}"
echo "========================================="
echo ""

# Start the application
exec "$@"
