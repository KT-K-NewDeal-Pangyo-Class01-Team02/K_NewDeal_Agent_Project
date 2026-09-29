# 더 줘 (thejo_project)

판매점 사장님이 **복잡한 인센티브와 누적 판매 구조를 놓치지 않도록** 돕는 에이전트입니다. (담당: 정주희)

Command Center 홈과 **같은 Flask 프로세스**에서 Blueprint 로 돕니다. 별도 서버·별도 포트가 없습니다.

## 실행

Python **3.12 이상** (3.14 에서 동작 확인). 저장소 루트에서:

```powershell
python -m venv .venv
.\.venv\Scripts\Activate.ps1
pip install -r command_center/requirements.txt
python -m command_center.app
```

| 화면 | 주소 |
|---|---|
| Command Center 홈 | http://localhost:5000/ |
| 더 줘 대시보드 | http://localhost:5000/thejo/ |
| 위험 경고 | http://localhost:5000/thejo/warnings |
| 수익 기회 | http://localhost:5000/thejo/opportunities |

## 테스트

```powershell
python -m unittest thejo_project.tests.test_thejo -v
```

추가 패키지 없이 표준 `unittest` 로 돕니다.

## 기능

### ① Warning 알림
인센티브가 환수되거나 수익이 줄 수 있는 거래를 위험 등급·예상 손실·확인 기한·권장 조치와 함께 보여 줍니다.
카드마다 **거래 확인**(문자 모달) / **조치 완료** 버튼이 있습니다.

### ② 놓치고 있는 수익 구조
월 누적 판매량과 인센티브 구간을 계산해 추가 수익 기회를 알려 줍니다.
구간을 달성하면 그 달의 **모든 판매 건에 상향 단가가 소급 적용**됩니다.

```
9건  → 건당 10만 → 총 90만
10건 → 건당 20만 → 총 200만
10번째 판매로 늘어나는 총인센티브 = 110만

고객 혜택 활용 가능 금액 = 110만 - 최소 확보 수익 70만 = 40만
```

### ③ 고객 안내 문자
Warning 카드의 **거래 확인**을 누르면 그 거래의 고객 정보가 채워진 문자 모달이 열립니다.

```
거래 확인 → 거래·고객 정보 확인 → 템플릿 칩 클릭 → 내용 수정
         → 문자 전송 → 확인창 → 발송 → '문자 안내 완료' 배지
```

- 템플릿 3종(유지조건 안내 / 환수위험 안내 / 상담요청 안내)의 `{중괄호}` 변수는 **서버가** 거래 데이터로 치환합니다.
- 90바이트 이하는 `SMS`, 넘으면 `LMS`. 한글은 2바이트로 셉니다(EUC-KR 기준). 서버와 JS 가 같은 규칙을 씁니다.
- 내용이 비었거나 고객 전화번호가 없으면 전송 버튼이 회색으로 잠깁니다.
- 화면이 보낸 고객 정보는 신뢰하지 않습니다. 서버가 `transaction_id` 로 다시 채워 발송합니다.

## n8n 연결

지금은 **데모 모드**입니다. 실제로 문자를 보내려면 `thejo_project/.env` 에 한 줄을 넣으세요.

```
N8N_SMS_WEBHOOK_URL=https://<내 n8n>/webhook/sms
N8N_SMS_TIMEOUT=10
```

- Webhook URL 은 **서버에서만** 읽습니다. 템플릿·JS·API 응답 어디에도 나가지 않습니다.
- 응답 제한시간은 10초입니다. 실패하면 모달이 닫히지 않고 오류가 뜹니다.
- 환경변수가 없으면 실제 발송 없이 `{"success": true, "demo": true}` 를 돌려줍니다.
- `.env` 는 루트 `.gitignore` 에 걸려 있어 커밋되지 않습니다.

n8n 으로 가는 본문은 이렇습니다.

```json
{
  "transaction_id": "TX-202609-018",
  "customer_id": "C-018",
  "customer_name": "정○현",
  "customer_phone": "010-1234-5678",
  "template_id": "PLAN_MAINTENANCE",
  "message": "고객에게 전송할 최종 문자 내용",
  "plan_name": "초이스 프리미엄",
  "maintenance_end_date": "2027-03-17",
  "remaining_days": 150,
  "expected_clawback": 300000,
  "store_id": "STORE-01",
  "store_phone": "02-1234-5678"
}
```

## 라우트

| 메서드 | 경로 | 용도 |
|---|---|---|
| GET | `/thejo/` | 대시보드 |
| GET | `/thejo/warnings` | 위험 경고 목록 |
| GET | `/thejo/opportunities` | 수익 기회 + 시뮬레이터 |
| GET | `/thejo/api/transactions/<id>` | 모달이 쓰는 거래 정보 + 치환된 템플릿 3개 |
| POST | `/thejo/api/sms/send` | 문자 발송 |
| POST | `/thejo/warnings/<id>/ack` | 조치 완료 |
| GET | `/thejo/api/simulate?units=N` | 혜택 시뮬레이션 |

## 구조

```
thejo_project/
├─ __init__.py        thejo_bp 를 내보낸다
├─ routes.py          Blueprint 정의 · 라우트 · 금액 표기 필터(won, manwon)
├─ config.py          정책 상수 + 문자 템플릿 + n8n 설정 ← 정책·문구가 바뀌면 여기만
├─ data/
│   ├─ demo_data.py   거래·고객·경고 데모 데이터 (계산하지 않는다)
│   ├─ sms_store.py   문자 발송 기록 (sms_log.json)
│   └─ sms_log.json   실행 중 생성. 새로고침해도 발송 상태가 남게 한다
├─ services/          비즈니스 계산. 모든 금액 계산이 여기에만 있다
│   ├─ incentive_service.py     구간 계산 (순수 함수)
│   ├─ transaction_service.py   거래 조회 + 유지일수 계산
│   ├─ warning_service.py       위험 경고 조회 · 조치 완료
│   ├─ opportunity_service.py   수익 기회 · 대시보드 요약
│   └─ sms_service.py           템플릿 치환 · SMS/LMS 판정 · 발송
├─ templates/thejo/   Jinja2. Command Center 의 cc_layout.html 을 그대로 상속한다
│   └─ _sms_modal.html  고객 안내 문자 모달
├─ static/            css/ js/ images/ — /thejo/static/ 으로 서빙
└─ tests/             unittest
```

### 설계 규칙

- 금액은 내부에서 **원 단위 정수**로만 다루고, 만 원 표기는 템플릿 필터(`| manwon`)에서만 합니다.
- 계산 결과와 문자 본문을 HTML·JS 에 하드코딩하지 않습니다. JS 는 서버가 준 값을 표기만 바꿉니다.
- 유지 종료일과 남은 일수는 **저장하지 않고** 개통일 + 필수 유지일수로 계산합니다. 두 값이 어긋날 수 없습니다.
- 계산 함수는 순수 함수라 같은 입력이면 항상 같은 결과가 나옵니다. 금액 계산에 LLM 을 쓰지 않습니다.
- 정책(`config.py`)·데이터(`data/`)·계산(`services/`)이 분리되어 있어, CSV·Sheets·DB 로 바꿀 때 `data/` 의 `get_*` 함수 본문만 교체하면 됩니다.
- `requests` 대신 표준 `urllib` 을 씁니다. 패키지를 늘리지 않기 위해서입니다.

## 남은 일

- `data/demo_data.py` 를 실제 데이터 소스로 교체하고, `DEMO_TODAY` 를 `date.today()` 로 바꿉니다.
- **`조치 완료` 상태는 프로세스 메모리에만** 남습니다. 서버를 끄면 초기화됩니다. (문자 발송 기록은 파일에 남습니다.)
- `data/sms_log.json` 이 git 에 추적됩니다. 팀에서 합의되면 루트 `.gitignore` 에 추가하세요 (공용 파일이라 팀 동의 필요).
- 인센티브 구간이 1~19건까지만 정의되어 있습니다. 20건 이상 정책이 정해지면 `config.py` 에 구간을 추가합니다.
- 문자 발송 결과를 n8n 이 비동기로 알려주는 경우(콜백)는 아직 처리하지 않습니다. 지금은 요청 응답만 봅니다.
