# SAVEDEAL

통신유통 예약판매 이탈 방지 **운영 Agent**. 이미 등록된 예약 목록을 계속 감시하고, 미완료 예약을 처리 우선순위대로 정렬한 뒤, 문제마다 해결책을 제안하고 직원이 승인하도록 한다. 승인한 해결책이 실패하면 새 대안을 다시 생성한다.

팀 프로젝트 Command Center(저장소 루트의 `command_center/`, 포트 5000)의 "예약판매 이탈 방지" 카드가 이 앱(`http://localhost:5001/savedeal`)으로 연결된다.

## 기술 스택

- Python 3.14 / Flask, Jinja2 + 순수 HTML/CSS/JavaScript
- 예약·해결책·처리이력: SQLite (`data/savedeal.db`, git에 올리지 않음)
- 고객·매장·단말·재고 기준 정보: `data/` 아래 JSON mock data
- pytest

## 설계 원칙

- 판정·우선순위·해결책 생성은 모두 Python 규칙 기반 서비스에서 한다. 프론트 JavaScript에는 업무 판정 로직을 넣지 않고, API가 준 값(라벨, `can_approve` 같은 플래그)을 그리기만 한다.
- `routes`(요청/응답) → `services`(판정·비즈니스 로직) → `repositories`(데이터 I/O) 순으로 계층을 나누고, `schemas`는 요청 검증을 맡는다.
- API 응답은 `{"success": bool, "data": ..., "error": {"code", "message"} | null}` 형태로 통일한다.
- 실제 통신사 API, 실제 개인정보·신용정보 조회, 실제 개통 전산 연동, 실제 문자 발송은 하지 않는다. 재고 이동과 고객 연락은 **가상 실행**이다.
- 판매정책 검증, 인센티브 계산, 점포손익 계산은 범위가 아니다.

## 디렉터리 구조

```
app.py            Flask application factory (시작 시 DB 생성·mock 시드)
config.py         환경설정 (DATA_DIR, DB_PATH, PORT, COMMAND_CENTER_URL 등)
db/               SQLite 스키마(schema.sql), 연결(connection.py), mock 시드(seed.py)
data/             JSON 기준 정보 + savedeal.db
routes/           pages(화면), reservations(운영 API), precheck(사전검증 API), main(health)
services/         codes(상태·문제·해결책 코드), risk_scoring, action, dashboard, reservation, 사전검증 서비스들
repositories/     JSON 리포지토리 + SQLite 리포지토리(reservation, proposed_action, action_history)
templates/        savedeal.html(대시보드), savedeal_new.html(신규 예약)
static/           css/common.css, css/dashboard.css, css/savedeal.css, js/dashboard.js, js/precheck.js
tests/            pytest (테스트마다 시드된 임시 DB 사본 사용)
```

## 화면

- `/savedeal`: 예약 운영 대시보드(메인). 요약 카드, 필터(전체/처리 필요/고위험/오늘 마감/완료), 우선순위 순 예약 테이블, 예약 클릭 시 오른쪽 상세 패널(좁은 화면에서는 drawer).
- `/savedeal/new`: 신규 예약 사전검증 → "이 조건으로 예약 등록"으로 운영 DB에 저장.
- `/`는 `/savedeal`로 이동한다. 사이드바 "홈"은 Command Center로 간다.

## 데이터 모델 (SQLite)

- `reservations`: 예약 정보, 진행상태(`ACTION_REQUIRED` 처리 필요 / `IN_PROGRESS` 해결 진행 중 / `READY` 개통 대기 / `COMPLETED` / `CANCELLED`), 미해결 문제 목록 `issues`(JSON), `retry_count`, `customer_waiting_since`, `activation_deadline`
- `proposed_actions`: 문제별 해결책. `PROPOSED` → `APPROVED` → `SUCCEEDED`/`FAILED`. 같은 문제의 다른 제안은 승인 시 `DISCARDED`(보류)
- `action_history`: 처리이력

문제 원인 → 해결책 (`services/action_service.py`):
- 재고 미확보 → 인근 점포 재고 이동, 다른 색상·용량, 대체 단말, 수령일 변경
- 할부한도 부족 → 선납금 적용, 할부기간 조정
- 서류 미제출 → 누락서류 요청(문자/매장 방문)
- 본인인증 실패 → 본인인증 재시도(같은 방식/대면)
- 개통 반려 → 개통 반려 입력값 수정
- 고객 미응답 → 고객 재연락(전화/알림톡)
- 요금 미납 → 미납요금 납부 안내
- 한 문제의 안이 모두 실패하면 → 점장 에스컬레이션

## 점수 (`services/risk_scoring_service.py`, 조회할 때마다 다시 계산하며 DB에 저장하지 않음)

- `churn_risk_score`(0~100): 문제 원인별 점수 + 고객 대기시간 + 재시도 횟수 + 마감 임박/초과. 45 이상 고위험, 25 이상 주의. 문제가 없으면 0.
- `priority_score`: 위험도 + 개통 마감까지 남은 시간 + 고객 대기시간 + 재시도 횟수 + 재고 미확보 + 서류 미제출 + 개통 반려. 완료·취소 예약은 0.

## API

```
GET  /api/reservations?filter=all|needs_action|high_risk|due_today|completed
GET  /api/reservations/<id>
POST /api/reservations                                   신규 예약(사전검증 + 저장 + 해결책 생성)
POST /api/reservations/<id>/actions/<action_id>/approve  승인 (가상 실행 시작)
POST /api/reservations/<id>/actions/<action_id>/succeed  실행 성공 → 문제 해결
POST /api/reservations/<id>/actions/<action_id>/fail     실행 실패 → retry_count+1, 새 대안 생성
POST /api/reservations/<id>/complete                     개통 완료 (READY일 때만)
POST /api/demo/reset                                     mock 데이터로 초기화
POST /api/precheck                                       사전검증만 (저장 안 함)
```

## 실행 방법

```
pip install -r requirements.txt
copy .env.example .env
python -m app
```

`http://localhost:5001/savedeal` (포트 5001 고정, 루트 CLAUDE.md 포트 표 참고). 처음 실행하면 `data/savedeal.db`가 mock 예약 17건으로 만들어진다. mock 시각은 시드하는 순간을 기준으로 하므로, 날이 지나 "오늘 마감"이 맞지 않으면 대시보드의 "데모 데이터 초기화" 버튼이나 `python -m db.seed`로 다시 채운다.

## 테스트 방법

```
pytest
```

## 참고

- mock data의 고객/예약 정보는 모두 가상의 데이터이며 실제 개인정보가 아니다.
- `POST /api/precheck` 응답의 `churn_risk_score`, `recommended_action`은 사전검증 전용이라 여전히 `null`이다. 이탈위험 점수는 운영 대시보드(예약 저장 후)에서 계산된다.
- 아직 없는 것: 생성형 AI 안내문 생성, 실제 알림 발송, 사용자(직원) 인증.
