#!/usr/bin/env python3
"""직접 REST API 호출 - Naver Cafe 게시글 작성"""
import json, requests, time

CLUB_ID = '31386031'
MENU_ID = 4  # 자유게시판

# 세션 로드
with open('naver_state.json') as f:
    state = json.load(f)

s = requests.Session()
for c in state.get('cookies', []):
    s.cookies.set(c['name'], c['value'], domain=c.get('domain', '.naver.com'))

headers = {
    'User-Agent': 'Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/131.0.0.0 Safari/537.36',
    'Accept': 'application/json, text/plain, */*',
    'Accept-Language': 'ko-KR,ko;q=0.9,en;q=0.8',
    'Content-Type': 'application/json;charset=UTF-8',
    'Origin': 'https://cafe.naver.com',
    'Referer': 'https://cafe.naver.com/ca-fe/cafes/{}/articles/write?boardType=L'.format(CLUB_ID),
    'x-naver-correlation-id': 'cafe-pc-write-' + str(int(time.time())),
}

ts = str(int(time.time()))
payload = {
    "article": {
        "cafeId": CLUB_ID,
        "contentJson": json.dumps({
            "body": "<p>직접 REST API 호출 테스트</p>",
            "elements": [],
            "elementsData": {}
        }),
        "from": "pc",
        "menuId": str(MENU_ID),
        "subject": "REST API 테스트 " + ts,
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

url = 'https://apis.cafe.naver.com/editor/v2.0/cafes/{}/menus/{}/articles'.format(CLUB_ID, MENU_ID)

print("=== POST {} ===".format(url), flush=True)
print("Payload: {}".format(json.dumps(payload, ensure_ascii=False)[:500]), flush=True)
print("Cookies: {} 개".format(len(s.cookies)), flush=True)

resp = s.post(url, json=payload, headers=headers, timeout=30)
print("\nStatus: {}".format(resp.status_code), flush=True)
print("Headers: {}".format(dict(resp.headers)), flush=True)
print("Body: {}".format(resp.text[:1000]), flush=True)

# 실패시 다양한 시도
if resp.status_code != 200:
    print("\n=== 대체 시도 ===", flush=True)
    
    # Content-Type 변경
    headers2 = headers.copy()
    headers2['Content-Type'] = 'text/plain;charset=UTF-8'
    resp2 = s.post(url, data=json.dumps(payload, ensure_ascii=False), headers=headers2, timeout=30)
    print("Content-Type text/plain: {} - {}".format(resp2.status_code, resp2.text[:300]), flush=True)
