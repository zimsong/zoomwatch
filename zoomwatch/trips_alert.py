"""
타겟 여행 알림.

docs/trips.json에 저장된 여행(출국일=가는편, 입국일=오는편)을 읽어,
현재 보드 데이터(편도 프레스티지 좌석)에 그 좌석이 '새로' 떴는지 확인하고 알림을 만든다.

- 좌석 가능 여부는 board.build_board_data() 결과(bd)에서 바로 판단(추가 수집 없음).
- '새로 떴을 때만' 알리기 위해 직전 상태를 state/trips_seen.json에 저장하고 비교.
- 첫 실행(파일 없음)에는 기준선만 저장하고 알리지 않는다(한꺼번에 쏟아짐 방지).
"""
import json
import os


def _load(path, default):
    if os.path.exists(path):
        try:
            with open(path, "r", encoding="utf-8") as f:
                return json.load(f)
        except Exception:
            return default
    return default


def load_trips(path):
    data = _load(path, {"trips": []})
    trips = data.get("trips") if isinstance(data, dict) else []
    return trips if isinstance(trips, list) else []


def _avail_set(board_data):
    """보드 데이터 → 가능한 'city|dir|date' 집합."""
    s = set()
    for c in board_data.get("cities", []):
        city = c.get("city", "")
        for seat in c.get("seats", []):
            if len(seat) >= 2:
                s.add(city + "|" + seat[1] + "|" + seat[0])
    return s


def check(trips, board_data, seen_path):
    """새로 가능해진 타겟 레그 목록과 현재 상태를 반환. (first_run이면 알림 억제)"""
    avail = _avail_set(board_data)
    first_run = not os.path.exists(seen_path)
    prev = _load(seen_path, {})
    cur, alerts = {}, []
    for t in trips:
        city = t.get("city")
        if not city:
            continue
        for direction, date in (("O", t.get("out")), ("I", t.get("in"))):
            if not date:
                continue
            key = city + "|" + direction + "|" + date
            is_avail = key in avail
            cur[key] = is_avail
            if is_avail and not prev.get(key):
                alerts.append((city, direction, date))

    os.makedirs(os.path.dirname(seen_path), exist_ok=True)
    with open(seen_path, "w", encoding="utf-8") as f:
        json.dump(cur, f, ensure_ascii=False)

    if first_run:
        return [], cur
    return alerts, cur


def format_msg(alerts):
    if not alerts:
        return None
    lines = ["🎯 타겟 항공권 좌석 떴어요!"]
    for city, direction, date in alerts:
        leg = f"가는편 ICN→{city}" if direction == "O" else f"오는편 {city}→ICN"
        lines.append(f"• {city} {leg} {date} 프레스티지 ○")
    lines.append("→ 대한항공 앱/홈페이지에서 예약")
    return "\n".join(lines)
