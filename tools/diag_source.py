# -*- coding: utf-8 -*-
"""일회성 진단: zoommytrip 현재 데이터 구조를 로그로 덤프한다."""
import os, json, traceback
import sys
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from collections import Counter
os.environ.setdefault("ZOOMWATCH_FETCH", "browser")
from zoomwatch import source

def j(o, n=600):
    try: return json.dumps(o, ensure_ascii=False)[:n]
    except Exception: return str(o)[:n]

try:
    idx = source.load_index()
    print("TOPKEYS:", list(idx.keys()))
    print("UPDATED_AT:", idx.get("updated_at"))
    files = idx.get("files", [])
    print("FILES_LEN:", len(files))
    print("AIRLINES:", dict(Counter(f.get("airline") for f in files)))
    print("TYPES:", dict(Counter(f.get("type") for f in files)))
    print("CONTINENTS:", dict(Counter(f.get("continent") for f in files)))
    for i, f in enumerate(files[:3]):
        safe = {k: (f"[{len(v)} parts]" if k == "parts" and isinstance(v, list) else v) for k, v in f.items()}
        print(f"ENTRY[{i}]:", j(safe, 500))
    ke = source.files_for(idx, airline="KE", trip="oneway")
    print("KE_ONEWAY_FILES:", len(ke))
    if not ke and files:
        # 필터가 0이면, oneway 비슷한/KE 비슷한 걸 완화 탐색
        print("FALLBACK_any_oneway:", len(source.files_for(idx, trip="oneway")))
        print("FALLBACK_KE_any:", len(source.files_for(idx, airline="KE")))
    if ke:
        f0 = ke[0]
        print("F0_KEYS:", list(f0.keys()))
        top = source._load(idx.get("_base"), f0.get("url") or f0.get("file"))
        print("TOP_KEYS:", list(top.keys())[:20], "rows_type:", type(top.get("rows")).__name__)
        print("TOP_COLUMNS:", (top.get("columns") or [])[:20])
        print("PARTS_LEN:", len(f0.get("parts", [])))
        if f0.get("parts"):
            p0 = f0["parts"][0]
            print("PART0_KEYS:", list(p0.keys()), "PART0:", j(p0, 300))
            pdoc = source._load(idx.get("_base"), p0.get("url"))
            print("PDOC_KEYS:", list(pdoc.keys())[:20], "PDOC_COLS:", (pdoc.get("columns") or [])[:20])
            rows = pdoc.get("rows")
            print("PDOC_ROWS_TYPE:", type(rows).__name__, "N:", (len(rows) if isinstance(rows, list) else rows))
            if isinstance(rows, list) and rows:
                print("PDOC_ROW0:", j(rows[0], 300))
        recs = source.fetch_records(idx, f0)
        print("REC_COUNT_FILE0:", len(recs))
        if recs:
            print("REC0:", j(recs[0], 400))
except Exception as e:
    print("DIAG_ERROR:", type(e).__name__, e)
    traceback.print_exc()
finally:
    try: source.close_browser()
    except Exception: pass
