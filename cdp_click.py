#!/usr/bin/env python3
"""CDP로 진짜 마우스 클릭 전송 + isTrusted 우회"""
import json, time
from playwright.sync_api import sync_playwright

STATE_FILE = 'naver_state.json'
CLUB_ID = '31386031'
WRITE_URL = 'https://cafe.naver.com/ca-fe/cafes/{}/articles/write?boardType=L'.format(CLUB_ID)

with sync_playwright() as p:
    browser = p.chromium.launch(headless=True, channel='chrome',
        args=['--disable-blink-features=AutomationControlled'])
    ctx = browser.new_context(viewport={'width':1280,'height':900},
        locale='ko-KR', timezone_id='Asia/Seoul')
    with open(STATE_FILE) as f: ctx.add_cookies(json.load(f).get('cookies', []))
    page = ctx.new_page()
    
    requests = []
    def handle_route(route, request):
        if request.method == 'POST':
            requests.append({
                'url': request.url[:250],
                'method': request.method,
                'type': request.resource_type,
                'post_data': request.post_data[:2000] if request.post_data else None
            })
        elif request.resource_type == 'xhr':
            requests.append({
                'url': request.url[:250],
                'method': request.method,
                'type': request.resource_type,
                'post_data': request.post_data[:2000] if request.post_data else None
            })
        route.continue_()
    
    page.route('**/*', handle_route)
    
    page.goto(WRITE_URL, wait_until='networkidle', timeout=30000)
    time.sleep(5)
    
    # 폼 작성
    page.locator('button:has-text("게시판을 선택해 주세요")').first.click()
    time.sleep(1)
    page.locator('button:has-text("자유게시판")').first.click()
    time.sleep(2)
    page.locator('textarea[placeholder*="제목"]').fill('CDP 클릭 ' + str(int(time.time())))
    time.sleep(1)
    page.evaluate("""() => {
        var se = document.querySelector('.se-content');
        if (se) { se.innerHTML = '<p>CDP click test</p>'; }
    }""")
    time.sleep(2)
    requests.clear()
    
    # 등록 버튼 위치 찾기
    btn_box = page.locator('a.BaseButton:has(span.BaseButton__txt:text("등록"))').first.bounding_box()
    print("=== 등록 버튼 위치: {} ===".format(btn_box), flush=True)
    
    if btn_box:
        cx = btn_box['x'] + btn_box['width'] / 2
        cy = btn_box['y'] + btn_box['height'] / 2
        
        # CDP 세션으로 진짜 마우스 이벤트 전송
        cdp = page.context.new_cdp_session(page)
        
        # 1. mouseMoved (마우스 이동)
        cdp.send('Input.dispatchMouseEvent', {
            'type': 'mouseMoved',
            'x': cx, 'y': cy,
            'button': 'left',
            'clickCount': 0
        })
        time.sleep(0.3)
        
        # 2. mousePressed
        cdp.send('Input.dispatchMouseEvent', {
            'type': 'mousePressed',
            'x': cx, 'y': cy,
            'button': 'left',
            'clickCount': 1
        })
        time.sleep(0.1)
        
        # 3. mouseReleased
        cdp.send('Input.dispatchMouseEvent', {
            'type': 'mouseReleased',
            'x': cx, 'y': cy,
            'button': 'left',
            'clickCount': 1
        })
        
        print("CDP click sent at ({}, {})".format(int(cx), int(cy)), flush=True)
    
    time.sleep(5)
    
    # 결과
    posts = [r for r in requests if r['method'] == 'POST' and 'jackpot' not in r['url'] and 'scv' not in r['url']]
    print("\n=== 관련 POST: {}개 ===".format(len(posts)), flush=True)
    for r in posts:
        print("  [{}] {}".format(r['method'], r['url'][:200]), flush=True)
        if r.get('post_data'):
            print("    body: {}".format(r['post_data'][:600]), flush=True)
    
    all_posts = [r for r in requests if r['method'] == 'POST']
    print("\n=== 전체 POST: {}개 ===".format(len(all_posts)), flush=True)
    for r in all_posts:
        print("  [{}] {}".format(r['method'], r['url'][:200]), flush=True)
    
    xhr_reqs = [r for r in requests if r['type'] == 'xhr']
    print("\n=== XHR: {}개 ===".format(len(xhr_reqs)), flush=True)
    for r in xhr_reqs:
        print("  [{}] {}".format(r['method'], r['url'][:200]), flush=True)
    
    print("\nURL: {}".format(page.url), flush=True)
    ctx.close()
    browser.close()
