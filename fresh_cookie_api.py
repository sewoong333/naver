#!/usr/bin/env python3
"""브라우저에서 신선한 쿠키 추출 후 직접 API 호출"""
import json, time, requests
from playwright.sync_api import sync_playwright

STATE_FILE = 'naver_state.json'
CLUB_ID = '31386031'
WRITE_URL = 'https://cafe.naver.com/ca-fe/cafes/{}/articles/write?boardType=L'.format(CLUB_ID)

with sync_playwright() as p:
    browser = p.chromium.launch(headless=True, channel='chrome')
    ctx = browser.new_context(viewport={'width':1280,'height':900},
        locale='ko-KR', timezone_id='Asia/Seoul')
    with open(STATE_FILE) as f: ctx.add_cookies(json.load(f).get('cookies', []))
    page = ctx.new_page()
    
    # 네트워크 요청 캡처 (응답도)
    api_responses = {}
    def capture(route, request):
        url = request.url
        if 'editor/v2.0/cafes' in url and 'articles' in url and request.method == 'POST':
            api_responses['request'] = {
                'url': url,
                'headers': dict(request.headers),
                'body': request.post_data[:3000] if request.post_data else None,
            }
        route.continue_()
    
    def on_response(response):
        url = response.url
        if 'editor/v2.0/cafes' in url and 'articles' in url:
            try:
                api_responses['response'] = {
                    'status': response.status,
                    'body': response.body().decode('utf-8')[:2000]
                }
            except:
                pass
    
    page.route('**/*', capture)
    page.on('response', on_response)
    
    page.goto(WRITE_URL, wait_until='networkidle', timeout=30000)
    time.sleep(6)
    
    # 폼 작성
    ts = str(int(time.time()))
    page.locator('textarea[placeholder*="제목"]').fill('신선한쿠키 ' + ts)
    time.sleep(1)
    page.evaluate("""() => {
        var se = document.querySelector('.se-content');
        if (se) { se.innerHTML = '<p>신선한 쿠키 테스트</p>'; }
    }""")
    time.sleep(1)
    
    # 브라우저에서 신선한 쿠키 추출
    fresh_cookies = ctx.cookies()
    print("=== 신선한 쿠키: {}개 ===".format(len(fresh_cookies)), flush=True)
    nid_ses = None
    nid_aut = None
    for c in fresh_cookies:
        if c['name'] == 'NID_SES':
            nid_ses = c['value']
            print("NID_SES: {}...".format(c['value'][:30]), flush=True)
        if c['name'] == 'NID_AUT':
            nid_aut = c['value']
            print("NID_AUT: {}...".format(c['value'][:30]), flush=True)
    
    # Vuex를 통한 API 호출 (응답 캡처)
    print("\n=== Vuex uploadArticle 호출 ===", flush=True)
    result = page.evaluate("""async () => {
        var app = document.querySelector('#app');
        if (!app || !app.__vue__) return JSON.stringify({error: 'no vue'});
        var store = app.__vue__.$store;
        if (!store) return JSON.stringify({error: 'no store'});
        
        try {
            // menuId=4로 설정
            var art = store.state.articleWriting.article;
            if (art && art.menu) { art.menu.menuId = 4; art.menu.menuName = '자유게시판'; art._menuId = '4'; }
            
            // 제목 설정
            store.commit('articleWriting/updateSubject', '신선한쿠키 ' + Date.now());
            
            // SmartEditor 강제 동기화
            store.dispatch('articleWriting/updateContent');
            
            var payload = {
                content: {body: '<p>신선한 쿠키 테스트</p>', elements: [], elementsData: {}},
                contentText: '신선한 쿠키 테스트'
            };
            
            var result = await store.dispatch('articleWriting/uploadArticle', payload);
            return JSON.stringify({status: 'success', result: String(result).substring(0, 500)});
        } catch(e) {
            return JSON.stringify({error: e.message, stack: (e.stack || '').substring(0, 500)});
        }
    }""")
    
    print("Result: {}".format(result), flush=True)
    time.sleep(5)
    
    # API 요청/응답 출력
    if api_responses:
        print("\n=== API 요청 ===", flush=True)
        req = api_responses.get('request', {})
        print("URL: {}".format(req.get('url', '')), flush=True)
        for k, v in sorted(req.get('headers', {}).items()):
            if k.lower() in ('content-type', 'referer', 'origin', 'x-cafe-product', 'x-cafe-version', 'x-cafe-phase', 'se-authorization', 'se-app-id'):
                print("  {}: {}".format(k, v[:100]), flush=True)
        
        resp = api_responses.get('response', {})
        print("\n=== API 응답 ===", flush=True)
        print("Status: {}".format(resp.get('status', '?')), flush=True)
        print("Body: {}".format(resp.get('body', '?')[:1000]), flush=True)
    else:
        print("\n❌ API 응답 없음", flush=True)
    
    print("\nURL: {}".format(page.url), flush=True)
    ctx.close()
    browser.close()
