# 빅또리 (vicDDory) — 옥외 BTL 캠페인 에이전트

직영점이 발의한 옥외 BTL 캠페인을 **3시간 만에 기획**하고, 캠페인이 끝나면 **성과를 환류**하는 콘솔입니다.
Command Center(홈)의 에이전트 중 하나로 붙습니다.

- 담당: 최우용 (GitHub: crwayon)
- 포트: **5500** (Command Center 5000, 통하길 스튜디오 5004)

## 실행

```powershell
# vicDDory_wooyong 폴더에서
pip install -r requirements.txt
copy .env.example .env      # 필요하면 값 수정
python -m vicddory_campaign.app
```

브라우저에서 <http://localhost:5500> 접속.

`.env` 의 `N8N_WEBHOOK_URL` 을 비우면 **데모 모드**로 떠서, n8n 없이 화면 흐름만 확인할 수 있습니다.

## 구조

| 파일 | 역할 |
|---|---|
| `vicddory_campaign/app.py` | Flask 앱, 화면과 `/api/plan` |
| `vicddory_campaign/layout.py` | Command Center 공통 사이드바·상단 바를 붙임 |
| `vicddory_campaign/n8n_client.py` | n8n 웹훅 호출 및 응답 파싱 |
| `vicddory_campaign/templates/campaign.html` | 화면 |
| `vicddory_campaign/static/` | 빅또리 전용 CSS·JS |
| `Outdoor-Public-Relations-Campaign-Agent-main/index.html` | Flask 이전의 초기 프로토타입 (참고용 보관) |

## Command Center 연동

사이드바·상단 바는 이승현님 폴더의 `tonghagil_LEESEUNGHYUN/shared/` 를 **읽어서** 씁니다.
(팀 규칙에 따라 그 폴더의 파일은 수정하지 않습니다.)

Command Center 홈에 빅또리 카드가 뜨려면 `shared/agents.json` 에 아래 항목이 필요합니다.
**이승현님께 추가를 요청해 주세요.**

```json
{
  "id": "vicddory",
  "name": "빅또리",
  "description": "직영점 발의 옥외 BTL 캠페인을 3시간 만에 기획하고 성과를 환류합니다.",
  "icon": "qr-code",
  "color": "orange",
  "status": "운영 중",
  "url": "http://localhost:5500"
}
```

아직 등록 전이라도 빅또리 화면의 사이드바에는 빅또리가 보입니다
(`layout.py` 가 메모리상으로만 한 줄 끼워 넣습니다. 원본 `agents.json` 은 건드리지 않습니다).

## 브라우저 CORS 관련

이전 `index.html` 은 브라우저가 n8n 을 직접 불러서 CORS 에 막힐 수 있었습니다.
지금은 **Flask 서버가 대신 호출**하므로 그 문제가 없습니다.
