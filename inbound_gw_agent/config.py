from functools import lru_cache
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    # Webhook 서버
    webhook_host: str = "0.0.0.0"
    webhook_port: int = 8000
    webhook_secret: str = ""           # Power Automate 요청 검증용 (선택)
    dashboard_secret: str = ""         # 대시보드/리포트 HTTP Basic Auth 비밀번호 (선택, 설정 시 인증 활성화)

    # Jira
    jira_enabled: bool = True       # Jira 연결 활성화 (수동 생성 가능)
    jira_auto_create: bool = False  # True 시 수신 즉시 자동 생성
    jira_server: str = ""
    jira_email: str = ""
    jira_api_token: str = ""
    jira_project_key: str = ""
    jira_story_epic_key: str = ""       # 스토리 Epic Key (예: GW-5)
    jira_story_sprint_name: str = ""    # 스프린트 이름 (예: 2026 디지털혁신본부 업무)
    jira_account_id: str = ""           # Jira 로그인 ID (Server) 또는 accountId (Cloud) — 담당자·보고자용

    # Ollama
    ollama_base_url: str = "http://localhost:11434"
    ollama_model: str = "llama3.2"

    # Personal email classification
    user_name: str = ""        # 예: 홍길동
    user_email: str = ""       # 예: hong@mastern.co.kr
    user_keywords: str = ""    # 쉼표 구분, 예: IT인프라,서버,보안,장애

    # Agent behavior
    rule_confidence_threshold: float = 0.8
    state_db_path: str = "state.db"
    poll_interval_seconds: int = 300  # Outlook COM 폴링 간격 (초), 기본 5분

    # Microsoft Graph API (메일 자동 수집용)
    azure_client_id: str = ""
    azure_tenant_id: str = "common"
    token_cache_path: str = ".token_cache.bin"

    model_config = SettingsConfigDict(env_file=".env", env_file_encoding="utf-8")


@lru_cache
def get_settings() -> Settings:
    return Settings()
