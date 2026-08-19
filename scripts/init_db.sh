#!/usr/bin/env bash
# ==============================================================================
# Horus 2.0 - Database Initialization & Verification Script
# ==============================================================================
set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
PROJECT_ROOT="$(cd "${SCRIPT_DIR}/.." && pwd)"
INIT_SQL="${PROJECT_ROOT}/docker/init-db/init.sql"

echo "================================================================="
echo "🗄️  Horus 2.0 PostgreSQL Database Initialization"
echo "================================================================="

# 1. Check if Docker container is running
if docker ps --format '{{.Names}}' | grep -q "horus-postgres"; then
    echo "✅ Found running 'horus-postgres' container."
    
    echo "⏳ Waiting for PostgreSQL service to be ready..."
    until docker exec -i horus-postgres pg_isready -U horus -d horus > /dev/null 2>&1; do
        sleep 1
    done
    echo "✅ PostgreSQL is ready for connections."

    echo "🚀 Applying schema & seed data from init.sql..."
    docker exec -i horus-postgres psql -U horus -d horus < "${INIT_SQL}" > /dev/null
    
    echo "🔍 Verifying created tables and seed data..."
    docker exec -i horus-postgres psql -U horus -d horus -c "
        SELECT 
            table_name, 
            (xpath('/row/cnt/text()', xml_count))[1]::text::int as row_count
        FROM (
            SELECT table_name, 
                   query_to_xml(format('SELECT COUNT(*) as cnt FROM %I', table_name), false, true, '') as xml_count
            FROM information_schema.tables 
            WHERE table_schema = 'public' 
              AND table_name IN ('crawl_sources', 'articles', 'term_frequencies', 'stock_daily', 'stock_closing_targets', 'reco_feedbacks', 'article_images')
        ) t ORDER BY table_name;
    "

    echo ""
    echo "✨ Database initialized successfully!"
else
    echo "⚠️  'horus-postgres' container is not running."
    echo "💡 Starting containers with docker compose..."
    cd "${PROJECT_ROOT}/docker"
    if [ ! -f .env ] && [ -f .env.example ]; then
        cp .env.example .env
        echo "📄 Copied docker/.env.example to docker/.env"
    fi
    docker compose up -d postgres redis neo4j
    
    echo "⏳ Waiting 5 seconds for container startup..."
    sleep 5
    
    exec "${BASH_SOURCE[0]}"
fi
