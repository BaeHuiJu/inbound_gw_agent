import json

import pytest

from datetime import datetime, timezone

from inbound_gw_agent.handlers.fix_suggester import (
    _fallback,
    _format_similar_cases,
    _looks_like_error,
    _normalize,
    _parse_json_response,
)
from inbound_gw_agent.models.message import InboundMessage, MessageSource
from inbound_gw_agent.state.store import StateStore


# --- _parse_json_response ---

def test_parse_direct_json():
    raw = '{"diagnosis": "DB 연결 풀 고갈", "fix_steps": []}'
    assert _parse_json_response(raw) == {"diagnosis": "DB 연결 풀 고갈", "fix_steps": []}


def test_parse_json_in_markdown_codeblock():
    raw = '설명입니다.\n```json\n{"diagnosis": "메모리 부족"}\n```'
    assert _parse_json_response(raw) == {"diagnosis": "메모리 부족"}


def test_parse_json_with_surrounding_text():
    raw = '분석 결과: {"diagnosis": "타임아웃"} 입니다.'
    assert _parse_json_response(raw) == {"diagnosis": "타임아웃"}


def test_parse_returns_none_when_no_json():
    assert _parse_json_response("JSON 없는 일반 텍스트") is None


# --- _normalize ---

def test_normalize_fills_missing_fields():
    result = _normalize({})
    assert result == {
        "diagnosis": "",
        "fix_steps": [],
        "verification": "",
        "risk": "",
        "reference_note": None,
    }


def test_normalize_string_steps_converted_to_dict():
    result = _normalize({"fix_steps": ["서버 재시작", {"title": "로그 확인", "detail": "tail -f app.log"}]})
    assert result["fix_steps"] == [
        {"title": "조치", "detail": "서버 재시작"},
        {"title": "로그 확인", "detail": "tail -f app.log"},
    ]


def test_normalize_null_string_reference_note_becomes_none():
    assert _normalize({"reference_note": "null"})["reference_note"] is None
    assert _normalize({"reference_note": ""})["reference_note"] is None
    assert _normalize({"reference_note": "유사 사례 참고"})["reference_note"] == "유사 사례 참고"


def test_fallback_marked_as_error_and_normal_result_not():
    # 실패 결과는 error=True로 표시되어 캐시 대상에서 제외된다
    assert _fallback("(LLM 호출 실패)")["error"] is True
    assert "error" not in _normalize({"diagnosis": "정상 진단"})


def test_normalize_not_error_verdict():
    # LLM이 비대상 판별 시 사유만 담은 verdict 반환 — error 마커 없음(캐시 가능)
    result = _normalize({"not_error": True, "reason": "회의 일정 안내 메일입니다"})
    assert result == {"not_error": True, "reason": "회의 일정 안내 메일입니다"}
    assert "error" not in result


def test_normalize_not_error_without_reason_gets_default():
    result = _normalize({"not_error": True})
    assert result["not_error"] is True
    assert result["reason"]  # 기본 사유 문구 존재


# --- _looks_like_error ---

def _msg(subject, body=""):
    return InboundMessage(
        id="t", source=MessageSource.OUTLOOK, sender="a@b.com",
        subject=subject, body=body or "본문", received_at=datetime.now(timezone.utc),
    )


@pytest.mark.parametrize("subject,expected", [
    ("그룹웨어 접속 오류", True),
    ("서버 장애 발생", True),
    ("로그인이 안 됩니다", True),
    ("500 Internal Server Error", True),
    ("결재 화면이 느려요", True),
    ("6월 정기 회의 일정 안내", False),
    ("주간 보고서 공유", False),
])
def test_looks_like_error_keyword_detection(subject, expected):
    assert _looks_like_error(_msg(subject)) is expected


def test_looks_like_error_checks_body_too():
    assert _looks_like_error(_msg("문의드립니다", "첨부 파일이 열리지 않고 에러 창이 뜹니다")) is True


# --- _format_similar_cases ---

def test_format_similar_cases_empty():
    assert _format_similar_cases([]) == "(과거 유사 사례 없음)"


def test_format_similar_cases_includes_status_and_summary():
    cases = [{"subject": "DB 접속 오류", "jira_status": "완료", "summary": "커넥션 풀 확장으로 해결"}]
    text = _format_similar_cases(cases)
    assert "[완료] DB 접속 오류" in text
    assert "커넥션 풀 확장으로 해결" in text


# --- StateStore.find_similar_cases / update_fix_suggestion ---

@pytest.fixture
def store(tmp_path):
    s = StateStore(db_path=str(tmp_path / "test.db"))
    yield s
    s.close()


def test_find_similar_cases_matches_keyword_and_excludes_self(store):
    store.mark_processed("m1", "outlook", intent_type="urgent",
                         subject="그룹웨어 서버 접속 오류", body="접속 불가")
    store.mark_processed("m2", "outlook", intent_type="urgent",
                         subject="그룹웨어 로그인 오류 발생", body="로그인 실패")
    store.mark_processed("m3", "outlook", intent_type="info",
                         subject="그룹웨어 점검 안내", body="정기 점검")

    cases = store.find_similar_cases("m1", subject="그룹웨어 서버 접속 오류")

    ids = [c["id"] for c in cases]
    assert "m1" not in ids        # 자기 자신 제외
    assert "m2" in ids            # urgent + 키워드 일치
    assert "m3" not in ids        # info는 제외


def test_find_similar_cases_resolved_first(store):
    store.mark_processed("target", "outlook", intent_type="urgent",
                         subject="결재 시스템 오류", body="")
    store.mark_processed("open1", "outlook", intent_type="urgent",
                         subject="결재 지연 오류", body="")
    store.mark_processed("done1", "outlook", intent_type="urgent",
                         subject="결재 승인 오류", body="")
    store.update_jira_status("done1", "완료")

    cases = store.find_similar_cases("target", subject="결재 시스템 오류")

    assert cases[0]["id"] == "done1"  # 해결 완료 사례 우선


def test_find_similar_cases_no_keywords_returns_empty(store):
    assert store.find_similar_cases("x", subject=None, body=None) == []


def test_update_and_read_fix_suggestion(store):
    store.mark_processed("m1", "outlook", intent_type="urgent", subject="오류")
    payload = json.dumps({"suggestion": {"diagnosis": "테스트"}}, ensure_ascii=False)

    store.update_fix_suggestion("m1", payload)

    row = store.get_message_by_id("m1")
    assert json.loads(row["fix_suggestion"])["suggestion"]["diagnosis"] == "테스트"
