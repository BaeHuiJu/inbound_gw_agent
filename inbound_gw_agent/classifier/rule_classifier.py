from __future__ import annotations

import re

from inbound_gw_agent.models.intent import ClassifiedIntent, IntentType
from inbound_gw_agent.models.message import InboundMessage

# (pattern, IntentType, weight)
_RULES: list[tuple[re.Pattern, IntentType, float]] = [
    # URGENT — 긴급/장애/보안
    (re.compile(r"긴급|장애|오류|에러|error|먹통|접속\s*불가|실패|오작동|끊김|문제\s*발생|서버.*다운|서비스.*중단", re.I), IntentType.URGENT, 0.95),
    (re.compile(r"안\s*됩니다|안됩니다|작동.*안|안.*작동|실행.*안|안.*실행|보안\s*이슈|해킹|침해|취약점", re.I), IntentType.URGENT, 0.9),

    # SPAM — 광고/홍보 (동점 시 TASK보다 우선 — _TIE_BREAK_PRIORITY 참고)
    (re.compile(r"수신\s*거부|광고|홍보|할인|이벤트.*참여|무료.*제공|구독.*취소|unsubscribe|promotion", re.I), IntentType.SPAM, 0.95),
    (re.compile(r"특가|세일|sale|limited\s*offer|지금\s*신청|혜택.*받으세요|newsletter", re.I), IntentType.SPAM, 0.9),

    # INFO — 시스템 알림 / 자동발송 (가중치 0.92+로 TASK보다 높음. 동점 시에는 TASK 우선)
    (re.compile(r"atlassian\.net|jira@|github\.com|noreply@|no-reply@|donotreply@|do-not-reply@|notifications@", re.I), IntentType.INFO, 0.95),
    (re.compile(r"\[jira\]|\[github\]|\[confluence\]|\[slack\]|automated\s*message|auto-generated|자동\s*발송|시스템\s*알림", re.I), IntentType.INFO, 0.92),
    # Re:/Fw: 답장·전달 (threshold 0.8 미만 → LLM 최종 판단)
    (re.compile(r"(?:^|\s)(?:re|fwd?)\s*:", re.I), IntentType.INFO, 0.75),
    # 정보성/공지
    (re.compile(r"공지|안내|뉴스레터|보고서|리포트|report|주간\s*보고|월간\s*보고|결과\s*공유|업데이트\s*안내", re.I), IntentType.INFO, 0.9),
    (re.compile(r"공유\s*드립니다|알려\s*드립니다|안내\s*드립니다|첨부.*확인|참고\s*바랍니다|배포\s*드립니다", re.I), IntentType.INFO, 0.8),

    # TASK — 작업 요청
    (re.compile(r"요청|부탁|해\s*주세요|해\s*주십시오|처리\s*해|진행\s*해|결재|승인\s*부탁|작업.*의뢰", re.I), IntentType.TASK, 0.9),
    (re.compile(r"수정.*해|변경.*해|추가.*해|삭제.*해|배포.*해|설치.*해", re.I), IntentType.TASK, 0.85),

    # PROJECT — 프로젝트/협업
    (re.compile(r"제안|기획|협업|협조|프로젝트|신규.*건|킥오프|kickoff", re.I), IntentType.PROJECT, 0.9),
    (re.compile(r"검토.*해\s*주|의견.*주세요|피드백|리뷰\s*부탁|방향성|계획.*공유|미팅.*요청|회의.*제안", re.I), IntentType.PROJECT, 0.85),

    # INQUIRY — 단순 문의
    (re.compile(r"문의|질문|궁금|어떻게|방법|알려\s*주세요|확인\s*부탁|알고\s*싶", re.I), IntentType.INQUIRY, 0.9),
    (re.compile(r"어디서|어떤|가능한가요|되나요|맞나요|언제|몇\s*시|무엇인지|뭐예요|어떤가요", re.I), IntentType.INQUIRY, 0.8),
]


# 동점 시 우선순위 — 행동이 필요한 분류(URGENT/TASK)를 정보성 분류(INFO)보다 우선한다.
# 예: "보고서 양식 수정 처리해 주세요" → INFO(보고서)와 TASK(처리해)가 0.9 동점 → TASK 채택.
# SPAM은 광고 메일이 작업 티켓으로 새지 않도록 TASK보다 앞에 둔다.
_TIE_BREAK_PRIORITY = [
    IntentType.URGENT,
    IntentType.SPAM,
    IntentType.TASK,
    IntentType.PROJECT,
    IntentType.INQUIRY,
    IntentType.INFO,
    IntentType.UNKNOWN,
]


class RuleClassifier:
    def classify(self, msg: InboundMessage) -> ClassifiedIntent:
        text = msg.full_text
        scores: dict[IntentType, float] = {}
        matched_keywords: list[str] = []

        for pattern, intent_type, weight in _RULES:
            found = pattern.findall(text)
            if found:
                matched_keywords.extend(found[:3])
                scores[intent_type] = max(scores.get(intent_type, 0.0), weight)

        if not scores:
            return ClassifiedIntent(type=IntentType.UNKNOWN, confidence=0.0, classifier="rule")

        best_score = max(scores.values())
        best_type = next(t for t in _TIE_BREAK_PRIORITY if scores.get(t) == best_score)
        return ClassifiedIntent(
            type=best_type,
            confidence=best_score,
            classifier="rule",
            keywords=list(set(matched_keywords)),
        )
