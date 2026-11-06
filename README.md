# zoomwatch — 마일리지 보너스 좌석 감시·알림 (개인/가족용)

zoommytrip.kr이 매일 공개하는 대한항공·아시아나 마일리지 좌석 데이터(`/data/*.json`)를 읽어,
**대표님이 지정한 구간(예: 인천-밴쿠버 비즈)에 새 좌석이 뜨면 카카오톡으로 알려주는** 개인 도구입니다.

- 상업용 아님, 비공개(대표님과 가족만), 공개 JSON만 읽음(로그인·크롤링 없음), 하루 4회.
- 외부 라이브러리 없이 **파이썬 표준 라이브러리만** 사용 → GitHub Actions에서 설치 없이 그대로 돕니다.

---

## 0. 먼저 알아둘 제약 (솔직하게)

1. **zoommytrip 데이터에 종속됩니다.** 그 사이트가 `/data/` 구조를 바꾸거나 닫으면 이 도구도 멈춥니다.
   공개 JSON이라 HTML보다 안정적이지만, 영구 보장은 아닙니다.
2. **신선도는 zoommytrip의 수집 주기만큼**입니다. 그쪽이 자정 직후(약 00:35) 수집하고 낮에도 갱신하므로,
   이 도구도 그 범위 안에서만 최신입니다. **오픈런(오픈 즉시 초 단위 경쟁) 예약용이 아니라, 취소표·신규 좌석 감시용**입니다.
3. **카카오 '나에게 보내기'는 알림(푸시)이 안 뜰 수 있습니다** (카카오 공식 안내상 '메모' 취급).
   발급 후 테스트에서 핑이 안 울리면, 아래 "텔레그램으로 바꾸기"로 교체하세요. 가족 공유도 텔레그램이 낫습니다.

---

## 1. 동작 구조

```
GitHub Actions(하루 4회 cron)
   └─ main.py
        1) config/watchlist.json 의 감시 구간을 읽고
        2) https://zoommytrip.kr/data/index.json 에서 파일 목록을 찾아
        3) 데이터 파일(JSON)을 받아 레코드로 정규화(편도/왕복 스키마 통합)
        4) [보드] 전 도시 편도 비즈(프레스티지) 좌석을 docs/data.json 으로 출력
        5) 어제 스냅샷(state/snapshot.json)과 비교해 '새로 뜬 좌석'만 추려
        6) 카카오톡 '나에게 보내기'로 발송
        7) state/snapshot.json + docs/data.json 커밋(다음 비교 기준 · 보드 갱신)

   └─ GitHub Pages가 docs/ 폴더를 웹사이트로 서빙
        → 좌석 보드(docs/index.html)가 같은 자리의 docs/data.json을 읽어
          매일 자동 갱신. CORS 문제 없음(같은 도메인).
        → https://<GitHub사용자명>.github.io/<저장소명>/ 로 어디서나 접속
```

---

## 2. 설치 (약 15분)

### 2-1. GitHub 저장소 만들기
1. github.com 에서 **New repository** → 이름 예: `zoomwatch` → **Private**(비공개)로 생성.
2. 이 폴더의 파일들을 그 저장소에 올립니다. (GitHub Desktop 앱으로 드래그, 또는 터미널에서 `git push`)

### 2-2. 카카오 앱 만들고 토큰 발급
`tools/kakao_get_token.py` 안의 사전 준비(1~5단계)를 먼저 한 뒤, 본인 컴퓨터에서:
```
python3 tools/kakao_get_token.py
```
안내대로 따라가면 끝에 **KAKAO_REST_API_KEY**와 **KAKAO_REFRESH_TOKEN** 두 값을 출력합니다. 복사해 두세요.

### 2-3. GitHub Secrets 등록
저장소 → **Settings → Secrets and variables → Actions → New repository secret** 에서 아래를 등록:

| 이름 | 값 |
|---|---|
| `NOTIFY_PROVIDER` | `kakao` |
| `KAKAO_REST_API_KEY` | (2-2에서 받은 값) |
| `KAKAO_REFRESH_TOKEN` | (2-2에서 받은 값) |

### 2-4. 자동 실행 확인
저장소 → **Actions** 탭 → 워크플로우 `zoomwatch` → **Run workflow**(수동 실행) 버튼으로 한 번 돌려봅니다.
- 첫 실행은 **기준 스냅샷만 저장하고 알림을 보내지 않습니다**(정상). 다음 실행부터 '새로 뜬 좌석'이 의미를 가집니다.
- 단, **보드 데이터(docs/data.json)는 첫 실행부터 갱신**됩니다.
- 이후에는 하루 4회(한국시간 01:00 / 09:10 / 13:00 / 21:00) 자동 실행됩니다.

### 2-5. 좌석 보드를 웹에 공개 (GitHub Pages)
저장소 → **Settings → Pages** 에서:
- **Source**: `Deploy from a branch`
- **Branch**: `main` / 폴더 `/docs` → **Save**

1~2분 뒤 `https://<GitHub사용자명>.github.io/<저장소명>/` 주소로 좌석 보드가 열립니다.
이 주소는 북마크해 두면 PC·폰 어디서나 접속 가능하고, Actions가 돌 때마다 데이터가 자동으로 바뀝니다.
- 비공개로 쓰고 싶으면: Public 저장소 + Pages 공개가 가장 간단합니다(주소를 모르면 접근은 어렵지만 완전 비공개는 아님).
  완전 비공개가 필요하면 저장소를 Private로 두고 Pages의 접근 제한(유료 플랜) 또는 로컬에서 docs/index.html 직접 열기를 쓰세요.
- 보드 화면만 바꾸고 싶을 때는 `docs/index.html` 을 수정해 커밋하면 됩니다.

---

## 3. 감시 구간 바꾸기 — `config/watchlist.json`

`watches` 배열에 항목을 추가하거나 `enabled`를 바꾸면 됩니다. 주요 필드:

| 필드 | 뜻 |
|---|---|
| `airline` | `KE`(대한항공) / `OZ`(아시아나) / `any` |
| `trip` | `roundtrip`(왕복) / `oneway`(편도) / `any` |
| `continent` | `north_america` / `asia` / `japan` / `europe` / `oceania` |
| `city_contains` | 도시명 일부. `"밴쿠버"`. 비우면 대륙 전체 |
| `cabin` | `business` / `first` / `upgrade`(승급) / `any` |
| `direction` | 편도 전용. `outbound`(가는편) / `inbound`(오는편) / `any` |
| `dep_from`, `dep_to` | 출발일 범위 (YYYY-MM-DD). 비우면 제한 없음 |
| `dep_dates` | 콕 집은 날짜들. 예: `["2027-07-25","2027-07-26"]` |
| `require_out_seat` | 해당 좌석이 `O`여야 알림 |
| `require_ret_seat` | 왕복 오는편 좌석까지 `O`여야 알림 |
| `notify` | `new`(어제 없던 신규만) / `all`(조건 맞으면 매번) |

**다른 나라 갈 때**: 예시로 꺼둔 "도쿄" 항목처럼 새 항목을 만들고 `enabled: true`로 바꾸면 됩니다.
**특정 여행일을 노릴 때**: `dep_dates`에 날짜를 넣고 `notify: "all"`로 두면 그 날짜 좌석이 있을 때마다 알립니다.

---

## 4. 로컬에서 테스트

실제 수집 없이, 포함된 샘플 데이터로 동작을 확인:
```
ZOOMWATCH_BASE=./_testfixture/data NOTIFY_PROVIDER=console python3 main.py
```
`state/snapshot.json`을 지우면 '첫 실행(기준선)' 상태로 돌아갑니다.

---

## 5. 텔레그램으로 바꾸기 (카카오 알림이 약하면)

1. 텔레그램에서 `@BotFather`로 봇 생성 → **봇 토큰** 받기.
2. 가족 그룹방을 만들고 그 봇을 초대, 아무 메시지나 보낸 뒤
   `https://api.telegram.org/bot<봇토큰>/getUpdates` 를 열어 그룹의 **chat id**(보통 `-100…`)를 확인.
3. GitHub Secrets를 이렇게 바꿉니다:

| 이름 | 값 |
|---|---|
| `NOTIFY_PROVIDER` | `telegram` |
| `TELEGRAM_BOT_TOKEN` | (봇 토큰) |
| `TELEGRAM_CHAT_ID` | (그룹 chat id) |

코드 수정 없이 알림 채널만 바뀝니다. 가족 전원이 그룹방에서 함께 받습니다.

---

## 6. 유지보수 메모

- 카카오 `refresh_token`은 약 2개월마다 교체가 필요할 수 있습니다. 갱신되면 **본인 카톡('나와의 채팅')으로 새 값이 전송**됩니다
  (공개 저장소라 Actions 로그에는 토큰을 남기지 않음). 그 값으로 `KAKAO_REFRESH_TOKEN` 시크릿을 교체하세요.
- 데이터 구조(컬럼·경로)는 2026-11-06 기준입니다. zoommytrip이 바꾸면 `zoomwatch/source.py`의 정규화 부분을 손봐야 합니다.
```
데이터 출처: https://zoommytrip.kr/data/index.json  (BASE = https://zoommytrip.kr/data/)
왕복 컬럼: route, city, cabin, dep_date, ret_date, nights, dep_time, ret_time, min_seats, award_region, miles_low, miles_peak, out_seats, ret_seats, is_new
편도 컬럼: date, direction(outbound/inbound), route, city, dep_time, first, business, upgrade, award_region, is_new  (월별 parts 파일)
```
