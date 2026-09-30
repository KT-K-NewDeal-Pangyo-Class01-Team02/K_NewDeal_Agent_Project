# Command Center 홈 (팀 공용 허브)

에이전트 카드와 사이드바를 보여 주는 홈 화면입니다. → http://localhost:5000
관리는 이승현이 합니다. 팀원은 **자기 에이전트 항목만** 고칩니다 (루트 `CLAUDE.md`의 "공용 허브" 규칙).

## 실행
- Python **3.12 이상** (3.14에서 동작 확인).
- 저장소 루트에서 `python -m command_center.app`을 실행하거나, `command_center/app.py`를 열고 VS Code ▶를 누릅니다.
- 전체 실행은 루트의 `start_all.bat`으로 합니다.
- 필요한 패키지: `pip install -r command_center/requirements.txt` (flask, python-dotenv)
  - 통하길 스튜디오(`/studio/`)·QR(`/qr/`)까지 쓰려면 `tonghagil_LEESEUNGHYUN/requirements.txt`도 설치합니다(requests, google-auth, segno). 없으면 그 에이전트만 건너뛰고 허브는 뜹니다.
- 선택: `command_center/.env`에 `COMMAND_CENTER_PORT=5000`, `CC_USER_NAME=김지현 매니저` 등을 넣을 수 있습니다. git에는 올라가지 않습니다.

## 내 에이전트 등록하기 (`agents.json`)

**자기 에이전트 항목 한 개**만 추가하거나 수정하세요. 이 항목 하나로 세 가지가 자동으로 됩니다.
1. 홈 **카드**
2. 모든 에이전트 화면의 **사이드바** 메뉴 (허브의 `agents.json`을 읽는 화면)
3. `start_all.bat`의 **전체 실행** 목록 (`server`가 있을 때)

### ① 별도 서버: 자기 포트로 따로 띄우기 (카드는 새 탭)
```json
{
  "id": "tonghagil-qr",
  "name": "통하길 QR",
  "description": "카드에 보일 한두 줄 설명",
  "icon": "qr-code",
  "color": "teal",
  "status": "운영 중",
  "url": "http://localhost:5005",
  "server": { "dir": "tonghagil_LEESEUNGHYUN", "port": 5005, "python": "tonghagil_qr.app" }
}
```
- `server.dir`: 저장소 루트 기준 폴더. 이 폴더에서 명령을 실행합니다.
- `server.python`: `python -m <이 값>`으로 실행합니다.
- Node 프런트엔드라면 `python` 대신 `"npm": "dev"`를 적습니다. 그러면 `npm run dev`로 실행하고, 처음에는 `npm install`부터 합니다.
- `server.port`: 루트 README 포트 표의 포트로 고정합니다. `url`의 포트와 같아야 합니다.
- 서버를 따로 띄우지 않을 거면(아직 준비 중 등) `server`를 빼면 됩니다.

### ② Blueprint: 허브와 한 프로세스로 돌리기 (카드는 같은 탭)
```json
{
  "id": "deo-jwo",
  "name": "더 줘",
  "description": "카드에 보일 한두 줄 설명",
  "icon": "coins",
  "color": "blue",
  "status": "운영 중",
  "endpoint": "thejo.dashboard",
  "path": "/thejo/",
  "url": ""
}
```
- `endpoint`: 허브 안에서 쓰는 Flask 엔드포인트 이름(`<blueprint>.<함수>`)입니다.
- `path`: 같은 화면의 허브 기준 주소입니다. **허브 밖의 에이전트 화면**(빅또리 등)이 사이드바에서 `http://localhost:5000` + `path`로 찾아갈 때 씁니다. 반드시 같이 적으세요.
- 지금 Blueprint 로 붙은 에이전트: 더 줘(`/thejo/`), 통하길 스튜디오(`/studio/`), 통하길 QR(`/qr/`, 카드는 부스 담당자 화면 `/qr/staff/`).
- 화면·JS 의 주소는 `url_for` 나 Blueprint 기준 상대 주소로 만드세요. `/api/...` 처럼 루트 기준으로 적으면 다른 에이전트와 겹치고, `http://localhost:...` 로 적으면 ngrok 등 공개 주소에서 깨집니다.
- `url`은 비워 둡니다. `url`이 있으면 새 탭 링크로 취급됩니다.
- `app.py`에 `register_blueprint` 한 줄을 넣어야 해서 **관리자(이승현) 동의가 필요**합니다. `start_all`에는 따로 넣지 않습니다. 허브와 함께 뜹니다.

| 필드 | 값 |
|---|---|
| `icon` | image, qr-code, calendar-x, coins, headset, sparkles, bot |
| `color` | red, blue, green, purple, orange, teal |
| `status` | 운영 중, 준비 중 |
| `url` / `endpoint` / `path` | 셋 다 비어 있으면 카드를 눌렀을 때 "주소 미등록" 안내가 뜹니다. |

## 다른 에이전트 화면의 사이드바
각 에이전트는 허브의 `agents.json`을 **읽어서** 자기 사이드바를 그립니다. 허브 디자인 사본(`cc_layout.html`)을 쓰는 방식이에요.
Blueprint 에이전트는 `url`이 비어 있으니, 사이드바 코드에서 `url`이 없고 `path`가 있으면 `허브 주소 + path`를 링크로 쓰세요.
```python
hub = os.getenv("COMMAND_CENTER_URL", "http://localhost:5000").rstrip("/")
for agent in agents:
    if not (agent.get("url") or "").strip() and (agent.get("path") or "").strip():
        agent["url"] = hub + "/" + agent["path"].strip().lstrip("/")
```
