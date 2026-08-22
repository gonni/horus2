#!/usr/bin/env bash
# ==============================================================================
# Horus Core Backend Server (FastAPI) 실행 스크립트
# Ctrl+C (SIGINT) 시 즉시 안전 종료
# ==============================================================================

set -e

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
cd "$SCRIPT_DIR"

if [ -d "$SCRIPT_DIR/.venv" ]; then
    VENV_DIR="$SCRIPT_DIR/.venv"
elif [ -d "$SCRIPT_DIR/horus-server/.venv" ]; then
    VENV_DIR="$SCRIPT_DIR/horus-server/.venv"
else
    echo "❌ [오류] Python 가상환경(.venv)을 찾을 수 없습니다."
    echo "  먼저 ./scripts/setup.sh 를 실행하여 가상환경을 구성해주세요."
    exit 1
fi

VENV_PYTHON="$VENV_DIR/bin/python"

echo "⚡ [Horus Server] 백엔드 API 서버를 시작합니다..."
echo "👉 Swagger API 문서: http://localhost:8000/docs"
echo "💡 중단하려면 [Ctrl + C]를 누르세요. (즉시 종료됩니다)"
echo "--------------------------------------------------------"

cd "$SCRIPT_DIR/horus-server"
export PYTHONPATH="$SCRIPT_DIR/horus-server:$SCRIPT_DIR/horus-eyes:$PYTHONPATH"

# SIGINT(Ctrl+C) 및 SIGTERM 트랩 설정 (즉각 종료)
trap 'exit 0' INT TERM

# exec를 사용하여 쉘 프로세스를 uvicorn 프로세스로 직접 대체 (Ctrl+C 즉시 반응)
exec "$VENV_PYTHON" -m uvicorn app.main:app --reload --host 0.0.0.0 --port 8000 "$@"
