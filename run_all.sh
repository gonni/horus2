#!/usr/bin/env bash
# ==============================================================================
# Horus 2.0 전체 실행 스크립트 (Backend Server + Web UI)
# Ctrl+C (SIGINT) 시 모든 백그라운드 프로세스 즉시 안전 종료
# ==============================================================================

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
cd "$SCRIPT_DIR"

SERVER_PID=""
ADMIN_PID=""
WEB_PID=""

cleanup() {
    # 트랩 중복 호출 방지
    trap - INT TERM EXIT
    echo ""
    echo "🛑 [Horus] 모든 서비스를 종료합니다..."
    
    if [ -n "$SERVER_PID" ] && kill -0 "$SERVER_PID" 2>/dev/null; then
        kill "$SERVER_PID" 2>/dev/null || true
    fi
    
    if [ -n "$ADMIN_PID" ] && kill -0 "$ADMIN_PID" 2>/dev/null; then
        kill "$ADMIN_PID" 2>/dev/null || true
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
echo "🌟 [Horus 2.0] 백엔드 코어, 어드민 콘솔 및 서비스 웹 UI 동시 실행"
echo "👉 서비스 Web UI:   http://localhost:3005 (프록시: http://localhost:3000)"
echo "👉 어드민 Console:   http://localhost:3001"
echo "👉 백엔드 API Docs:  http://localhost:8000/docs"
echo "💡 중단하려면 [Ctrl + C]를 누르세요. (즉시 모두 종료됩니다)"
echo "========================================================"

# 1. 백엔드 서버 실행 (:8000)
"$SCRIPT_DIR/run_server.sh" &
SERVER_PID=$!

# 2. 어드민 콘솔 실행 (:3001)
"$SCRIPT_DIR/run_admin.sh" &
ADMIN_PID=$!

# 3. 서비스 웹 UI 실행 (:3000)
"$SCRIPT_DIR/run_web.sh" &
WEB_PID=$!

# 프로세스 대기
wait

