#!/usr/bin/env bash
# ==============================================================================
# HorusEyes AI Crawler 실행 스크립트
# Ctrl+C (SIGINT) 시 즉시 안전 종료
# ==============================================================================

set -e

# 스크립트 위치 기준 프로젝트 루트 경로 계산
SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
cd "$SCRIPT_DIR"

# Python 가상환경 탐색
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

# SIGINT(Ctrl+C) 및 SIGTERM 트랩 설정 (즉각 종료)
trap 'exit 0' INT TERM

echo "🚀 [HorusEyes] AI 크롤러를 시작합니다..."
echo "💡 중단하려면 [Ctrl + C]를 누르세요. (즉시 종료됩니다)"
echo "--------------------------------------------------------"

cd "$SCRIPT_DIR/horus-eyes"
export PYTHONPATH="$SCRIPT_DIR/horus-eyes:$SCRIPT_DIR/horus-server:$PYTHONPATH"

# exec를 사용하여 쉘 프로세스를 Python 프로세스로 직접 대체 (Ctrl+C 즉시 반응)
exec "$VENV_PYTHON" main.py "$@"
