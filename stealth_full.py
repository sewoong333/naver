#!/usr/bin/env python3
"""Playwright 스텔스 패치 풀세트 - 모든 자동화 탐지 우회"""
import json, time
from playwright.sync_api import sync_playwright

STATE_FILE = 'naver_state.json'
CLUB_ID = '31386031'
WRITE_URL = 'https://cafe.naver.com/ca-fe/cafes/{}/articles/write?boardType=L'.format(CLUB_ID)

with sync_playwright() as p:
    browser = p.chromium.launch(headless=True, channel='chrome',
        args=[
            '--disable-blink-features=AutomationControlled',
            '--disable-features=IsolateOrigins,site-per-process',
            '--disable-web-security',
            '--no-sandbox',
            '--disable-setuid-sandbox',
            '--disable-dev-shm-usage',
            '--disable-infobars',
        ])
    ctx = browser.new_context(
        viewport={'width': 1920, 'height': 1080},
        locale='ko-KR', timezone_id='Asia/Seoul',
        user_agent='Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/131.0.0.0 Safari/537.36',
    )
    with open(STATE_FILE) as f: ctx.add_cookies(json.load(f).get('cookies', []))
    page = ctx.new_page()
    
    # ==== 스텔스 패치 주입 ====
    page.add_init_script("""
    // 1. navigator.webdriver 제거
    Object.defineProperty(navigator, 'webdriver', {get: () => undefined});
    
    // 2. chrome.runtime 우회
    window.chrome = {runtime: {}};
    
    // 3. 플러그인 정보
    Object.defineProperty(navigator, 'plugins', {
        get: () => [1, 2, 3, 4, 5]
    });
    
    // 4. languages 포맷
    Object.defineProperty(navigator, 'languages', {get: () => ['ko-KR', 'ko']});
    
    // 5. permission
    const origQuery = window.navigator.permissions.query;
    window.navigator.permissions.query = (params) => (
        params.name === 'notifications' ?
            Promise.resolve({state: 'prompt'}) :
            origQuery(params)
    );
    
    // 6. isTrusted 패치 - 모든 Event 타입
    const patchIsTrusted = function(proto) {
        try {
            Object.defineProperty(proto, 'isTrusted', {
                get: function() { return true; },
                configurable: true
            });
        } catch(e) {}
    };
    patchIsTrusted(Event.prototype);
    patchIsTrusted(MouseEvent.prototype);
    patchIsTrusted(PointerEvent.prototype);
    patchIsTrusted(KeyboardEvent.prototype);
    patchIsTrusted(FocusEvent.prototype);
    patchIsTrusted(TouchEvent.prototype);
    patchIsTrusted(WheelEvent.prototype);
    patchIsTrusted(DragEvent.prototype);
    
    // 7. navigator.connection
    if (navigator.connection) {
        Object.defineProperty(navigator.connection, 'rtt', {get: () => 100});
    }
    
    // 8. WebGL vendor
    const getParameter = WebGLRenderingContext.prototype.getParameter;
    WebGLRenderingContext.prototype.getParameter = function(p) {
        if (p === 37445) return 'Intel Inc.';
        if (p === 37446) return 'Intel Iris OpenGL Engine';
        return getParameter.apply(this, arguments);
    };
    
    // 9. canvas fingerprint 우회
    HTMLCanvasElement.prototype.toDataURL = function() {
        return 'data:image/png;base64,FAKE';
    };
    
    console.log('[STEALTH] All patches applied');
    """)
    
    # 네트워크 캡처
    requests = []
    def handle_route(route, request):
        url = request.url
        if request.method == 'POST' or request.resource_type == 'xhr':
            requests.append({
                'url': url[:250],
                'method': request.method,
                'type': request.resource_type,
                'post_data': request.post_data[:3000] if request.post_data else None,
                'headers': dict(request.headers) if request.resource_type == 'xhr' else None,
            })
        route.continue_()
    
    page.route('**/*', handle_route)
    
    page.goto(WRITE_URL, wait_until='networkidle', timeout=30000)
    time.sleep(8)
    
    # 확인
    is_automated = page.evaluate("""() => {
        var checks = {
            webdriver: navigator.webdriver,
            plugins: navigator.plugins.length,
            languages: JSON.stringify(navigator.languages),
            isTrusted: (function() { var e = new MouseEvent('click'); return e.isTrusted; })(),
            chrome: typeof window.chrome,
        };
        return JSON.stringify(checks);
    }""")
    print("Stealth check: {}".format(is_automated), flush=True)
    
    # 폼 작성
    page.locator('button:has-text("게시판을 선택해 주세요")').first.click()
    time.sleep(1)
    page.locator('button:has-text("자유게시판")').first.click()
    time.sleep(2)
    page.locator('textarea[placeholder*="제목"]').fill('스텔스 테스트 ' + str(int(time.time())))
    time.sleep(1)
    
    # SmartEditor에 본문 직접 입력 (execCommand 사용)
    page.evaluate("""() => {
        var editable = document.querySelector('[contenteditable="true"]');
        if (editable) {
            editable.focus();
            var sel = window.getSelection();
            sel.selectAllChildren(editable);
            document.execCommand('insertHTML', false, '<p>스텔스 패치 테스트입니다.</p>');
        }
    }""")
    time.sleep(2)
    requests.clear()
    
    # 클릭 - dispatchEvent + CDP 콤보
    print("=== 클릭 시도 ===", flush=True)
    
    # 1) CDP 마우스 이벤트
    btn_box = page.locator('a.BaseButton:has(span.BaseButton__txt:text("등록"))').first.bounding_box()
    if btn_box:
        cx = btn_box['x'] + btn_box['width'] / 2
        cy = btn_box['y'] + btn_box['height'] / 2
        cdp = page.context.new_cdp_session(page)
        cdp.send('Input.dispatchMouseEvent', {'type': 'mouseMoved', 'x': cx, 'y': cy, 'button': 'left', 'clickCount': 0})
        time.sleep(0.2)
        cdp.send('Input.dispatchMouseEvent', {'type': 'mousePressed', 'x': cx, 'y': cy, 'button': 'left', 'clickCount': 1})
        time.sleep(0.05)
        cdp.send('Input.dispatchMouseEvent', {'type': 'mouseReleased', 'x': cx, 'y': cy, 'button': 'left', 'clickCount': 1})
        print("CDP click at ({}, {})".format(int(cx), int(cy)), flush=True)
    
    time.sleep(5)
    
    # 2) Playwright click (fallback)
    if page.url == WRITE_URL:
        print("Playwright fallback click...", flush=True)
        try:
            page.locator('a.BaseButton:has(span.BaseButton__txt:text("등록"))').first.click(force=True, timeout=5000)
            print("PW click done", flush=True)
            time.sleep(5)
        except Exception as e:
            print("PW click error: {}".format(e), flush=True)
    
    # 결과
    posts = [r for r in requests if r['method'] == 'POST' and 'jackpot' not in r['url'] and 'scv' not in r['url']]
    print("\n=== 관련 POST: {}개 ===".format(len(posts)), flush=True)
    for r in posts:
        print("  [{}] {}".format(r['method'], r['url'][:200]), flush=True)
        if r.get('post_data'):
            print("    body({}B): {}".format(len(r['post_data']), r['post_data'][:600]), flush=True)
    
    all_posts = [r for r in requests if r['method'] == 'POST']
    print("\n=== 전체 POST: {}개 ===".format(len(all_posts)), flush=True)
    for r in all_posts:
        print("  [{}] {}".format(r['method'], r['url'][:150]), flush=True)
    
    xhrs = [r for r in requests if r['type'] == 'xhr']
    print("\n=== XHR: {}개 ===".format(len(xhrs)), flush=True)
    for r in xhrs:
        print("  [{}] {}".format(r['method'], r['url'][:150]), flush=True)
    
    print("\nURL: {}".format(page.url), flush=True)
    ctx.close()
    browser.close()
