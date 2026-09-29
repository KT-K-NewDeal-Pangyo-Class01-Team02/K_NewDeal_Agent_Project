# CLAUDE.md — 통하길 스튜디오 (이승현 담당 폴더)

> ## 🚫 절대 규칙: 이 폴더의 주인은 **이승현 (GitHub: EffortLEE1008)** 입니다
> - 지금 사용자가 이승현 본인이 **아니라면**, 이 폴더(`tonghagil_LEESEUNGHYUN/`) 안의 파일을 **만들지도, 고치지도, 지우지도, 옮기지도 마세요.** 읽기만 허용됩니다.
> - 수정이 필요해 보이면 작업을 멈추고 사용자에게 알리세요. "이 폴더는 이승현님의 폴더입니다. 이승현님의 동의를 먼저 받아 주세요."라고 말하고, 바꿀 파일과 이유, 바꿀 내용을 함께 전달하세요.
> - 사용자가 이승현님의 동의를 받았다고 **명확히** 말한 경우에만, 동의받은 범위 안에서 한 번만 수정할 수 있습니다.
> - 이승현 본인도 **다른 팀원의 폴더**는 위와 같은 규칙으로 다룹니다. 전체 규칙은 저장소 루트의 `CLAUDE.md`에 있습니다.

## 프로젝트 배경
- 팀 프로젝트 **Command Center**: 통신유통 업무용 AI 에이전트 4개(예약판매 이탈 방지, 더 줘, 사후관리, 통하길 스튜디오)를 모은 허브.
- 이 폴더 담당자는 **통하길 스튜디오**를 만든다. 저장소 루트의 팀 공용 허브(`command_center/`, `start_all.*`)도 관리한다. 다른 팀원 에이전트는 각자 따로 만든다.
- 통하길 스튜디오 = 행사 홍보 포스터 생성 Agent. **QR 현장 서비스(스탬프·챗봇·구역별 통신 안내)는 보류**했고, 나중에 별도 에이전트로 "새 에이전트 추가"를 통해 붙인다.
- 저장소: 조직 리포 `KT-K-NewDeal-Pangyo-Class01-Team02/K_NewDeal_Agent_Project`. 루트 아래 팀원별 폴더를 두는 구조이고, `.git`, `.gitignore`, `.gitattributes`는 저장소 루트에 있다.

## 정해진 결정
- **Flask + Jinja 템플릿**을 쓴다. 팀 합의로 프론트엔드까지 Python으로 통일했다.
- 에이전트마다 별도 앱과 포트를 쓴다. 홈 카드와 사이드바는 각 에이전트 URL을 **새 탭**으로 연다.
- 2026-09-29: Command Center 허브를 이 폴더에서 **저장소 루트 `command_center/`(팀 공용)**로 옮겼다. `shared/` 폴더는 없앴다.
  - 에이전트 목록은 루트의 `command_center/agents.json` 하나로 관리한다. 홈 카드와 사이드바 메뉴가 여기서 자동으로 만들어진다.
  - 스튜디오는 허브와 **독립**이다. 디자인(`cc_layout.html`, `_icons.html`, `common.css`, `common.js`)은 `tonghagil_studio/` 안에 사본으로 둔다. `tonghagil_studio/layout.py`는 사이드바용으로 허브의 `agents.json`만 **읽는다**. 파일이 없으면 빈 목록을 쓰고, `CC_AGENTS_FILE`로 경로를 바꿀 수 있다.
  - 전체 실행은 루트 `start_all.bat`/`start_all.ps1`로 한다. 포트는 홈 5000, 스튜디오 5004, 더 줘 5173이다.
- 포스터 이미지는 n8n → 구글 드라이브에서 온다. 화면은 이미지 출처를 모르게 설계했다.
- 갤러리는 **구글 드라이브 폴더를 서비스 계정 + Drive API(B 방법)로 직접 읽는다** (2026-09-29 결정). n8n으로 목록을 가져오는 A 방법은 채택하지 않았다.
  - `DRIVE_FOLDER_ID`와 키 파일이 둘 다 있으면 `DriveFolderPosterStore`, 아니면 `JsonPosterStore`(샘플)를 쓴다.
  - 드라이브 폴더가 기준 목록이다. `posters.json`은 스튜디오 요청의 부가 정보(제목·행사 유형·요청 문구)를 파일 ID로 합치는 용도로만 쓴다.
  - 이미지는 `/drive-image/<id>` 프록시로 보여 준다. 비공개 파일도 보이고, 썸네일은 `data/drive_cache/`에 캐시한다. 폴더 목록이나 스튜디오 기록에 없는 ID는 404로 막는다.
  - 연결된 폴더는 `프로젝트이미지`(`1iQiLggZv0QpnRMAs_KjgSSz_CjKVK9l7`)다. 서비스 계정 `tonghagil-gallery@tonghagil-studio.iam.gserviceaccount.com`이 **편집자**로 공유되어 있다. OAuth 범위는 `auth/drive`다.
  - **수정** = 드라이브 파일 이름을 `행사유형_제목_YYYYMMDD.확장자`로 바꾸고, `posters.json` 기록도 함께 고친다(`PATCH /api/posters/<id>`).
  - **삭제** = 폴더 안 `_보관함` 하위 폴더로 옮긴다(`DELETE /api/posters/<id>`). 이유: 파일 소유자가 사용자 본인(shlee6630)이라 서비스 계정은 `canTrash/canDelete=False`이고, `canRename`과 `canRemoveChildren`만 `True`다(2026-09-29 실측).

## 구조
```
(루트) command_center/  팀 공용 허브 (포트 5000): app.py, layout.py, agents.json, templates/, static/
tonghagil_studio/  스튜디오 (포트 5004)
  app.py           GET / · GET/POST /api/posters(?refresh=1) · PATCH/DELETE /api/posters/<id> · GET /drive-image/<id>(?download=1) · GET /placeholder.svg
  layout.py        사이드바·상단 바 값 주입 (허브 agents.json 읽기 전용)
  templates/       studio.html + cc_layout.html·_icons.html (허브 디자인 사본)
  static/          studio.css/js + common.css/js (허브 디자인 사본)
  config.py        .env 읽기 (N8N_*, DRIVE_FOLDER_ID, GOOGLE_SERVICE_ACCOUNT_FILE, DRIVE_CACHE_SECONDS)
  n8n_client.py    n8n Chat URL 호출 + 응답에서 드라이브 링크/파일ID 추출
  drive.py         드라이브 링크 ↔ 파일 ID 변환 도우미
  drive_store.py   DriveClient(서비스 계정, Drive API REST) + DriveFolderPosterStore(폴더 갤러리)
  poster_store.py  JsonPosterStore (data/posters.json, 없으면 sample_posters.json)
  placeholder.py   샘플/데모용 SVG 포스터 생성
```

## 실행
VS Code 실행(▶) 버튼으로 `app.py`를 직접 실행해도 된다. 각 `app.py` 맨 위에서 `__package__`가 없으면 `sys.path`에 상위 폴더를 추가한다. 여러 서버를 ▶로 켤 때는 "전용 터미널에서 실행"을 쓴다. 한 터미널에는 서버 하나만 돌릴 수 있다.
```powershell
# Anaconda: C:\ProgramData\anaconda3\envs\knewdeal (Python 3.14). PowerShell 에는 conda init 이 안 되어 있어 절대경로로 실행
& "C:\ProgramData\anaconda3\envs\knewdeal\python.exe" -m tonghagil_studio.app   # 이 폴더에서, http://localhost:5004
& "C:\ProgramData\anaconda3\envs\knewdeal\python.exe" -m command_center.app     # 저장소 루트에서, http://localhost:5000
```
- 이 PC에는 Node.js가 설치되어 있지 않다. 그래서 `start_all`이 더 줘(5173)를 건너뛴다.
- 의존성: `requirements.txt` (flask, requests, python-dotenv, google-auth). knewdeal 환경에 모두 설치되어 있다.
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

## 남은 일 / 주의
- [ ] 외부 공개(VS Code 포트 전달, 배포) 전에 할 일:
  - `debug=True`를 `.env`로 끌 수 있게 바꾼다. 디버그 모드 공개는 보안 위험이다.
  - `agents.json`의 `localhost` URL과 `COMMAND_CENTER_URL`을 공개 주소로 바꾼다.
- [ ] 허브를 루트로 옮긴 것(2026-09-29)과 새 규칙을 팀에 공지한다. 공지 내용: 각자 `agents.json`과 `start_all.ps1`에서 자기 줄만 수정한다는 것, 포트 표, 정주희님은 더 줘 URL(`http://localhost:5173/agents/more`)과 Vite 포트 고정(`strictPort`)을 확인해 달라는 것.
- [ ] 발표 전에 배포 방식을 정한다(Render 등). 무료 서버는 `posters.json`과 추가한 에이전트가 초기화될 수 있다.
- [ ] QR 현장 서비스 에이전트(통하길 QR)는 나중에 만든다. 포트 **5005**를 예약해 두었다. 이 폴더 안에 패키지(예: `tonghagil_qr/`)로 만들고, 허브 `agents.json`에 항목 하나를 추가하면 카드, 사이드바, `start_all`에 자동으로 들어간다. 추가할 항목은 `url` + `server: {dir: "tonghagil_LEESEUNGHYUN", port: 5005, python: "tonghagil_qr.app"}`이고, 예시는 `command_center/README.md`에 있다.
- 2026-09-29: `start_all`을 **한 창 실행**으로 바꿨다. 창을 닫거나 Ctrl+C를 누르면 전부 종료되고, Job Object의 KILL_ON_JOB_CLOSE를 안전장치로 쓴다. 실행 목록은 `agents.json`의 `server`에서 읽는다. 스튜디오 사이드바는 `url`이 없고 `path`만 있는 에이전트(더 줘)에 `COMMAND_CENTER_URL + path`를 붙인다.
- 실제 드라이브 연결은 확인했다(2026-09-29). 포스터 4장의 목록과 썸네일을 읽어 왔다. **수정·삭제는 실제 드라이브에서 아직 시험하지 않았다.** 사용자 파일을 바꾸는 작업이라 가짜 클라이언트로만 테스트했다.
- [ ] n8n Upload file 노드가 모든 파일을 `festival_poster`라는 같은 이름으로 저장한다. `행사유형_제목_날짜` 규칙으로 저장하게 바꾸면 갤러리 제목이 자동으로 붙는다.
- 스모크 테스트는 Flask test client로 27개 항목, 드라이브 테스트는 34개 항목을 확인했고 모두 통과했다. 브라우저에서 화면이 어떻게 보이는지는 아직 확인하지 않았다.

## 작업 방식
- 사용자는 한국어로 소통한다. UI 문구와 코드 주석도 한국어로 쓴다.
- 사용자가 "먼저 설명해 달라"고 하면 코드를 작성하지 않고 이해한 내용부터 설명한다.
- 커밋과 push는 사용자가 GitHub Desktop으로 직접 한다.
