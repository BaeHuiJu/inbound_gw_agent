# inbound_gw_agent

그룹웨어 인바운드 자동화 에이전트.  
Outlook 메일 / Teams 메시지를 수신하여 LLM으로 분류하고, Jira 티켓을 자동 생성합니다.

---

## 주요 기능

- **메일 자동 수집** — Microsoft Graph API (MSAL Device Code Flow)
- **웹훅 수신** — Power Automate → FastAPI 엔드포인트
- **의도 분류** — 규칙(키워드/regex) → Ollama LLM 순차 처리
- **Jira 연동** — 티켓(Bug/Task) 및 스토리 자동/수동 생성
- **대시보드** — 실시간 수신 현황, 분류 통계, 리포트, 테이블 정렬·삭제

---

## 아키텍처

```
Power Automate (클라우드)
  ├── Outlook 트리거 → POST /webhook/message
  └── Teams 트리거  → POST /webhook/message
          ↓ (ngrok HTTPS 터널)
  FastAPI 서버 (localhost:5000)
          ↓
  Pipeline.process_message()
    → StateStore.is_processed?  → 중복이면 건너뜀
    → RuleClassifier  (신뢰도 ≥ 0.8 → 완료)
    → LLMClassifier   (Ollama fallback)
    → JiraTicketHandler (선택적 자동 생성)
    → StateStore.mark_processed
```

---

## 파일 구조

```
inbound_gw_agent/
├── __main__.py              # uvicorn 서버 진입점
├── config.py                # pydantic-settings (.env 로드)
├── pipeline.py              # 분류 → 처리 → 저장 오케스트레이션
├── connectors/
│   ├── webhook_receiver.py  # FastAPI 앱 + 대시보드 HTML
│   ├── graph_client.py      # Microsoft Graph API 클라이언트
│   └── outlook_reader.py    # Outlook 메일 수집
├── classifier/
│   ├── rule_classifier.py   # 키워드/regex 규칙 기반 분류
│   └── llm_classifier.py    # Ollama 비동기 LLM 분류
├── handlers/
│   └── ticket_handler.py    # Jira 티켓/스토리 생성
├── state/
│   └── store.py             # SQLite 처리 이력 관리
└── utils/
    └── retry.py
```

---

## 설치

```powershell
python -m venv .venv
.venv\Scripts\pip install -r requirements.txt
```

---

## 환경 변수 설정

`.env.example`을 복사하여 `.env`로 저장 후 값을 채웁니다.

```powershell
copy .env.example .env
```

| 변수 | 기본값 | 설명 |
|------|--------|------|
| `WEBHOOK_PORT` | `5000` | 서버 포트 |
| `WEBHOOK_SECRET` | (없음) | 웹훅 요청 검증 비밀키 (선택) |
| `JIRA_ENABLED` | `true` | Jira 티켓 생성 활성화 |
| `JIRA_AUTO_CREATE` | `false` | 수신 즉시 자동 생성 여부 |
| `JIRA_SERVER` | — | Jira 서버 URL |
| `JIRA_EMAIL` | — | Jira 로그인 이메일 |
| `JIRA_API_TOKEN` | — | Jira API 토큰 |
| `JIRA_PROJECT_KEY` | — | Jira 프로젝트 키 |
| `JIRA_STORY_EPIC_KEY` | — | 스토리 연결 Epic 키 (예: GW-5) |
| `JIRA_STORY_SPRINT_NAME` | — | 스프린트 이름 |
| `JIRA_ACCOUNT_ID` | — | 담당자·보고자용 Jira 계정 ID |
| `OLLAMA_BASE_URL` | `http://localhost:11434` | Ollama 서버 URL |
| `OLLAMA_MODEL` | `llama3.2` | LLM 모델명 |
| `AZURE_CLIENT_ID` | — | Azure AD 앱 클라이언트 ID |
| `AZURE_TENANT_ID` | `common` | Azure AD 테넌트 ID |
| `USER_NAME` | — | 담당자 이름 (스토리 설명 자동 기입) |
| `USER_EMAIL` | — | 개인 메일 필터링용 이메일 |
| `USER_KEYWORDS` | — | 개인 관련 키워드 (쉼표 구분) |
| `RULE_CONFIDENCE_THRESHOLD` | `0.8` | 규칙 분류기 신뢰도 임계값 |

---

## 서버 실행

```powershell
.venv\Scripts\python.exe -m inbound_gw_agent
```

### 서버 재시작 (한 줄)

```powershell
$p = (netstat -ano | Select-String ":5000\s.*LISTENING" | Select-Object -First 1).ToString().Trim() -split "\s+" | Select-Object -Last 1; if ($p) { Stop-Process -Id $p -Force }; Start-Sleep -Seconds 1; .venv\Scripts\python.exe -m inbound_gw_agent
```

---

## Microsoft Graph 인증 (최초 1회)

서버 최초 실행 시 터미널에 아래 메시지가 출력됩니다.

```
To sign in, use a web browser to open the page https://login.microsoft.com/device
and enter the code XXXXXXXX to authenticate.
```

1. 브라우저에서 `https://login.microsoft.com/device` 접속
2. 출력된 코드 입력 후 회사 계정으로 로그인
3. 인증 완료 시 `.token_cache.bin`에 토큰 저장 → 이후 자동 인증

---

## 대시보드

서버 실행 후 브라우저에서 접속합니다.

- **대시보드**: `http://localhost:5000/dashboard`
- **리포트**: `http://localhost:5000/report`

### 주요 기능

| 기능 | 설명 |
|------|------|
| 실시간 수신 현황 | 메일/Teams 메시지 목록, 분류·중요도·카테고리 표시 |
| 테이블 정렬 | 컬럼 헤더 클릭 → ▲/▼ asc/desc 정렬 |
| 메일 삭제 | 행별 🗑 버튼 또는 상세 패널에서 삭제 |
| Jira 티켓 생성 | 메일 선택 후 수동 티켓 생성 |
| Jira 스토리 생성 | 팀·업무·M/D·레이블·기한·시작일·우선순위 입력 후 생성 |
| 리포트 | 기간별 수신 현황, Jira 등록률, 기한 초과 티켓 현황 |

---

## Webhook API

**POST `/webhook/message`**

```json
{
  "source": "outlook",
  "sender": "user@company.com",
  "subject": "제목 (선택)",
  "body": "메시지 본문",
  "received_at": "2026-05-14T10:00:00Z"
}
```

`WEBHOOK_SECRET` 설정 시 헤더 `X-Webhook-Secret: {secret}` 필요.

### 테스트

```powershell
Invoke-RestMethod -Uri http://localhost:5000/webhook/message `
  -Method Post -ContentType "application/json; charset=utf-8" `
  -Body '{"source":"outlook","sender":"test@test.com","subject":"서버 오류","body":"접속이 안 됩니다"}'
```

---

## ngrok 연동

Power Automate에서 로컬 서버로 요청을 보내려면 ngrok으로 외부 URL을 발급합니다.

```powershell
winget install ngrok.ngrok
ngrok http 5000
# → https://xxxx.ngrok-free.app 형태의 URL 발급
```

---

## Power Automate 플로우 설정

### Outlook 플로우

1. 트리거: **새 이메일이 도착하면(V3)**
2. 작업: **HTTP**
   - 메서드: `POST`
   - URI: `https://xxxx.ngrok-free.app/webhook/message`
   - 헤더: `Content-Type: application/json`
   - 본문:
     ```json
     {
       "source": "outlook",
       "sender": "@{triggerBody()?['from']?['emailAddress']?['address']}",
       "subject": "@{triggerBody()?['subject']}",
       "body": "@{triggerBody()?['body']?['content']}",
       "received_at": "@{triggerBody()?['receivedDateTime']}"
     }
     ```

### Teams 플로우

1. 트리거: **채널에 새 메시지가 게시됨**
2. 작업: **HTTP** (위와 동일, `source`를 `"teams"`로 변경)

---

## 개발

```powershell
# 테스트 실행
.venv\Scripts\pytest

# 커버리지 포함
.venv\Scripts\pytest --cov=inbound_gw_agent --cov-report=term-missing
```

---

## 라이선스

MIT
