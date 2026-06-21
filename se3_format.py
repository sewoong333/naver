#!/usr/bin/env python3
"""임시저장에서 발견한 SmartEditor 3 포맷으로 게시 API 호출"""
import json, time
from playwright.sync_api import sync_playwright

STATE_FILE = 'naver_state.json'
CLUB_ID = '31386031'

with sync_playwright() as p:
    browser = p.chromium.launch(headless=True, channel='chrome')
    ctx = browser.new_context(viewport={'width':1280,'height':900},
        locale='ko-KR', timezone_id='Asia/Seoul')
    with open(STATE_FILE) as f: ctx.add_cookies(json.load(f).get('cookies', []))
    page = ctx.new_page()
    
    page.goto('https://cafe.naver.com/ca-fe/cafes/{}/articles/write?boardType=L'.format(CLUB_ID),
              wait_until='networkidle', timeout=30000)
    time.sleep(5)
    
    # SmartEditor 3 포맷으로 API 호출
    ts = str(int(time.time()))
    content_json = json.dumps({
        "document": {
            "version": "2.9.0",
            "theme": "default",
            "language": "ko-KR",
            "id": "SE-" + ts,
            "components": [{
                "id": "SE-COMP-" + ts,
                "layout": "default",
                "value": [{
                    "id": "SE-P-" + ts,
                    "nodes": [{
                        "id": "SE-T-" + ts,
                        "value": "SmartEditor 3 포맷으로 게시글 등록 성공!",
                        "@ctype": "textNode"
                    }],
                    "@ctype": "paragraph"
                }],
                "@ctype": "text"
            }],
            "di": {
                "dif": False,
                "dio": [{
                    "dis": "N",
                    "dia": {"t": 0, "p": 0, "st": 1, "sk": 0}
                }, {
                    "dis": "N",
                    "dia": {"t": 0, "p": 0, "st": 17, "sk": 0}
                }]
            }
        },
        "documentId": ""
    })
    
    print("=== SmartEditor 3 포맷으로 게시 API 호출 ===", flush=True)
    
    payload = {
        "article": {
            "cafeId": CLUB_ID,
            "contentJson": content_json,
            "from": "pc",
            "menuId": 1,
            "subject": "SE3포맷 " + ts,
            "tagList": [],
            "editorVersion": 4,
            "parentId": 0,
            "open": False,
            "naverOpen": True,
            "externalOpen": True,
            "enableComment": True,
            "enableScrap": True,
            "enableCopy": False,
            "useAutoSource": True,
            "cclTypes": [],
            "useCcl": False
        }
    }
    
    # 응답 캡처
    api_resp = {}
    def on_resp(response):
        if 'editor/v2.0/cafes' in response.url and 'articles' in response.url:
            try:
                api_resp['status'] = response.status
                api_resp['body'] = response.body().decode('utf-8')[:2000]
                print("<<< 응답: {}".format(response.status), flush=True)
            except: pass
        if 'temporary-articles' in response.url:
            try:
                api_resp['temp'] = {
                    'status': response.status,
                    'body': response.body().decode('utf-8')[:1000]
                }
            except: pass
    
    page.on('response', on_resp)
    
    # 브라우저 내 fetch 실행
    result = page.evaluate("""(payload) => {
        return fetch('https://apis.cafe.naver.com/editor/v2.0/cafes/31386031/menus/1/articles', {
            method: 'POST',
            credentials: 'include',
            headers: {'Content-Type': 'application/json', 'x-cafe-product': 'pc'},
            body: JSON.stringify(payload)
        }).then(function(r) {
            return r.text().then(function(t) {
                return JSON.stringify({status: r.status, body: t.substring(0, 2000)});
            });
        }).catch(function(e) {
            return JSON.stringify({error: e.message});
        });
    }""", payload)
    
    print("Result: {}".format(result[:1000]), flush=True)
    
    # 응답 확인
    if api_resp:
        print("\n=== API 응답 ===", flush=True)
        for k, v in api_resp.items():
            print("{}: status={}, body={}".format(k, v.get('status'), str(v.get('body',''))[:500]), flush=True)
    
    # 페이지 확인
    print("\nURL: {}".format(page.url), flush=True)
    
    ctx.close()
    browser.close()
