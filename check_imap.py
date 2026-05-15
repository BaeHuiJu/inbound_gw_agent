"""IMAP 연결 진단 스크립트 — python check_imap.py"""
import imaplib
import os
import sys

# Windows 콘솔 UTF-8 출력
if sys.platform == "win32":
    sys.stdout.reconfigure(encoding="utf-8")

from dotenv import load_dotenv
load_dotenv()

server   = os.getenv("IMAP_SERVER", "outlook.office365.com")
port     = int(os.getenv("IMAP_PORT", "993"))
username = os.getenv("IMAP_USERNAME", "")
password = os.getenv("IMAP_PASSWORD", "")

print(f"서버  : {server}:{port}")
print(f"계정  : {username}")
print(f"비번  : {'*' * len(password)} ({len(password)}자)")
print()

# 1단계 - TCP 연결
try:
    imap = imaplib.IMAP4_SSL(server, port)
    print("[OK] 1단계: TCP/SSL 연결 성공")
except Exception as e:
    print(f"[FAIL] 1단계: TCP/SSL 연결 실패 - {e}")
    print("   -> 네트워크 또는 방화벽 문제")
    raise SystemExit(1)

# 2단계 - CAPABILITY 확인
_, caps = imap.capability()
cap_str = caps[0].decode() if caps else ""
print(f"   서버 기능: {cap_str}")
if "AUTH=PLAIN" in cap_str or "AUTH=LOGIN" in cap_str:
    print("[OK] 기본 인증(Basic Auth) 지원 확인")
else:
    print("[WARNING] 기본 인증이 목록에 없음 - 조직이 Basic Auth를 비활성화했을 가능성 높음")

# 3단계 - 로그인
print()
try:
    imap.login(username, password)
    print("[OK] 2단계: 로그인 성공!")
    _, folders = imap.list()
    print("   사서함 폴더 목록:")
    for f in (folders or [])[:5]:
        print(f"     {f.decode('utf-8', errors='replace')}")
    imap.logout()
except imaplib.IMAP4.error as e:
    err = str(e)
    print(f"[FAIL] 2단계: 로그인 실패 - {err}")
    print()
    if "LOGIN failed" in err or "Authentication" in err:
        print("=== 원인 가능성 ===")
        print("  A) 조직이 기본 인증(Basic Auth)을 차단함  <- Microsoft 365 가장 흔함")
        print("  B) 비밀번호 오류")
        print("  C) MFA 계정 - 앱 비밀번호 필요")
        print()
        print("=== 확인 방법 ===")
        print("  1. https://outlook.office.com 에서 직접 로그인 확인")
        print("  2. MFA 사용 중이면 앱 비밀번호 생성:")
        print("     account.microsoft.com -> 고급 보안 -> 앱 비밀번호")
        print("  3. 위 방법 모두 안되면 IT관리자에게 IMAP 기본 인증 허용 요청")
