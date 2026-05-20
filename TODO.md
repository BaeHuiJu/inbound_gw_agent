# 개발 우선 처리 목록

코드 리뷰(2026-05-20) 결과 도출된 필수 처리 항목입니다.

---

## 1. ✅ 대시보드 API 인증 추가 (완료)
**심각도:** Must / 보안  
**파일:** `connectors/webhook_receiver.py`, `config.py`  
**내용:** `/dashboard/*`, `/report/*` 전체 엔드포인트에 인증 없음.  
ngrok으로 외부 노출 시 누구나 메일 본문·발신자 정보에 접근 가능.  
**해결:** HTTP Basic Auth 의존성 추가. `.env`에 `DASHBOARD_SECRET` 설정 시 활성화.

---

## 2. ✅ 웹훅 시크릿 타이밍 공격(Timing Attack) 방어 (완료)
**심각도:** Must / 보안  
**파일:** `connectors/webhook_receiver.py:3247`  
**내용:** 문자열 `!=` 비교는 일치하지 않는 첫 문자에서 즉시 반환 → 타이밍 공격 취약.  
**해결:**
```python
# 현재
if x_webhook_secret != settings.webhook_secret:

# 개선
if not hmac.compare_digest(x_webhook_secret or "", settings.webhook_secret):
```

---

## 3. ✅ SQLite 멀티스레드 안전성 확보 (완료)
**심각도:** Must / 데이터 정합성  
**파일:** `state/store.py:32`  
**내용:** `check_same_thread=False` 상태에서 `asyncio.to_thread`(Jira) 등이 동시에 DB에 접근 가능.  
**해결:** `threading.Lock`으로 DB 접근 보호 또는 `aiosqlite` 전환.

---

## 4. 이메일 ID 생성 로직 통일
**심각도:** Must / 버그  
**파일:** `__main__.py`, `connectors/webhook_receiver.py`  
**내용:** 동일 메일이 Graph API 수집과 webhook 양쪽으로 들어올 때 ID가 달라 중복 처리됨.
```python
# __main__.py
raw_id = f"{received_at.isoformat()}|{subject}|{body[:50]}"

# webhook_receiver.py
raw_id = f"{payload.sender}|{received_at.isoformat()}|{payload.body[:50]}"
```
**해결:** ID 생성 로직을 공통 유틸 함수로 분리하여 일관성 확보.

---

## 5. `/dashboard/settings` 입력값 검증
**심각도:** Must / 보안  
**파일:** `connectors/webhook_receiver.py`  
**내용:** `USER_NAME`/`USER_KEYWORDS` 값에 줄바꿈 문자 포함 시 `.env` 파싱 깨짐.  
**해결:**
```python
"USER_NAME": payload.user_name.replace("\n", "").replace("\r", ""),
"USER_KEYWORDS": payload.user_keywords.replace("\n", "").replace("\r", ""),
```

---

## 6. ✅ 마이그레이션 `OperationalError` 조용히 무시 개선 (완료)
**심각도:** Must / 안정성  
**파일:** `state/store.py`  
**내용:** `OperationalError`는 "column already exists" 외에도 다양한 원인 발생 가능.  
**해결:** `PRAGMA table_info()`로 컬럼 존재 여부 사전 확인 후 `ALTER TABLE` 실행.

---

## Should (추가 개선 권장)

| # | 파일 | 내용 |
|---|------|------|
| S1 | `__main__.py` | `asyncio.create_task()` 이벤트 루프 시작 전 호출 위험 |
| S2 | `webhook_receiver.py` | `pipeline._store`, `pipeline._handler` 직접 접근 — 캡슐화 위반 |
| S3 | `webhook_receiver.py` | 파일 3,000줄 초과 — HTML 인라인 템플릿 분리 |
| S4 | `webhook_receiver.py` | `fetchall()` 무제한 — 대량 데이터 시 메모리 문제 |
| S5 | `webhook_receiver.py` | `JIRA_BASE` URL이 JavaScript에 하드코딩 |
| S6 | `llm_classifier.py` | `confidence` 값 0~1 클램핑 없음 |
| S7 | `llm_classifier.py` | 비탐욕 JSON 정규식으로 중첩 JSON 파싱 실패 가능 |
| S8 | `llm_classifier.py` | Ollama 연결 타임아웃 없음 |
| S9 | `ticket_handler.py` | Jira 연결 실패 시 예외 처리 없음 |
| S10 | `ticket_handler.py` | `import json` 메서드 내부 반복 임포트 |
| S11 | `ticket_handler.py` | 메일 본문 전체 Jira 설명 포함 — 길이 제한 필요 |
| S12 | 전체 | 민감정보(토큰, 자격증명)가 로그에 노출 가능 |
| S13 | 전체 | 테스트 코드 없음 |
