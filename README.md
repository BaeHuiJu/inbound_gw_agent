<div align="center">

# 📬 inbound_gw_agent

**그룹웨어 인바운드 자동화 에이전트**

Outlook 메일과 Teams 메시지를 LLM으로 분류하고 Jira 티켓을 자동 생성합니다.

[![Python](https://img.shields.io/badge/Python-3.11%2B-3776AB?style=flat-square&logo=python&logoColor=white)](https://www.python.org/)
[![FastAPI](https://img.shields.io/badge/FastAPI-0.111-009688?style=flat-square&logo=fastapi&logoColor=white)](https://fastapi.tiangolo.com/)
[![Ollama](https://img.shields.io/badge/Ollama-llama3.2-black?style=flat-square)](https://ollama.com/)
[![Jira](https://img.shields.io/badge/Jira-Cloud%2FServer-0052CC?style=flat-square&logo=jira&logoColor=white)](https://www.atlassian.com/software/jira)
[![License](https://img.shields.io/badge/License-MIT-green?style=flat-square)](LICENSE)

[빠른 시작](#-빠른-시작) ◆ [아키텍처](#-아키텍처) ◆ [대시보드](#-대시보드) ◆ [API](#-webhook-api) ◆ [설정](#-환경변수-설정)

</div>

---

## 🆕 최신 업데이트

- **[2026/05]** 대시보드 테이블 헤더 클릭 정렬 (asc/desc) 기능 추가
- **[2026/05]** Jira 스토리 생성 시 레이블·기한·시작일·우선순위·제목 직접 입력 지원
- **[2026/05]** 메일 삭제 기능 추가 (행별 삭제 + 상세 패널 삭제)
- **[2026/05]** 리포트 뷰 F5 새로고침 시 현재 탭 유지
- **[2026/05]** Microsoft Graph API 기반 Outlook 메일 자동 수집

---

## 💡 왜 inbound_gw_agent인가?

하루에도 수십 통 쏟아지는 업무 메일, 매번 수동으로 Jira에 등록하고 계신가요?

| 기존 방식 | inbound_gw_agent |
|-----------|-----------------|
| 메일 확인 → 수동 티켓 생성 | 수신 즉시 LLM 분류 → 원클릭 티켓 생성 |
| 긴급/일반 메일 구분 어려움 | 규칙 + LLM 이중 분류로 정확도 향상 |
| Jira 등록 누락 위험 | 미처리 메일 실시간 알림 |
| 분류 기준이 사람마다 달라짐 | 일관된 규칙 기반 분류 |

---

## ⚡ 빠른 시작

**2분 안에 서버를 실행해보세요.**

### 1. 설치

```powershell
git clone https://github.com/BaeHuiJu/inbound_gw_agent.git
cd inbound_gw_agent
python -m venv .venv
.venv\Scripts\pip install -r requirements.txt
```

### 2. 환경 설정

```powershell
copy .env.example .env
# .env 파일을 열어 Jira / Ollama 설정 입력
```

### 3. 서버 실행

```powershell
.venv\Scripts\python.exe -m inbound_gw_agent
```

### 4. 대시보드 접속

브라우저에서 `http://localhost:5000/dashboard` 를 엽니다.

### 5. 테스트 메시지 전송

```powershell
Invoke-RestMethod -Uri http://localhost:5000/webhook/message `
  -Method Post -ContentType "application/json; charset=utf-8" `
  -Body '{"source":"outlook","sender":"test@test.com","subject":"서버 장애","body":"접속이 안 됩니다"}'
```

> **사전 요구사항**: Python 3.11+, [Ollama](https://ollama.com/) (`ollama pull llama3.2`), Jira 계정

---

## 🏗️ 아키텍처

```
┌─────────────────────────────────────────────────────────┐
│                    외부 트리거                            │
│  Power Automate (Outlook) ──┐                            │
│  Power Automate (Teams)  ───┼─→ POST /webhook/message   │
│  Microsoft Graph API     ───┘   (자동 수집)              │
└──────────────────────┬──────────────────────────────────┘
                       │ ngrok HTTPS 터널
┌──────────────────────▼──────────────────────────────────┐
│              FastAPI 서버 (localhost:5000)               │
│                                                         │
│   webhook_receiver.py                                   │
│   ├── /webhook/message    ← 메시지 수신                  │
│   ├── /dashboard          ← 실시간 대시보드              │
│   └── /report             ← 기간별 리포트               │
└──────────────────────┬──────────────────────────────────┘
                       │
┌──────────────────────▼──────────────────────────────────┐
│                Pipeline.process_message()               │
│                                                         │
│  1. StateStore.is_processed?  → 중복이면 건너뜀         │
│  2. RuleClassifier            → 신뢰도 ≥ 0.8 시 완료   │
│  3. LLMClassifier (Ollama)    → 규칙 미충족 시 fallback │
│  4. JiraTicketHandler         → 자동/수동 티켓 생성      │
│  5. StateStore.mark_processed → SQLite에 이력 저장      │
└─────────────────────────────────────────────────────────┘
```

---

## 📂 파일 구조

```
inbound_gw_agent/
├── __main__.py              # uvicorn 서버 진입점
├── config.py                # pydantic-settings (.env 로드)
├── pipeline.py              # 분류 → 처리 → 저장 오케스트레이션
├── connectors/
│   ├── webhook_receiver.py  # FastAPI 앱 + 대시보드 HTML (단일 파일)
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

## 🖥️ 대시보드

`http://localhost:5000/dashboard` 에서 아래 기능을 사용할 수 있습니다.

### 오늘의 수신 현황

| 기능 | 설명 |
|------|------|
| 실시간 목록 | 메일/Teams 수신 메시지, 30초 자동 갱신 |
| 컬럼 정렬 | 헤더 클릭 → ▲/▼ 정렬 토글 |
| 메시지 검색 | 제목·발신자 실시간 필터 |
| 분류 필터 | 긴급/작업/문의/프로젝트/개인/정보 |
| 메일 삭제 | 행별 🗑 또는 상세 패널에서 삭제 |

### Jira 연동

| 기능 | 설명 |
|------|------|
| 티켓 생성 | 분류에 따라 Bug/Task 자동 매핑 |
| 스토리 생성 | 팀명·M/D·레이블·기한·시작일·우선순위 입력 |
| LLM 자동 분석 | 메일에서 팀·기한·핵심 업무 자동 추출 |

### 리포트 (`/report`)

- 기간별 수신 현황 및 Jira 등록률
- 팀별 요청 건수 차트
- 기한 초과 티켓 목록
- Jira 스토리 이력 조회

---

## ⚙️ 환경변수 설정

`.env.example`을 복사해 `.env`로 저장 후 입력합니다.

```powershell
copy .env.example .env
```

### 필수 설정

```env
# Jira
JIRA_SERVER=https://yourorg.atlassian.net
JIRA_EMAIL=your-email@company.com
JIRA_API_TOKEN=your-jira-api-token
JIRA_PROJECT_KEY=PROJ

# Microsoft Graph API (메일 자동 수집)
AZURE_CLIENT_ID=your-azure-app-client-id
AZURE_TENANT_ID=your-tenant-id
```

### 전체 옵션

| 변수 | 기본값 | 설명 |
|------|--------|------|
| `WEBHOOK_PORT` | `5000` | 서버 포트 |
| `WEBHOOK_SECRET` | (없음) | 웹훅 요청 검증 비밀키 |
| `JIRA_ENABLED` | `true` | Jira 티켓 생성 활성화 |
| `JIRA_AUTO_CREATE` | `false` | 수신 즉시 자동 생성 |
| `JIRA_STORY_EPIC_KEY` | — | 스토리 연결 Epic 키 (예: GW-5) |
| `JIRA_STORY_SPRINT_NAME` | — | 스프린트 이름 |
| `JIRA_ACCOUNT_ID` | — | 담당자·보고자 Jira 계정 ID |
| `OLLAMA_BASE_URL` | `http://localhost:11434` | Ollama 서버 URL |
| `OLLAMA_MODEL` | `llama3.2` | LLM 모델명 |
| `USER_NAME` | — | 담당자 이름 |
| `USER_EMAIL` | — | 개인 메일 필터링 이메일 |
| `USER_KEYWORDS` | — | 개인 관련 키워드 (쉼표 구분) |
| `RULE_CONFIDENCE_THRESHOLD` | `0.8` | 규칙 분류기 신뢰도 임계값 |

---

## 🔐 Microsoft Graph 인증

서버 최초 실행 시 Device Code Flow로 인증합니다.

```
To sign in, use a web browser to open the page https://login.microsoft.com/device
and enter the code XXXXXXXX to authenticate.
```

1. `https://login.microsoft.com/device` 접속
2. 터미널에 출력된 코드 입력 후 회사 계정으로 로그인
3. 인증 완료 시 `.token_cache.bin`에 저장 → 이후 자동 인증

> `.token_cache.bin` 삭제 시 재인증 필요합니다.

---

## 🌐 Webhook API

### POST `/webhook/message`

수신 메시지를 파이프라인에 전달합니다.

```json
{
  "source": "outlook",
  "sender": "user@company.com",
  "subject": "제목 (선택)",
  "body": "메시지 본문",
  "received_at": "2026-05-14T10:00:00Z"
}
```

- `source`: `"outlook"` 또는 `"teams"`
- `WEBHOOK_SECRET` 설정 시 헤더에 `X-Webhook-Secret: {secret}` 필요

### 의도 분류 결과

| 분류 | Jira 이슈 타입 | 우선순위 |
|------|---------------|----------|
| `urgent` | Bug | Highest |
| `task` | Task | High |
| `inquiry` | Task | Medium |
| `project` | Task | High |
| `personal` | — | — |
| `info` | — | — |

---

## 🔗 ngrok + Power Automate 연동

### ngrok 설치 및 실행

```powershell
winget install ngrok.ngrok
ngrok http 5000
# → https://xxxx.ngrok-free.app
```

### Outlook 플로우 (Power Automate)

1. 트리거: **새 이메일이 도착하면(V3)**
2. 작업: **HTTP POST** → `https://xxxx.ngrok-free.app/webhook/message`
3. 본문:
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

위와 동일하되 `"source": "teams"` 로 변경합니다.

---

## 🛠️ 개발

```powershell
# 테스트 실행
.venv\Scripts\pytest

# 커버리지 포함
.venv\Scripts\pytest --cov=inbound_gw_agent --cov-report=term-missing

# 서버 재시작 (한 줄)
$p = (netstat -ano | Select-String ":5000\s.*LISTENING" | Select-Object -First 1).ToString().Trim() -split "\s+" | Select-Object -Last 1; if ($p) { Stop-Process -Id $p -Force }; Start-Sleep -Seconds 1; .venv\Scripts\python.exe -m inbound_gw_agent
```

---

## 🤝 기여하기

기여를 환영합니다! 아래 영역에서 개선이 가능합니다.

- 새로운 분류 규칙 추가 (`classifier/rule_classifier.py`)
- 다른 이슈 트래커(GitHub Issues, Linear 등) 핸들러 추가
- 대시보드 UI 개선
- 테스트 커버리지 확대

---

## 📄 라이선스

[MIT](LICENSE) © 2026 BaeHuiJu
