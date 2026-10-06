# SAVEDEAL

통신유통 예약판매 이탈 방지 **운영 Agent**. 이미 등록된 예약 목록을 계속 감시하고, 미완료 예약을 처리 우선순위대로 정렬한 뒤, 문제마다 해결책을 제안하고 직원이 승인하도록 한다. 승인한 해결책이 실패하면 새 대안을 다시 생성한다.

팀 프로젝트 Command Center(저장소 루트의 `command_center/`, 포트 5000)의 "예약판매 이탈 방지" 카드가 이 앱(`http://localhost:5001/savedeal`)으로 연결된다. 사이드바·상단 바는 허브와 같은 공통 틀(`templates/cc_layout.html` 사본)을 쓴다.

## 기술 스택

- Python 3.14 / Flask, Jinja2 + 순수 HTML/CSS/JavaScript
- 운영 데이터: SQLite (`data/savedeal.db`, git에 올리지 않음) — 예약·해결책·처리이력·고객·재고·업로드·알림·AI 기록
- 기본 기준 정보: `data/*.json` (DB가 비어 있을 때 고객·재고를 채우는 원본, 매장·단말 목록)
- 엑셀 업로드: openpyxl / 외부 호출: requests (n8n Webhook, OpenAI API)
- pytest

## 설계 원칙

- 판정·우선순위·해결책 생성은 모두 Python 규칙 기반 서비스에서 한다. 프론트 JavaScript에는 업무 판정 로직을 넣지 않고, API가 준 값(라벨, `can_approve` 같은 플래그)을 그리기만 한다.
- **AI(OpenAI)는 글을 읽고 쓰는 일만** 한다: 메모 해석, 고객 안내문, 직원 브리핑. 판정에는 개입하지 않는다. 키가 없거나 실패하면 규칙 기반 결과로 대체하고, 모든 호출을 `ai_logs`에 남긴다.
- **n8n은 전달만** 한다 (SaveDeal → n8n Webhook → Gmail). 메일 문구는 SaveDeal이 만든다. 주소가 없으면 데모 기록만 남긴다.
- **외부 이벤트**(개통 반려·입고 지연·서류 도착·개통 완료·취소)는 n8n이 `POST /api/events`로 보내거나, SaveDeal 서버가 백그라운드로 `EVENT_SYNC_SECONDS`마다 n8n에서 가져온다(`N8N_EVENTS_URL`, `services/event_sync.py`, `python -m app`으로 켤 때만 돌고 테스트에서는 돌지 않음). 반영 규칙은 `services/event_service.py`: 문제 발생 → 문제 추가·해결책 생성(진행 중인 안이 있으면 실패 처리 후 재제안, 이미 있는 문제가 다시 생기면 재시도 +1), 문제 해소 → 해결 처리, 종료 이벤트 → 예약 종료. 같은 이벤트는 `external_id`로 한 번만 반영한다. 시연에서는 구글시트를 가짜 전산으로 쓴다 (`docs/n8n_events_setup.md`).
- **정기 점검**(`POST /api/monitor/scan`, `services/monitor_service.py`): 시간이 지나 새로 고위험이 된 예약만 알린다. 알린 예약은 `risk_alerts`에 기록해 반복하지 않는다.
- `routes`(요청/응답) → `services`(판정·비즈니스 로직) → `repositories`(데이터 I/O) 순으로 계층을 나누고, `schemas`는 요청 검증을 맡는다. 현업 전환 시 repositories 만 실제 DB·전산 API로 바꾸면 된다.
- API 응답은 `{"success": bool, "data": ..., "error": {"code", "message"} | null}` 형태로 통일한다.
- **교육용 가상 데이터만** 다룬다. 업로드는 마스킹된 연락처(010-****-1234)만 받고, n8n·AI로 나가는 정보에는 마스킹된 이름만 담는다. 원본 업로드 파일은 저장하지 않는다.
- 실제 통신사 API, 실제 개인정보·신용정보 조회, 실제 개통 전산 연동, 실제 고객 문자 발송은 하지 않는다. 재고 이동과 고객 연락은 **가상 실행**이다 (고객 안내 메일은 담당자 메일로 받는다).
- 판매정책 검증, 인센티브 계산, 점포손익 계산은 범위가 아니다.
- **화면·메일·처리이력 문구에 '가상', '데모' 같은 표현을 쓰지 않는다** (실제 운영 제품처럼). 코드 주석·개발 문서에서는 가상 데이터라고 설명해도 된다. `tests/test_wording.py`가 확인한다.

## 디렉터리 구조

```
app.py            Flask application factory (시작 시 DB 생성·mock 시드, 허브 공통 틀 연결)
config.py         환경설정 (DATA_DIR, DB_PATH, PORT, COMMAND_CENTER_URL, N8N_*, EVENT_SYNC_SECONDS, OPENAI_*)
db/               SQLite 스키마(schema.sql), 연결·마이그레이션(connection.py), mock 시드(seed.py)
data/             JSON 기준 정보 + savedeal.db
docs/             n8n_openai_setup.md (n8n Gmail 워크플로·OpenAI 키 설정, 시연 순서), n8n_events_setup.md (외부 이벤트·정기 점검)
samples/          사전예약_명단_예시.xlsx (업로드 시연용), 외부이벤트_시트_예시.csv (구글시트 가짜 전산)
routes/           pages(화면), reservations(운영·알림·AI API), uploads(업로드 API), events(외부 이벤트·정기 점검 API), precheck, main,
                  layout(허브 사이드바 값)
services/         codes, risk_scoring, action, dashboard, reservation, upload, notification, n8n_client, ai_service, ai_client,
                  event(외부 이벤트 반영), event_sync(가져오기·백그라운드 자동 확인), monitor(정기 점검),
                  device_images, carriers, 사전검증 서비스들
repositories/     reservation·proposed_action·action_history(SQLite), customer·inventory(SQLite 또는 JSON), store·device(JSON)
templates/        cc_layout.html·cc_icons.html(허브 사본), base.html, savedeal.html(대시보드), savedeal_new.html, savedeal_upload.html
static/           css(cc_common·common·dashboard·savedeal·upload), js(cc_common·dashboard·precheck·upload), img(devices·carriers)
tests/            pytest (테스트마다 시드된 임시 DB 사본, 실제 네트워크 요청 차단)
```

## 화면 (상단 탭)

- `/savedeal` 예약 운영: 요약 카드, 필터, 우선순위 순 예약 테이블, 상세 패널(고객 메모·AI 브리핑·해결책·알림 기록·처리이력). 상단에 n8n·AI·외부 이벤트 연동 상태, **이벤트 발생** 버튼(`services/event_trigger.py`: 첫 번째는 정하늘에게 이벤트를 더해 우선순위 1위로, 그다음부터는 무작위 한 명에게 이벤트 하나. 출처 '수동 발생'으로 외부 이벤트와 같은 경로로 반영되고, 결과 배너·▲순위 변화·NEW 문제 칩으로 보여 준다), **최신화** 버튼(외부 이벤트 즉시 가져오기 + 고위험 점검 + 화면 새로 고침), 리포트 메일·데이터 초기화 버튼. 외부 이벤트가 반영되면 15초 안에 목록·상세가 자동으로 다시 그려진다 (가져오기는 서버가 하고, 화면은 바뀐 게 있는지만 확인). 남은 시간·대기 시간은 1초마다 흐르고(서버 `generated_at` 기준, 마감 1시간 전부터 초 단위), 점수·우선순위·건수는 1분마다 서버에서 다시 받는다.
- `/savedeal/new` 신규 예약: 사전검증 → 예약 등록.
- `/savedeal/upload` 예약 업로드: 사전예약 명단·고객 정보·재고 현황 엑셀/CSV → 행별 검증 미리보기 → 등록.

## 데이터 모델 (SQLite)

- `reservations`: 예약 정보, 진행상태, 문제 목록 `issues`(JSON), `retry_count`, 기존 통신사, `memo`·`memo_insight`(메모 해석 JSON)
- `proposed_actions`, `action_history`: 해결책과 처리이력
- `customers`, `inventory`: 고객·재고 기준 정보 (업로드로 갱신, 데모 초기화 시 JSON + mock 고객으로 복원)
- `upload_batches`: 업로드 미리보기·확정 기록 (검증된 행은 확정 전까지만 보관)
- `notifications`: 알림 (`SENT` / `FAILED` / `DEMO`)
- `ai_logs`: AI 사용 기록 (기능, `ai`/`rule`, 모델, 성공 여부, 응답 시간)
- `inbound_events`: 받은 외부 이벤트 (`external_id` 고유, 결과 `APPLIED`/`SKIPPED`/`ERROR`)
- `risk_alerts`: 고위험 알림을 이미 보낸 예약 (정기 점검 중복 방지)

문제 원인 → 해결책 (`services/action_service.py`): 재고 미확보 → 인근 점포 이동·색상/용량·대체 단말·수령일 변경 / 할부한도 부족 → 선납금·할부기간 / 서류 미제출 → 누락서류 요청 / 본인인증 실패 → 재시도 / 개통 반려 → 입력값 수정 / 고객 미응답 → 재연락 / 요금 미납 → 납부 안내 / 고객 정보 확인 필요 → 전산 조회 / 모두 실패 → 점장 에스컬레이션. 메모 해석 결과(대체 가능 색상, 선호 연락)는 해결책 **순서와 설명**에만 반영한다.

## API

```
GET  /api/reservations?filter=…&status=…&risk=…
GET  /api/reservations/<id>                              상세 (알림 기록 포함)
POST /api/reservations                                   신규 예약
POST /api/reservations/<id>/actions/<aid>/approve|succeed|fail   (approve: 고객 안내 메일)
POST /api/reservations/<id>/complete
POST /api/reservations/<id>/briefing                     직원 브리핑 (AI 또는 규칙)
GET  /api/uploads · POST /api/uploads (kind, file) · POST /api/uploads/<id>/commit|cancel · GET /api/uploads/template/<kind>
GET  /api/notifications · POST /api/notifications/<id>/retry · POST /api/notifications/daily-report
GET  /api/integrations                                   n8n·AI·외부 이벤트 연동 상태와 최근 AI 기록
POST /api/events · POST /api/events/sync · GET /api/events   외부 이벤트 (n8n 호출은 N8N_WEBHOOK_SECRET 헤더 인증,
                                                         비밀값이 없으면 이 컴퓨터에서 온 요청만)
POST /api/monitor/scan                                   정기 점검 (새 고위험 알림)
POST /api/demo/reset · POST /api/precheck
```

## 실행 방법

```
pip install -r requirements.txt
copy .env.example .env      (n8n·OpenAI 설정은 docs/n8n_openai_setup.md)
python -m app
```

`http://localhost:5001/savedeal`. 처음 실행하면 `data/savedeal.db`가 mock 데이터로 만들어진다.

DB는 git에 올라가지 않으므로, **mock 데이터를 바꿀 때는** `db/demo_migrations.py`의 `DEMO_DATA_VERSION`을 올리고 `MIGRATIONS`에 단계를 추가한다. 이미 만들어진 DB는 앱이 켜질 때 바뀐 부분만 자동으로 고쳐진다 (예전 값을 그대로 가진 mock 예약만, 업로드·직접 등록한 데이터는 건드리지 않음). 날이 지나 "오늘 마감"이 맞지 않으면 "데모 데이터 초기화" 버튼이나 `python -m db.seed`로 다시 채운다.

## 테스트 방법

```
pytest
```

테스트는 n8n·OpenAI 주소를 비우고, 실제 네트워크 요청이 나가면 실패하게 되어 있다.
