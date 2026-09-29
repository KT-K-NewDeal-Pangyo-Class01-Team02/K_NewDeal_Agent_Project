# Command Center

통신유통 업무를 돕는 AI 에이전트 모음입니다. **홈(Command Center)**에서 에이전트 카드를 누르면 각 에이전트가 **새 탭**으로 열립니다.
에이전트마다 서버가 따로 돌고, 모두 **같은 컴퓨터의 `localhost`**에서 실행됩니다.

```
K_NewDeal_Agent_Project/
├─ command_center/          🟢 팀 공용 허브 (홈 화면 + agents.json)        → http://localhost:5000
├─ start_all.bat / .ps1     🟢 팀 공용: 모든 서버를 한 번에 실행
├─ tonghagil_LEESEUNGHYUN/  통하길 스튜디오 (이승현)                     → http://localhost:5004
├─ thejo_project/           더 줘 (정주희) — 허브에 Blueprint 로 내장      → http://localhost:5000/thejo/
└─ vicDDory_wooyong/        (최우용) 준비 중
```

## 포트 표

| 서버 | 포트 | 폴더 | 실행 방식 |
|---|---|---|---|
| Command Center 홈 | **5000** | `command_center/` | Python (Flask) |
| 통하길 스튜디오 | **5004** | `tonghagil_LEESEUNGHYUN/` | Python (Flask) |
| 더 줘 | **5000** (`/thejo/`) | `thejo_project/` | Python (Flask Blueprint, 홈과 같은 프로세스) |
| (최우용) | 미정 | `vicDDory_wooyong/` | 미정 |

에이전트가 허브에 붙는 방법은 두 가지입니다.

| 방식 | 언제 쓰나 | 카드를 누르면 | `agents.json` 에 적는 것 |
|---|---|---|---|
| **Blueprint** | Flask 로 만들었고 허브와 한 프로세스로 돌려도 될 때 | **같은 탭**으로 이동 | `"endpoint": "<blueprint>.<함수>"` |
| **별도 서버** | 자기 포트에서 따로 띄워야 할 때 | **새 탭**으로 열림 | `"url": "http://localhost:<포트>"` |

별도 서버로 붙이는 새 에이전트는 **겹치지 않는 포트**를 골라 이 표, `start_all.ps1`, `command_center/agents.json`에 한 줄씩 추가해 주세요.
Blueprint 로 붙이는 에이전트는 포트가 필요 없습니다. `command_center/app.py`에 `register_blueprint` 한 줄을 추가하면 되고, 이건 허브 코드라 **관리자(이승현) 동의**가 필요합니다.

## 처음 한 번만

**Python 3.12 이상** (3.14 에서 동작 확인). 가상환경을 하나 만들고 패키지를 설치합니다.

conda 를 쓸 때:
```powershell
conda create -n knewdeal python=3.12 -y
conda activate knewdeal
pip install -r command_center/requirements.txt -r tonghagil_LEESEUNGHYUN/requirements.txt
```

conda 가 없을 때 (표준 venv):
```powershell
python -m venv .venv
.\.venv\Scripts\Activate.ps1
pip install -r command_center/requirements.txt -r tonghagil_LEESEUNGHYUN/requirements.txt
```

에이전트별 추가 설정(`.env`, 키 파일 등)은 각 폴더의 README를 보세요. 설정이 없어도 대부분 데모 모드로 뜹니다.
Node.js 는 더 이상 필요하지 않습니다. 더 줘가 Vite 대신 Flask Blueprint 로 바뀌었습니다.

## 실행

**`start_all.bat` 더블클릭**
- 서버마다 창이 하나씩 뜨고, 잠시 뒤 브라우저에서 http://localhost:5000 이 열립니다.
- 서버를 끄려면 **각 서버 창을 닫으세요.**
- 이미 켜져 있는 서버는 건너뜁니다.
- Python을 못 찾으면 이 폴더에 `start_all.local.ps1`을 만들고 `$Python = "C:\경로\python.exe"` 한 줄을 적으세요. 이 파일은 git에 올라가지 않습니다.
- `.\start_all.ps1 -DryRun`으로 실행하면 실제로 띄우지 않고 계획만 보여 줍니다.

**하나씩 실행할 때**
- 홈: 저장소 루트에서 `python -m command_center.app`을 실행하거나, `command_center/app.py`를 열고 VS Code ▶ 버튼을 누릅니다.
  이 하나로 **더 줘까지 같이 뜹니다** (http://localhost:5000/thejo/).
- 여러 서버를 ▶로 켤 때는 ▶ 옆 화살표 → **"전용 터미널에서 Python 파일 실행"**을 고르세요. 터미널 하나에는 서버 하나만 돌릴 수 있습니다.

## 접속 주소

| 화면 | 주소 |
|---|---|
| Command Center 홈 | http://localhost:5000/ |
| 더 줘 대시보드 | http://localhost:5000/thejo/ |
| 더 줘 · 위험 경고 | http://localhost:5000/thejo/warnings |
| 더 줘 · 수익 기회 | http://localhost:5000/thejo/opportunities |
| 통하길 스튜디오 | http://localhost:5004/ |

## 테스트

저장소 루트에서 실행합니다. 추가 패키지는 필요 없습니다.

```powershell
python -m unittest thejo_project.tests.test_thejo -v
```

## 다른 컴퓨터끼리는 연결되지 않아요
`localhost`는 **"지금 이 컴퓨터"**라는 뜻입니다. A 컴퓨터의 홈에서 B 컴퓨터의 더 줘로 이동할 수는 없습니다.
각자 `git pull` 받아서 **자기 컴퓨터에서 필요한 서버를 모두 켜고** 테스트하세요. 시연도 **노트북 한 대**에서 `start_all`로 모두 켜서 합니다.

## 규칙
다른 팀원의 폴더는 주인의 동의 없이 수정하지 않습니다. 자세한 내용은 [CLAUDE.md](CLAUDE.md)를 보세요.
