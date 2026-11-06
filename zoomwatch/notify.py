"""
알림 발송 (교체 가능한 구조).

NOTIFY_PROVIDER 환경변수로 선택:
  kakao    : 카카오톡 '나에게 보내기' (대표님 본인 카톡으로)
  telegram : 텔레그램 봇 (가족 그룹방 가능) — 나중에 갈아끼울 때
  console  : 그냥 출력 (테스트용, 기본값)

표준 라이브러리만 사용 — GitHub Actions에서 pip install 불필요.
"""
import json
import os
import urllib.parse
import urllib.request

KAKAO_TOKEN_URL = "https://kauth.kakao.com/oauth/token"
KAKAO_SEND_URL = "https://kapi.kakao.com/v2/api/talk/memo/default/send"
TELEGRAM_API = "https://api.telegram.org/bot{token}/sendMessage"
ZMT_URL = "https://zoommytrip.kr/"


# ---------- 메시지 조립 ----------

def _cabin_ko(c):
    return {"business": "비즈", "first": "퍼스트"}.get(c, c or "")


def _dir_ko(d):
    return {"outbound": "가는편", "inbound": "오는편", "roundtrip": ""}.get(d, "")


def format_alerts(alerts, max_lines=12):
    """alerts(logic.run 결과)를 사람이 읽는 한국어 메시지로. 카카오 200자 제한 고려해 요약."""
    if not alerts:
        return None
    lines = []
    for a in alerts:
        r = a["rec"]
        trip = {"roundtrip": "왕복", "oneway": "편도", "upgrade": "승급"}.get(r.get("trip"), r.get("trip"))
        date_str = r.get("dep_date") or ""
        if r.get("ret_date"):
            date_str += "~" + r.get("ret_date")
        # 편도는 방향 표시, 왕복은 좌석 O 표시
        if r.get("trip") == "oneway":
            extra = _dir_ko(r.get("direction"))
        else:
            seats = []
            if str(r.get("seat_out")).upper() == "O":
                seats.append("가O")
            if str(r.get("seat_ret")).upper() == "O":
                seats.append("오O")
            extra = "/".join(seats)
        tag = "🆕" if a["reason"] == "new" else "•"
        lines.append(f"{tag} {r.get('city')} {_cabin_ko(r.get('cabin'))} {trip} {date_str} {extra}".strip())

    total = len(lines)
    head = f"[마일리지 좌석 {total}건]"
    shown = lines[:max_lines]
    more = total - len(shown)
    body = "\n".join(shown)
    if more > 0:
        body += f"\n…외 {more}건"
    return f"{head}\n{body}"


# ---------- 카카오 ----------

def _post_form(url, data, headers=None):
    body = urllib.parse.urlencode(data).encode()
    req = urllib.request.Request(url, data=body, headers=headers or {})
    with urllib.request.urlopen(req, timeout=30) as r:
        return json.load(r)


def kakao_refresh_access_token(rest_api_key, refresh_token):
    """refresh_token으로 새 access_token을 발급. Kakao가 새 refresh_token을 줄 때도 있다."""
    res = _post_form(KAKAO_TOKEN_URL, {
        "grant_type": "refresh_token",
        "client_id": rest_api_key,
        "refresh_token": refresh_token,
    })
    return res  # {access_token, expires_in, [refresh_token, refresh_token_expires_in]}


def kakao_send_memo(access_token, text, link_url=ZMT_URL):
    template = {
        "object_type": "text",
        "text": text[:200],  # 카카오 텍스트 200자 제한
        "link": {"web_url": link_url, "mobile_web_url": link_url},
        "button_title": "좌석 보기",
    }
    return _post_form(
        KAKAO_SEND_URL,
        {"template_object": json.dumps(template, ensure_ascii=False)},
        headers={"Authorization": f"Bearer {access_token}"},
    )


def send_kakao(text):
    rest = os.environ["KAKAO_REST_API_KEY"]
    refresh = os.environ["KAKAO_REFRESH_TOKEN"]
    tok = kakao_refresh_access_token(rest, refresh)
    access = tok["access_token"]
    kakao_send_memo(access, text)
    # Kakao가 refresh_token을 갱신해 주면 알려준다(2개월마다 교체 필요).
    if tok.get("refresh_token"):
        print("::warning:: 카카오가 새 refresh_token을 발급했습니다. "
              "GitHub Secret(KAKAO_REFRESH_TOKEN)을 아래 값으로 교체하세요:")
        print("NEW_KAKAO_REFRESH_TOKEN=" + tok["refresh_token"])


# ---------- 텔레그램 (교체용) ----------

def send_telegram(text):
    token = os.environ["TELEGRAM_BOT_TOKEN"]
    chat_id = os.environ["TELEGRAM_CHAT_ID"]
    _post_form(TELEGRAM_API.format(token=token), {"chat_id": chat_id, "text": text})


# ---------- 디스패처 ----------

def notify(text):
    if not text:
        return
    provider = os.environ.get("NOTIFY_PROVIDER", "console").lower()
    if provider == "kakao":
        send_kakao(text)
    elif provider == "telegram":
        send_telegram(text)
    else:
        print("[console 알림]\n" + text)
