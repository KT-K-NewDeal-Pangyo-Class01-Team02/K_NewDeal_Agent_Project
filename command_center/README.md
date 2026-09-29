# Command Center 홈 (팀 공용 허브)

에이전트 카드와 사이드바를 보여 주는 홈 화면입니다. → http://localhost:5000
관리는 이승현이 합니다. 팀원은 **자기 에이전트 항목만** 고칩니다 (루트 `CLAUDE.md`의 "공용 허브" 규칙).

## 실행
- 저장소 루트에서 `python -m command_center.app`을 실행하거나, `command_center/app.py`를 열고 VS Code ▶를 누릅니다.
- 전체 실행은 루트의 `start_all.bat`으로 합니다.
- 필요한 패키지: `pip install -r command_center/requirements.txt` (flask, python-dotenv)
- 선택: `command_center/.env`에 `COMMAND_CENTER_PORT=5000`, `CC_USER_NAME=김지현 매니저` 등을 넣을 수 있습니다. git에는 올라가지 않습니다.

## 내 에이전트 등록하기 (`agents.json`)

자기 에이전트 항목 **한 개**만 추가하거나 수정하세요. 홈 카드와 사이드바 메뉴가 자동으로 생깁니다.
홈 화면의 **"새 에이전트 추가"** 카드로 추가해도 같은 파일에 저장됩니다.

```json
{
  "id": "deo-jwo",
  "name": "더 줘",
  "description": "카드에 보일 한두 줄 설명",
  "icon": "coins",
  "color": "blue",
  "status": "운영 중",
  "url": "http://localhost:5173/agents/more"
}
```

| 필드 | 값 |
|---|---|
| `icon` | image, qr-code, calendar-x, coins, headset, sparkles, bot |
| `color` | red, blue, green, purple, orange, teal |
| `status` | 운영 중, 준비 중 |
| `url` | 내 에이전트 주소. **새 탭**으로 열립니다. 비어 있으면 "주소 미등록" 안내가 뜹니다. 포트는 루트 README의 포트 표를 따르세요. |

카드를 등록했으면 루트 `start_all.ps1`의 `$Servers`에도 자기 서버 한 줄을 추가하세요. 그래야 전체 실행 때 같이 켜집니다.
