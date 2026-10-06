# 외부 이벤트 연동: 개통 반려·입고 지연·서류 도착을 SaveDeal에 자동 반영

SaveDeal은 예약을 등록할 때의 데이터로 문제를 판정합니다. 등록 **이후** 바깥에서 생긴 일(개통 전산의 반려, 물류의 입고 지연, 고객의 서류 제출 등)은 **외부 이벤트**로 받아 반영합니다.
실제 전산이 없으므로 시연에서는 **구글시트를 가짜 전산**으로 씁니다. 시트에 한 줄 적으면 n8n이 SaveDeal에 전달합니다.

```
[구글시트 = 가짜 개통 전산·물류]  ──n8n──▶  SaveDeal  ──▶  문제 추가/해결 → 해결책 재생성 → 화면 자동 갱신 → 메일
```

이벤트를 받으면 SaveDeal이 하는 일:

| 이벤트 종류 | SaveDeal이 하는 일 |
|---|---|
| 문제 발생 (개통 반려, 입고 지연 …) | 문제를 추가하고 해결책을 만든다. 같은 문제로 **이미 승인해 진행 중인 해결책이 있으면 실패 처리하고 다른 대안을 다시 만든다** (재시도 횟수 +1) |
| 문제 해소 (서류 제출, 재고 도착 …) | 문제를 해결 처리한다. 진행 중이던 해결책은 성공, 남은 제안은 보류 |
| 개통 완료 / 예약 취소 | 예약을 종료한다 |

반영한 결과는 **"외부 이벤트 반영" 메일 한 통**으로 담당자에게 갑니다 (기존 n8n → Gmail 워크플로를 그대로 씀).
**같은 줄을 여러 번 보내도 한 번만 반영**하므로, n8n이 시트 전체를 몇 분마다 통째로 보내도 됩니다.

---

## 1. 구글시트 만들기

`samples/외부이벤트_시트_예시.csv`를 구글시트로 가져오거나(파일 → 가져오기), 아래 머리글로 새 시트를 만듭니다.

| 발생시각 | 예약번호 | 이벤트 | 사유 | 서류 | 예정일 | 반려 항목 |
|---|---|---|---|---|---|---|
| 2026-10-06 10:00 | R2003 | 개통 반려 | 주소 불일치 | | | 주소 |
| 2026-10-06 10:10 | R2011 | 입고 지연 | 물류센터 출고 지연 | | 2026-10-09 | |
| 2026-10-06 10:20 | R2013 | 서류 제출 | | | | |

- **필수**: 예약번호, 이벤트. 나머지는 선택입니다.
- **발생시각은 꼭 적어 주세요.** 같은 내용을 나중에 다시 보내야 할 때 발생시각이 다르면 새 이벤트로 받습니다.
- 서류는 쉼표로 여러 개 (`신분증, 가족관계증명서`), 예정일은 `YYYY-MM-DD`.
- 영어 이름(`reservation_id`, `type`, `reason`, `occurred_at`, `documents`, `date`, `field`, `event_id`)도 받습니다.

### 이벤트 이름 (띄어쓰기 무시, 아래 중 아무거나)

| 구분 | 이벤트 | 이렇게 적어도 됨 | 반영되는 문제 |
|---|---|---|---|
| 문제 발생 | 개통 반려 | 개통 거절 | 개통 반려 (사유·반려 항목 표시) |
| | 재고 확보 지연 | 입고 지연, 재고 이동 지연, 배송 지연, 입고 취소, 재고 부족 | 재고 미확보 (예정일이 있으면 수령일 변경안) |
| | 서류 보완 요청 | 서류 보완, 서류 미제출, 서류 반려 | 서류 미제출 |
| | 본인인증 실패 | 인증 실패 | 본인인증 실패 |
| | 고객 미응답 | 미응답, 연락 두절 | 고객 미응답 |
| | 요금 미납 | 미납 | 요금 미납 |
| 문제 해소 | 개통 재접수 승인 | 재접수 승인, 재접수 완료, 반려 해소 | 개통 반려 해결 |
| | 재고 도착 | 입고 완료, 재고 확보, 배송 완료, 재고 이동 완료 | 재고 미확보 해결 |
| | 서류 제출 완료 | 서류 제출, 서류 도착, 서류 완료 | 서류 미제출 해결 |
| | 본인인증 완료 | 본인인증 성공, 인증 완료 | 본인인증 실패 해결 |
| | 고객 응답 | 고객 회신, 연락 완료 | 고객 미응답 해결 |
| | 미납 납부 확인 | 납부 완료, 미납 해소 | 요금 미납 해결 |
| 종료 | 개통 완료 | 개통 성공 | 예약 종료 (개통 완료) |
| | 예약 취소 | 고객 취소, 취소 | 예약 종료 (취소) |

---

## 2. 연결 방법 고르기

n8n은 클라우드에 있어서 **내 컴퓨터의 `localhost`로는 들어올 수 없습니다.** 그래서 두 가지 방법을 준비했습니다.

| | A. n8n이 보내기 (정석) | B. SaveDeal이 가져오기 |
|---|---|---|
| 방향 | n8n → SaveDeal `POST /api/events` | SaveDeal → n8n Webhook (목록 받기) |
| 필요한 것 | SaveDeal **공개 주소** (이승현님 서버의 `https://savedeal.ngrok.dev`) | 없음 (내 PC에서 바로 됨) |
| 언제 반영 | n8n 스케줄 간격 (예: 1분마다) | **SaveDeal 서버가 켜져 있는 동안** `EVENT_SYNC_SECONDS`(기본 60초)마다. 브라우저를 닫아도 됨 |
| 정기 점검 | n8n 스케줄이 `POST /api/monitor/scan` 호출 | 가져올 때마다 같이 점검 |
| 추천 | n8n에서 직접 스케줄을 관리하고 싶을 때 | **대부분 이걸로 충분** (내 PC·서버 모두) |

두 방법을 같이 켜도 됩니다 (같은 이벤트는 한 번만 반영).

---

## 3-A. n8n이 보내기 (서버 · 공개 주소)

**SaveDeal 서버 `.env`**: `N8N_WEBHOOK_SECRET`이 꼭 있어야 합니다. 비어 있으면 외부(ngrok)에서 온 요청은 거절합니다(403).

**n8n 새 워크플로 "SaveDeal 외부 이벤트 보내기"** (노드 4개)

1. **Schedule Trigger**: Every 1 Minutes (시연용. 실제라면 5~10분)
2. **Google Sheets** → *Get Row(s) in sheet*: 위 시트 선택 (구글 계정 연결)
3. **Code** (Run Once for All Items):
   ```js
   return [{ json: { events: $input.all().map(item => item.json) } }];
   ```
4. **HTTP Request**
   - Method `POST`, URL `https://savedeal.ngrok.dev/api/events`
   - Authentication: *Generic Credential Type* → *Header Auth* → 이름 `X-SaveDeal-Key`, 값 = `N8N_WEBHOOK_SECRET` (알림 Webhook에 쓴 그 Credential을 그대로 골라도 됨)
   - Send Body: JSON, *Using JSON* → `{{ $json }}`

저장 후 **Publish(Active)**.

**정기 점검 워크플로 "SaveDeal 정기 점검"** (노드 2개): Schedule Trigger (Every 1 Hours) → HTTP Request `POST https://savedeal.ngrok.dev/api/monitor/scan` (같은 Header Auth, Body 없음).

## 3-B. SaveDeal이 가져오기 (내 PC)

**n8n 새 워크플로 "SaveDeal 외부 이벤트 목록"** (노드 3개)

1. **Webhook**
   - HTTP Method `POST`, Path `savedeal-events`
   - Authentication: *Header Auth* (알림 Webhook과 같은 Credential)
   - Respond: *Using 'Respond to Webhook' Node*
2. **Google Sheets** → *Get Row(s) in sheet*: 위 시트
3. **Respond to Webhook** → Respond With: *All Incoming Items*

저장 후 **Publish(Active)** 하고, Webhook 노드의 **Production URL**(`…/webhook/savedeal-events`)을 복사합니다.

**SaveDeal `.env`**
```
N8N_EVENTS_URL=https://<내 n8n 주소>/webhook/savedeal-events
EVENT_SYNC_SECONDS=60
```
SaveDeal을 다시 켜면 서버가 **스스로 60초마다** n8n에서 이벤트를 가져와 반영하고, 새로 고위험이 된 예약도 점검합니다.
대시보드 상단 칩이 **"외부 이벤트 자동 확인 · 60초"**로 바뀌고, 칩에 마우스를 올리면 마지막 확인 시각이 보입니다. n8n 주소나 비밀값이 틀리면 칩이 **"외부 이벤트 연결 확인 필요"**로 바뀝니다.

- 대시보드를 열어 두지 않아도 됩니다. SaveDeal 서버(start_all 창)만 켜져 있으면 됩니다.
- 대시보드를 열어 두면 이벤트가 반영될 때 15초 안에 화면이 자동으로 다시 그려집니다.
- `N8N_EVENTS_URL`이 없고 `N8N_WEBHOOK_URL`만 있으면, 가져오기 없이 정기 점검(새 고위험 알림)만 주기적으로 합니다.
- 간격은 최소 15초입니다. `EVENT_SYNC_SECONDS=0`이면 자동 확인을 끕니다 (대시보드가 열려 있을 때 화면이 대신 가져옴).

---

## 4. 확인 · 시연 순서

1. 대시보드(`/savedeal`)를 열어 둡니다. 상단에 "외부 이벤트 받는 중/가져오는 중" 칩이 보입니다.
2. 구글시트에 한 줄 추가: `2026-10-06 14:00 | R2003 | 개통 반려 | 주소 불일치 | | | 주소`
3. 1분쯤 기다리면
   - 화면 아래에 "외부 이벤트 반영: R2003 개통 반려" 알림이 뜨고 목록이 자동으로 바뀝니다.
   - R2003 상세: 문제에 **개통 반려**, 해결책에 **주소 수정 후 재접수**, 처리이력에 **외부 이벤트**가 생깁니다.
   - Gmail로 **"[SaveDeal] 외부 이벤트 1건 반영"** 메일이 옵니다.
4. 해결책을 승인한 뒤 시트에 같은 예약으로 `개통 반려`(발생시각 다르게)를 한 번 더 적으면 → 진행 중이던 안이 **실패** 처리되고 **새 대안**이 나옵니다 (재시도 +1).
5. `개통 재접수 승인`을 적으면 → 문제가 해결되고 "개통 대기"가 됩니다. `개통 완료`를 적으면 예약이 종료됩니다.

### n8n 없이 내 PC에서 바로 시험하기 (PowerShell)

`N8N_WEBHOOK_SECRET`이 **비어 있으면** 이 컴퓨터에서 보낸 요청은 그대로 받습니다.
```powershell
$body = '{"events":[{"예약번호":"R2003","이벤트":"개통 반려","사유":"주소 불일치","발생시각":"2026-10-06 14:00"}]}'
Invoke-RestMethod -Method Post -Uri http://localhost:5001/api/events -ContentType "application/json; charset=utf-8" -Body ([Text.Encoding]::UTF8.GetBytes($body))
Invoke-RestMethod -Method Post -Uri http://localhost:5001/api/monitor/scan
```
비밀값을 정해 뒀다면 `-Headers @{ "X-SaveDeal-Key" = "<비밀값>" }`을 붙입니다.

---

## API 정리

```
POST /api/events          이벤트 반영. 한 건 {..}, 목록 [..], {"events": [..]} 모두 가능 (최대 500건)
                          응답: received, counts{APPLIED/SKIPPED/ERROR/DUPLICATE}, results[], notification
POST /api/events/sync     가져오기를 지금 바로 1회 실행 (평소에는 서버가 자동으로 함) + 정기 점검
GET  /api/events          최근 받은 이벤트와 last_id (대시보드 자동 갱신용)
POST /api/monitor/scan    정기 점검: 새로 고위험이 된 예약만 알림 (이미 알린 예약은 다시 안 알림)
```

- 인증: `N8N_WEBHOOK_SECRET`이 있으면 `N8N_SECRET_HEADER`(기본 `X-SaveDeal-Key`) 헤더가 같아야 합니다. 없으면 이 컴퓨터에서 직접 온 요청만 받습니다.
- 결과: **APPLIED** 반영 / **SKIPPED** 반영할 필요 없음(종료된 예약, 이미 해결된 문제) / **ERROR** 예약번호·이벤트 이름 오류 / **DUPLICATE** 이미 받은 이벤트.
- 받은 이벤트는 `inbound_events` 테이블, 고위험 알림 기록은 `risk_alerts` 테이블에 남습니다. "데모 데이터 초기화"를 누르면 둘 다 지워집니다.
