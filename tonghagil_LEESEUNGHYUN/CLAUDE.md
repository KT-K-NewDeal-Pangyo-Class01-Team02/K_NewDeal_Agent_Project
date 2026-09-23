# CLAUDE.md — 통하길 스튜디오 (이승현 담당 폴더)

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
- 포스터 이미지는 n8n → 구글 드라이브에서 온다. 화면은 이미지 출처를 모르게 설계했다. 저장소를 바꿔 끼우면 드라이브 폴더 전체 조회로 확장할 수 있다.

## 구조
```
shared/            layout.py(init_layout), agents.json, templates/(cc_layout, _icons), static/(common.css/js)
command_center/    홈 화면 (포트 5000) — 카드 목록, 새 에이전트 추가(POST /api/agents → agents.json)
tonghagil_studio/  스튜디오 (포트 5004)
  app.py           GET / · GET/POST /api/posters · GET /placeholder.svg
  n8n_client.py    n8n Chat URL 호출 + 응답에서 드라이브 링크/파일ID 추출
  drive.py         드라이브 링크 → thumbnail?id= 이미지 주소 변환
  poster_store.py  JsonPosterStore (data/posters.json, 없으면 sample_posters.json)
  placeholder.py   샘플/데모용 SVG 포스터 생성
```

## 실행 (반드시 이 폴더에서 — `shared` import 때문)
```powershell
conda activate knewdeal          # Anaconda: C:\ProgramData\anaconda3\envs\knewdeal (Python 3.14)
python -m tonghagil_studio.app   # http://localhost:5004
python -m command_center.app     # http://localhost:5000 (별도 터미널)
```
- 의존성: `requirements.txt` (flask, requests, python-dotenv). knewdeal 환경에 이미 설치되어 있다.
- 설정: `.env` (`.env.example` 참고). `N8N_WEBHOOK_URL`이 비어 있으면 **데모 모드**로 동작한다.
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
- 스모크 테스트는 Flask test client로 27개 항목을 확인했고 모두 통과했다. 브라우저에서 화면이 어떻게 보이는지는 아직 확인하지 않았다.

## 작업 방식
- 사용자는 한국어로 소통한다. UI 문구와 코드 주석도 한국어로 쓴다.
- 사용자가 "먼저 설명해 달라"고 하면 코드를 작성하지 않고 이해한 내용부터 설명한다.
- 커밋과 push는 사용자가 GitHub Desktop으로 직접 한다.
