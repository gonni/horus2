#!/usr/bin/env bash
# ==============================================================================
# Horus 2.0 - One-Click Development Environment Setup Script
# ==============================================================================
set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
PROJECT_ROOT="$(cd "${SCRIPT_DIR}/.." && pwd)"

echo "================================================================="
echo "🌟 Horus 2.0 - Development Environment Setup"
echo "================================================================="
echo "📁 Project Root: ${PROJECT_ROOT}"
echo ""

# ------------------------------------------------------------------------------
# 1. Check Pre-requisites
# ------------------------------------------------------------------------------
echo "🔍 Checking prerequisites..."

command -v docker >/dev/null 2>&1 || { echo "❌ Docker is not installed or not in PATH. Please install Docker first."; exit 1; }
command -v docker compose >/dev/null 2>&1 || docker-compose --version >/dev/null 2>&1 || { echo "❌ Docker Compose is not installed."; exit 1; }
command -v python3 >/dev/null 2>&1 || { echo "❌ Python 3 is not installed or not in PATH."; exit 1; }
command -v npm >/dev/null 2>&1 || { echo "❌ Node.js/npm is not installed or not in PATH."; exit 1; }

echo "✅ Docker, Docker Compose, Python 3, Node.js/npm found."
echo ""

# ------------------------------------------------------------------------------
# 2. Setup Environment Variable Files (.env)
# ------------------------------------------------------------------------------
echo "📄 Setting up environment variable files..."

copy_env_if_missing() {
    local dir="$1"
    if [ ! -f "${dir}/.env" ] && [ -f "${dir}/.env.example" ]; then
        cp "${dir}/.env.example" "${dir}/.env"
        echo "  - Created ${dir}/.env from .env.example"
    else
        echo "  - ${dir}/.env already exists (skipped)"
    fi
}

copy_env_if_missing "${PROJECT_ROOT}"
copy_env_if_missing "${PROJECT_ROOT}/docker"
copy_env_if_missing "${PROJECT_ROOT}/horus-server"
copy_env_if_missing "${PROJECT_ROOT}/horus-eyes"
echo ""

# ------------------------------------------------------------------------------
# 3. Start Infrastructure via Docker Compose
# ------------------------------------------------------------------------------
echo "🐳 Starting Docker Infrastructure (PostgreSQL, Redis, Neo4j)..."
cd "${PROJECT_ROOT}/docker"
docker compose up -d
echo "✅ Docker containers started."
echo ""

# ------------------------------------------------------------------------------
# 4. Initialize Database Schema & Seed Data
# ------------------------------------------------------------------------------
echo "🗄️ Initializing Database..."
bash "${PROJECT_ROOT}/scripts/init_db.sh"
echo ""

# ------------------------------------------------------------------------------
# 5. Setup Python Virtual Environment & Install Dependencies
# ------------------------------------------------------------------------------
echo "🐍 Setting up Python Virtual Environment..."
cd "${PROJECT_ROOT}"

if [ ! -d ".venv" ]; then
    python3 -m venv .venv
    echo "  - Created shared .venv at project root"
fi

# Activate virtual environment
source .venv/bin/activate
pip install --upgrade pip

echo "📦 Installing Python module dependencies..."
for req in horus-server/requirements.txt horus-eyes/requirements.txt horus-nlp/requirements.txt horus-quant/requirements.txt; do
    if [ -f "${PROJECT_ROOT}/${req}" ]; then
        echo "  - Installing ${req}..."
        pip install -r "${PROJECT_ROOT}/${req}"
    fi
done

echo "🎭 Installing Playwright browser dependencies..."
playwright install chromium || echo "⚠️ Playwright browser install skipped or needs manual run."
echo ""

# ------------------------------------------------------------------------------
# 6. Setup Frontend Dependencies (horus-web)
# ------------------------------------------------------------------------------
echo "⚛️ Setting up Frontend (horus-web)..."
cd "${PROJECT_ROOT}/horus-web"
npm install
echo "✅ Frontend dependencies installed."
echo ""

# ------------------------------------------------------------------------------
# Done Summary
# ------------------------------------------------------------------------------
echo "================================================================="
echo "🎉 Horus 2.0 Setup Completed Successfully!"
echo "================================================================="
echo ""
echo "🚀 Quick Start Commands:"
echo "  1) Start Backend API (Port 8000):"
echo "     source .venv/bin/activate && cd horus-server && uvicorn app.main:app --reload --port 8000"
echo ""
echo "  2) Start Frontend Web Dashboard (Port 3000):"
echo "     cd horus-web && npm run dev"
echo ""
echo "  3) Run AI Crawler:"
echo "     source .venv/bin/activate && cd horus-eyes && python main.py"
echo ""
echo "  4) Run NLP Pipeline:"
echo "     source .venv/bin/activate && cd horus-nlp && python main.py"
echo ""
echo "  5) Run Stock Quant Scheduler:"
echo "     source .venv/bin/activate && cd horus-quant && python main.py"
echo "================================================================="
