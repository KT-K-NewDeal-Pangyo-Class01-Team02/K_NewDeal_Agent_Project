"""SaveDeal 의 AI 사용 지점. 판정(위험도·우선순위·해결책)은 Python 규칙이 하고, AI 는 글을 읽고 쓰는 일만 한다.

1. 메모 해석 (MEMO_INSIGHT): 업로드 명단의 자유 메모 → 대체 가능 색상, 서류 제출 예정일, 선호 연락 방법
2. 고객 안내문 (CUSTOMER_NOTICE): 승인한 해결책을 고객에게 보낼 안내 문구로
3. 직원 브리핑 (STAFF_BRIEFING): 예약이 왜 급한지 3줄 요약

OPENAI_API_KEY 가 없거나 호출이 실패하면 같은 형식의 규칙 기반 결과를 돌려준다(source="rule").
모든 호출은 ai_logs 에 남긴다. AI 에는 마스킹된 가상 정보만 보낸다.
"""
import json
import re
from datetime import date, datetime, timedelta

from db.connection import connect, ensure_database
from services.ai_client import AIError, OpenAIClient

FEATURE_MEMO = "MEMO_INSIGHT"
FEATURE_NOTICE = "CUSTOMER_NOTICE"
FEATURE_BRIEFING = "STAFF_BRIEFING"
FEATURE_LABELS = {FEATURE_MEMO: "메모 해석", FEATURE_NOTICE: "고객 안내문", FEATURE_BRIEFING: "직원 브리핑"}

PHONE_PATTERN = re.compile(r"01[0-9][-\s.]?\d{3,4}[-\s.]?\d{4}")

COLOR_ALIASES = {
    "블랙": "Black", "검정": "Black", "검은": "Black", "black": "Black",
    "실버": "Silver", "은색": "Silver", "silver": "Silver",
    "화이트": "White", "흰색": "White", "white": "White",
    "블루": "Blue", "파랑": "Blue", "파란": "Blue", "blue": "Blue",
    "라이트블루": "Light Blue", "하늘색": "Light Blue",
    "라벤더": "Lavender", "보라": "Lavender", "lavender": "Lavender",
    "버건디": "Burgundy", "와인": "Burgundy", "burgundy": "Burgundy",
    "그레이": "Titanium Gray", "회색": "Titanium Gray",
}
WEEKDAYS = {"월요일": 0, "화요일": 1, "수요일": 2, "목요일": 3, "금요일": 4, "토요일": 5, "일요일": 6}
CONTACT_WORDS = {"전화": "전화", "통화": "전화", "문자": "문자", "알림톡": "알림톡", "카톡": "알림톡", "카카오": "알림톡"}


def mask_text(text: str) -> str:
    """메모에 실수로 들어간 전화번호를 가린다."""
    return PHONE_PATTERN.sub("010-****-****", text or "")


class AIService:
    def __init__(self, db_path, config: dict, client=None, clock=datetime.now):
        ensure_database(db_path)
        self.db_path = db_path
        self.clock = clock
        if client is not None:
            self.client = client
        elif config.get("OPENAI_API_KEY"):
            self.client = OpenAIClient(config["OPENAI_API_KEY"], config.get("OPENAI_MODEL") or "gpt-4o-mini",
                                       float(config.get("OPENAI_TIMEOUT", 20)))
        else:
            self.client = None

    @property
    def mode(self) -> str:
        return "ai" if self.client is not None else "rule"

    @property
    def model(self) -> str | None:
        return getattr(self.client, "model", None)

    # ── 기록 ───────────────────────────────────────────────────────

    def _log(self, feature: str, reservation_id, mode: str, success: bool, latency_ms=None, error=None) -> None:
        with connect(self.db_path) as conn:
            conn.execute(
                """INSERT INTO ai_logs (feature, reservation_id, mode, provider, model, success, latency_ms, error, created_at)
                   VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)""",
                (feature, reservation_id, mode, getattr(self.client, "provider", None) if mode == "ai" else None,
                 self.model if mode == "ai" else None, int(success), latency_ms, error,
                 self.clock().isoformat(timespec="seconds")),
            )

    def recent_logs(self, limit: int = 10) -> list[dict]:
        with connect(self.db_path) as conn:
            rows = conn.execute("SELECT * FROM ai_logs ORDER BY log_id DESC LIMIT ?", (limit,)).fetchall()
        return [{**dict(row), "feature_label": FEATURE_LABELS.get(row["feature"], row["feature"]),
                 "success": bool(row["success"])} for row in rows]

    def _run(self, feature: str, reservation_id, ai_call, rule_call) -> dict:
        """AI 가 켜져 있으면 ai_call, 아니면(또는 실패하면) rule_call. 결과에 출처를 붙인다."""
        if self.client is not None:
            try:
                result, latency = ai_call()
                self._log(feature, reservation_id, "ai", True, latency)
                return {**result, "source": "ai", "model": self.model, "latency_ms": latency}
            except AIError as exc:
                self._log(feature, reservation_id, "ai", False, error=str(exc))
                result = rule_call()
                return {**result, "source": "rule", "model": None, "latency_ms": None, "ai_error": str(exc)}
        result = rule_call()
        self._log(feature, reservation_id, "rule", True)
        return {**result, "source": "rule", "model": None, "latency_ms": None}

    # ── 1. 메모 해석 ───────────────────────────────────────────────

    def interpret_memo(self, memo: str, reservation_id: str | None = None, today: date | None = None) -> dict:
        memo = mask_text(memo).strip()
        today = today or self.clock().date()

        def ai_call():
            system = (
                "너는 통신 매장 예약 메모를 구조화하는 도우미다. 메모에 있는 사실만 뽑고 추측하지 마라. "
                "JSON 객체로만 답한다: {\"flexible_colors\": [영문 색상명], \"document_eta\": \"YYYY-MM-DD\" 또는 null, "
                "\"contact_preference\": \"전화\"|\"문자\"|\"알림톡\"|null, \"summary\": \"한 문장 요약\"}. "
                f"오늘은 {today.isoformat()} 이다. 색상명은 Black, Silver, White, Blue, Light Blue, Lavender, Burgundy, "
                "Titanium Gray 중에서 고른다."
            )
            text, latency = self.client.chat(system, f"메모: {memo}", json_mode=True)
            return self._normalize_insight(json.loads(text)), latency

        return self._run(FEATURE_MEMO, reservation_id, ai_call, lambda: self._rule_memo(memo, today))

    def _normalize_insight(self, data: dict) -> dict:
        colors = [c for c in data.get("flexible_colors") or [] if isinstance(c, str)]
        eta = data.get("document_eta")
        try:
            eta = date.fromisoformat(eta).isoformat() if eta else None
        except (TypeError, ValueError):
            eta = None
        contact = data.get("contact_preference")
        return {
            "flexible_colors": colors[:4],
            "document_eta": eta,
            "contact_preference": contact if contact in ("전화", "문자", "알림톡") else None,
            "summary": str(data.get("summary") or "")[:120],
        }

    def _rule_memo(self, memo: str, today: date) -> dict:
        lowered = memo.lower()
        found = sorted((lowered.find(word), color) for word, color in COLOR_ALIASES.items() if word in lowered)
        colors = []
        for _, color in found:  # 메모에 나온 순서대로
            if color not in colors:
                colors.append(color)
        eta = None
        for word, weekday in WEEKDAYS.items():
            if word in memo:
                days = (weekday - today.weekday()) % 7 or 7
                eta = (today + timedelta(days=days)).isoformat()
                break
        if eta is None:
            if "내일" in memo:
                eta = (today + timedelta(days=1)).isoformat()
            else:
                match = re.search(r"(\d{1,2})\s*[/월.]\s*(\d{1,2})", memo)
                if match:
                    try:
                        eta = date(today.year, int(match.group(1)), int(match.group(2))).isoformat()
                    except ValueError:
                        eta = None
        if eta and "서류" not in memo:
            eta = None
        contact = next((label for word, label in CONTACT_WORDS.items() if word in memo), None)
        return {"flexible_colors": colors, "document_eta": eta, "contact_preference": contact, "summary": memo[:80]}

    # ── 2. 고객 안내문 ─────────────────────────────────────────────

    def compose_notice(self, masked_name: str, action: dict, issue_label: str, reservation_id: str) -> dict:
        def ai_call():
            system = (
                "너는 KT 매장 직원이다. 예약 고객에게 보낼 짧은 안내 문자를 쓴다. 3~4문장, 존댓말, 과장·약속 금지, "
                "주어진 정보 밖의 혜택이나 금액을 지어내지 마라. 고객 이름은 주어진 마스킹 이름 그대로 쓴다."
            )
            user = (
                f"고객: {masked_name}\n문제: {issue_label}\n진행할 조치: {action['title']}\n"
                f"조치 설명: {action['description']}"
            )
            text, latency = self.client.chat(system, user)
            return {"text": text}, latency

        def rule_call():
            body = re.sub(r"\s*\((가상[^)]*)\)", "", action["description"]).strip()
            return {
                "text": f"{masked_name} 고객님, KT 매장입니다. 예약하신 단말 개통과 관련해 안내드립니다.\n"
                        f"{action['title']}: {body}\n문의 사항은 매장으로 연락 주세요."
            }

        return self._run(FEATURE_NOTICE, reservation_id, ai_call, rule_call)

    # ── 3. 직원 브리핑 ─────────────────────────────────────────────

    def staff_briefing(self, detail: dict, masked_name: str) -> dict:
        factors = sorted(detail.get("priority_factors", []), key=lambda f: -f["points"])
        issues = [f"{i['label']}({i['summary']})" for i in detail.get("issues", [])]
        first_action = next((a for a in detail.get("actions", []) if a.get("can_approve") or a.get("can_record_result")), None)

        def ai_call():
            system = "너는 통신 매장 운영 담당자를 돕는다. 주어진 데이터만으로 한국어 3줄 브리핑을 쓴다. 각 줄은 '- '로 시작한다."
            user = json.dumps({
                "고객": masked_name, "우선순위점수": detail.get("priority_score"), "이탈위험": detail.get("risk_label"),
                "마감": detail.get("deadline_label"), "점수근거": factors[:4], "문제": issues,
                "다음조치": first_action["title"] if first_action else None,
            }, ensure_ascii=False)
            text, latency = self.client.chat(system, user)
            return {"text": text}, latency

        def rule_call():
            reasons = ", ".join(f"{f['label']}(+{f['points']})" for f in factors[:3]) or "특이 사항 없음"
            lines = [
                f"- 우선순위 {detail.get('priority_score')}점 · 이탈위험 {detail.get('risk_label')} · 마감 {detail.get('deadline_label')}",
                f"- 주요 근거: {reasons}",
                f"- 다음 조치: {first_action['title'] if first_action else '남은 조치 없음'}"
                + (f" (문제: {', '.join(issues)})" if issues else ""),
            ]
            return {"text": "\n".join(lines)}

        return self._run(FEATURE_BRIEFING, detail.get("reservation_id"), ai_call, rule_call)
