"""
하루 단위 '새로 뜬 좌석' 판정 (화면 삼각 표식용).

목표: "전날 대비 오늘 새로 생긴 좌석"을 하루 동안 표시한다.

방식:
- 매 KST 날짜마다, '어제의 마지막 상태(last)'를 그날의 기준선(baseline)으로 고정한다.
- 그날 동안은 계속 그 기준선과 비교해서, 기준선에 없던 좌석만 is_new=1로 표시한다.
- 매 실행마다 '오늘의 최신 상태(last)'를 갱신해 두고, 다음 날 첫 실행 때 그게 기준선이 된다.
- 최초 실행(상태 없음)에는 기준선=현재라 신규 0건(한꺼번에 쏟아짐 방지).

상태 파일: state/daily_new.json = {date, baseline:[key...], last:[key...]}
key 형식: "city|dir|date"  (dir: O 가는편 / I 오는편)

board.build_board_data() 결과(dict)의 각 좌석 is_new(seat[3])를 이 기준으로 덮어쓴다.
(zoommytrip 자체 is_new 대신 우리의 '전날 대비' 기준을 쓴다.)
"""
import json
import os
from datetime import datetime, timezone, timedelta

KST = timezone(timedelta(hours=9))


def _keys(board_data):
    s = set()
    for c in board_data.get("cities", []):
        city = c.get("city", "")
        for seat in c.get("seats", []):
            if len(seat) >= 2:
                s.add(city + "|" + seat[1] + "|" + seat[0])
    return s


def _load(path):
    if os.path.exists(path):
        try:
            with open(path, "r", encoding="utf-8") as f:
                return json.load(f)
        except Exception:
            return {}
    return {}


def _save(path, data):
    os.makedirs(os.path.dirname(path), exist_ok=True)
    with open(path, "w", encoding="utf-8") as f:
        json.dump(data, f, ensure_ascii=False, separators=(",", ":"))


def mark_new(board_data, state_path):
    today = datetime.now(KST).strftime("%Y-%m-%d")
    cur = sorted(_keys(board_data))
    cur_set = set(cur)
    st = _load(path=state_path)

    if st.get("date") == today:
        # 오늘 안: 기준선 그대로 유지, 최신 상태만 갱신
        baseline = set(st.get("baseline", []))
        st["last"] = cur
    else:
        # 새 날 첫 실행: 어제의 마지막 상태(last)를 오늘 기준선으로 고정
        baseline = set(st.get("last", cur))  # 최초 실행이면 cur → 신규 0
        st = {"date": today, "baseline": sorted(baseline), "last": cur}

    _save(state_path, st)
    new_keys = cur_set - baseline

    cnt = 0
    for c in board_data.get("cities", []):
        city = c.get("city", "")
        for seat in c.get("seats", []):
            if len(seat) < 2:
                continue
            k = city + "|" + seat[1] + "|" + seat[0]
            v = 1 if k in new_keys else 0
            if len(seat) >= 4:
                seat[3] = v
            cnt += v

    return {"date": today, "new": cnt, "baseline": len(baseline)}
