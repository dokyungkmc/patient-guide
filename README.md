# 도경한의원 환자 안내 페이지

노션 '근골격 진단·생활관리 콘텐츠 창고'를 읽어 질환별 환자 안내 페이지를 만들고 GitHub Pages로 공개합니다.

- 공개 주소: https://dokyungkmc.github.io/patient-guide/<콘텐츠 ID 소문자>/  (예: MSK-DX-2 → /msk-dx-2/)
- 노출 규칙: 질환·생활관리·재활운동은 검수 상태 '사용중'만. 영상은 '영상 승인'=승인 이고 '환자 공개' 체크된 것만 페이지 안에서 재생.
- 갱신: `NOTION_TOKEN=... ./publish.sh` (맥미니). 노션 질환 DB '환자 안내 페이지 URL' 칸도 자동으로 채움.
- 질환 그림: `figures/<slug>.svg` 가 있으면 그 그림, 없으면 부위 표시 그림. 설명 글은 `figures/<slug>.txt`.
- 공유 이미지(카톡 미리보기): `og/<부위코드>.png`.
- 내부 미리보기(승인 안 된 영상 포함): `python3 build.py --all-videos --out /tmp/preview` — 공개 배포 금지.
