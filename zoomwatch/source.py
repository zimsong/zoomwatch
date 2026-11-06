"""
zoommytrip 공개 데이터(/data/*.json) 수집·파싱·정규화 모듈.

구조 (2026-11 브라우저 분석으로 확인):
  BASE/index.json  → 파일 카탈로그. files[]: {airline, type, continent, url, parts[...]}
  데이터 파일/파트 → {columns:[...], rows:[[...]...]}  (행은 컬럼 순서의 값 배열)

왕복/편도는 컬럼 구조가 다르다:
  왕복(roundtrip): route, city, cabin, dep_date, ret_date, nights, dep_time, ret_time,
                   min_seats, award_region, miles_low, miles_peak, out_seats, ret_seats, is_new
  편도(oneway):    date, direction(outbound/inbound), route, city, dep_time,
                   first, business, upgrade(각각 좌석 O/0), award_region, is_new
  편도 파일은 top-level에 rows가 없고 월별 parts로만 존재. 승급은 oneway의 upgrade 컬럼.

→ 둘을 '공통 레코드(canonical)'로 정규화해서 뒤쪽 로직이 한 형태만 다루게 한다.
공통 레코드 필드:
  airline, trip, continent, city, route,
  cabin('business'|'first'|'upgrade'),
  direction('outbound'|'inbound'|'roundtrip'),
  dep_date, ret_date, dep_time, ret_time,
  seat_out(이 편/가는편 좌석 'O'/'-'), seat_ret(왕복 오는편 좌석),
  miles_low, miles_peak, award_region, is_new
"""
import json
import os
import urllib.request
from urllib.parse import urljoin

DEFAULT_BASE = "https://zoommytrip.kr/data/"
CABIN_COLS = ("business", "first", "upgrade")  # 편도 파일의 좌석 컬럼들

# 서버(GitHub Actions)에서 요청해도 차단되지 않도록 실제 브라우저처럼 보이는 헤더.
BROWSER_UA = ("Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 "
              "(KHTML, like Gecko) Chrome/125.0.0.0 Safari/537.36")


def _get_json(url, timeout=30):
    req = urllib.request.Request(url, headers={
        "User-Agent": BROWSER_UA,
        "Accept": "application/json, text/plain, */*",
        "Accept-Language": "ko,en-US;q=0.9,en;q=0.8",
        "Referer": "https://zoommytrip.kr/",
    })
    with urllib.request.urlopen(req, timeout=timeout) as r:
        status = getattr(r, "status", None)
        ctype = r.headers.get("Content-Type", "")
        raw = r.read()
    try:
        return json.loads(raw)
    except Exception as e:
        # 실패 시 무엇이 돌아왔는지 진단용으로 남긴다(원인 파악).
        snippet = raw[:300].decode("utf-8", "replace") if raw else "(빈 응답)"
        raise RuntimeError(
            f"JSON 파싱 실패 @ {url} status={status} content-type={ctype!r} "
            f"len={len(raw)} body[:300]={snippet!r}"
        ) from e


# ---- 브라우저 기반 수집 (JS 봇 차단 통과용) ----
# zoommytrip은 접속 시 JS 챌린지(cupid.js: 쿠키 계산 후 재요청)를 요구한다.
# 일반 HTTP로는 HTML 챌린지 페이지만 돌아와 JSON 파싱이 실패하므로,
# 실제 브라우저(Playwright/Chromium)로 JS를 실행해 통과시킨다.
# 환경변수 ZOOMWATCH_FETCH=browser 일 때만 사용.
_PW_STATE = None


def _browser_session():
    global _PW_STATE
    if _PW_STATE is not None:
        return _PW_STATE
    from playwright.sync_api import sync_playwright
    pw = sync_playwright().start()
    browser = pw.chromium.launch(args=["--no-sandbox", "--disable-dev-shm-usage"])
    ctx = browser.new_context(user_agent=BROWSER_UA, locale="ko-KR")
    page = ctx.new_page()
    # 데이터 경로로 진입해 JS 챌린지가 쿠키를 세팅하도록 한 번 통과시킨다.
    page.goto("https://zoommytrip.kr/data/index.json",
              wait_until="networkidle", timeout=60000)
    _PW_STATE = (pw, browser, ctx, page)
    return _PW_STATE


def _browser_get_json(url, timeout=60000):
    _, _, ctx, page = _browser_session()
    resp = ctx.request.get(url, headers={"Referer": "https://zoommytrip.kr/"}, timeout=timeout)
    raw = resp.body()
    try:
        return json.loads(raw)
    except Exception:
        # 쿠키가 아직이면 페이지로 직접 이동해 챌린지를 통과한 뒤 본문을 파싱
        page.goto(url, wait_until="networkidle", timeout=timeout)
        el = page.query_selector("pre")
        txt = el.inner_text() if el else page.evaluate("document.body.innerText")
        return json.loads(txt)


def close_browser():
    global _PW_STATE
    if _PW_STATE:
        pw, browser, ctx, page = _PW_STATE
        try:
            browser.close()
        finally:
            pw.stop()
        _PW_STATE = None


def _read_local(path):
    with open(path, "r", encoding="utf-8") as f:
        return json.load(f)


def _resolve(base, ref):
    if ref.startswith("http://") or ref.startswith("https://"):
        return ref
    if base.startswith("http://") or base.startswith("https://"):
        return urljoin(base, ref)
    return os.path.join(base, os.path.basename(ref))  # 로컬 픽스처


def _load(base, ref):
    url = _resolve(base, ref)
    if url.startswith("http://") or url.startswith("https://"):
        if os.environ.get("ZOOMWATCH_FETCH") == "browser":
            return _browser_get_json(url)
        return _get_json(url)
    return _read_local(url)


def load_index(base=None):
    base = base or os.environ.get("ZOOMWATCH_BASE") or DEFAULT_BASE
    index = _load(base, "index.json")
    index["_base"] = base
    return index


def files_for(index, airline="any", trip="any", continent=None):
    out = []
    for f in index.get("files", []):
        if airline != "any" and f.get("airline") != airline:
            continue
        if trip != "any" and f.get("type") != trip:
            continue
        if continent and f.get("continent") != continent:
            continue
        out.append(f)
    return out


def _raw_rows(doc):
    cols = doc.get("columns") or []
    for r in doc.get("rows") or []:
        yield {cols[i]: (r[i] if i < len(r) else None) for i in range(len(cols))}


def _normalize_row(raw, meta):
    """raw 행 dict → 공통 레코드 리스트(편도는 좌석 등급별로 여러 건으로 펼침)."""
    airline = meta.get("airline")
    trip = meta.get("type")
    continent = meta.get("continent")
    base = dict(airline=airline, trip=trip, continent=continent,
                city=raw.get("city"), route=raw.get("route"),
                award_region=raw.get("award_region"), is_new=raw.get("is_new"))

    if trip == "roundtrip":
        rec = dict(base)
        rec.update(
            cabin=raw.get("cabin"),
            direction="roundtrip",
            dep_date=raw.get("dep_date"),
            ret_date=raw.get("ret_date"),
            dep_time=raw.get("dep_time"),
            ret_time=raw.get("ret_time"),
            seat_out=raw.get("out_seats"),
            seat_ret=raw.get("ret_seats"),
            miles_low=raw.get("miles_low"),
            miles_peak=raw.get("miles_peak"),
        )
        return [rec]

    # oneway (편도): 좌석 등급별 컬럼을 각각 1건으로 펼친다
    out = []
    for cabin in CABIN_COLS:
        if cabin not in raw:
            continue
        seat = raw.get(cabin)
        rec = dict(base)
        rec.update(
            cabin=cabin,
            direction=raw.get("direction"),      # outbound(가는편) / inbound(오는편)
            dep_date=raw.get("date"),
            ret_date=None,
            dep_time=raw.get("dep_time"),
            ret_time=None,
            seat_out=seat,                        # 이 등급·이 편의 좌석 가부
            seat_ret=None,
            miles_low=None, miles_peak=None,      # 편도 파일엔 마일 정보 없음
        )
        out.append(rec)
    return out


def fetch_records(index, file_entry):
    """파일 1개(대륙 단위) → 공통 레코드 리스트. top-level rows가 없으면 월별 parts를 합침."""
    base = index.get("_base", DEFAULT_BASE)
    docs = []
    top = _load(base, file_entry.get("url") or file_entry.get("file"))
    if top.get("rows"):
        docs.append(top)
    else:
        top_cols = top.get("columns")
        for p in file_entry.get("parts", []):
            pdoc = _load(base, p.get("url"))
            if "columns" not in pdoc and top_cols:
                pdoc["columns"] = top_cols
            docs.append(pdoc)

    recs = []
    for doc in docs:
        for raw in _raw_rows(doc):
            recs.extend(_normalize_row(raw, file_entry))
    return recs


def collect(watches, base=None):
    """워치리스트가 필요로 하는 파일을 (중복 1회) 수집 → 공통 레코드 전체 반환."""
    index = load_index(base)
    seen = {}
    for w in watches:
        if not w.get("enabled", True):
            continue
        for f in files_for(index, w.get("airline", "any"), w.get("trip", "any"), w.get("continent")):
            seen[f.get("file") or f.get("url")] = f
    records = []
    for f in seen.values():
        records.extend(fetch_records(index, f))
    return records, index
