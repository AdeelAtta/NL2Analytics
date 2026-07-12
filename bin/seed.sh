#!/usr/bin/env bash
set -uo pipefail

# ============================================================
# bin/seed.sh  –  Load a test-database SQL dump into PostgreSQL
#
# Usage:
#   ./bin/seed.sh                          # list available databases
#   ./bin/seed.sh <database_name>          # seed one database
#   ./bin/seed.sh --all                    # seed all test databases
#   ./bin/seed.sh --docker                 # use docker-compose postgres
#
# Examples:
#   ./bin/seed.sh lego
#   ./bin/seed.sh chinook
#   ./bin/seed.sh --all
# ============================================================

ROOT="$(cd "$(dirname "$0")/.." && pwd)"
SQL_DIR="$ROOT/test-databases"

# ---- Detect how to reach psql ---------------------------------
USE_DOCKER=false
SERVICE_NAME="postgres"          # docker-compose service name

# Connection defaults — override via env or .env.dev
PGUSER="${POSTGRES_USER:-postgres}"
PGPASSWORD="${POSTGRES_PASSWORD:-postgres}"
PGHOST="${POSTGRES_HOST:-127.0.0.1}"
PGPORT="${POSTGRES_PORT:-5432}"
PGDB="${POSTGRES_DB:-postgres}"

# ---- Parse arguments ------------------------------------------
TARGET="${1:-}"
if [ "$TARGET" = "--docker" ]; then
    USE_DOCKER=true
    TARGET="${2:-}"
elif [ "$TARGET" = "--all" ]; then
    TARGET="ALL"
fi

# ---- Helper: run psql -----------------------------------------
run_psql() {
    local db="${1:-$PGDB}"
    local sql="$2"
    if [ "$USE_DOCKER" = true ]; then
        local cid
        cid="$(docker compose ps -q "$SERVICE_NAME" 2>/dev/null || true)"
        if [ -z "$cid" ]; then
            echo "ERROR: Docker service '$SERVICE_NAME' is not running."
            echo "       Start it with:  docker compose -f docker-compose.dev.yml up -d postgres"
            exit 1
        fi
        echo "$sql" | docker exec -i "$cid" psql -U "$PGUSER" -d "$db" 2>&1
    else
        PGPASSWORD="$PGPASSWORD" psql -h "$PGHOST" -p "$PGPORT" -U "$PGUSER" -d "$db" -c "$sql" 2>&1
    fi
}

run_sql_file() {
    local db="${1:-$PGDB}"
    local file="$2"
    if [ "$USE_DOCKER" = true ]; then
        local cid
        cid="$(docker compose ps -q "$SERVICE_NAME" 2>/dev/null || true)"
        if [ -z "$cid" ]; then
            echo "ERROR: Docker service '$SERVICE_NAME' is not running."
            exit 1
        fi
        docker exec -i "$cid" psql -U "$PGUSER" -d "$db" < "$file" 2>&1
    else
        PGPASSWORD="$PGPASSWORD" psql -h "$PGHOST" -p "$PGPORT" -U "$PGUSER" -d "$db" -f "$file" 2>&1
    fi
}

# ---- Seed logic ------------------------------------------------
seed_db() {
    local db_name="$1"
    local sql_file="$SQL_DIR/${db_name}.sql"

    if [ ! -f "$sql_file" ]; then
        echo "  ✗  SQL file not found: $sql_file"
        return 1
    fi

    echo ""
    echo "  → Creating database '$db_name' ..."

    # Create the database (ignore "already exists" error)
    run_psql "$PGDB" "CREATE DATABASE $db_name;" 2>/dev/null || true

    echo "  → Loading $db_name.sql ..."
    run_sql_file "$db_name" "$sql_file"

    echo "  ✓  '$db_name' seeded successfully"
}

# ---- Main -----------------------------------------------------
echo ""
echo "╔═══════════════════════════════════════════╗"
echo "║        SchemaIntern Database Seeder       ║"
echo "╚═══════════════════════════════════════════╝"

if [ "$TARGET" = "ALL" ]; then
    echo ""
    echo "Seeding ALL test databases..."
    for f in "$SQL_DIR"/*.sql; do
        db_name="$(basename "$f" .sql)"
        seed_db "$db_name"
    done
    echo ""
    echo " All databases seeded!"
    echo ""

elif [ -n "$TARGET" ]; then
    seed_db "$TARGET"

else
    echo ""
    echo " Available databases:"
    echo ""
    for f in "$SQL_DIR"/*.sql; do
        db_name="$(basename "$f" .sql)"
        echo "   ./bin/seed.sh $db_name"
    done
    echo ""
    echo "   ./bin/seed.sh --all     # seed everything"
    echo "   ./bin/seed.sh --docker  # target docker-compose postgres"
    echo ""
fi
