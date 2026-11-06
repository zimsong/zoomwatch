"""
워치리스트 매칭 + 델타(신규 좌석) 감지. 입력은 source.py가 정규화한 공통 레코드.

핵심: 마일리지 좌석은 '가격'이 아니라 '가부(O/–)'다.
그래서 '어제 스냅샷 vs 오늘 스냅샷' 차이(새 행 / 좌석이 열린 행)를 델타로 본다.
"""


def make_key(rec):
    return (
        rec.get("airline"), rec.get("trip"), rec.get("city"), rec.get("cabin"),
        rec.get("direction"), rec.get("dep_date"), rec.get("ret_date"),
        rec.get("dep_time"), rec.get("ret_time"),
    )


def _key_str(rec):
    return "|".join("" if x is None else str(x) for x in make_key(rec))


def _has_seat(v):
    return str(v).strip().upper() == "O"


def matches(rec, w):
    # 레코드가 여러 파일에서 한 풀로 모이므로, 워치의 항공사/타입/대륙을 여기서 자기완결적으로 확인
    if w.get("airline", "any") != "any" and rec.get("airline") != w["airline"]:
        return False
    if w.get("trip", "any") != "any" and rec.get("trip") != w["trip"]:
        return False
    if w.get("continent") and rec.get("continent") != w["continent"]:
        return False
    if w.get("cabin", "any") != "any" and rec.get("cabin") != w["cabin"]:
        return False
    cc = w.get("city_contains") or ""
    if cc and cc not in (rec.get("city") or ""):
        return False

    # 방향 필터(편도에서만 의미): outbound(가는편)/inbound(오는편)/any
    wd = w.get("direction", "any")
    if wd and wd != "any" and rec.get("trip") == "oneway":
        if rec.get("direction") != wd:
            return False

    dep = rec.get("dep_date") or ""
    dep_dates = w.get("dep_dates") or []
    if dep_dates:
        if dep not in dep_dates:
            return False
    else:
        df, dt = w.get("dep_from") or "", w.get("dep_to") or ""
        if df and dep < df:
            return False
        if dt and dep > dt:
            return False

    if w.get("require_out_seat") and not _has_seat(rec.get("seat_out")):
        return False
    if w.get("require_ret_seat") and not _has_seat(rec.get("seat_ret")):
        return False
    return True


def build_snapshot(records):
    snap = {}
    for rec in records:
        snap[_key_str(rec)] = [rec.get("seat_out"), rec.get("seat_ret")]
    return snap


def _is_new(prev_val, cur_val):
    """어제 없던 키이거나, 없던 좌석(O)이 새로 열린 경우 True."""
    if prev_val is None:
        return True
    po, pr = prev_val
    co, cr = cur_val
    opened_out = (not _has_seat(po)) and _has_seat(co)
    opened_ret = (not _has_seat(pr)) and _has_seat(cr)
    return opened_out or opened_ret


def run(watches, records, prev_snapshot):
    """반환: (alerts, new_snapshot). alerts=[{watch, reason('new'|'all'), rec}]"""
    prev = prev_snapshot or {}
    cur_snapshot = build_snapshot(records)
    alerts, seen = [], set()

    for w in watches:
        if not w.get("enabled", True):
            continue
        mode = w.get("notify", "new")
        for rec in records:
            if not matches(rec, w):
                continue
            k = _key_str(rec)
            dedup = (w.get("name"), k)
            if dedup in seen:
                continue
            new = _is_new(prev.get(k), [rec.get("seat_out"), rec.get("seat_ret")])
            if mode == "new" and not new:
                continue
            seen.add(dedup)
            alerts.append({"watch": w.get("name"), "reason": "new" if new else "all", "rec": rec})

    return alerts, cur_snapshot
