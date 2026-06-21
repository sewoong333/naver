#!/usr/bin/env python3
"""브라우저 내 fetch()로 직접 API 호출"""
import json, time
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
    
    # 응답 캡처
    api_resp = {}
    def on_response(response):
        url = response.url
        if 'editor/v2.0/cafes' in url and 'articles' in url:
            try:
                api_resp['status'] = response.status
                api_resp['body'] = response.body().decode('utf-8')[:2000]
                api_resp['url'] = url
            except Exception as e:
                api_resp['error'] = str(e)
    
    page.on('response', on_response)
    
    page.goto(WRITE_URL, wait_until='networkidle', timeout=30000)
    time.sleep(5)
    
    # 브라우저 내에서 fetch()로 직접 API 호출
    print("=== 브라우저 내 fetch API 호출 ===", flush=True)
    
    ts = str(int(time.time()))
    result = page.evaluate("""async (ts) => {
        var url = 'https://apis.cafe.naver.com/editor/v2.0/cafes/31386031/menus/4/articles';
        var payload = {
            article: {
                cafeId: '31386031',
                contentJson: JSON.stringify({
                    body: '<p>Browser fetch direct API test</p>',
                    elements: [],
                    elementsData: {}
                }),
                from: 'pc',
                menuId: '4',
                subject: 'BrowserFetch ' + ts,
                tagList: [],
                editorVersion: 4,
                parentId: 0,
                open: false,
                naverOpen: true,
                externalOpen: true,
                enableComment: true,
                enableScrap: true,
                enableCopy: false,
                useAutoSource: true,
                cclTypes: [],
                useCcl: false
            }
        };
        
        try {
            var resp = await fetch(url, {
                method: 'POST',
                credentials: 'include',
                headers: {
                    'Content-Type': 'application/json;charset=UTF-8',
                    'x-cafe-product': 'pc',
                },
                body: JSON.stringify(payload)
            });
            
            var text = await resp.text();
            return JSON.stringify({
                status: resp.status,
                headers: Object.fromEntries(resp.headers.entries()),
                body: text.substring(0, 2000)
            });
        } catch(e) {
            return JSON.stringify({error: e.message, stack: e.stack});
        }
    }""", ts)
    
    print("Fetch result: {}".format(result[:1000]), flush=True)
    
    time.sleep(3)
    
    # on_response로 캡처된 응답
    if api_resp:
        print("\n=== on_response capture ===", flush=True)
        print("Status: {}".format(api_resp.get('status')), flush=True)
        print("Body: {}".format(api_resp.get('body', '')[:1000]), flush=True)
    
    ctx.close()
    browser.close()
