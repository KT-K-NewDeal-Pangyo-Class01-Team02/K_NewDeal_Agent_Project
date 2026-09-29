# 통하길 스튜디오 (이승현)

행사 홍보 포스터를 채팅으로 요청하면 n8n이 이미지를 만들고, 구글 드라이브 폴더의 포스터를 갤러리로 보여 줍니다.
Command Center 홈(저장소 루트의 `command_center/`)에서 카드를 누르면 새 탭으로 열립니다. → http://localhost:5004

```
tonghagil_studio/
  app.py          화면·API (포스터 생성/목록/수정/삭제, 드라이브 이미지 프록시)
  layout.py       사이드바·상단 바 (디자인은 허브와 같은 모양의 사본, 에이전트 목록만 허브의 agents.json 을 읽음)
  n8n_client.py   n8n 호출
  drive_store.py  구글 드라이브 폴더 갤러리
  poster_store.py 요청 기록(posters.json) / 샘플 포스터
```

## 실행

- 전체를 켤 때: 저장소 루트의 **`start_all.bat`**을 쓰세요.
- 스튜디오만 켤 때: `tonghagil_studio/app.py`를 열고 VS Code ▶를 누르거나, 이 폴더에서 아래를 실행하세요.
  ```powershell
  pip install -r requirements.txt     # 처음 한 번
  copy .env.example .env              # 처음 한 번, 값 채우기
  python -m tonghagil_studio.app
  ```

## 통하길 스튜디오 ↔ n8n 연결

`.env` 의 `N8N_WEBHOOK_URL` 이 비어 있으면 **데모 모드**(샘플 포스터 생성)로 동작합니다.

1. n8n의 **When chat message received** 노드에서 `Make Chat Publicly Available` 을 켜고,
   `Authentication: None`, `Response Mode: When Last Node Finishes` 로 둡니다.
2. 노드에 표시된 **Chat URL** 을 `.env` 의 `N8N_WEBHOOK_URL` 에 넣습니다.
3. 워크플로를 **Active** 로 바꿉니다. (테스트 URL `/webhook-test/...` 는 에디터에서 실행 대기 중일 때만 동작)
4. 마지막 노드(Edit Fields)가 드라이브 공유 링크 또는 파일 ID를 내보내면 됩니다. 필드 이름은 상관없습니다.

스튜디오는 `chatInput`(설명 + 스타일 + 행사 유형)을 보내고, 응답에서 드라이브 링크를 찾아
갤러리에 보여 줍니다. 요청 기록(제목·행사 유형·요청 문구)은 `tonghagil_studio/data/posters.json` 에 쌓입니다.

## 갤러리 ↔ 구글 드라이브 폴더 연결 (서비스 계정)

`.env` 의 `DRIVE_FOLDER_ID` 가 비어 있으면 샘플 포스터를 보여 줍니다. 설정하면 **그 폴더의 이미지**를 최신순으로 보여 줍니다.

1. [Google Cloud 콘솔](https://console.cloud.google.com/) → 새 프로젝트 만들기
2. **API 및 서비스 → 라이브러리** → `Google Drive API` 검색 → **사용**
3. **IAM 및 관리자 → 서비스 계정 → 서비스 계정 만들기** (이름만 넣고, 역할은 비워 둔 채 완료)
4. 만든 서비스 계정 → **키 → 키 추가 → 새 키 만들기 → JSON** → 파일이 다운로드됨
5. 그 파일을 `tonghagil_LEESEUNGHYUN/credentials/service-account.json` 으로 저장
   (`credentials/` 는 `.gitignore` 에 있어서 GitHub 에 올라가지 않습니다. **절대 커밋·공유 금지**)
6. 구글 드라이브에서 n8n이 이미지를 올리는 폴더 → **공유** → 서비스 계정 이메일
   (`…@….iam.gserviceaccount.com`, 키 파일의 `client_email`) 을 **편집자**로 추가 ("이메일 알림 보내기" 체크 해제)
   (보기만 할 거면 뷰어도 되지만, 스튜디오에서 정보 수정·삭제를 하려면 편집자여야 합니다)
7. `.env` 에 폴더 ID(또는 폴더 주소 전체) 입력 후 서버 재시작
   ```
   DRIVE_FOLDER_ID=https://drive.google.com/drive/folders/1AbCdEf...
   ```

- 갤러리 제목 옆 배지가 **구글 드라이브** 로 바뀌면 연결된 것입니다. 오류가 나면 갤러리에 원인이 표시됩니다.
- 목록은 60초 동안 캐시합니다(`DRIVE_CACHE_SECONDS`). 갤러리의 **새로고침(↻)** 버튼은 바로 다시 읽습니다.
- 이미지는 Flask 가 서비스 계정으로 받아서 대신 보여 주므로(`/drive-image/<ID>`) 비공개 파일도 보입니다.
  썸네일은 `tonghagil_studio/data/drive_cache/` 에 저장해 두고 재사용합니다.
- 파일 이름을 `행사유형_제목_날짜.png` (예: `축제_한강 불꽃축제_20261003.png`) 로 저장하면 행사 유형과 제목이 자동으로 붙습니다.
  스튜디오에서 요청한 포스터는 요청할 때 입력한 제목·행사 유형이 우선합니다.

### 갤러리에서 수정 · 삭제 (카드의 `⋯` 메뉴)
- **정보 수정**: 제목·행사 유형을 바꾸면 드라이브 파일 이름도 `행사유형_제목_날짜.png` 로 실제로 바뀝니다.
- **삭제**: 파일을 드라이브 폴더 안 **`_보관함`** 하위 폴더로 옮깁니다(처음 삭제할 때 자동 생성).
  파일 소유자가 아니면 휴지통으로 보낼 수 없어서(구글 드라이브 규칙) 이렇게 처리합니다.
  되돌리려면 드라이브에서 `_보관함` 의 파일을 원래 폴더로 옮기면 되고, 완전히 지우려면 드라이브에서 직접 삭제하세요.
- 수정·삭제 메뉴는 드라이브 포스터에만 보입니다(샘플·데모 포스터 제외).
