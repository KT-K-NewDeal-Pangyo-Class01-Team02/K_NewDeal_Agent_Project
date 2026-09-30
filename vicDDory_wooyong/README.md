# 빅또리출동! (vicDDory) — 옥외 BTL 캠페인 에이전트

직영점이 발의한 옥외 BTL 캠페인을 **3시간 만에 기획**하고, 캠페인이 끝나면 **성과를 환류**하는 콘솔입니다.
Command Center(홈)의 에이전트 중 하나로 붙습니다.

- 담당: 최우용 (GitHub: crwayon)
- 포트: **5500** (Command Center 5000, SaveDeal 5001, 통하길 스튜디오 5004)

## 실행

```powershell
# vicDDory_wooyong 폴더에서
pip install -r requirements.txt
copy .env.example .env      # 필요하면 값 수정
python -m vicddory_campaign.app
```

브라우저에서 <http://localhost:5500> 접속.

`.env` 의 `N8N_WEBHOOK_URL` 과 `N8N_BASE_URL` 을 모두 비우면 **데모 모드**로 떠서, n8n 없이 화면 흐름만 확인할 수 있습니다.

## 구조

| 파일 | 역할 |
|---|---|
| `vicddory_campaign/app.py` | Flask 앱, 화면과 API (`/api/plan`, `/api/f01/scan`, `/api/f01/select`) |
| `vicddory_campaign/config.py` | `.env` 설정. n8n 웹훅 주소를 여기서 만든다 |
| `vicddory_campaign/layout.py` | Command Center 공통 사이드바·상단 바를 붙임 |
| `vicddory_campaign/n8n_client.py` | n8n 웹훅 호출 및 응답 파싱 |
| `vicddory_campaign/templates/campaign.html` | 화면 |
| `vicddory_campaign/static/campaign.js` | 캠페인 발의(8개 파라미터) → F-02 검증 → 기획안 |
| `vicddory_campaign/static/f01.js` | F-01 이번 주 옥외 기회 스캔 · 카드 선택 |
| `Outdoor-Public-Relations-Campaign-Agent-main/index.html` | Flask 이전의 초기 프로토타입 (참고용 보관, 더 이상 수정하지 않음) |

## 화면과 n8n 워크플로

브라우저는 Flask 만 부르고, n8n 호출은 Flask 가 대신합니다. 그래서 CORS 설정이 필요 없고 웹훅 주소도 브라우저에 드러나지 않습니다.

| 화면 동작 | Flask API | n8n 웹훅 | 설정 |
|---|---|---|---|
| 기회 스캔 | `POST /api/f01/scan` | `F01_scan` (`/webhook/f01-scan`) | `N8N_BASE_URL` |
| 이 카드로 캠페인 시작 | `POST /api/f01/select` | `F01_select` (`/webhook/f01-select`) | `N8N_BASE_URL` |
| 캠페인 발의 폼 채우기 (근무자 · 장소 · 재고) | `POST /api/f02/options` | `F02_validate` (`/webhook/f02-validate`, action=options) | `N8N_BASE_URL` |
| 캠페인 발의 제출 ① 제약 검증 | `POST /api/f02/validate` | `F02_validate` (action=validate) | `N8N_BASE_URL` |
| 캠페인 발의 제출 ② 기획서 생성 (검증 통과 시) | `POST /api/plan` | `WF_plan` (`/webhook/wf-plan`) → `F03_site` → `F04_copy` → `F05_callsheet` | `N8N_BASE_URL` |
| (F-02 없이 부를 때만) 기존 기획서 생성 | `POST /api/plan` | `BTL 기획안 생성 (Webhook)` (`/webhook/plan-gen`) | `N8N_WEBHOOK_URL` |

기획안은 마크다운을 문서로 바꿔 보여 주며, **서식 복사**(워드·한글·구글 문서에 표 그대로 붙여 넣기)와 **PDF 저장**(A4 인쇄 창)을 지원합니다. 입지 섹션에는 캠페인 이미지 자리가 있고, 통하길 스튜디오 포스터 제작으로 링크합니다.

n8n 쪽 공용 부품: `00_dummy_data`(프로모션·유동인구·과거 성과 더미), Supabase `roster`·`opportunity_cards`·`campaigns` 테이블.

## Command Center 연동

사이드바·상단 바 디자인(`cc_layout.html`, `common.css` 등)은 허브와 같은 모양의 **사본을 이 폴더에** 둡니다.
사이드바의 에이전트 목록만 허브의 `command_center/agents.json` 을 **읽어서** 씁니다 (수정하지 않음).

`agents.json` 의 빅또리출동! 항목은 id `aftercare`, 주소 `http://localhost:5500` 으로 등록되어 있습니다.
`layout.py` 의 `AGENT_ID` 가 이 id 와 같아야 사이드바에서 현재 페이지로 표시됩니다.
