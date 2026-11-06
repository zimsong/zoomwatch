#!/usr/bin/env python3
"""
카카오 '나에게 보내기' refresh_token 발급 도우미.
대표님 컴퓨터에서 한 번만 실행하면 됩니다. (표준 라이브러리만 사용)

사전 준비 (카카오 개발자 사이트, developers.kakao.com):
  1) 내 애플리케이션 > 애플리케이션 추가하기 → 앱 생성
  2) 앱 설정 > 요약 정보 > 'REST API 키' 복사
  3) 제품 설정 > 카카오 로그인 > 활성화 ON
  4) 제품 설정 > 카카오 로그인 > Redirect URI 등록: https://localhost  (정확히 이 값)
  5) 제품 설정 > 카카오 로그인 > 동의항목 > '카카오톡 메시지 전송(talk_message)' 사용 설정

그다음 이 스크립트를 실행하고 안내를 따라가세요:
  python3 tools/kakao_get_token.py
"""
import json
import sys
import urllib.parse
import urllib.request

AUTH = "https://kauth.kakao.com/oauth/authorize"
TOKEN = "https://kauth.kakao.com/oauth/token"
REDIRECT = "https://localhost"


def post(url, data, headers=None):
    body = urllib.parse.urlencode(data).encode()
    req = urllib.request.Request(url, data=body, headers=headers or {})
    with urllib.request.urlopen(req, timeout=30) as r:
        return json.load(r)


def main():
    print("=== 카카오 refresh_token 발급 ===\n")
    rest = input("1) REST API 키를 붙여넣고 Enter: ").strip()
    if not rest:
        print("REST API 키가 필요합니다."); return 1

    params = urllib.parse.urlencode({
        "client_id": rest,
        "redirect_uri": REDIRECT,
        "response_type": "code",
        "scope": "talk_message",
    })
    url = f"{AUTH}?{params}"
    print("\n2) 아래 주소를 브라우저에 붙여넣어 열고, 카카오 로그인 후 '동의하기'를 누르세요:\n")
    print("   " + url)
    print("\n   동의하면 주소창이 'https://localhost/?code=XXXXX' 로 바뀝니다.")
    print("   (localhost 페이지는 안 열려도 정상 — 주소창의 code 값만 쓰면 됩니다.)\n")

    code = input("3) 주소창의 code= 뒤 값을 붙여넣고 Enter: ").strip()
    if not code:
        print("code 값이 필요합니다."); return 1

    try:
        tok = post(TOKEN, {
            "grant_type": "authorization_code",
            "client_id": rest,
            "redirect_uri": REDIRECT,
            "code": code,
        })
    except urllib.error.HTTPError as e:
        print("\n발급 실패:", e.read().decode()[:300])
        print("code는 1회용이라 만료됐을 수 있습니다. 2번 주소부터 다시 시도하세요.")
        return 1

    print("\n=== 발급 완료 ===")
    print("아래 두 값을 GitHub Secrets에 등록하세요:\n")
    print("  KAKAO_REST_API_KEY   =", rest)
    print("  KAKAO_REFRESH_TOKEN  =", tok.get("refresh_token"))
    print("\n(access_token은 매 실행 때 자동 갱신되므로 저장할 필요 없습니다.)")

    # 테스트 발송
    if input("\n지금 테스트 메시지를 '나에게' 보내볼까요? (y/N): ").strip().lower() == "y":
        try:
            post("https://kapi.kakao.com/v2/api/talk/memo/default/send",
                 {"template_object": json.dumps({
                     "object_type": "text",
                     "text": "zoomwatch 연결 테스트 ✅ 이 메시지가 보이면 알림이 정상 작동합니다.",
                     "link": {"web_url": "https://zoommytrip.kr/", "mobile_web_url": "https://zoommytrip.kr/"},
                 }, ensure_ascii=False)},
                 headers={"Authorization": "Bearer " + tok["access_token"]},
                 )
            print("보냈습니다. 카카오톡 '나와의 채팅'을 확인하세요.")
            print("※ 알림(배지/푸시)이 뜨는지도 꼭 확인하세요 — 안 뜨면 텔레그램으로 바꾸는 게 낫습니다.")
        except urllib.error.HTTPError as e:
            print("테스트 발송 실패:", e.read().decode()[:300])
    return 0


if __name__ == "__main__":
    sys.exit(main())
