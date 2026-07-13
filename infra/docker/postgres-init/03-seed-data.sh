#!/bin/bash
set -e

TEST_DB_DIR="/test-databases"

if [ ! -d "$TEST_DB_DIR" ] || [ -z "$(ls -A "$TEST_DB_DIR"/*.sql 2>/dev/null)" ]; then
    echo "No test databases found at $TEST_DB_DIR — skipping seed."
    exit 0
fi

for sql_file in "$TEST_DB_DIR"/*.sql; do
    dbname=$(basename "$sql_file" .sql)
    echo "Creating database: $dbname"
    psql -v ON_ERROR_STOP=1 --username "$POSTGRES_USER" --dbname "$POSTGRES_DB" \
        -c "CREATE DATABASE $dbname;" 2>/dev/null || echo "  Database '$dbname' already exists — skipping create."

    echo "Seeding $dbname..."
    set +e
    psql --username "$POSTGRES_USER" --dbname "$dbname" -f "$sql_file" > /dev/null 2>&1
    set -e
    echo "  Done."
done

echo "All test databases seeded successfully."
