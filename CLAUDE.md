# CLAUDE.md

이 파일은 Claude Code(claude.ai/code)가 이 저장소에서 작업할 때 참고하는 안내 문서입니다.

## 프로젝트 개요

Python 기반 그룹웨어 인바운드 자동화 에이전트.
- **수신 방식**: Microsoft Graph API(시작 시 자동 수집) + webhook
- **메시지 출처**: Outlook 메일 + Teams 메시지
- **처리**: 규칙(키워드/regex) → Ollama LLM 순으로 의도 분류 → Jira 티켓 생성(옵션)
- **대시보드**: `http://localhost:5000/dashboard`

## 서버 시작 / 재시작

```powershell
# 가상환경 없을 때 최초 1회
python -m venv .venv
.venv\Scripts\pip install -r requirements.txt

# 서버 시작
cd D:\inbound_gw_agent
.venv\Scripts\python.exe -m inbound_gw_agent
```

### 서버 재시작 (한 줄 명령어)

```powershell
# 포트 5000 프로세스 종료 후 재시작 (PowerShell)
$p = (netstat -ano | Select-String ":5000\s.*LISTENING" | Select-Object -First 1).ToString().Trim() -split "\s+" | Select-Object -Last 1; if ($p) { Stop-Process -Id $p -Force }; Start-Sleep -Seconds 1; cd D:\inbound_gw_agent; .venv\Scripts\python.exe -m inbound_gw_agent
```

단계별로 실행할 경우:

```powershell
# 1. 실행 중인 서버 종료
$p = (netstat -ano | Select-String ":5000\s.*LISTENING" | Select-Object -First 1).ToString().Trim() -split "\s+" | Select-Object -Last 1
Stop-Process -Id $p -Force

# 2. 서버 재시작
cd D:\inbound_gw_agent
.venv\Scripts\python.exe -m inbound_gw_agent
```

> **주요 옵션 변경 예시 (.env)**
> ```env
> JIRA_ENABLED=false   # Jira 티켓 생성 비활성화
> JIRA_ENABLED=true    # Jira 티켓 생성 활성화
> WEBHOOK_PORT=5000    # 서버 포트 변경
> ```
> `.env` 수정 후 반드시 재시작해야 반영됩니다.

### Microsoft Graph 인증 (최초 1회만)

서버 최초 실행 시 터미널에 아래와 같은 메시지가 출력됩니다:

```
To sign in, use a web browser to open the page https://login.microsoft.com/device
and enter the code XXXXXXXX to authenticate.
```

1. 브라우저에서 `https://login.microsoft.com/device` 접속
2. 출력된 코드 입력 후 회사 계정으로 로그인
3. 인증 완료 시 토큰이 `.token_cache.bin`에 저장 → 이후 재시작 시 자동 인증

> `.token_cache.bin` 삭제 시 재인증 필요.

## 주요 명령어

```powershell
# 서버 실행
.venv\Scripts\python.exe -m inbound_gw_agent

# ngrok으로 외부 노출 (별도 터미널)
ngrok http 5000

# 테스트 메시지 전송
Invoke-RestMethod -Uri http://localhost:5000/webhook/message `
  -Method Post -ContentType "application/json; charset=utf-8" `
  -Body '{"source":"outlook","sender":"test@test.com","subject":"서버 오류","body":"접속이 안 됩니다"}'

# 대시보드 데이터 확인
Invoke-RestMethod http://localhost:5000/dashboard/data

pytest
```

## 아키텍처

```
Power Automate (클라우드)
  ├── Outlook 트리거 → POST /webhook/message  {"source":"outlook", ...}
  └── Teams 트리거  → POST /webhook/message  {"source":"teams",   ...}
          ↓ (ngrok HTTPS 터널)
  FastAPI 웹훅 서버 (localhost:5000)
          ↓
  Pipeline.process_message()
    → StateStore.is_processed?  → 중복이면 건너뜀
    → RuleClassifier  (신뢰도 ≥ 0.8 → 완료)
    → LLMClassifier   (Ollama fallback)
    → JiraTicketHandler (incident→Bug, inquiry/request→Task)
    → StateStore.mark_processed
```

## 파일 구조

```
inbound_gw_agent/
├── __main__.py              # uvicorn 서버 시작
├── config.py                # pydantic-settings (.env 로드)
├── pipeline.py              # 분류 → 처리 → 저장 오케스트레이션
├── connectors/
│   └── webhook_receiver.py  # FastAPI 앱 + /webhook/message 엔드포인트
├── classifier/
│   ├── rule_classifier.py   # 키워드/regex 규칙 — 빠른 경로
│   └── llm_classifier.py    # Ollama 비동기 클라이언트 — fallback
├── handlers/
│   └── ticket_handler.py    # jira.JIRA → asyncio.to_thread
├── state/
│   └── store.py             # SQLite: 처리 이력 (SHA256 해시 ID 기준)
└── utils/
    └── retry.py
```

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

`WEBHOOK_SECRET` 설정 시 헤더에 `X-Webhook-Secret: {secret}` 필요.

## ngrok 설치 및 실행

```bash
# winget으로 설치
winget install ngrok.ngrok

# 실행 (에이전트와 별도 터미널)
ngrok http 8000
# → https://xxxx.ngrok-free.app 형태의 URL이 발급됨
```

## Power Automate 플로우 설정

### Outlook 플로우
1. 트리거: **"새 이메일이 도착하면(V3)"**
2. 작업: **"HTTP"**
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
1. 트리거: **"채널에 새 메시지가 게시됨"** 또는 **"새 채팅 메시지 수신"**
2. 작업: **"HTTP"** (위와 동일, source를 `"teams"`로 변경)
   ```json
   {
     "source": "teams",
     "sender": "@{triggerBody()?['from']?['user']?['displayName']}",
     "subject": "@{triggerBody()?['channelIdentity']?['channelId']}",
     "body": "@{triggerBody()?['body']?['content']}",
     "received_at": "@{triggerBody()?['createdDateTime']}"
   }
   ```

## 환경변수

| 변수 | 기본값 | 설명 |
|------|--------|------|
| `WEBHOOK_PORT` | `5000` | 서버 포트 |
| `WEBHOOK_SECRET` | (없음) | 웹훅 요청 검증 비밀키 (선택) |
| `JIRA_ENABLED` | `true` | `false`로 설정 시 Jira 티켓 생성 건너뜀 |
| `JIRA_SERVER` | — | Jira 서버 URL |
| `JIRA_EMAIL` | — | Jira 로그인 이메일 |
| `JIRA_API_TOKEN` | — | Jira API 토큰 |
| `JIRA_PROJECT_KEY` | — | Jira 프로젝트 키 |
| `OLLAMA_MODEL` | `llama3.2` | LLM 모델명 |
| `AZURE_CLIENT_ID` | (없음) | Azure AD 앱 클라이언트 ID (Graph API 인증용) |
| `AZURE_TENANT_ID` | `common` | Azure AD 테넌트 ID |
| `RULE_CONFIDENCE_THRESHOLD` | `0.8` | 규칙 분류기 신뢰도 임계값 |
