import pytest

from inbound_gw_agent.handlers.ticket_handler import _extract_team_from_footer


@pytest.mark.parametrize("body,expected", [
    ("업무 요청드립니다.\n\n---\n홍길동\n그룹웨어팀\nhuiju@mastern.co.kr", "그룹웨어팀"),
    ("업무 요청드립니다.\n\n---\n홍길동\n개발실\nhuiju@mastern.co.kr", "개발실"),
    ("업무 요청드립니다.\n\n---\n홍길동\nIT본부\nhuiju@mastern.co.kr", "IT본부"),
    ("업무 요청드립니다.\n\n---\n홍길동\n마스턴회사\nhuiju@mastern.co.kr", "마스턴회사"),
    # 팀+실 동시 → 팀 우선
    ("업무 요청드립니다.\n\n---\n홍길동\n개발실 그룹웨어팀\nhuiju@mastern.co.kr", "그룹웨어팀"),
    # 꼬리말에 없음 → 빈 문자열
    ("업무 요청드립니다. 확인 부탁드립니다.", ""),
    # 본문 중간에 있어도 꼬리말(하단 30줄) 안이면 추출
    ("\n".join(["내용"] * 40) + "\n\nIT인프라팀\nhuiju@mastern.co.kr", "IT인프라팀"),
])
def test_extract_team_from_footer(body, expected):
    assert _extract_team_from_footer(body) == expected
