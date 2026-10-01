# SaveDeal 연동 설정: n8n(Gmail 알림) · OpenAI(AI)

둘 다 **설정하지 않아도 앱은 동작**합니다.

- n8n 주소가 비어 있으면 → 메일을 보내지 않고 **데모 기록**만 남깁니다 (대시보드 상단 `n8n 데모 모드`).
- OpenAI 키가 비어 있으면 → AI를 부르지 않고 **규칙 기반 문구**를 씁니다 (`AI 꺼짐 · 규칙 기반`).

설정을 바꾼 뒤에는 SaveDeal 서버를 다시 켜야 반영됩니다.

---

## 1. n8n → Gmail 알림

SaveDeal이 n8n Webhook을 부르는 방향이라 **ngrok이 필요 없습니다** (n8n Cloud 그대로 사용).

### 워크플로 만들기 (노드 3개)

```
Webhook (POST) → Gmail (Send) → Respond to Webhook
```

| 노드 | 설정 |
|---|---|
| **Webhook** | HTTP Method `POST` · Path `savedeal-notify` · Authentication `Header Auth` (Name `X-SaveDeal-Key`, Value = 아래 `.env`의 `N8N_WEBHOOK_SECRET`) · Respond `Using 'Respond to Webhook' Node` |
| **Gmail** | Credential: 내 구글 계정(Gmail OAuth2) 연결 · Resource `Message` · Operation `Send` · To `{{ $json.body.to || '내메일@gmail.com' }}` · Subject `{{ $json.body.subject }}` · Email Type `Text` · Message `{{ $json.body.text }}` · Options → Append n8n Attribution `끄기` |
| **Respond to Webhook** | Respond With `JSON` · `{ "status": "sent", "notification_id": "{{ $('Webhook').item.json.body.notification_id }}" }` |

- 워크플로를 **Active(Publish)** 로 켜고, Webhook 노드의 **Production URL**(`…/webhook/savedeal-notify`)을 복사합니다.
  테스트 주소(`/webhook-test/…`)는 에디터에서 "Listen for test event" 를 누른 동안만 동작합니다.

### SaveDeal 설정 (`savedeal_seunghoon/.env`)

```ini
N8N_WEBHOOK_URL=https://<내 n8n 주소>/webhook/savedeal-notify
N8N_WEBHOOK_SECRET=<Header Auth 에 넣은 값과 같게>
N8N_SECRET_HEADER=X-SaveDeal-Key
NOTIFY_EMAIL_TO=        # 비우면 Gmail 노드의 To 기본값으로 감
```

### SaveDeal이 보내는 JSON (`$json.body.<이름>`)

| 이름 | 내용 |
|---|---|
| `kind` | `UPLOAD_SUMMARY`(업로드 결과) · `HIGH_RISK`(고위험 경보) · `CUSTOMER_NOTICE`(가상 고객 안내) · `DAILY_REPORT`(운영 리포트) |
| `subject`, `text` | 메일 제목·본문 (SaveDeal이 만든 문구, 고객 이름은 마스킹) |
| `to` | `NOTIFY_EMAIL_TO` 값 (없으면 null) |
| `notification_id`, `idempotency_key` | 알림 번호 · 중복 발송 방지용 키 |
| `reservation_id` | 관련 예약번호 (없을 수 있음) |

### 언제 메일이 가나

| 알림 | 언제 |
|---|---|
| 업로드 결과 | 예약 업로드에서 "등록하기"를 누른 직후 |
| 고위험 경보 | 업로드·신규 등록으로 고위험 예약이 새로 생겼을 때 |
| 가상 고객 안내 | 고객 안내가 필요한 해결책(서류 요청, 수령일 변경, 색상 변경 등)을 승인했을 때. 실제 고객이 아니라 담당자 메일로 받습니다. |
| 운영 리포트 | 대시보드 "리포트 메일 보내기" 버튼 |

실패하면 상세 패널 "알림 기록"에 사유와 **다시 보내기** 버튼이 나옵니다.

### (선택) 매일 아침 리포트 자동 발송

n8n 스케줄이 SaveDeal을 불러야 해서 **ngrok 같은 공개 주소가 필요**합니다.
`Schedule Trigger (평일 09:00) → HTTP Request (POST https://<공개 주소>/api/notifications/daily-report)`

---

## 2. OpenAI (ChatGPT API)

ChatGPT 구독(Plus 등)과 **API는 결제가 따로**입니다.

1. https://platform.openai.com 에 로그인 → **API keys** → 새 키 만들기
2. **Billing** 에서 크레딧 충전 · **Usage limits** 에서 월 한도를 작게 설정 (시연용이면 소액으로 충분)
3. `savedeal_seunghoon/.env` 에 입력 (git에 올라가지 않습니다)

```ini
OPENAI_API_KEY=sk-...
OPENAI_MODEL=gpt-4o-mini   # 내 계정에서 쓸 수 있는 모델 이름으로
OPENAI_TIMEOUT=20
```

4. 서버를 다시 켜면 대시보드 상단이 `AI <모델명>` 으로 바뀝니다.

### AI가 쓰이는 곳 (판정은 그대로 Python 규칙)

| 기능 | 화면에서 확인 |
|---|---|
| 메모 해석 | 업로드한 예약의 상세 패널 "고객 메모" → `메모 해석 · AI 생성 · 모델 · 0.8초`. 대체 가능 색상·선호 연락 방법이 해결책 순서에 반영되고 "고객 메모 반영" 표시 |
| 고객 안내문 | 해결책 승인 → 알림 기록의 메일 본문 끝 `(AI 작성 · 모델 · 초)` |
| 직원 브리핑 | 상세 패널 "AI 브리핑 → 브리핑 생성" |

- AI 호출 기록은 DB `ai_logs` 테이블과 `GET /api/integrations` 에 남습니다 (기능, 모델, 성공 여부, 응답 시간).
- AI가 실패하면(키 오류, 크레딧 부족 등) 자동으로 규칙 기반 결과로 바꾸고, 실패 사유를 화면에 표시합니다.
- AI에는 마스킹된 이름만 보내고, 메모에 전화번호가 있으면 가려서 보냅니다.

---

## 시연 순서 (예시)

1. 대시보드 → **데모 데이터 초기화**
2. **예약 업로드** → `samples/사전예약_명단_예시.xlsx` 업로드 → 검증 결과(정상 6 · 오류 2: 실제 번호, 없는 매장·단말) 확인 → **등록하기**
3. 메일함: **업로드 결과**, **고위험 경보** 메일 도착
4. 예약 운영 → R3002(박서윤) 상세 → 고객 메모 해석 결과 확인 → "누락서류 요청 · 고객 메모 반영" **승인**
5. 메일함: **가상 고객 안내** 메일 도착 (AI 키가 있으면 AI가 쓴 문구)
6. **AI 브리핑 → 브리핑 생성**, 상단 **리포트 메일 보내기**

예시 파일의 희망 수령일은 파일을 만든 날 기준입니다. 날짜가 지났으면 엑셀에서 고쳐서 쓰세요.
