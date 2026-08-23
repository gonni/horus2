#!/usr/bin/env bash
# ==============================================================================
# Horus 2.0 Admin Console UI (Next.js) 실행 스크립트 (Port 3001)
# Ctrl+C (SIGINT) 시 즉시 안전 종료
# ==============================================================================

set -e

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
cd "$SCRIPT_DIR"

if ! command -v npm &>/dev/null; then
    echo "❌ [오류] Node.js / npm이 설치되어 있지 않습니다."
    exit 1
fi

if [ ! -d "$SCRIPT_DIR/horus-admin/node_modules" ]; then
    echo "📦 [horus-admin] 의존성 패키지를 설치합니다 (npm install)..."
    (cd "$SCRIPT_DIR/horus-admin" && npm install)
fi

echo "🛡️ [Horus Admin] 관리자 콘솔 대시보드를 시작합니다..."
echo "👉 접속 주소: http://localhost:3001"
echo "💡 중단하려면 [Ctrl + C]를 누르세요. (즉시 종료됩니다)"
echo "--------------------------------------------------------"

cd "$SCRIPT_DIR/horus-admin"

# SIGINT(Ctrl+C) 및 SIGTERM 트랩 설정 (즉각 종료)
trap 'exit 0' INT TERM

# exec를 사용하여 쉘 프로세스를 npm/next 프로세스로 직접 대체 (Ctrl+C 즉시 반응)
exec npm run dev -- "$@"
