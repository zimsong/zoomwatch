"""
보드용 data.json 생성 모듈.

zoommytrip 공개 데이터에서 **편도(oneway)·비즈니스(프레스티지) 좌석만** 뽑아
좌석 보드(docs/index.html)가 바로 읽는 포맷으로 docs/data.json을 만든다.

보드 포맷:
  {
    "updated": "2026-11-06T17:09+09:00",
    "note": "...",
    "cities": [
      {"cont": "북미", "city": "밴쿠버",
       "seats": [[date, dir('O'|'I'), dep_time, is_new(0|1)], ...]},
      ...
    ]
  }
  dir: 'O'=가는편(outbound, ICN→도시), 'I'=오는편(inbound, 도시→ICN)

워치리스트와 무관하게 전 대륙 편도 파일을 모두 모은다(보드는 전체를 보여주므로).
"""
import json
import os
from datetime import datetime, timezone, timedelta

from . import source

# zoommytrip 대륙 키 → 보드 표기(한글)
CONT_KO = {
    "north_america": "북미",
    "japan": "일본",
    "asia": "아시아",
    "europe": "유럽",
    "oceania": "오세아니아",
}
# 보드 섹션 정렬 순서
CONT_ORDER = {"북미": 0, "일본": 1, "아시아": 2, "유럽": 3, "오세아니아": 4}
KST = timezone(timedelta(hours=9))


def _available(seat):
    """좌석 값이 'O'면 가능. (zoommytrip 편도 좌석 컬럼은 'O' 또는 0)"""
    return seat is not None and str(seat).strip().upper() == "O"


def build_board_data(base=None, airline="KE", cabin="business"):
    index = source.load_index(base)
    files = source.files_for(index, airline=airline, trip="oneway")

    bycity = {}  # city -> {"cont": 한글, "seats": {(date,dir): (time, is_new)}}
    for f in files:
        cont_ko = CONT_KO.get(f.get("continent"), f.get("continent") or "기타")
        for rec in source.fetch_records(index, f):
            if rec.get("cabin") != cabin:
                continue
            if not _available(rec.get("seat_out")):
                continue
            city = rec.get("city")
            date = rec.get("dep_date")
            if not city or not date:
                continue
            direction = "O" if rec.get("direction") == "outbound" else "I"
            t = rec.get("dep_time") or ""
            isnew = 1 if rec.get("is_new") else 0
            entry = bycity.setdefault(city, {"cont": cont_ko, "seats": {}})
            key = (date, direction)
            prev = entry["seats"].get(key)
            # 같은 날짜·방향 중복 시 신규 플래그가 있으면 살림
            if prev is None or (isnew and not prev[1]):
                entry["seats"][key] = (t, isnew)

    cities = []
    for city, v in bycity.items():
        seats = [[d, dr, t, n]
                 for (d, dr), (t, n) in sorted(v["seats"].items(),
                                               key=lambda x: (x[0][0], x[0][1]))]
        cities.append({"cont": v["cont"], "city": city, "seats": seats})

    # 대륙 순서 → 좌석 많은 도시 우선(밴쿠버가 북미 맨 위로)
    cities.sort(key=lambda c: (CONT_ORDER.get(c["cont"], 9), -len(c["seats"]), c["city"]))

    updated = datetime.now(KST).isoformat(timespec="minutes")
    return {
        "updated": updated,
        "note": "zoommytrip 공개 데이터 기반 · 편도 프레스티지(비즈) · 매일 자동 갱신",
        "cities": cities,
    }


def write_board_data(path, base=None):
    data = build_board_data(base)
    os.makedirs(os.path.dirname(path), exist_ok=True)
    with open(path, "w", encoding="utf-8") as f:
        json.dump(data, f, ensure_ascii=False, separators=(",", ":"))
    return data
