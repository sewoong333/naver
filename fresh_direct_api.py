#!/usr/bin/env python3
"""브라우저 신선한 쿠키 → requests 직접 API 호출"""
import json, time, requests
from playwright.sync_api import sync_playwright

STATE_FILE = 'naver_state.json'
CLUB_ID = '31386031'

with sync_playwright() as p:
    browser = p.chromium.launch(headless=True, channel='chrome')
    ctx = browser.new_context(viewport={'width':1280,'height':900},
        locale='ko-KR', timezone_id='Asia/Seoul')
    with open(STATE_FILE) as f: ctx.add_cookies(json.load(f).get('cookies', []))
    page = ctx.new_page()
    
    # 먼저 네이버 메인 + 카페 페이지 로드 (쿠키 갱신)
    page.goto('https://www.naver.com/', wait_until='networkidle', timeout=30000)
    time.sleep(2)
    page.goto('https://cafe.naver.com/ca-fe/cafes/{}/articles/write?boardType=L'.format(CLUB_ID),
              wait_until='networkidle', timeout=30000)
    time.sleep(5)
    
    # 신선한 쿠키 추출
    fresh_cookies = ctx.cookies()
    
    # requests 세션 구성
    s = requests.Session()
    for c in fresh_cookies:
        s.cookies.set(c['name'], c['value'], domain=c.get('domain', '.naver.com'))
    
    print("=== 신선한 쿠키: {}개 ===".format(len(fresh_cookies)), flush=True)
    for c in fresh_cookies:
        if c['name'] in ('NID_SES', 'NID_AUT', 'NID_JST'):
            print("  {} = {}...".format(c['name'], c['value'][:30]), flush=True)
    
    # 직접 API 호출
    headers = {
        'User-Agent': 'Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/131.0.0.0 Safari/537.36',
        'Accept': 'application/json, text/plain, */*',
        'Content-Type': 'application/json;charset=UTF-8',
        'Origin': 'https://cafe.naver.com',
        'Referer': 'https://cafe.naver.com/ca-fe/cafes/{}/articles/write?boardType=L'.format(CLUB_ID),
        'x-cafe-product': 'pc',
    }
    
    ts = str(int(time.time()))
    payload = {
        "article": {
            "cafeId": CLUB_ID,
            "contentJson": json.dumps({
                "body": "<p>Playwright fresh cookie direct API test</p>",
                "elements": [],
                "elementsData": {}
            }),
            "from": "pc",
            "menuId": "4",
            "subject": "FreshCookie " + ts,
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
    
    url = 'https://apis.cafe.naver.com/editor/v2.0/cafes/{}/menus/4/articles'.format(CLUB_ID)
    print("\n=== POST {} ===".format(url), flush=True)
    
    for attempt in range(3):
        try:
            resp = s.post(url, json=payload, headers=headers, timeout=15)
            print("Attempt {}: Status={}, Body={}".format(attempt+1, resp.status_code, resp.text[:500]), flush=True)
            if resp.status_code == 200:
                print("\n🎉 SUCCESS!", flush=True)
                print("Response: {}".format(resp.text[:1000]), flush=True)
                break
        except Exception as e:
            print("Attempt {}: Error={}".format(attempt+1, e), flush=True)
        time.sleep(1)
    
    ctx.close()
    browser.close()
