"""오류 자동수정 제안 생성기.

오류 메일 본문 + 과거 유사 사례를 LLM에 전달해
단계별 수정 방안을 JSON으로 생성한다. Jira 의존성 없음.
"""
from __future__ import annotations

import asyncio
import json
import re

import ollama
import structlog

from inbound_gw_agent.config import get_settings
from inbound_gw_agent.models.message import InboundMessage

log = structlog.get_logger()

_LLM_TIMEOUT_SECONDS = 60.0

_FIX_FORMAT_BLOCK = """\
Fix proposal JSON format (all fields mandatory):
{"diagnosis":"one-paragraph root cause diagnosis","fix_steps":[{"title":"short step name","detail":"concrete commands/settings/actions"}],"verification":"how to confirm the fix worked","risk":"side effects or cautions when applying the fix","reference_note":"insight from past similar cases, or null if none"}

Rules:
- fix_steps: 2~5 steps, ordered, each step actionable by an IT operator
- If past similar cases are provided, reference how they were resolved
- Respond in Korean. Output the JSON object only.
"""

# 오류 키워드가 확인된 메일용 — 판별 없이 항상 제안 생성
_FIX_SUGGEST_SYSTEM_FORCE = f"""\
You are a senior IT engineer who proposes concrete fixes for system errors.
Analyze the error email below and respond ONLY with valid JSON.
Do NOT include any explanation, markdown, or text outside the JSON object.

{_FIX_FORMAT_BLOCK}"""

# 애매한 메일용 — 오류 보고가 아니면 not_error 반환
_FIX_SUGGEST_SYSTEM_DISCRIMINATE = f"""\
You are a senior IT engineer who proposes concrete fixes for system errors.
Analyze the email below and respond ONLY with valid JSON.
Do NOT include any explanation, markdown, or text outside the JSON object.

First decide: does this email report a technical problem that needs fixing?
- Clearly NOT a fix target: meeting notices, newsletters, schedules, approvals, greetings.
- If you are CONFIDENT it is not a fix target, respond with exactly:
{{"not_error": true, "reason": "one-line Korean explanation"}}
- If it reports any technical problem, OR if you are uncertain, respond with the fix proposal format below.

{_FIX_FORMAT_BLOCK}"""

# 명백한 오류 신호 — 하나라도 있으면 LLM 판별을 건너뛰고 무조건 제안 생성
_ERROR_KEYWORD_RE = re.compile(
    r"오류|에러|장애|버그|실패|불가|안\s*됩니다|안\s*돼|먹통|다운|중단|느려|깨짐|깨져"
    r"|error|exception|fail|crash|timeout|타임아웃"
    r"|\b(?:4\d\d|5\d\d)\b",
    re.IGNORECASE,
)


def _looks_like_error(msg: InboundMessage) -> bool:
    return bool(_ERROR_KEYWORD_RE.search(f"{msg.subject or ''} {msg.body[:500]}"))


def _parse_json_response(raw: str) -> dict | None:
    """LLM 응답에서 JSON 객체를 추출한다. 직접 파싱 → 코드블록 → 중괄호 순."""
    try:
        return json.loads(raw)
    except json.JSONDecodeError:
        pass

    if "```" in raw:
        for part in raw.split("```")[1::2]:
            candidate = part.lstrip("json \n\r").strip()
            try:
                return json.loads(candidate)
            except json.JSONDecodeError:
                pass

    m = re.search(r"\{.*\}", raw, re.DOTALL)
    if m:
        try:
            return json.loads(m.group())
        except json.JSONDecodeError:
            pass
    return None


def _format_similar_cases(similar_cases: list[dict]) -> str:
    if not similar_cases:
        return "(과거 유사 사례 없음)"
    lines = []
    for i, case in enumerate(similar_cases, 1):
        status = case.get("jira_status") or "미처리"
        parts = [f"{i}. [{status}] {case.get('subject') or '(제목 없음)'}"]
        if case.get("summary"):
            parts.append(f"   요약: {case['summary'][:200]}")
        if case.get("suggested_action"):
            parts.append(f"   당시 조치: {case['suggested_action'][:200]}")
        lines.append("\n".join(parts))
    return "\n".join(lines)


async def suggest_fix(msg: InboundMessage, similar_cases: list[dict]) -> dict:
    """오류 메일에 대한 단계별 수정 제안을 생성한다. 실패 시 폴백 dict 반환."""
    settings = get_settings()
    user_content = (
        f"[오류 메일]\n"
        f"발신자: {msg.sender}\n"
        f"제목: {msg.subject or '(없음)'}\n"
        f"본문:\n{msg.body[:3000]}\n\n"
        f"[과거 유사 사례]\n{_format_similar_cases(similar_cases)}"
    )

    # 오류 키워드가 명확하면 판별 생략(무조건 제안), 애매하면 LLM이 대상 여부 판별
    system_prompt = (
        _FIX_SUGGEST_SYSTEM_FORCE if _looks_like_error(msg)
        else _FIX_SUGGEST_SYSTEM_DISCRIMINATE
    )

    raw = ""
    try:
        client = ollama.AsyncClient(host=settings.ollama_base_url)
        response = await asyncio.wait_for(
            client.chat(
                model=settings.ollama_model,
                messages=[
                    {"role": "system", "content": system_prompt},
                    {"role": "user", "content": user_content},
                ],
                # 유효한 JSON 출력 강제 + 기술 제안의 일관성을 위해 낮은 온도
                format="json",
                options={"temperature": 0.2},
            ),
            timeout=_LLM_TIMEOUT_SECONDS,
        )
        raw = response.message.content.strip()
        parsed = _parse_json_response(raw)
        if parsed is not None:
            return _normalize(parsed)

        log.warning("fix_suggest_no_json", raw=raw[:200])
        return _fallback(diagnosis="(LLM이 JSON을 반환하지 않았습니다)", detail=raw[:1000])
    except asyncio.TimeoutError:
        log.warning("fix_suggest_timeout", msg_id=msg.id)
        return _fallback(diagnosis="(LLM 응답 시간 초과 — 잠시 후 재시도해 주세요)")
    except Exception as exc:
        log.warning("fix_suggest_failed", error=str(exc)[:120])
        return _fallback(diagnosis=f"(LLM 호출 실패: {str(exc)[:200]})")


def _normalize(data: dict) -> dict:
    """필수 필드를 보장하고 fix_steps 형식을 정규화한다."""
    # LLM이 "수정 제안 대상 아님"으로 판별한 경우 — 정상 결과로 취급되어 캐시된다
    if data.get("not_error"):
        return {
            "not_error": True,
            "reason": str(data.get("reason") or "오류·기술 문제 메일이 아니어서 수정 제안을 생성하지 않았습니다."),
        }
    steps = data.get("fix_steps") or []
    normalized_steps = []
    for step in steps:
        if isinstance(step, dict):
            normalized_steps.append({
                "title": str(step.get("title") or "조치"),
                "detail": str(step.get("detail") or ""),
            })
        elif isinstance(step, str):
            normalized_steps.append({"title": "조치", "detail": step})
    reference_note = data.get("reference_note")
    if reference_note in ("", "null", "None"):
        reference_note = None
    return {
        "diagnosis": str(data.get("diagnosis") or ""),
        "fix_steps": normalized_steps,
        "verification": str(data.get("verification") or ""),
        "risk": str(data.get("risk") or ""),
        "reference_note": reference_note,
    }


def _fallback(diagnosis: str, detail: str = "") -> dict:
    # error=True인 결과는 캐시하지 않는다 (webhook_receiver의 fix-suggestion 엔드포인트 참고)
    return {
        "diagnosis": diagnosis,
        "fix_steps": [{"title": "수동 확인 필요", "detail": detail or "LLM 제안 생성에 실패했습니다. 메일 본문을 직접 확인해 주세요."}],
        "verification": "",
        "risk": "",
        "reference_note": None,
        "error": True,
    }
