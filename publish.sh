#!/bin/bash
# 노션에서 읽어 docs/ 를 새로 만들고 GitHub에 올린 뒤, 노션 질환 DB에 공개 주소를 기록합니다.
# NOTION_TOKEN 은 환경변수로 받습니다 (clinic-automation 과 같은 통합 토큰).
set -euo pipefail
cd "$(dirname "$0")"
: "${NOTION_TOKEN:?NOTION_TOKEN 이 필요합니다}"
python3 build.py --out docs
git add -A docs
if git diff --cached --quiet; then
  echo "바뀐 내용 없음"
else
  git commit -q -m "안내 페이지 갱신 $(date '+%Y-%m-%d %H:%M')"
  git push -q origin main
  echo "올림 완료"
fi
python3 build.py --out docs --write-urls >/dev/null
echo "노션 URL 칸 확인 완료"
