# 통하길 스튜디오 · 통하길 QR (이승현)

이 폴더에는 에이전트가 두 개 있습니다. 둘 다 허브에 Blueprint로 들어가 있어서 따로 켜지 않습니다.
- **통하길 스튜디오** (`tonghagil_studio/`, `/studio/`): 행사 포스터 생성 → 아래 설명
- **통하길 QR** (`tonghagil_qr/`, `/qr/`): QR 현장 안내·스탬프 이벤트 → [맨 아래 "통하길 QR"](#통하길-qr)

행사 홍보 포스터를 채팅으로 요청하면 n8n이 이미지를 만들고, 구글 드라이브 폴더의 포스터를 갤러리로 보여 줍니다.
Command Center 허브(저장소 루트의 `command_center/`)에 **Blueprint로 내장**되어 `/studio/` 아래에서 허브와 같은 프로세스로 돕니다(더 줘와 같은 방식). 따로 서버를 띄우지 않습니다. → http://localhost:5000/studio/

```
tonghagil_studio/
  __init__.py     studio_bp 내보내기 (허브가 register_blueprint)
  routes.py       화면·API (포스터 생성/목록/수정/삭제, 드라이브 이미지 프록시)
  config.py       이 폴더의 .env 읽기 (os.environ 에 풀지 않음 → 허브·다른 에이전트 설정과 안 섞임)
  n8n_client.py   n8n 호출
  drive_store.py  구글 드라이브 폴더 갤러리
  poster_store.py 요청 기록(posters.json) / 샘플 포스터
  templates/tonghagil_studio/studio.html   허브의 cc_layout.html 을 확장
  static/         studio.css, studio.js (공통 디자인은 허브의 common.css/js 사용)
```

## 실행

- 전체를 켤 때: 저장소 루트의 **`start_all.bat`**을 쓰세요.
- 허브만 켤 때(스튜디오 포함): 저장소 루트에서 아래를 실행하거나 `command_center/app.py`에서 VS Code ▶를 누르세요.
  ```powershell
  pip install -r tonghagil_LEESEUNGHYUN/requirements.txt     # 처음 한 번
  copy tonghagil_LEESEUNGHYUN\.env.example tonghagil_LEESEUNGHYUN\.env   # 처음 한 번, 값 채우기
  python -m command_center.app                               # → http://localhost:5000/studio/
  ```

### 주소 규칙 (ngrok 대비)
- 화면과 API는 모두 `/studio/` 아래에 있습니다: `/studio/api/posters`, `/studio/drive-image/<id>`, `/studio/placeholder.svg`, `/studio/static/…`
- `studio.js`는 페이지의 `data-base`(=`url_for('tonghagil_studio.studio')`)로 API 주소를 만듭니다. `/api/…`나 `http://localhost…`를 직접 적지 않습니다.
- `posters.json`에는 `/drive-image/…`, `/placeholder.svg?…`처럼 **접두사 없이** 저장하고, 응답할 때 `/studio/`를 붙입니다(`routes._localized`). 예전 기록도 그대로 보입니다.

## 통하길 스튜디오 ↔ n8n 연결

`.env` 의 `N8N_WEBHOOK_URL` 이 비어 있으면 **데모 모드**(샘플 포스터 생성)로 동작합니다.

워크플로 (n8n Cloud, **Webhook 방식**):

```
Webhook (POST) → Generate an image → Upload file → Respond to Webhook
```

| 노드 | 설정 |
|---|---|
| **Webhook** | HTTP Method `POST` · Path `tonghagil-poster` · Authentication `Header Auth`(Name `X-Tonghagil-Key`, Value = `.env` 의 `N8N_WEBHOOK_SECRET`) · Respond `Using 'Respond to Webhook' Node` |
| **Generate an image** | Prompt: `{{ $json.body.chatInput }}` |
| **Upload file** | Parent Folder: **프로젝트이미지** (갤러리 폴더와 같아야 함) · File Name: `{{ $('Webhook').item.json.body.fileName }}` |
| **Respond to Webhook** | Respond With `JSON` · `{ "fileId": "{{ $('Upload file').item.json.id }}" }` |

- 워크플로를 **Active(Publish)** 로 켜고, Webhook 노드의 **Production URL**(`…/webhook/tonghagil-poster`)을 `.env` 의 `N8N_WEBHOOK_URL` 에 넣습니다.
  Test URL(`/webhook-test/…`)은 에디터에서 "Listen for test event" 를 누른 동안만 동작합니다.
- 공유(Share file) 노드는 필요 없습니다. 스튜디오가 서비스 계정으로 이미지를 가져오므로 비공개 파일도 보입니다.

스튜디오가 보내는 JSON (`$json.body.<이름>`):

| 이름 | 예 |
|---|---|
| `chatInput` | 이미지 프롬프트 = 설명 + `[포스터 스타일] …` + `[행사 유형] …` |
| `fileName` | `축제_10월 한강 불꽃축제_20260929.png` |
| `title`, `eventType`, `style`, `message` | 원본 값 (참고용) |

요청 기록(제목·행사 유형·요청 문구)은 `tonghagil_studio/data/posters.json` 에 쌓이고, 드라이브 파일 ID로 갤러리와 합쳐집니다.

## 갤러리 ↔ 구글 드라이브 폴더 연결 (서비스 계정)

`.env` 의 `DRIVE_FOLDER_ID` 가 비어 있으면 샘플 포스터를 보여 줍니다. 설정하면 **그 폴더의 이미지**를 최신순으로 보여 줍니다.

1. [Google Cloud 콘솔](https://console.cloud.google.com/) → 새 프로젝트 만들기
2. **API 및 서비스 → 라이브러리** → `Google Drive API` 검색 → **사용**
3. **IAM 및 관리자 → 서비스 계정 → 서비스 계정 만들기** (이름만 넣고, 역할은 비워 둔 채 완료)
4. 만든 서비스 계정 → **키 → 키 추가 → 새 키 만들기 → JSON** → 파일이 다운로드됨
5. 그 파일을 `tonghagil_LEESEUNGHYUN/credentials/service-account.json` 으로 저장
   (`credentials/` 는 `.gitignore` 에 있어서 GitHub 에 올라가지 않습니다. **절대 커밋·공유 금지**)
6. 구글 드라이브에서 n8n이 이미지를 올리는 폴더 → **공유** → 서비스 계정 이메일
   (`…@….iam.gserviceaccount.com`, 키 파일의 `client_email`) 을 **편집자**로 추가 ("이메일 알림 보내기" 체크 해제)
   (보기만 할 거면 뷰어도 되지만, 스튜디오에서 정보 수정·삭제를 하려면 편집자여야 합니다)
7. `.env` 에 폴더 ID(또는 폴더 주소 전체) 입력 후 서버 재시작
   ```
   DRIVE_FOLDER_ID=https://drive.google.com/drive/folders/1AbCdEf...
   ```

- 갤러리 제목 옆 배지가 **구글 드라이브** 로 바뀌면 연결된 것입니다. 오류가 나면 갤러리에 원인이 표시됩니다.
- 목록은 60초 동안 캐시합니다(`DRIVE_CACHE_SECONDS`). 갤러리의 **새로고침(↻)** 버튼은 바로 다시 읽습니다.
- 이미지는 Flask 가 서비스 계정으로 받아서 대신 보여 주므로(`/drive-image/<ID>`) 비공개 파일도 보입니다.
  썸네일은 `tonghagil_studio/data/drive_cache/` 에 저장해 두고 재사용합니다.
- 파일 이름을 `행사유형_제목_날짜.png` (예: `축제_한강 불꽃축제_20261003.png`) 로 저장하면 행사 유형과 제목이 자동으로 붙습니다.
  스튜디오에서 요청한 포스터는 요청할 때 입력한 제목·행사 유형이 우선합니다.

### 갤러리에서 수정 · 삭제 (카드의 `⋯` 메뉴)
- **정보 수정**: 제목·행사 유형을 바꾸면 드라이브 파일 이름도 `행사유형_제목_날짜.png` 로 실제로 바뀝니다.
- **삭제**: 파일을 드라이브 폴더 안 **`_보관함`** 하위 폴더로 옮깁니다(처음 삭제할 때 자동 생성).
  파일 소유자가 아니면 휴지통으로 보낼 수 없어서(구글 드라이브 규칙) 이렇게 처리합니다.
  되돌리려면 드라이브에서 `_보관함` 의 파일을 원래 폴더로 옮기면 되고, 완전히 지우려면 드라이브에서 직접 삭제하세요.
- 수정·삭제 메뉴는 드라이브 포스터에만 보입니다(샘플·데모 포스터 제외).

---

## 통하길 QR

방문객이 QR을 찍어 **행사 안내 · KT 부스 위치 · 구역별 통신 상태 · 스탬프 이벤트 · 안내 챗봇**을 이용합니다.
허브에 Blueprint로 내장되어 `/qr/` 아래에서 돕니다. 로그인 없이 휴대폰 브라우저 쿠키로 방문객을 구분합니다(개인정보 저장 없음).

| 화면 | 주소 | 누가 |
|---|---|---|
| 행사 안내 홈 | `/qr/` (포스터 QR은 `/qr/?src=poster`) | 방문객 |
| 지도 · 통신 상태 | `/qr/map` (KT 부스 위치, 구역별 모의 통신 상태 30초마다 갱신) | 방문객 |
| 스탬프 | `/qr/stamps` (5곳 다 모으면 쿠폰 자동 발급) | 방문객 |
| 스탬프 찍기 | `/qr/s/<token>` (스탬프 지점 QR이 가리키는 주소) | 방문객 |
| 안내 챗봇 | `/qr/chat` (지금은 고정 답변 "테스트 단계입니다") | 방문객 |
| 부스 담당자 | `/qr/staff/` (PIN 잠금: 현황, 쿠폰 지급, QR 인쇄, 시연 기록 초기화) | 부스 담당자 · 허브 카드 |

```
tonghagil_qr/
  routes.py       화면·API (방문객 쿠키, 스탬프, 쿠폰, 담당자 PIN)
  event.py        data/event.json 읽기 (파일을 고치면 재시작 없이 반영)
  network.py      구역별 통신 상태 모의 데이터 (30초마다 바뀜)
  store.py        SQLite 기록 data/qr.db (방문객·스탬프·쿠폰·조회) — git 제외
  chat_client.py  안내 챗봇 (n8n 연결 전 고정 답변)
  qr_image.py     QR 이미지(SVG) 생성 (segno)
  data/event.json 행사 정보: 행사명·일시·부스·혜택·구역(약도 좌표)·스탬프 5곳(토큰)
```

### 시연 흐름
1. 허브 카드 **통하길 QR** → 담당자 PIN(기본 `1234`) → **인쇄용 페이지**에서 입장 QR 1장 + 스탬프 QR 5장을 인쇄
2. 방문객이 포스터의 입장 QR → 행사 안내 홈
3. 스탬프 지점 QR 5곳을 찍으면 스탬프 화면에 쿠폰 코드(6자리)가 뜸
4. 부스 담당자가 담당자 화면에 코드를 입력하고 **지급 처리** → 방문객 화면이 5초 안에 "지급 완료"로 바뀜
5. 리허설이 끝나면 담당자 화면 맨 아래 **기록 모두 지우기**

- **휴대폰으로 QR을 찍으려면 공개 주소가 필요합니다.** `localhost`는 휴대폰에서 안 열립니다. ngrok을 연결한 뒤 `.env`에 `QR_PUBLIC_BASE_URL=https://<도메인>`을 넣고 QR을 다시 인쇄하세요. 담당자 화면이 localhost 주소일 때 경고를 띄웁니다.
- 스탬프 토큰은 `event.json`에 있습니다. 토큰을 바꾸면 이미 인쇄한 스탬프 QR은 쓸 수 없게 됩니다.

### 행사 내용 바꾸기
`tonghagil_qr/data/event.json`만 고치면 됩니다(서버 재시작 불필요). 지금은 시연용 가상 행사 **2026 판교 테크노밸리 페스티벌**(KT판교빌딩 일대)입니다.
약도 좌표는 `viewBox 0 0 360 400` 기준입니다(`zones`의 x·y·w·h, `booth`·`stamps`의 x·y).

### 카카오맵 연결 (지도 화면)
`.env`의 `QR_KAKAO_MAP_KEY`가 비어 있으면 지도 화면이 **그림 약도**로 나옵니다. 키를 넣으면 실제 카카오맵 위에 구역(통신 상태 색), KT 부스, 스탬프 QR 위치를 그립니다.
- 마커를 누르면 안내 팝업이 뜹니다. 스탬프 팝업에는 QR이 붙은 곳이 나옵니다.
- **행사장 전체**, **KT 부스**, **내 위치** 버튼이 있습니다. 내 위치를 누르면 가장 가까운 남은 스탬프를 알려 줍니다(https 또는 localhost에서만 동작).
- 아래 목록의 스탬프나 구역을 누르면 지도가 그곳으로 이동합니다.
- 카카오맵이 8초 안에 안 뜨면(키 오류, 도메인 미등록, 통신 불량) 자동으로 그림 약도로 바뀝니다.

키 발급 (카드 등록 불필요):
1. [Kakao Developers](https://developers.kakao.com/) 로그인 → **내 애플리케이션 → 애플리케이션 추가하기**
2. **앱 설정 → 앱 키**에서 **JavaScript 키** 복사
3. **앱 설정 → 플랫폼 → Web → 사이트 도메인**에 `http://localhost:5000` 등록. ngrok을 쓰면 `https://<도메인>.ngrok-free.app`도 추가합니다.
4. **제품 설정 → 카카오맵 → 활성화 설정 ON** (이걸 안 켜면 지도가 안 뜹니다)
5. `.env`에 `QR_KAKAO_MAP_KEY=<JavaScript 키>`를 넣고 허브를 다시 켭니다.

- 무료 쿼터는 계정에서 **처음 카카오맵을 활성화한 앱 하나**에만 있습니다. 비즈월렛을 연결하지 않으면 쿼터를 넘어도 요금이 나가지 않습니다(호출만 막힘).
- JavaScript 키는 브라우저에 보이는 공개용 키입니다. 3번에 등록한 도메인에서만 동작합니다.
- 위경도는 `event.json`의 `map.center`, `booth.geo`, `stamps[].geo`, `zones[].circle`(`center` + `radius` m, 지도에 원으로 그림)입니다. 하나라도 빠지면 그림 약도를 씁니다.
- **KT 홍보부스는 KT판교빌딩의 실제 좌표**(37.40656, 127.09082, OpenStreetMap 건물 중심)입니다. 스탬프 5곳은 주변에 적당히 배치한 값이라 현장에 맞게 자유롭게 옮기면 됩니다.

### 안내 챗봇 ↔ n8n 연결 (나중에)
`.env`의 `QR_CHAT_WEBHOOK_URL`이 비어 있으면 고정 답변 **"테스트 단계입니다"**를 돌려줍니다. 주소를 넣으면 화면 코드는 그대로 두고 n8n이 답합니다.

```
Webhook (POST, Header Auth X-Tonghagil-Key) → AI Agent (또는 규칙) → Respond to Webhook  { "reply": "…" }
```

통하길 QR이 보내는 JSON (`$json.body.<이름>`):

| 이름 | 내용 |
|---|---|
| `chatInput` | 방문객 질문 |
| `sessionId` | 방문객 ID (대화 기억 Memory 노드의 키로 쓰면 됨) |
| `eventId` | 행사 ID |
| `context` | 행사 요약: 행사명·일시·장소·안내·부스·혜택·구역·스탬프 지점 (답변 근거로 넣으면 잘못된 안내가 줄어듦) |
| `network` | 지금 구역별 통신 상태(모의)·가장 원활한 곳·부스 대기 인원 |
| `stamps` | 이 방문객이 찍은 스탬프 이름 목록 |

- 응답은 `{"reply": "…"}`를 권장합니다. `output`(n8n AI Agent 기본), `text`, `message`, `answer`나 글자만 온 응답도 받습니다.
- 스탬프 토큰은 n8n에 보내지 않습니다.
