# Command Center

통신유통 업무를 돕는 AI 에이전트 모음입니다. **홈(Command Center)**의 카드나 각 화면의 **사이드바**에서 다른 에이전트로 이동합니다.
모든 서버는 **같은 컴퓨터의 `localhost`**에서 실행되고, **`start_all.bat` 하나로 전부 켜고 끕니다.**

```
K_NewDeal_Agent_Project/
├─ command_center/          🟢 팀 공용 허브 (홈 화면 + agents.json)        → http://localhost:5000
├─ start_all.bat / .ps1     🟢 팀 공용: 모든 서버를 한 창에서 실행
├─ savedeal_seunghoon/      예약판매 이탈 방지 (SaveDeal, 장승훈)           → http://localhost:5001/savedeal
├─ thejo_project/           더 줘 (정주희) — 허브에 Blueprint 로 내장      → http://localhost:5000/thejo/
├─ vicDDory_wooyong/        빅또리출동! (최우용)                           → http://localhost:5500
└─ tonghagil_LEESEUNGHYUN/  통하길 스튜디오·QR (이승현) — 허브에 Blueprint 로 내장 → http://localhost:5000/studio/, /qr/
```

## 포트 표

| 서버 | 포트 | 폴더 | 실행 방식 |
|---|---|---|---|
| Command Center 홈 (+ 더 줘, 통하길 스튜디오·QR) | **5000** | `command_center/` | Python (Flask). 더 줘는 `/thejo/`, 통하길 스튜디오는 `/studio/`, 통하길 QR은 `/qr/`로 같은 프로세스에서 돌아요 |
| 예약판매 이탈 방지 (SaveDeal) | **5001** | `savedeal_seunghoon/` | Python (Flask) |
| 통하길 스튜디오 | **5000** (`/studio/`) | `tonghagil_LEESEUNGHYUN/` | Python (Flask Blueprint). 홈과 같은 프로세스라 따로 띄우지 않아요 |
| 통하길 QR | **5000** (`/qr/`) | `tonghagil_LEESEUNGHYUN/` | Python (Flask Blueprint). 홈과 같은 프로세스라 따로 띄우지 않아요 |
| 빅또리출동! | **5500** | `vicDDory_wooyong/` | Python (Flask) |

## 에이전트 붙이기: `command_center/agents.json`에 항목 하나

`agents.json` **한 파일**이 홈 카드, 모든 화면의 사이드바, `start_all` 실행 목록을 한꺼번에 정합니다.
새 에이전트(예: 통하길 QR)는 **자기 항목 하나만 추가**하면 카드, 사이드바, 전체 실행에 모두 자동으로 들어갑니다. 자세한 형식은 [command_center/README.md](command_center/README.md)에 있습니다.

| 방식 | 언제 쓰나 | 카드를 누르면 | 항목에 적는 것 |
|---|---|---|---|
| **별도 서버** | 자기 포트로 따로 띄울 때 | **새 탭** | `"url"` + `"server": { "dir", "port", "python" 또는 "npm" }` |
| **Blueprint** | 허브와 한 프로세스로 돌릴 때 | **같은 탭** | `"endpoint"` + `"path"` (`register_blueprint`가 필요해서 관리자 동의 필요) |

## 처음 한 번만

**Python 3.12 이상** (3.14에서 동작 확인). 가상환경을 하나 만들고 모든 에이전트의 패키지를 설치합니다.

conda를 쓸 때:
```powershell
conda create -n knewdeal python=3.12 -y
conda activate knewdeal
pip install -r command_center/requirements.txt -r tonghagil_LEESEUNGHYUN/requirements.txt -r savedeal_seunghoon/requirements.txt -r vicDDory_wooyong/requirements.txt
```

conda가 없을 때 (표준 venv, 저장소 루트에 `.venv`):
```powershell
python -m venv .venv
.\.venv\Scripts\Activate.ps1
pip install -r command_center/requirements.txt -r tonghagil_LEESEUNGHYUN/requirements.txt -r savedeal_seunghoon/requirements.txt -r vicDDory_wooyong/requirements.txt
```

에이전트별 추가 설정(`.env`, 키 파일 등)은 각 폴더의 README를 보세요. 설정이 없어도 대부분 데모 모드로 뜹니다.

## 실행

**`start_all.bat` 더블클릭**
- 창 **하나**에서 모든 서버가 켜지고, 준비되면 브라우저에서 http://localhost:5000 이 열립니다.
- **그 창을 닫거나 Ctrl+C를 누르면 모든 서버가 함께 꺼집니다.**
- 각 서버의 출력은 `logs\<에이전트id>.log`, 오류는 `.err.log`에 쌓입니다. 서버가 죽으면 창에 마지막 오류 줄이 표시됩니다.
- 이미 켜져 있는 포트는 건너뜁니다. 그 서버는 이 창으로 끌 수 없습니다.
- Python을 못 찾으면 이 폴더에 `start_all.local.ps1`을 만들고 `$Python = "C:\경로\python.exe"` 한 줄을 적으세요. 이 파일은 git에 올라가지 않습니다.
- `.\start_all.ps1 -DryRun`은 실행하지 않고 계획만 보여 줍니다. `-NoBrowser`를 붙이면 브라우저를 열지 않습니다.

**하나씩 실행할 때**
- 홈: 저장소 루트에서 `python -m command_center.app`을 실행하거나 `command_center/app.py`에서 VS Code ▶를 누릅니다. 더 줘, 통하길 스튜디오, 통하길 QR도 같이 뜹니다.
- 여러 서버를 ▶로 켤 때는 ▶ 옆 화살표 → **"전용 터미널에서 Python 파일 실행"**을 고르세요.

## 접속 주소

| 화면 | 주소 |
|---|---|
| Command Center 홈 | http://localhost:5000/ |
| 예약판매 이탈 방지 | http://localhost:5001/savedeal |
| 더 줘 대시보드 | http://localhost:5000/thejo/ (위험 경고 `/thejo/warnings`, 수익 기회 `/thejo/opportunities`) |
| 빅또리출동! | http://localhost:5500/ |
| 통하길 스튜디오 | http://localhost:5000/studio/ |
| 통하길 QR | 방문객 http://localhost:5000/qr/ · 부스 담당자 http://localhost:5000/qr/staff/ |

## 테스트

저장소 루트에서 실행합니다.

```powershell
python -m unittest thejo_project.tests.test_thejo -v
```

## 다른 컴퓨터끼리는 연결되지 않아요
`localhost`는 **"지금 이 컴퓨터"**라는 뜻입니다. 각자 `git pull` 받아서 **자기 컴퓨터에서 `start_all`로 모두 켜고** 테스트하세요. 시연도 **노트북 한 대**에서 합니다.

## 규칙
다른 팀원의 폴더는 주인의 동의 없이 수정하지 않습니다. 자세한 내용은 [CLAUDE.md](CLAUDE.md)를 보세요.
