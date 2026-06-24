#!/Users/se-ung/.hermes/hermes-agent/venv/bin/python3
"""
browser-cookie3로 Chrome 네이버 세션 쿠키 추출 → Playwright storage_state 저장
Chrome이 실행 중이고 네이버에 로그인된 상태에서 실행.
"""
import browser_cookie3
import json
import os
import sys
import time
import http.cookiejar

BASE_DIR = os.path.expanduser("~/.hermes/profiles/choi-yonghyun/scripts/cafe-crawler")
STORAGE_FILE = os.path.join(BASE_DIR, "naver_storage.json")
SESSION_META = os.path.join(BASE_DIR, "naver_session_meta.json")


def log(msg):
    print(f'[{time.strftime("%H:%M:%S")}] {msg}', flush=True)


def chrome_cookie_to_playwright(chrome_cookie):
    """http.cookiejar.Cookie → Playwright storage_state cookie format"""
    # domain 정리: Chrome은 '.naver.com' 형식
    domain = chrome_cookie.domain
    if domain and not domain.startswith('.'):
        domain = f'.{domain}'

    # expires: Chrome은 Unix timestamp (float)
    expires = chrome_cookie.expires if chrome_cookie.expires else int(time.time()) + 86400 * 30

    # sameSite 매핑
    same_site_map = {0: 'Lax', 1: 'Lax', 2: 'Strict', 3: 'None'}
    same_site = same_site_map.get(getattr(chrome_cookie, 'same_site', 0), 'Lax')

    return {
        "name": chrome_cookie.name,
        "value": chrome_cookie.value,
        "domain": domain,
        "path": chrome_cookie.path or '/',
        "expires": expires,
        "httpOnly": chrome_cookie.has_nonstandard_attr('httponly') if hasattr(chrome_cookie, 'has_nonstandard_attr') else False,
        "secure": chrome_cookie.secure,
        "sameSite": same_site,
    }


def main():
    log("🔍 Chrome 브라우저에서 네이버 세션 쿠키 추출...")

    # browser-cookie3로 Chrome 쿠키 읽기
    jar = browser_cookie3.chrome(domain_name='naver.com')
    cookies = list(jar)

    # NID_SES, NID_AUT 필터
    target_cookies = [c for c in cookies if c.name in ('NID_SES', 'NID_AUT')]
    # 나머지 유용한 쿠키도 포함 (NID_JST 등)
    other_cookies = [c for c in cookies if c.name not in ('NID_SES', 'NID_AUT')]

    if not target_cookies:
        log("❌ Chrome에 NID_SES/NID_AUT 쿠키 없음. 네이버 로그인 필요.")
        sys.exit(1)

    # Playwright storage_state 형식으로 변환
    pw_cookies = [chrome_cookie_to_playwright(c) for c in target_cookies + other_cookies]

    # Playwright 호환성: boolean 필드 정규화
    for c in pw_cookies:
        c["secure"] = bool(c.get("secure", False))
        c["httpOnly"] = bool(c.get("httpOnly", False))

    # 기존 storage 로드 (origins 등 보존)
    existing = {}
    if os.path.exists(STORAGE_FILE):
        try:
            with open(STORAGE_FILE) as f:
                existing = json.load(f)
        except:
            pass

    # 중복 제거 (name + domain 기준)
    seen = set()
    deduped = []
    for c in pw_cookies:
        key = (c["name"], c["domain"])
        if key in seen:
            continue
        seen.add(key)
        deduped.append(c)

    state = {
        "cookies": deduped,
        "origins": existing.get("origins", []),
    }

    # 저장
    with open(STORAGE_FILE, "w") as f:
        json.dump(state, f, ensure_ascii=False)

    meta = {
        "saved_at": time.time(),
        "date": time.strftime("%Y-%m-%dT%H:%M:%S"),
        "cookie_count": len(deduped),
        "source": "chrome_browser_cookie3",
        "has_nid_ses": any(c["name"] == "NID_SES" for c in deduped),
        "has_nid_aut": any(c["name"] == "NID_AUT" for c in deduped),
    }
    with open(SESSION_META, "w") as f:
        json.dump(meta, f, ensure_ascii=False)

    # 결과 출력
    has_ses = meta["has_nid_ses"]
    has_aut = meta["has_nid_aut"]

    for c in target_cookies:
        log(f'  ✅ {c.name}: {c.value[:30]}...')

    if has_ses:
        log(f'✅ 네이버 세션 복원 완료! (Chrome → Playwright storage)')
        print(f'\n✅ 세션 정상')
        print(f'   저장 위치: {STORAGE_FILE}')
        print(f'   출처: Chrome 브라우저 쿠키')
        print(f'   NID_SES: ✅ | NID_AUT: {"✅" if has_aut else "❌"}')
    else:
        log("❌ NID_SES 없음")
        sys.exit(1)


if __name__ == "__main__":
    main()
