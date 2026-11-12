"""
좌석 변화 로그 누적(미래 예측용).

매 실행마다 '현재 가능한 편도 프레스티지 좌석 집합'을 직전 실행과 비교해
- 새로 뜬 좌석(appear)
- 사라진 좌석(disappear)
만 history/events.jsonl 에 한 줄(JSON)씩 append 한다.

각 이벤트에 관측 시각(ts)과 출발일(date)이 들어가므로, 나중에
"관측 시각 → 출발일" 리드타임, 좌석 지속기간, 취소표 재등장 패턴 등을 분석할 수 있다.
보드(docs/data.json)는 최신 1건만 유지하고, 이 파일은 별도 누적 레이어.

입력은 board.build_board_data()가 만든 보드 데이터(dict)를 그대로 쓴다
(추가 수집 없이 이미 받아온 전 도시 좌석을 재사용).
"""
import json
import os

SEP = "|"


def _key(cont, city, direction, date, tag="B"):
    return SEP.join([cont, city, direction, date, tag])


def _load_prev(path):
    """직전 상태(dict: key->dep_time). 파일이 없으면 None(=첫 실행), 깨졌으면 {}."""
    if not os.path.exists(path):
        return None
    try:
        with open(path, "r", encoding="utf-8") as f:
            return json.load(f)
    except Exception:
        return {}


def _save(path, data):
    os.makedirs(os.path.dirname(path), exist_ok=True)
    with open(path, "w", encoding="utf-8") as f:
        json.dump(data, f, ensure_ascii=False, separators=(",", ":"))


def update_from_board(board_data, seen_path, events_path):
    ts = board_data.get("updated")
    cur = {}  # key -> dep_time
    for c in board_data.get("cities", []):
        cont, city = c.get("cont", ""), c.get("city", "")
        for s in c.get("seats", []):
            # s = [date, dir('O'|'I'), dep_time, is_new, tag('B'|'U')]
            date = s[0] if len(s) > 0 else ""
            direction = s[1] if len(s) > 1 else ""
            dep_time = s[2] if len(s) > 2 else ""
            tag = s[4] if len(s) > 4 else "B"
            if date and direction:
                cur[_key(cont, city, direction, date, tag)] = dep_time

    prev = _load_prev(seen_path)
    _save(seen_path, cur)

    if prev is None:
        # 첫 실행: 기준선만 저장하고 이벤트는 남기지 않는다(전부 appear로 쏟아지는 것 방지).
        return {"first_run": True, "baseline": len(cur)}
    if any(k.count(SEP) < 4 for k in prev):
        # 등급 태그(B/U) 도입 전의 구 형식 키가 섞임 → 이번 실행은 기준선만 재설정(일회성 폭주 방지).
        return {"first_run": True, "baseline": len(cur), "migrated": True}

    prev_keys, cur_keys = set(prev.keys()), set(cur.keys())
    appeared = cur_keys - prev_keys
    disappeared = prev_keys - cur_keys

    def ev(kind, k, dep_time):
        parts = k.split(SEP)
        cont, city, direction, date = parts[0], parts[1], parts[2], parts[3]
        tag = parts[4] if len(parts) > 4 else "B"
        return json.dumps({
            "ts": ts, "event": kind,
            "cont": cont, "city": city, "dir": direction,
            "date": date, "dep_time": dep_time, "tag": tag,
        }, ensure_ascii=False)

    lines = [ev("appear", k, cur[k]) for k in sorted(appeared)]
    lines += [ev("disappear", k, prev.get(k, "")) for k in sorted(disappeared)]

    if lines:
        os.makedirs(os.path.dirname(events_path), exist_ok=True)
        with open(events_path, "a", encoding="utf-8") as f:
            f.write("\n".join(lines) + "\n")

    return {"appeared": len(appeared), "disappeared": len(disappeared), "now": len(cur)}
