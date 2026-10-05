"""통하길 QR 사은품 뽑기.

부스에서 쿠폰을 확인(지급 처리)하면 방문객 화면에 뽑기가 열리고, 방문객이 누르는 순간 사은품이 정해진다.
뽑힐 확률은 **남은 수량에 비례**한다. 하나가 나갈 때마다 수량이 줄어 다음 사람의 확률이 달라진다.

재고의 기준은 구글 스프레드시트다. .env 에 QR_GIFT_WEBHOOK_URL 을 넣으면 n8n 이 시트를 읽어 뽑고 수량을 1 줄인다.
    Webhook(POST) → Google Sheets(Get rows) → Code(남은 수량 비례로 하나 고름) → Google Sheets(Update row) → Respond to Webhook

보내는 JSON:  action "draw", eventId, visitor(별칭), couponCode
받는 응답:    {"id": 5, "item": "티니핑 사탕", "remaining": 499}   (item 대신 name·gift, remaining 대신 quantity 도 알아듣는다)
              모두 소진됐으면 {"soldOut": true}

주소가 없으면 시트 없이 동작한다: event.json 의 benefit.gifts 수량에서 지금까지 뽑힌 수를 빼고 같은 규칙으로 뽑는다.

뽑기는 AI 가 하지 않는다. 무작위 선택과 수량 계산은 코드(n8n Code 노드 또는 아래 local_draw)가 한다.
"""
import random
import sys
from dataclasses import dataclass

import requests

_NAME_KEYS = ("item", "name", "gift")
_LEFT_KEYS = ("remaining", "quantity", "left")


class GiftError(Exception):
    """방문객 화면에 그대로 보여 줄 수 있는 메시지를 담은 오류."""


@dataclass
class Gift:
    id: str
    name: str
    remaining: int | None  # 뽑은 뒤 이 품목의 남은 수량. 모르면 None
    source: str            # "n8n" (스프레드시트) | "local" (event.json, 시트 미연결)


def remaining_stock(items, drawn):
    """[{id, name, quantity}] 에서 지금까지 뽑힌 수(drawn: {이름: 수})를 뺀 남은 수량. 0 인 품목은 뺀다."""
    left = [{**it, "quantity": int(it["quantity"]) - drawn.get(it["name"], 0)} for it in items]
    return [it for it in left if it["quantity"] > 0]


def local_draw(items, drawn, rng=random):
    """시트 없이 뽑기. 남은 수량에 비례한 확률로 하나 고른다."""
    stock = remaining_stock(items, drawn)
    if not stock:
        raise GiftError("준비한 사은품이 모두 소진됐어요. 직원에게 문의해 주세요.")
    pick = rng.choices(stock, weights=[it["quantity"] for it in stock])[0]
    return Gift(str(pick["id"]), pick["name"], pick["quantity"] - 1, "local")


def draw(*, webhook_url, timeout, headers=None, event_id="", visitor="", coupon_code="", items=(), drawn=None):
    if not webhook_url:
        return local_draw(list(items), drawn or {})

    payload = {"action": "draw", "eventId": event_id, "visitor": visitor, "couponCode": coupon_code}
    try:
        resp = requests.post(webhook_url, json=payload, headers=headers or {}, timeout=timeout)
    except requests.Timeout as exc:
        raise GiftError("뽑기가 늦어지고 있어요. 잠시 후 다시 눌러 주세요.") from exc
    except requests.RequestException as exc:
        raise GiftError("뽑기 서버에 연결하지 못했어요. 잠시 후 다시 눌러 주세요.") from exc

    if resp.status_code >= 400:
        print(f"[통하길 QR] n8n 사은품 뽑기 오류 HTTP {resp.status_code}: {resp.text[:500]}", file=sys.stderr)
        raise GiftError(f"뽑기에 실패했어요 (HTTP {resp.status_code}). 직원에게 알려 주세요.")
    try:
        data = resp.json()
    except ValueError:
        data = None
    gift = parse_gift(data)
    if gift is None:
        print(f"[통하길 QR] n8n 사은품 뽑기 응답을 읽지 못함: {resp.text[:500]}", file=sys.stderr)
        raise GiftError("뽑기 결과를 받지 못했어요. 직원에게 알려 주세요. (담당자: Respond to Webhook 의 item 값 확인)")
    return gift


def parse_gift(data):
    """n8n 응답에서 뽑힌 사은품을 찾는다. 배열이나 한 겹 싸인 값도 받는다. 못 찾으면 None."""
    if isinstance(data, list):
        data = data[0] if data else None
    if not isinstance(data, dict):
        return None
    if data.get("soldOut") in (True, "true", 1):
        # n8n Code 노드가 reason 을 같이 보내면 붙여 준다 (시트를 못 읽었는지, 정말 다 나갔는지 구분하려고)
        reason = str(data.get("reason") or "").strip()[:160]
        raise GiftError("준비한 사은품이 모두 소진됐어요. 직원에게 문의해 주세요." + (f" (담당자: {reason})" if reason else ""))
    name = next((str(data[k]).strip() for k in _NAME_KEYS if isinstance(data.get(k), (str, int)) and str(data[k]).strip()), "")
    if not name:
        for value in data.values():  # {"json": {...}} 처럼 한 겹 싸인 경우
            if isinstance(value, (dict, list)):
                found = parse_gift(value)
                if found:
                    return found
        return None
    left = next((data[k] for k in _LEFT_KEYS if k in data), None)
    try:
        left = int(left)
    except (TypeError, ValueError):
        left = None
    return Gift(str(data.get("id", "")), name, left, "n8n")
