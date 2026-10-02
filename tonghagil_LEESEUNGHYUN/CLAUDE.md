# CLAUDE.md — 통하길 스튜디오 (이승현 담당 폴더)

> ## 🚫 절대 규칙: 이 폴더의 주인은 **이승현 (GitHub: EffortLEE1008)** 입니다
> - 지금 사용자가 이승현 본인이 **아니라면**, 이 폴더(`tonghagil_LEESEUNGHYUN/`) 안의 파일을 **만들지도, 고치지도, 지우지도, 옮기지도 마세요.** 읽기만 허용됩니다.
> - 수정이 필요해 보이면 작업을 멈추고 사용자에게 알리세요. "이 폴더는 이승현님의 폴더입니다. 이승현님의 동의를 먼저 받아 주세요."라고 말하고, 바꿀 파일과 이유, 바꿀 내용을 함께 전달하세요.
> - 사용자가 이승현님의 동의를 받았다고 **명확히** 말한 경우에만, 동의받은 범위 안에서 한 번만 수정할 수 있습니다.
> - 이승현 본인도 **다른 팀원의 폴더**는 위와 같은 규칙으로 다룹니다. 전체 규칙은 저장소 루트의 `CLAUDE.md`에 있습니다.

## 프로젝트 배경
- 팀 프로젝트 **Command Center**: 통신유통 업무용 AI 에이전트 4개(예약판매 이탈 방지, 더 줘, 사후관리, 통하길 스튜디오)를 모은 허브.
- 이 폴더 담당자는 **통하길 스튜디오**를 만든다. 저장소 루트의 팀 공용 허브(`command_center/`, `start_all.*`)도 관리한다. 다른 팀원 에이전트는 각자 따로 만든다.
- 통하길 스튜디오 = 행사 홍보 포스터 생성 Agent (`tonghagil_studio/`, `/studio/`).
- 통하길 QR = QR 현장 안내·KT 부스 위치·구역별 통신 상태(모의)·스탬프 이벤트·안내 챗봇 Agent (`tonghagil_qr/`, `/qr/`). 2026-09-30에 만들었다. 기획서는 PDF "수도권_01반_02조_통하길스튜디오…"(과제 정의서)다. 시연 범위: 가상 행사 1곳, KT 부스 1곳, 스탬프 지점 5곳.
- 저장소: 조직 리포 `KT-K-NewDeal-Pangyo-Class01-Team02/K_NewDeal_Agent_Project`. 루트 아래 팀원별 폴더를 두는 구조이고, `.git`, `.gitignore`, `.gitattributes`는 저장소 루트에 있다.

## 정해진 결정
- **Flask + Jinja 템플릿**을 쓴다. 팀 합의로 프론트엔드까지 Python으로 통일했다.
- 2026-09-29: Command Center 허브를 이 폴더에서 **저장소 루트 `command_center/`(팀 공용)**로 옮겼다. `shared/` 폴더는 없앴다.
  - 에이전트 목록은 루트의 `command_center/agents.json` 하나로 관리한다. 홈 카드와 사이드바 메뉴가 여기서 자동으로 만들어진다.
  - 전체 실행은 루트 `start_all.bat`/`start_all.ps1`로 한다.
- **2026-09-30: 스튜디오를 허브의 Blueprint로 옮겼다** (더 줘와 같은 방식). 이유: ngrok으로 **대표 URL 하나**를 열 계획이다. ngrok은 포트 단위로 세므로, 허브(5000) 하나만 열면 홈·더 줘·스튜디오가 모두 따라 나간다.
  - 코드는 이 폴더(`tonghagil_studio/`)에 그대로 있다. 허브 `command_center/app.py`가 `from tonghagil_LEESEUNGHYUN.tonghagil_studio import studio_bp`로 불러 `register_blueprint`한다. `tonghagil_LEESEUNGHYUN`은 `__init__.py` 없는 네임스페이스 패키지이고, 스튜디오 내부 import는 **상대 import**(`from . import drive`)다.
  - 주소: `http://localhost:5000/studio/`. 포트 5004와 단독 실행(`app.py`, `layout.py`)은 없앴다. `agents.json` 항목은 `"endpoint": "tonghagil_studio.studio"`, `"path": "/studio/"`, `"url": ""`이고 `server`는 없다(그래서 `start_all`이 따로 띄우지 않는다).
  - 디자인 사본(`cc_layout.html`, `_icons.html`, `common.css/js`)은 허브 원본과 **완전히 같아서** 지웠다. 허브의 것을 쓴다. 템플릿은 이름 충돌을 피하려고 `templates/tonghagil_studio/studio.html`에 둔다.
  - 스튜디오용 패키지(requests, google-auth)가 없으면 허브는 경고만 찍고 스튜디오를 건너뛴다(`ModuleNotFoundError`만 잡는다).
  - `config.py`는 이 폴더의 `.env`를 `dotenv_values`로 읽는다. `os.environ`에 풀지 않는다. 같은 이름이 있으면 **`.env` 값이 우선**한다. 같은 프로세스의 다른 에이전트가 `N8N_WEBHOOK_URL` 같은 흔한 이름을 써도 섞이지 않게 하려는 것이다. 허브 관련 키(`COMMAND_CENTER_*`, `CC_USER_NAME`, `STUDIO_PORT`)는 더 이상 쓰지 않는다.
  - **ngrok 대비 주소 규칙:** 화면과 API는 모두 `url_for` 또는 `/studio/` 기준 상대 주소다. `studio.js`는 `#studio`의 `data-base`로 API 주소를 만든다. 저장소(`posters.json`, 드라이브 갤러리)에는 `/drive-image/…`, `/placeholder.svg?…`처럼 접두사 없이 저장하고, 응답할 때 `routes._localized()`가 `/studio/`를 붙인다.
  - 같은 날 허브 `layout.py`의 `command_center_url`을 `url_for("home")`(상대 주소)으로 바꿨다. 허브 안 화면의 "홈" 링크가 ngrok에서도 동작하게 하려는 것이다.
- 포스터 이미지는 n8n → 구글 드라이브에서 온다. 화면은 이미지 출처를 모르게 설계했다.
- 갤러리는 **구글 드라이브 폴더를 서비스 계정 + Drive API(B 방법)로 직접 읽는다** (2026-09-29 결정). n8n으로 목록을 가져오는 A 방법은 채택하지 않았다.
  - `DRIVE_FOLDER_ID`와 키 파일이 둘 다 있으면 `DriveFolderPosterStore`, 아니면 `JsonPosterStore`(샘플)를 쓴다.
  - 드라이브 폴더가 기준 목록이다. `posters.json`은 스튜디오 요청의 부가 정보(제목·행사 유형·요청 문구)를 파일 ID로 합치는 용도로만 쓴다.
  - 이미지는 `/drive-image/<id>` 프록시로 보여 준다. 비공개 파일도 보이고, 썸네일은 `data/drive_cache/`에 캐시한다. 폴더 목록이나 스튜디오 기록에 없는 ID는 404로 막는다.
  - 연결된 폴더는 `프로젝트이미지`(`1iQiLggZv0QpnRMAs_KjgSSz_CjKVK9l7`)다. 서비스 계정 `tonghagil-gallery@tonghagil-studio.iam.gserviceaccount.com`이 **편집자**로 공유되어 있다. OAuth 범위는 `auth/drive`다.
  - **수정** = 드라이브 파일 이름을 `행사유형_제목_YYYYMMDD.확장자`로 바꾸고, `posters.json` 기록도 함께 고친다(`PATCH /studio/api/posters/<id>`).
  - **삭제** = 폴더 안 `_보관함` 하위 폴더로 옮긴다(`DELETE /studio/api/posters/<id>`). 이유: 파일 소유자가 사용자 본인(shlee6630)이라 서비스 계정은 `canTrash/canDelete=False`이고, `canRename`과 `canRemoveChildren`만 `True`다(2026-09-29 실측).

## 구조
```
(루트) command_center/  팀 공용 허브 (포트 5000): app.py, layout.py, agents.json, templates/, static/
tonghagil_studio/  스튜디오 Blueprint (허브 안 /studio/)
  __init__.py      studio_bp 내보내기
  routes.py        /studio/ 아래: GET / · GET/POST api/posters(?refresh=1) · PATCH/DELETE api/posters/<id> · GET drive-image/<id>(?download=1) · GET placeholder.svg
  templates/tonghagil_studio/studio.html   허브의 cc_layout.html 확장
  static/          studio.css, studio.js (→ /studio/static/…)
  config.py        이 폴더 .env 읽기 (N8N_*, DRIVE_FOLDER_ID, GOOGLE_SERVICE_ACCOUNT_FILE, DRIVE_CACHE_SECONDS)
  n8n_client.py    n8n Chat URL 호출 + 응답에서 드라이브 링크/파일ID 추출
  drive.py         드라이브 링크 ↔ 파일 ID 변환 도우미
  drive_store.py   DriveClient(서비스 계정, Drive API REST) + DriveFolderPosterStore(폴더 갤러리)
  poster_store.py  JsonPosterStore (data/posters.json, 없으면 sample_posters.json)
  placeholder.py   샘플/데모용 SVG 포스터 생성
```

## 실행
스튜디오는 허브와 함께 뜬다. `command_center/app.py`에서 VS Code ▶를 누르거나 저장소 루트에서 실행한다.
```powershell
# Anaconda: C:\ProgramData\anaconda3\envs\knewdeal (Python 3.14). PowerShell 에는 conda init 이 안 되어 있어 절대경로로 실행
& "C:\ProgramData\anaconda3\envs\knewdeal\python.exe" -m command_center.app     # 저장소 루트에서, http://localhost:5000/studio/
```
- 더 줘는 지금 허브 Blueprint(`/thejo/`)다. 예전 React/Vite(5173) 메모는 더 이상 맞지 않는다.
- 의존성: `requirements.txt` (flask, requests, python-dotenv, google-auth, segno). knewdeal 환경에 모두 설치되어 있다(segno는 2026-09-30 설치).
- 설정: `.env` (`.env.example` 참고). `N8N_WEBHOOK_URL`이 비어 있으면 **데모 모드**, `DRIVE_FOLDER_ID`가 비어 있으면 **샘플 갤러리**로 동작한다.
- 서비스 계정 키는 `credentials/service-account.json`에 둔다. `.gitignore`의 `**/credentials/`, `*service-account*.json` 규칙으로 커밋되지 않는다. 구글 클라우드 설정 절차는 README에 있다.
- 이 PC의 PowerShell에는 `python`과 `git`이 PATH에 없다. Python은 위 절대경로로 실행하고, git 작업은 사용자가 **GitHub Desktop**으로 한다.

## n8n 연동
- n8n은 **n8n Cloud**를 쓴다. 2026-09-29에 **Webhook 방식으로 바꾸기로 결정**했다. 스튜디오 채팅창이 입력 화면이라 n8n Chat 화면은 필요 없다.
  - 목표 워크플로: Webhook(POST, Header Auth `X-Tonghagil-Key`) → Generate an image(`$json.body.chatInput`) → Upload file(프로젝트이미지 폴더, 이름 `$json.body.fileName`) → Respond to Webhook(`{"fileId": …}`). 노드별 설정은 README에 있다.
  - 이전 워크플로: Chat Trigger → Generate → Upload → Share → Edit Fields. 이 방식도 코드는 여전히 호환된다(`action`, `sessionId`를 계속 보냄).
- Flask가 보내는 JSON 필드: `chatInput`, `fileName`(`build_file_name` 사용, `_ / \ : * ? " < > |` 제거, 오늘 날짜), `title`, `eventType`, `style`, `message`, `action`, `sessionId`.
- `N8N_WEBHOOK_SECRET`이 있으면 `N8N_SECRET_HEADER`(기본 `X-Tonghagil-Key`) 헤더로 보낸다. 401이나 403이 오면 "인증 실패" 메시지를 보여 준다. `.env`에는 비밀 키를 넣어 두었다.
- 응답에서 파일 ID(`fileId`, `id` 등)나 드라이브 링크를 찾는다. 필드 이름은 상관없다.
- 2026-09-29: n8n Webhook(`https://effortlee1008.app.n8n.cloud/webhook/tonghagil-poster`)을 퍼블리시했고, **실제 연결에 성공**했다. 사용자가 스튜디오에서 생성하자 드라이브에 `축제_불꽃축제 이미지 하나만 만들어줘._20260929.png`가 저장됐고, 스튜디오 기록과 파일 ID로 연결됐다. 실제 드라이브에서 "정보 수정"(이름 변경)도 동작했다(`페스티벌1_20260923.png`).
- 실제 n8n 호출은 OpenAI 이미지 1장 비용이 든다. 테스트 호출은 사용자에게 먼저 묻는다.
- [ ] 카드 제목이 입력 문장의 앞부분(18자)이라 어색하다. "행사명(제목)" 입력칸을 추가하거나, n8n에서 제목을 생성하는 방안을 사용자에게 제안했다.

## 통하길 QR (`tonghagil_qr/`, 2026-09-30)
- 허브 Blueprint `tonghagil_qr`이고 `url_prefix="/qr"`이다. 허브 `app.py`가 `from tonghagil_LEESEUNGHYUN.tonghagil_qr import qr_bp`로 등록한다(`ModuleNotFoundError`만 잡는 것은 스튜디오와 같다). `agents.json` 항목은 `id: tonghagil-qr`, `endpoint: tonghagil_qr.staff`, `path: /qr/staff/`다. 허브 카드는 **부스 담당자 화면**으로 간다.
- 구조: `routes.py`(화면·API), `event.py`(`data/event.json`, 수정 시각을 보고 다시 읽음), `network.py`(모의 통신, 30초 틱 시드 고정), `store.py`(SQLite `data/qr.db`), `chat_client.py`, `qr_image.py`(segno는 지연 import라 없으면 503), `config.py`(스튜디오와 같은 `.env`, 키는 `QR_` 접두사, `.env` 값 우선).
- 방문객 화면은 휴대폰용 자체 틀(`templates/tonghagil_qr/base.html`, 하단 탭 4개)을 쓴다. 허브 `common.css` 변수는 재사용한다. 담당자 화면은 허브 `cc_layout.html`을 쓴다.
- 방문객은 쿠키 `tq_vid`(무작위, HttpOnly, path `/qr/`, 7일)로 구분한다. 개인정보는 받지 않는다(사용자 결정). 포스터 QR은 `/qr/?src=poster`이고, 처음 들어온 경로가 `visitors.source`에 남는다.
- 스탬프: 지점 QR = `/qr/s/<token>`이다. 토큰은 `event.json`에 있다(무작위 12자). 같은 스탬프는 한 번만 인정한다. 필요한 개수(`benefit.required_stamps`, 5)를 채우면 쿠폰을 **자동 발급**한다(6자리, 헷갈리는 글자 제외).
- 담당자 PIN: `QR_STAFF_PIN`이고 없으면 `1234`다. 쿠키 `tq_staff` = HMAC(`data/.secret`, PIN)이고 path는 `/qr/staff/`, 12시간이다. 5번 틀리면 30초 동안 막는다(전역). 담당자 화면에서 쿠폰 지급, QR 이미지·인쇄 페이지, **시연 기록 초기화**를 한다. 방문객 쿠폰 화면은 5초마다 `/qr/api/me`로 지급 여부를 확인한다.
- QR 주소 = `QR_PUBLIC_BASE_URL` 또는 `request.host_url`. localhost면 담당자 화면에 경고를 띄운다. 휴대폰 시연은 ngrok 공개 주소가 필요하다.
- 챗봇: `QR_CHAT_WEBHOOK_URL`이 비어 있으면 고정 답변 **"테스트 단계입니다"**를 준다(사용자 요청). n8n 연결을 대비해 `chatInput`, `sessionId`, `eventId`, `context`(토큰 제외 행사 요약), `network`, `stamps`를 보내고, 응답은 `reply`/`output`/`text`/`message`/`answer` 또는 문자열을 받도록 만들어 두었다. 형식은 README에 있다.
- **지도 = 카카오맵** (2026-09-30 사용자 결정). 네이버는 2025-07부터 옛 무료 이용량이 끝났고 결제 수단 등록이 필요할 수 있어서 제외했다. 카카오는 비즈월렛을 연결하지 않으면 과금되지 않는다. 키는 `QR_KAKAO_MAP_KEY`이고, 카카오 콘솔에서 "카카오맵 활성화 ON"과 사이트 도메인(localhost:5000, ngrok) 등록이 필요하다.
  - `static/qr_map.js`가 SDK를 `autoload=false`로 동적으로 불러온다. 8초 안에 안 뜨거나 오류가 나면 `#svg-map`(그림 약도)으로 바꾼다. 키가 없으면 서버가 처음부터 약도를 그린다.
  - 지도 데이터는 `event.map_data()` → `<script type="application/json" id="map-data">`로 넘긴다. **스탬프 토큰은 넣지 않는다.** `map`, `booth.geo`, `stamps[].geo`, `zones[].circle`({center, radius}) 중 하나라도 없으면 None이 되고 약도를 쓴다.
  - `qr.js`가 통신 상태를 갱신하면 `qr:network` 이벤트를 쏘고, `qr_map.js`가 받아서 구역 원(`kakao.maps.Circle`) 색을 바꾼다.
  - **2026-09-30 사용자 요청:** 시연 공감을 위해 행사장을 **KT판교빌딩**으로 옮겼다. 행사명은 "2026 판교 테크노밸리 페스티벌"로 바꿨다(한강 불꽃축제에서 변경). 구역은 네모 대신 **원**(스탬프 5곳 + KT 홍보부스 = 6개)이다. KT 마커는 "KT 로고 배지 + KT 홍보부스" 알약 모양이다. **KT 위치만 정확해야 한다**(사용자 요청): OSM relation 21205162 "KT 판교빌딩"의 중심 37.40656, 127.09082. 스탬프는 사용자가 그린 스케치의 상대 배치로 대략 놓았다(정확할 필요 없음). 그림 약도(예비)도 타원으로 바꿨다.
  - 2026-09-30: 카카오 앱 "n8n용 지도 보이기"의 카카오맵 활성화 OFF → sdk.js 403(`disabled OPEN_MAP_AND_LOCAL service`)이 원인이었다. 사용자가 켠 뒤 200을 확인했다. 같은 날 `.q-card{display:block}`이 `hidden`을 덮어 약도 전환이 안 되던 버그를 `.q-body [hidden]{display:none!important}`로 고쳤다.
  - **실제 카카오맵 표시는 키가 없어서 아직 확인하지 않았다.** 서버 쪽 70개 항목은 통과했고, JS는 esprima로 문법 검사만 했다(이 PC에는 Node가 없다).
- **2026-10-01 ngrok 휴대폰 실측:** 허브를 ngrok 무료 플랜(`https://fasting-transpose-earthling.ngrok-free.dev`)으로 열었다.
  - 휴대폰에서 빨간색이 전부 빠지는 문제가 있었다. 원인: ngrok 무료 **경고 페이지 통과 쿠키가 처음 들어온 경로(`/qr/`) 아래에서만 통해서**, 허브의 `/static/common.css`는 CSS 대신 경고 페이지(HTML)가 내려왔다. 해결: **방문객 화면은 `/qr/` 아래 파일만 부른다.** `qr.css` 맨 위에 `--cc-*` 변수와 기본 스타일을 직접 넣었고, `base.html`에서 `common.css` 링크를 뺐다. 방문객 템플릿에 `/qr/` 밖 주소를 넣지 않는다(테스트로 확인한다). 담당자 화면(`/qr/staff/`)은 허브 `cc_layout`을 쓰므로 무료 플랜 + 휴대폰에서는 같은 문제가 날 수 있다. 유료 플랜이면 경고 페이지가 없어 사라진다.
  - 휴대폰에서 지도가 약도로 나왔다. 원인: 카카오 콘솔 JavaScript SDK 도메인에 ngrok 주소가 없어서 401 `domain mismatched`가 났다. 디버그 모드와는 관계없다. 사용자가 콘솔에 ngrok 주소를 추가해야 한다.
  - 사용자 요청으로 찍은 스탬프 표시를 바꿨다: 번호를 남기고 **연노랑 채움(`--q-done-bg`) + 초록 체크 배지**(`.q-done-mark`, 카카오맵은 `.km-check`). 홈·스탬프 화면·지도 목록·카카오 마커·그림 약도에 모두 적용했다.
- **2026-10-01 방문객 채팅을 n8n에 연결했다.** `QR_CHAT_WEBHOOK_URL=https://effortlee1008.app.n8n.cloud/webhook/tonghagil-qr`, 흐름은 Webhook → AI Agent(+ Simple Memory, 키 `body.sessionId`) → Respond to Webhook. 화면 문구는 "챗봇" 대신 **"채팅 에이전트"**(하단 탭은 "채팅")로 바꿨다(사용자 요청). n8n 오류(HTTP 4xx/5xx)는 n8n이 준 `message`를 화면과 허브 창에 같이 보여 준다.
- **2026-10-02 관리자 에이전트 채팅을 담당자 화면에 붙였다** (`POST /qr/staff/api/chat`, `static/staff.js`, PIN 로그인 필요). 방문객용과 **다른 n8n 워크플로**이고 주소는 `QR_STAFF_CHAT_WEBHOOK_URL`(비우면 고정 답변, 비밀 값은 없으면 방문객용 것을 같이 씀)이다. 방문객용 payload에 `role: "staff"`와 `stats`(방문객 수 · `stamp.in_progress/completed/by_count/per_spot` · `coupon.issued/redeemed/waiting`)를 더 보낸다(`routes._staff_stats`). n8n은 이 PC의 DB를 못 읽어서 숫자를 같이 보내는 방식이다. `sessionId`는 `staff-<브라우저 탭이 만든 ID>`다. 사용자 계획: n8n에서 질문을 분류(Text Classifier)해 가지별로 처리하고, **사은품 재고는 구글 스프레드시트**에서 읽는다(앱에는 재고 표가 없다).
- 2026-10-02: ngrok 뒤에서는 Flask가 `http`로 알아서 QR 주소가 `http://`로 나왔다. `_public_base()`가 `X-Forwarded-Proto`를 보게 고쳤고, 담당자 화면의 주소 표시는 `/qr/`까지 보이게 했다. `.env`에 `QR_PUBLIC_BASE_URL`과 `QR_STAFF_PIN`은 아직 없다.
- **2026-10-02 ngrok Hobbyist 결제 후 공개 주소:** 허브 `https://command-center.ngrok.app`(5000, 예전 `fasting-transpose-earthling.ngrok-free.dev`에서 변경), SaveDeal `https://savedeal.ngrok.dev/savedeal`(5001), 빅또리 `https://vicddory.ngrok.app`(5500). `ngrok start --all`로 3개를 연다(설정 파일의 `endpoints`). 화면 안 링크는 루트의 `start_all.local.ps1`(이 PC 전용, git 제외)의 `$PublicMode`/`$PublicHub`/`$PublicUrls`가 공개 주소로 바꾼다. 주소를 바꾸면 ngrok 설정 파일, `start_all.local.ps1`, 카카오 JS 키 도메인을 같이 고치고 QR을 다시 인쇄한다.
- 실제 n8n 주소가 `.env`에 있으므로 **테스트 스크립트는 웹훅 주소를 비우고 돌린다**(2026-10-01에 스모크 테스트가 실제 n8n을 한 번 호출한 일이 있었다).
- `data/.gitignore`(이 폴더 안)가 `qr.db`와 `.secret`을 막는다. 루트 `.gitignore`는 공용 파일이라 건드리지 않았다.
- 검증(2026-09-30): 임시 DB로 방문객·스탬프·쿠폰·챗봇(가짜 n8n 응답 포함)·담당자 PIN·지급·초기화 57개 항목을 확인했고 모두 통과했다. 실제 서버에서도 `/qr/` 전 화면이 200이었다. **브라우저·휴대폰 화면은 아직 눈으로 확인하지 않았다.**

## 남은 일 / 주의
- [ ] 외부 공개(ngrok) 전에 할 일: 세이브딜·빅또리 카드의 `localhost` URL(`agents.json`)과 각 팀원의 `COMMAND_CENTER_URL`을 공개 주소로 바꾼다(팀원 동의 필요). 통하길 QR은 `.env`의 `QR_PUBLIC_BASE_URL`을 넣고 QR을 다시 인쇄한다.
- [ ] 허브를 루트로 옮긴 것(2026-09-29)과 새 규칙을 팀에 공지한다. 공지 내용: 각자 `agents.json`과 `start_all.ps1`에서 자기 줄만 수정한다는 것, 포트 표, 정주희님은 더 줘 URL(`http://localhost:5173/agents/more`)과 Vite 포트 고정(`strictPort`)을 확인해 달라는 것.
- [ ] 발표 전에 배포 방식을 정한다(Render 등). 무료 서버는 `posters.json`과 추가한 에이전트가 초기화될 수 있다.
- 2026-09-29: `start_all`을 **한 창 실행**으로 바꿨다. 창을 닫거나 Ctrl+C를 누르면 전부 종료되고, Job Object의 KILL_ON_JOB_CLOSE를 안전장치로 쓴다. 실행 목록은 `agents.json`의 `server`에서 읽는다. (스튜디오는 2026-09-30부터 허브 안이라 사이드바도 허브의 `agent_link`를 그대로 쓴다.)
- 통하길 QR은 허브 Blueprint(`/qr/`)로 붙였다(2026-09-30 사용자 결정). 포트 5005 예약은 없앴다.
- 실제 드라이브 연결은 확인했다(2026-09-29). 포스터 4장의 목록과 썸네일을 읽어 왔다. **수정·삭제는 실제 드라이브에서 아직 시험하지 않았다.** 사용자 파일을 바꾸는 작업이라 가짜 클라이언트로만 테스트했다.
- [ ] n8n Upload file 노드가 모든 파일을 `festival_poster`라는 같은 이름으로 저장한다. `행사유형_제목_날짜` 규칙으로 저장하게 바꾸면 갤러리 제목이 자동으로 붙는다.
- 스모크 테스트는 Flask test client로 27개 항목, 드라이브 테스트는 34개 항목을 확인했고 모두 통과했다. 브라우저에서 화면이 어떻게 보이는지는 아직 확인하지 않았다.
- 2026-09-30 Blueprint 이전 후 허브 test client로 31개 항목을 다시 확인했다(홈·더 줘·스튜디오 화면, 정적 파일, 실제 드라이브 목록·썸네일 읽기, 데모 생성은 임시 저장소로). 모두 통과했다. 실제 n8n 생성과 브라우저 화면은 아직 확인하지 않았다.
- 2026-09-30 결정: 허브 `debug=True`는 **그대로 켜 둔다** (사용자 결정). ngrok은 시연할 때만 잠깐 연다. 위험(오류 화면 노출, PIN으로 잠긴 디버그 콘솔)은 설명했다. 권장: 시연이 끝나면 ngrok을 바로 끈다.
- [ ] ngrok 공개 전에: 직원 화면 비밀번호 잠금 여부를 정한다.

## 작업 방식
- 사용자는 한국어로 소통한다. UI 문구와 코드 주석도 한국어로 쓴다.
- 사용자가 "먼저 설명해 달라"고 하면 코드를 작성하지 않고 이해한 내용부터 설명한다.
- 커밋과 push는 사용자가 GitHub Desktop으로 직접 한다.
