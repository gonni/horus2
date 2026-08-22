#!/usr/bin/env bash
# ==============================================================================
# Horus 2.0 전체 실행 스크립트 (Backend Server + Web UI)
# Ctrl+C (SIGINT) 시 모든 백그라운드 프로세스 즉시 안전 종료
# ==============================================================================

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
cd "$SCRIPT_DIR"

SERVER_PID=""
WEB_PID=""

cleanup() {
    # 트랩 중복 호출 방지
    trap - INT TERM EXIT
    echo ""
    echo "🛑 [Horus] 모든 서비스를 종료합니다..."
    
    if [ -n "$SERVER_PID" ] && kill -0 "$SERVER_PID" 2>/dev/null; then
        kill "$SERVER_PID" 2>/dev/null || true
    fi
    
    if [ -n "$WEB_PID" ] && kill -0 "$WEB_PID" 2>/dev/null; then
        kill "$WEB_PID" 2>/dev/null || true
    fi
    
    kill $(jobs -p) 2>/dev/null || true
    echo "✅ 모든 서비스가 안전하게 종료되었습니다."
    exit 0
}

trap cleanup INT TERM EXIT

echo "========================================================"
echo "🌟 [Horus 2.0] 백엔드 서버 및 웹 UI 동시 실행"
echo "👉 Web UI:    http://localhost:3000"
echo "👉 API Docs:  http://localhost:8000/docs"
echo "💡 중단하려면 [Ctrl + C]를 누르세요. (즉시 모두 종료됩니다)"
echo "========================================================"

# 1. 백엔드 서버 실행
"$SCRIPT_DIR/run_server.sh" &
SERVER_PID=$!

# 2. 웹 UI 실행
"$SCRIPT_DIR/run_web.sh" &
WEB_PID=$!

# 프로세스 대기
wait
