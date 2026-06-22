#!/Users/se-ung/.hermes/hermes-agent/venv/bin/python3
"""Naver ID/PW 자동 로그인 - QR/수동 개입 불필요"""

import json, os, sys, time, base64, re
from datetime import datetime
from playwright.sync_api import sync_playwright

BASE_DIR = os.path.dirname(os.path.abspath(__file__))
STORAGE_FILE = os.path.join(BASE_DIR, 'naver_storage.json')
SESSION_META = os.path.join(BASE_DIR, 'naver_session_meta.json')
CAPTCHA_FILE = os.path.join(BASE_DIR, 'captcha_screenshot.png')

NAVER_ID = sys.argv[1] if len(sys.argv) > 1 else os.environ.get('NAVER_ID')
NAVER_PW = sys.argv[2] if len(sys.argv) > 2 else os.environ.get('NAVER_PW')

def log(msg):
    print(f'[{datetime.now().strftime("%H:%M:%S")}] {msg}', flush=True)

def save_session(context):
    state = context.storage_state()
    with open(STORAGE_FILE, 'w') as f:
        json.dump(state, f, ensure_ascii=False)
    meta = {'saved_at': time.time(), 'date': datetime.now().isoformat(),
            'cookie_count': len(state.get('cookies', [])), 'auto_login': True}
    with open(SESSION_META, 'w') as f:
        json.dump(meta, f, ensure_ascii=False)

def is_logged_in(page):
    """nidlogin 페이지가 아니면 로그인됨"""
    return 'nidlogin' not in page.url.lower()

def human_type(page, selector, text):
    """사람처럼 한 글자씩 입력"""
    page.click(selector)
    time.sleep(0.3)
    for ch in text:
        page.type(selector, ch, delay=50 + int(ord(ch[0]) % 50) if ch else 50)
        time.sleep(0.02)

def auto_login():
    log('🚀 네이버 자동 로그인 시작 (ID/PW)')
    
    # Hide password from logs
    log(f'   ID: {NAVER_ID}')
    log(f'   PW: {"*" * len(NAVER_PW)}')
    
    with sync_playwright() as p:
        browser = p.chromium.launch(
            headless=True,
            args=[
                '--no-sandbox',
                '--disable-blink-features=AutomationControlled',
            ]
        )
        context = browser.new_context(
            viewport={'width': 1280, 'height': 900},
            locale='ko-KR',
            timezone_id='Asia/Seoul',
            user_agent=(
                'Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) '
                'AppleWebKit/537.36 (KHTML, like Gecko) '
                'Chrome/120.0.0.0 Safari/537.36'
            )
        )
        # Stealth: remove webdriver flag
        context.add_init_script("""
            Object.defineProperty(navigator, 'webdriver', { get: () => undefined });
            window.chrome = { runtime: {} };
            Object.defineProperty(navigator, 'plugins', { get: () => [1, 2, 3, 4, 5] });
        """)
        
        page = context.new_page()
        
        # Step 1: Go to login page (without mode=number to get ID/PW view)
        log('📍 로그인 페이지 접속...')
        page.goto('https://nid.naver.com/nidlogin.login', 
                   wait_until='networkidle', timeout=20000)
        time.sleep(2)
        
        # Step 2: If ID/PW tab not active, switch to it
        current_url = page.url
        log(f'   초기 URL: {current_url[:60]}')
        
        # Check if we're on disposable number tab - click ID tab
        id_tab = page.query_selector('#otnlog\\.logtab')
        if not id_tab:
            id_tab = page.query_selector('a[role="tab"]:has-text("ID")')
        if id_tab:
            is_selected = id_tab.get_attribute('aria-selected')
            if is_selected != 'true':
                log('📍 ID/전화번호 탭으로 전환...')
                id_tab.click()
                time.sleep(2)
                log('   ✅ ID/전화번호 탭 클릭 완료')
        
        # Step 3: Wait for ID/PW fields to appear (they load dynamically)
        log('📍 ID/PW 입력창 로딩 대기...')
        time.sleep(1)
        
        # Step 4: Fill in ID
        log('📍 아이디 입력...')
        id_input = page.query_selector('input[name="id"]')
        if not id_input:
            id_input = page.query_selector('input[id="id"]')
        if not id_input:
            # Try to find ANY visible text input
            id_input = page.query_selector('input[type="text"]:not([type="hidden"])')
        if id_input:
            human_type(page, f'input[name="{id_input.get_attribute("name")}"]', NAVER_ID)
            log('   ✅ 아이디 입력 완료')
        else:
            log('   ⚠️ 아이디 입력창 없음, 폼 직접 작성 시도')
        
        time.sleep(0.5)
        
        # Step 5: Fill in password - use fill() for reliability
        log('📍 비밀번호 입력...')
        pw_input = page.query_selector('input[name="pw"]')
        if not pw_input:
            pw_input = page.query_selector('input[id="pw"]')
        if not pw_input:
            pw_input = page.query_selector('input[type="password"]')
        if pw_input:
            pw_input.click()
            time.sleep(0.3)
            pw_input.fill(NAVER_PW)
            time.sleep(1)
            # Verify it was filled
            pw_val = page.evaluate('document.querySelector("input[name=\'pw\']")?.value')
            log(f'   PW 입력 확인: {"*" * len(pw_val if pw_val else "")} (길이: {len(pw_val) if pw_val else 0})')
            if not pw_val:
                # Fallback: JS set + dispatch events
                page.evaluate("""
                    (pw) => {
                        const el = document.querySelector('input[name="pw"]') || document.querySelector('input[type="password"]');
                        if (!el) return;
                        const nativeInputValueSetter = Object.getOwnPropertyDescriptor(window.HTMLInputElement.prototype, 'value').set;
                        nativeInputValueSetter.call(el, pw);
                        el.dispatchEvent(new Event('input', { bubbles: true }));
                        el.dispatchEvent(new Event('change', { bubbles: true }));
                    }
                """(NAVER_PW))
                time.sleep(0.5)
                pw_val = page.evaluate('document.querySelector("input[name=\'pw\']")?.value')
                log(f'   PW 재입력 확인: {"*" * len(pw_val if pw_val else "")} (길이: {len(pw_val) if pw_val else 0})')
            log('   ✅ 비밀번호 입력 완료')
        else:
            log('   ⚠️ 비밀번호 입력창 없음')
        
        time.sleep(1)
        
        # Step 5: Check "자동 로그인" checkbox
        log('📍 자동로그인 체크...')
        auto_check = page.query_selector('input[id="keep_login"]')
        if auto_check:
            is_checked = auto_check.is_checked()
            if not is_checked:
                auto_check.click()
                log('   ✅ 자동로그인 ON')
            else:
                log('   ✅ 자동로그인 이미 ON')
        else:
            log('   ⚠️ 자동로그인 체크박스 없음')
        
        time.sleep(0.5)
        
        # Step 6: Click login button
        log('📍 로그인 버튼 클릭...')
        login_btn = page.query_selector('button[type="submit"]')
        if not login_btn:
            login_btn = page.query_selector('input[type="submit"]')
        if not login_btn:
            login_btn = page.query_selector('span:has-text("로그인")')
        if not login_btn:
            login_btn = page.query_selector('[class*="btn_login"]')
        if login_btn:
            login_btn.click()
        else:
            log('   ⚠️ 로그인 버튼 못 찾음, Enter 키 전송')
            page.keyboard.press('Enter')
        
        # Step 7: Wait for login result
        log('⏳ 로그인 처리 대기...')
        time.sleep(5)
        
        current_url = page.url
        log(f'   현재 URL: {current_url[:80]}')
        
        # Check for CAPTCHA
        captcha_detected = ('captcha' in current_url.lower() or 
                           '자동입력방지' in page.content()[:2000] or
                           page.query_selector('[class*="captcha"]') is not None)
        
        if captcha_detected:
            log('⚠️ CAPTCHA 감지!')
            page.screenshot(path=CAPTCHA_FILE, full_page=True)
            print(f'CAPTCHA_SCREENSHOT:{CAPTCHA_FILE}', flush=True)
            log('⏳ CAPTCHA 해결 대기 중... (최대 60초)')
            
            # Wait for CAPTCHA to be solved (user solves on phone)
            for i in range(60):
                time.sleep(1)
                if is_logged_in(page):
                    log('✅ CAPTCHA 해결 완료!')
                    break
                # Check if CAPTCHA page changed
                if 'nidlogin' not in page.url.lower() and 'captcha' not in page.url.lower():
                    log('✅ 로그인 성공 (페이지 이동 감지)')
                    break
            else:
                log('❌ CAPTCHA 시간 초과')
                browser.close()
                return False
        
        # Check login result
        if is_logged_in(page):
            log('✅ 로그인 성공!')
            
            # Verify by visiting cafe write page
            page.goto('https://cafe.naver.com/ca-fe/cafes/31386031/articles/write',
                       wait_until='networkidle', timeout=15000)
            time.sleep(2)
            
            if is_logged_in(page):
                log('✅ 카페 글쓰기 접속 확인 완료')
                save_session(context)
                
                # Print cookie summary
                cookies = context.cookies()
                has_aut = any(c['name'] == 'NID_AUT' for c in cookies)
                has_ses = any(c['name'] == 'NID_SES' for c in cookies)
                log(f'📊 쿠키 상태: NID_AUT={"✅" if has_aut else "❌"} NID_SES={"✅" if has_ses else "❌"} 총 {len(cookies)}개')
                
                browser.close()
                return True
            else:
                log('❌ 카페 접속 실패')
        else:
            log(f'❌ 로그인 실패 (URL: {current_url[:60]})')
            # Save screenshot for debugging
            page.screenshot(path=os.path.join(BASE_DIR, 'login_fail.png'))
        
        browser.close()
        return False

if __name__ == '__main__':
    if not NAVER_ID or not NAVER_PW:
        log('❌ 사용법: python3 auto_login.py <id> <pw>')
        log('   또는 NAVER_ID, NAVER_PW 환경변수 설정')
        sys.exit(1)
    
    success = auto_login()
    if success:
        print('\n✅✅✅ 자동 로그인 성공!')
        print('   이제 keepalive 크론이 12시간마다 NID_SES를 자동 갱신합니다.')
        print('   다음 QR 필요 시점: NID_AUT 만료 (약 60일 후)')
    else:
        print('\n❌ 자동 로그인 실패')
        sys.exit(1)
