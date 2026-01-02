#!/bin/bash
# =============================================================================
# DOPPELGANGER TRACKER - Docker Entrypoint
# =============================================================================
# Smart entrypoint script for container initialization and health checks
# =============================================================================

set -e

# Colors for output
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
NC='\033[0m' # No Color

# Logging functions
log_info() {
    echo -e "${GREEN}[INFO]${NC} $1"
}

log_warn() {
    echo -e "${YELLOW}[WARN]${NC} $1"
}

log_error() {
    echo -e "${RED}[ERROR]${NC} $1"
}

# =============================================================================
# Wait for PostgreSQL to be ready
# =============================================================================
wait_for_postgres() {
    log_info "Waiting for PostgreSQL at ${POSTGRES_HOST:-postgres}:${POSTGRES_PORT:-5432}..."

    local max_attempts=30
    local attempt=1

    while [ $attempt -le $max_attempts ]; do
        if pg_isready -h "${POSTGRES_HOST:-postgres}" -p "${POSTGRES_PORT:-5432}" -U "${POSTGRES_USER:-doppelganger}" >/dev/null 2>&1; then
            log_info "PostgreSQL is ready!"
            return 0
        fi

        log_warn "PostgreSQL not ready yet (attempt $attempt/$max_attempts)..."
        sleep 2
        attempt=$((attempt + 1))
    done

    log_error "PostgreSQL failed to become ready after $max_attempts attempts"
    return 1
}

# =============================================================================
# Wait for Redis to be ready
# =============================================================================
wait_for_redis() {
    if [ -n "$REDIS_URL" ]; then
        log_info "Waiting for Redis..."

        local max_attempts=30
        local attempt=1

        # Extract host and port from REDIS_URL (redis://host:port/db)
        local redis_host=$(echo $REDIS_URL | sed -E 's|redis://([^:]+):.*|\1|')
        local redis_port=$(echo $REDIS_URL | sed -E 's|redis://[^:]+:([0-9]+).*|\1|')

        while [ $attempt -le $max_attempts ]; do
            if redis-cli -h "$redis_host" -p "$redis_port" ping >/dev/null 2>&1; then
                log_info "Redis is ready!"
                return 0
            fi

            log_warn "Redis not ready yet (attempt $attempt/$max_attempts)..."
            sleep 2
            attempt=$((attempt + 1))
        done

        log_warn "Redis failed to become ready, continuing anyway..."
    fi
}

# =============================================================================
# Initialize database if needed
# =============================================================================
init_database() {
    log_info "Checking if database needs initialization..."

    # Try to import and check if tables exist
    python -c "
from database import get_session, Source
try:
    session = get_session()
    session.query(Source).first()
    session.close()
    print('TABLES_EXIST')
except Exception:
    print('NEEDS_INIT')
" > /tmp/db_check.txt 2>&1

    local db_status=$(cat /tmp/db_check.txt | grep -o 'TABLES_EXIST\|NEEDS_INIT' || echo 'NEEDS_INIT')

    if [ "$db_status" = "NEEDS_INIT" ]; then
        log_info "Initializing database tables..."
        python main.py init-db
        log_info "Database initialized successfully!"
    else
        log_info "Database already initialized, skipping..."
    fi
}

# =============================================================================
# Main entrypoint logic
# =============================================================================

log_info "=========================================="
log_info "Doppelganger Tracker - Starting Container"
log_info "=========================================="

# Check if first argument is a known command
case "$1" in
    "init-db")
        log_info "Running database initialization..."
        wait_for_postgres
        exec python main.py init-db
        ;;

    "collect")
        log_info "Starting collection service..."
        wait_for_postgres
        wait_for_redis
        init_database
        exec python main.py collect "${@:2}"
        ;;

    "analyze")
        log_info "Starting analysis service..."
        wait_for_postgres
        init_database
        exec python main.py analyze "${@:2}"
        ;;

    "dashboard")
        log_info "Starting dashboard service..."
        wait_for_postgres
        init_database
        exec streamlit run dashboard/app.py --server.port="${STREAMLIT_SERVER_PORT:-8501}" --server.address="${STREAMLIT_SERVER_ADDRESS:-0.0.0.0}"
        ;;

    "test")
        log_info "Running test suite..."
        exec python main.py test "${@:2}"
        ;;

    "bash"|"sh")
        log_info "Starting interactive shell..."
        exec /bin/bash
        ;;

    *)
        # If it's a python command or other command, just execute it
        if [ "$1" = "python" ] || [ "$1" = "streamlit" ]; then
            log_info "Executing command: $*"
            exec "$@"
        else
            log_info "Executing custom command: $*"
            exec "$@"
        fi
        ;;
esac
