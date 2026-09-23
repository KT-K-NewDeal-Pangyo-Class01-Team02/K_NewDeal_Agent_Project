# Command Center

통신유통 업무를 돕는 AI 에이전트 모음. 홈 화면(Command Center)이 에이전트 카드를 보여 주고,
카드를 누르면 각 에이전트 앱이 **새 탭**으로 열립니다.

```
shared/              공통 틀 (사이드바·상단 바·버튼 스타일) + agents.json (에이전트 목록)
command_center/      홈 화면            → http://localhost:5000
tonghagil_studio/    통하길 스튜디오     → http://localhost:5004
```

## 실행

```powershell
python -m venv .venv
.venv\Scripts\activate
pip install -r requirements.txt
copy .env.example .env

# 터미널 1
python -m command_center.app
# 터미널 2
python -m tonghagil_studio.app
```

반드시 **프로젝트 루트**에서 실행하세요 (`shared` 폴더를 불러와야 합니다).

## 에이전트 추가하기

`shared/agents.json` 에 한 줄 추가하거나, 홈 화면의 **새 에이전트 추가** 카드를 누르세요.
홈 카드와 사이드바 메뉴가 자동으로 늘어납니다. `url` 이 비어 있으면 누를 때 "주소 미등록" 안내가 뜹니다.

| 필드 | 설명 |
|---|---|
| `icon` | image, qr-code, calendar-x, coins, headset, sparkles, bot |
| `color` | red, blue, green, purple, orange, teal |
| `url` | 에이전트 앱 주소 (새 탭으로 열림) |

다른 팀원의 앱도 `shared.layout.init_layout(app, active_agent_id="내-id")` 를 부르고
템플릿에서 `{% extends "cc_layout.html" %}` 하면 같은 사이드바·상단 바를 씁니다.

## 통하길 스튜디오 ↔ n8n 연결

`.env` 의 `N8N_WEBHOOK_URL` 이 비어 있으면 **데모 모드**(샘플 포스터 생성)로 동작합니다.

1. n8n의 **When chat message received** 노드에서 `Make Chat Publicly Available` 을 켜고,
   `Authentication: None`, `Response Mode: When Last Node Finishes` 로 둡니다.
2. 노드에 표시된 **Chat URL** 을 `.env` 의 `N8N_WEBHOOK_URL` 에 넣습니다.
3. 워크플로를 **Active** 로 바꿉니다. (테스트 URL `/webhook-test/...` 는 에디터에서 실행 대기 중일 때만 동작)
4. 마지막 노드(Edit Fields)가 드라이브 공유 링크 또는 파일 ID를 내보내면 됩니다. 필드 이름은 상관없습니다.

스튜디오는 `chatInput`(설명 + 스타일 + 행사 유형)을 보내고, 응답에서 드라이브 링크를 찾아
`https://drive.google.com/thumbnail?id=<파일ID>` 주소로 갤러리에 보여 줍니다.
생성 기록은 `tonghagil_studio/data/posters.json` 에 쌓입니다.
