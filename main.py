#!/usr/bin/env python3
"""
zoomwatch 메인 — 수집 → 매칭/델타 → 알림 → 스냅샷 저장.

실행:
  python3 main.py                # 실제 수집(GitHub Actions 등 인터넷 열린 환경)
  ZOOMWATCH_BASE=./_testfixture/data python3 main.py   # 로컬 픽스처로 테스트
  NOTIFY_PROVIDER=console python3 main.py              # 알림 대신 콘솔 출력

환경변수:
  ZOOMWATCH_BASE    데이터 베이스 URL/경로 (기본 https://zoommytrip.kr/data/)
  NOTIFY_PROVIDER   kakao | telegram | console (기본 console)
  KAKAO_REST_API_KEY, KAKAO_REFRESH_TOKEN      (카카오 사용 시)
  TELEGRAM_BOT_TOKEN, TELEGRAM_CHAT_ID         (텔레그램 사용 시)
"""
import json
import os
import sys

from zoomwatch import source, logic, notify, board, history, trips_alert, daily_new

ROOT = os.path.dirname(os.path.abspath(__file__))
WATCHLIST_PATH = os.path.join(ROOT, "config", "watchlist.json")
STATE_PATH = os.path.join(ROOT, "state", "snapshot.json")
DOCS_DATA_PATH = os.path.join(ROOT, "docs", "data.json")
SEEN_BOARD_PATH = os.path.join(ROOT, "state", "seen_board.json")
HISTORY_EVENTS_PATH = os.path.join(ROOT, "history", "events.jsonl")
TRIPS_PATH = os.path.join(ROOT, "docs", "trips.json")
TRIPS_SEEN_PATH = os.path.join(ROOT, "state", "trips_seen.json")
DAILY_NEW_PATH = os.path.join(ROOT, "state", "daily_new.json")


def load_watches():
    with open(WATCHLIST_PATH, "r", encoding="utf-8") as f:
        cfg = json.load(f)
    return [w for w in cfg.get("watches", [])]


def load_prev_snapshot():
    if os.path.exists(STATE_PATH):
        try:
            with open(STATE_PATH, "r", encoding="utf-8") as f:
                return json.load(f)
        except Exception:
            return {}
    return {}


def save_snapshot(snap):
    os.makedirs(os.path.dirname(STATE_PATH), exist_ok=True)
    with open(STATE_PATH, "w", encoding="utf-8") as f:
        json.dump(snap, f, ensure_ascii=False)


def main():
    watches = load_watches()
    enabled = [w for w in watches if w.get("enabled", True)]
    if not enabled:
        print("활성화된 워치가 없습니다.")
        return 0

    base = os.environ.get("ZOOMWATCH_BASE")
    try:
        records, index = source.collect(enabled, base=base)
    except Exception as e:
        print(f"::error:: 수집 실패: {type(e).__name__}: {e}")
        return 1

    # 보드용 data.json 출력(매 실행, 알림 로직과 무관하게 전체 좌석을 보드로 내보냄)
    bd = None
    try:
        bd = board.build_board_data(base=base)
        # 화면 '새로 뜬 좌석' 표식을 '전날(기준선) 대비 신규'로 재계산해 덮어씀
        dn = daily_new.mark_new(bd, DAILY_NEW_PATH)
        board.dump(DOCS_DATA_PATH, bd)
        print(f"보드 데이터 출력: docs/data.json ({len(bd['cities'])}개 도시, updated={bd['updated']}, 오늘 신규 {dn['new']}건/기준선 {dn['baseline']})")
    except Exception as e:
        print(f"::warning:: 보드 데이터 출력 실패: {type(e).__name__}: {e}")

    # 변화 로그 누적(미래 예측용): 좌석 appear/disappear 이벤트를 history/events.jsonl에 추가
    if bd is not None:
        try:
            h = history.update_from_board(bd, SEEN_BOARD_PATH, HISTORY_EVENTS_PATH)
            print(f"히스토리: {h}")
        except Exception as e:
            print(f"::warning:: 히스토리 기록 실패: {type(e).__name__}: {e}")

    # 타겟 여행 알림: trips.json의 여행 날짜에 좌석이 새로 뜨면 알림
    if bd is not None:
        try:
            trips = trips_alert.load_trips(TRIPS_PATH)
            if trips:
                t_alerts, _ = trips_alert.check(trips, bd, TRIPS_SEEN_PATH)
                tmsg = trips_alert.format_msg(t_alerts)
                if tmsg:
                    print("---- 타겟 여행 알림 ----")
                    print(tmsg)
                    try:
                        notify.notify(tmsg)
                    except Exception as e:
                        print(f"::error:: 타겟 알림 발송 실패: {type(e).__name__}: {e}")
                else:
                    print(f"타겟 여행 {len(trips)}건 — 새로 뜬 좌석 없음")
            else:
                print("타겟 여행 없음(docs/trips.json 비어있음)")
        except Exception as e:
            print(f"::warning:: 타겟 알림 처리 실패: {type(e).__name__}: {e}")

    prev = load_prev_snapshot()
    first_run = not prev  # 첫 실행이면 전부 '신규'로 쏟아지지 않게 알림은 건너뛰고 기준선만 저장

    alerts, snapshot = logic.run(enabled, records, prev)

    print(f"수집 레코드 {len(records)}건 / index updated_at={index.get('updated_at')} "
          f"/ 매칭·신규 알림 후보 {len(alerts)}건 / 첫실행={first_run}")

    if first_run:
        print("첫 실행: 기준 스냅샷만 저장하고 알림은 생략합니다(다음 실행부터 '신규'가 의미를 가짐).")
        save_snapshot(snapshot)
        return 0

    msg = notify.format_alerts(alerts)
    if msg:
        print("---- 알림 내용 ----")
        print(msg)
        try:
            notify.notify(msg)
        except Exception as e:
            print(f"::error:: 알림 발송 실패: {type(e).__name__}: {e}")
            # 알림 실패해도 스냅샷은 저장(같은 좌석으로 반복 실패 방지). 필요시 이 줄을 빼면 재시도됨.
    else:
        print("새로 뜬 좌석 없음 — 알림 생략.")

    save_snapshot(snapshot)
    return 0


if __name__ == "__main__":
    sys.exit(main())
