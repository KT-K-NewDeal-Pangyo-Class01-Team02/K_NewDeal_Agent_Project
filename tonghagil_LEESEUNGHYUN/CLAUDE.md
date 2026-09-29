# CLAUDE.md — 통하길 스튜디오 (이승현 담당 폴더)

> ## 🚫 절대 규칙: 이 폴더의 주인은 **이승현 (GitHub: EffortLEE1008)** 입니다
> - 지금 사용자가 이승현 본인이 **아니라면**, 이 폴더(`tonghagil_LEESEUNGHYUN/`) 안의 파일을 **만들지도, 고치지도, 지우지도, 옮기지도 마세요.** 읽기만 허용됩니다.
> - 수정이 필요해 보이면 작업을 멈추고 사용자에게 알리세요. "이 폴더는 이승현님의 폴더입니다. 이승현님의 동의를 먼저 받아 주세요."라고 말하고, 바꿀 파일과 이유, 바꿀 내용을 함께 전달하세요.
> - 사용자가 이승현님의 동의를 받았다고 **명확히** 말한 경우에만, 동의받은 범위 안에서 한 번만 수정할 수 있습니다.
> - 이승현 본인도 **다른 팀원의 폴더**는 위와 같은 규칙으로 다룹니다. 전체 규칙은 저장소 루트의 `CLAUDE.md`에 있습니다.

## 프로젝트 배경
- 팀 프로젝트 **Command Center**: 통신유통 업무용 AI 에이전트 4개(예약판매 이탈 방지, 더 줘, 사후관리, 통하길 스튜디오)를 모은 허브.
- 이 폴더 담당자는 **통하길 스튜디오**와 **Command Center 홈 화면**을 맡는다. 다른 팀원 에이전트는 각자 따로 만든다.
- 통하길 스튜디오 = 행사 홍보 포스터 생성 Agent. **QR 현장 서비스(스탬프·챗봇·구역별 통신 안내)는 보류**했고, 나중에 별도 에이전트로 "새 에이전트 추가"를 통해 붙인다.
- 저장소: 조직 리포 `KT-K-NewDeal-Pangyo-Class01-Team02/K_NewDeal_Agent_Project`. 루트 아래 팀원별 폴더를 두는 구조이고, `.git`, `.gitignore`, `.gitattributes`는 저장소 루트에 있다.

## 정해진 결정
- **Flask + Jinja 템플릿**을 쓴다. 팀 합의로 프론트엔드까지 Python으로 통일했다.
- 에이전트마다 별도 앱과 포트를 쓴다. 홈 카드와 사이드바는 각 에이전트 URL을 **새 탭**으로 연다.
- 에이전트 목록은 `shared/agents.json` 하나로 관리한다. 여기서 홈 카드와 사이드바 메뉴가 자동으로 만들어진다.
- 사이드바와 상단 바는 공통 틀(`shared/templates/cc_layout.html`)로 모든 앱이 함께 쓴다.
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
shared/            layout.py(init_layout), agents.json, templates/(cc_layout, _icons), static/(common.css/js)
command_center/    홈 화면 (포트 5000) — 카드 목록, 새 에이전트 추가(POST /api/agents → agents.json)
tonghagil_studio/  스튜디오 (포트 5004)
  app.py           GET / · GET/POST /api/posters(?refresh=1) · GET /drive-image/<id>(?download=1) · GET /placeholder.svg
  config.py        .env 읽기 (N8N_*, DRIVE_FOLDER_ID, GOOGLE_SERVICE_ACCOUNT_FILE, DRIVE_CACHE_SECONDS)
  n8n_client.py    n8n Chat URL 호출 + 응답에서 드라이브 링크/파일ID 추출
  drive.py         드라이브 링크 ↔ 파일 ID 변환 도우미
  drive_store.py   DriveClient(서비스 계정, Drive API REST) + DriveFolderPosterStore(폴더 갤러리)
  poster_store.py  JsonPosterStore (data/posters.json, 없으면 sample_posters.json)
  placeholder.py   샘플/데모용 SVG 포스터 생성
```

## 실행
VS Code 실행(▶) 버튼으로 `app.py`를 직접 실행해도 된다. 각 `app.py` 맨 위에서 `__package__`가 없으면 `sys.path`에 이 폴더를 추가한다. 터미널에서는 이 폴더에서 `-m`으로 실행한다.
```powershell
conda activate knewdeal          # Anaconda: C:\ProgramData\anaconda3\envs\knewdeal (Python 3.14)
python -m tonghagil_studio.app   # http://localhost:5004
python -m command_center.app     # http://localhost:5000 (별도 터미널)
```
- 의존성: `requirements.txt` (flask, requests, python-dotenv, google-auth). knewdeal 환경에 모두 설치되어 있다.
- 설정: `.env` (`.env.example` 참고). `N8N_WEBHOOK_URL`이 비어 있으면 **데모 모드**, `DRIVE_FOLDER_ID`가 비어 있으면 **샘플 갤러리**로 동작한다.
- 서비스 계정 키는 `credentials/service-account.json`에 둔다. `.gitignore`의 `**/credentials/`, `*service-account*.json` 규칙으로 커밋되지 않는다. 구글 클라우드 설정 절차는 README에 있다.
- 이 PC의 PowerShell에는 `python`과 `git`이 PATH에 없다. Python은 위 절대경로로 실행하고, git 작업은 사용자가 **GitHub Desktop**으로 한다.

## n8n 연동
- 현재 워크플로: When chat message received → Generate an image(OpenAI) → Upload file(Drive) → Share file(공개) → Edit Fields.
- Flask가 Chat URL로 `{action:"sendMessage", sessionId, chatInput, message, style, eventType}`를 POST한다.
- n8n 설정 조건:
  - Chat Trigger에서 **Make Chat Publicly Available**를 켠다.
  - **Response Mode: When Last Node Finishes**로 둔다.
  - 워크플로를 **Active**로 켠다.
- 마지막 노드 출력에 드라이브 공유 링크나 파일 ID가 있으면 된다. 필드 이름은 상관없다.

## 남은 일 / 주의
- [ ] 외부 공개(VS Code 포트 전달, 배포) 전에 할 일:
  - `debug=True`를 `.env`로 끌 수 있게 바꾼다. 디버그 모드 공개는 보안 위험이다.
  - `agents.json`의 `localhost` URL과 `COMMAND_CENTER_URL`을 공개 주소로 바꾼다.
- [ ] `shared/`와 `command_center/`를 저장소 루트의 팀 공용으로 옮길지 팀과 논의한다.
- [ ] 발표 전에 배포 방식을 정한다(Render 등). 무료 서버는 `posters.json`과 추가한 에이전트가 초기화될 수 있다.
- [ ] QR 현장 서비스 에이전트는 나중에 만든다.
- 실제 드라이브 연결은 확인했다(2026-09-29). 포스터 4장의 목록과 썸네일을 읽어 왔다. **수정·삭제는 실제 드라이브에서 아직 시험하지 않았다.** 사용자 파일을 바꾸는 작업이라 가짜 클라이언트로만 테스트했다.
- [ ] n8n Upload file 노드가 모든 파일을 `festival_poster`라는 같은 이름으로 저장한다. `행사유형_제목_날짜` 규칙으로 저장하게 바꾸면 갤러리 제목이 자동으로 붙는다.
- 스모크 테스트는 Flask test client로 27개 항목, 드라이브 테스트는 34개 항목을 확인했고 모두 통과했다. 브라우저에서 화면이 어떻게 보이는지는 아직 확인하지 않았다.

## 작업 방식
- 사용자는 한국어로 소통한다. UI 문구와 코드 주석도 한국어로 쓴다.
- 사용자가 "먼저 설명해 달라"고 하면 코드를 작성하지 않고 이해한 내용부터 설명한다.
- 커밋과 push는 사용자가 GitHub Desktop으로 직접 한다.
