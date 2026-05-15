"""IMAP 연결 테스트 — Exchange Online (outlook.office365.com)"""
import imaplib
import getpass
import sys

EMAIL = "huiju@mastern.co.kr"
IMAP_HOST = "outlook.office365.com"
IMAP_PORT = 993

print(f"\nIMAP 테스트: {EMAIL} @ {IMAP_HOST}:{IMAP_PORT}")
print("비밀번호 입력 (화면에 표시 안 됨):")
password = getpass.getpass("> ")

try:
    mail = imaplib.IMAP4_SSL(IMAP_HOST, IMAP_PORT)
    print("  [OK] 서버 연결 성공")
except Exception as e:
    print(f"  [FAIL] 서버 연결 실패: {e}")
    sys.exit(1)

try:
    mail._encoding = "utf-8"  # 한글/특수문자 비밀번호 지원
    mail.login(EMAIL, password)
    print("  [OK] 로그인 성공!")
except imaplib.IMAP4.error as e:
    print(f"  [FAIL] 로그인 실패: {e}")
    print("\n  → 회사 계정은 '앱 비밀번호'가 필요할 수 있습니다.")
    print("  → Microsoft 365 관리자가 IMAP/기본인증을 막았을 수 있습니다.")
    try: mail.logout()
    except: pass
    sys.exit(1)

try:
    mail.select("INBOX")
    status, data = mail.search(None, "ALL")
    count = len(data[0].split()) if data[0] else 0
    print(f"  [OK] 받은편지함 접근 성공 — 총 {count}개 메일")
    mail.logout()
    print("\n결과: IMAP 사용 가능!\n")
except Exception as e:
    print(f"  [FAIL] 메일박스 접근 실패: {e}")
    sys.exit(1)
