#!/usr/bin/env python3
"""
Naver Cafe Auto Poster v1.0
=================================
네이버 카페 게시글 자동 발행기
- QR 로그인 (최초 1회) → 세션 저장 → REST API 발행 (Playwright 불필요)
- 자유게시판 + 중고악기팝니다(N플리마켓) 지원
- 사용법: python naver_cafe_poster.py [옵션]

필수 선행 작업:
  1. python naver_cafe_poster.py --qr-login  (최초 1회 QR 로그인)
  2. python naver_cafe_poster.py --post --title "제목" --body "내용" --board free

Options:
  --qr-login          QR 코드 로그인 (최초 1회 실행)
  --post              게시글 발행
  --title TITLE       게시글 제목
  --body BODY         게시글 본문 (HTML)
  --board BOARD       게시판 선택 (free=자유게시판, trade=중고악기팝니다)
  --file FILE         JSON 파일로부터 발행 (articles.json)
  --crawl             소스 카페에서 크롤링 후 자동 발행
  --check             로그인 상태 확인
"""
import json, os, sys, time, re, argparse
from datetime import datetime

# ── 설정 ──────────────────────────────────────────────
BASE_DIR = os.path.dirname(os.path.abspath(__file__))
STATE_FILE = os.path.join(BASE_DIR, 'naver_state.json')

# 타겟 카페 (에코뮤직 중고악기백화점)
TARGET_CLUB_ID = '31386031'

# 게시판 매핑 (해당 카페의 실제 menuId)
BOARDS = {
    'free': {'id': 1, 'name': '자유게시판', 'boardType': 'L'},
    'used': {'id': 11, 'name': '중고거래 게시판', 'boardType': 'L'},
    'trade': {'id': 2, 'name': '중고 악기 팝니다', 'boardType': 'T'},
    'greeting': {'id': 3, 'name': '가입인사', 'boardType': 'L'},
    'session': {'id': 4, 'name': '세션구합니다', 'boardType': 'L'},
    'tip': {'id': 5, 'name': '꿀팁 게시판', 'boardType': 'L'},
    'review': {'id': 6, 'name': '리뷰게시판', 'boardType': 'L'},
    'lesson': {'id': 8, 'name': '개인레슨', 'boardType': 'L'},
}

API_BASE = 'https://apis.cafe.naver.com/editor/v2.0/cafes/{}/menus/{}/articles'
TEMP_API = 'https://apis.cafe.naver.com/editor/v2/cafes/{}/temporary-articles'

HEADERS = {
    'User-Agent': 'Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/131.0.0.0 Safari/537.36',
    'Accept': 'application/json, text/plain, */*',
    'Content-Type': 'application/json;charset=UTF-8',
    'Origin': 'https://cafe.naver.com',
    'x-cafe-product': 'pc',
}


# ── 유틸리티 ──────────────────────────────────────────

def log(msg): print(f'[{datetime.now().strftime("%H:%M:%S")}] {msg}', flush=True)

def load_session():
    """저장된 네이버 세션 로드"""
    if not os.path.exists(STATE_FILE):
        log('❌ 세션 파일 없음. --qr-login 으로 로그인 먼저 해주세요.')
        return None
    
    with open(STATE_FILE) as f:
        state = json.load(f)
    
    import requests
    s = requests.Session()
    for c in state.get('cookies', []):
        s.cookies.set(c['name'], c['value'], domain=c.get('domain', '.naver.com'))
    
    log(f'✅ 세션 로드 완료 (쿠키 {len(s.cookies)}개)')
    return s


# ── QR 로그인 ──────────────────────────────────────────

def qr_login():
    """Playwright로 QR 코드 로그인 (최초 1회)"""
    log('🔄 네이버 QR 로그인 시작...')
    log('📱 화면에 QR 코드가 표시됩니다. 네이버 앱으로 스캔해주세요.')
    
    try:
        from playwright.sync_api import sync_playwright
    except ImportError:
        log('❌ playwright 설치 필요: pip install playwright && playwright install')
        sys.exit(1)
    
    with sync_playwright() as p:
        browser = p.chromium.launch(headless=False)  # 화면 표시
        ctx = browser.new_context(
            viewport={'width': 1280, 'height': 900},
            locale='ko-KR', timezone_id='Asia/Seoul'
        )
        page = ctx.new_page()
        
        # 네이버 로그인 페이지 (QR 탭)
        page.goto('https://nid.naver.com/nidlogin.login?mode=qr', wait_until='networkidle')
        log('⏳ QR 코드 로그인 대기 중... (최대 3분)')
        
        # URL 변경 감지 (로그인 성공 시)
        try:
            page.wait_for_url(lambda url: 'nidlogin' not in url, timeout=180000)
            log('✅ QR 로그인 성공!')
        except:
            # 대체: 로그인 버튼 클릭
            page.wait_for_timeout(30000)
        
        time.sleep(3)
        
        # 쿠키 저장
        cookies = ctx.cookies()
        state = {'cookies': cookies, 'saved_at': time.time()}
        with open(STATE_FILE, 'w') as f:
            json.dump(state, f, ensure_ascii=False)
        
        log(f'✅ 세션 저장 완료 (쿠키 {len(cookies)}개)')
        browser.close()
    
    # 세션 유효성 확인
    session = load_session()
    if check_login(session):
        log('✅ 로그인 상태 정상')
    else:
        log('⚠️ 로그인 상태 확인 필요')


def check_login(session=None):
    """네이버 로그인 상태 확인"""
    if not session:
        session = load_session()
    if not session:
        return False
    
    try:
        resp = session.get('https://www.naver.com/', headers=HEADERS, timeout=10)
        return 'sewoong' in resp.text.lower() or 'profile' in resp.text.lower()
    except:
        return False


# ── SmartEditor 3 문서 포맷 생성 ─────────────────────

def make_se3_content(html_text):
    """HTML 본문을 SmartEditor 3 문서 포맷으로 변환"""
    import uuid
    
    doc_id = 'SE-' + uuid.uuid4().hex[:20].upper()
    comp_id = 'SE-' + uuid.uuid4().hex[:20].upper()
    para_id = 'SE-' + uuid.uuid4().hex[:20].upper()
    text_id = 'SE-' + uuid.uuid4().hex[:20].upper()
    
    # HTML에서 순수 텍스트 추출 (paragraphs)
    clean_text = re.sub(r'<[^>]+>', ' ', html_text)
    clean_text = re.sub(r'\s+', ' ', clean_text).strip()
    
    doc = {
        "document": {
            "version": "2.9.0",
            "theme": "default",
            "language": "ko-KR",
            "id": doc_id,
            "components": [{
                "id": comp_id,
                "layout": "default",
                "value": [{
                    "id": para_id,
                    "nodes": [{
                        "id": text_id,
                        "value": clean_text,
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
    }
    return json.dumps(doc, ensure_ascii=False)


# ── 게시글 발행 ───────────────────────────────────────

def post_article(session, title, body_html, board_key='free'):
    """
    게시글 발행 (직접 REST API)
    
    Args:
        session: requests.Session (로그인 상태)
        title: 게시글 제목
        body_html: 게시글 본문 (HTML)
        board_key: 게시판 키 ('free', 'trade', ...)
    
    Returns:
        dict: {"success": True/False, "article_id": N, "error": "..."}
    """
    if board_key not in BOARDS:
        return {'success': False, 'error': f'알 수 없는 게시판: {board_key}'}
    
    board = BOARDS[board_key]
    content_json = make_se3_content(body_html)
    
    payload = {
        "article": {
            "cafeId": TARGET_CLUB_ID,
            "contentJson": content_json,
            "from": "pc",
            "menuId": board['id'],
            "subject": title,
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
    
    url = API_BASE.format(TARGET_CLUB_ID, board['id'])
    headers = {**HEADERS, 'Referer': f'https://cafe.naver.com/ca-fe/cafes/{TARGET_CLUB_ID}/articles/write'}
    
    log(f'📤 발행 중: {title[:50]}... → {board["name"]}')
    
    try:
        resp = session.post(url, json=payload, headers=headers, timeout=30)
        
        if resp.status_code == 200:
            data = resp.json()
            article_id = data.get('result', {}).get('articleId', '?')
            log(f'✅ 발행 성공! articleId={article_id}')
            return {'success': True, 'article_id': article_id}
        else:
            error = resp.text[:300]
            log(f'❌ 발행 실패 ({resp.status_code}): {error}')
            return {'success': False, 'error': error}
    
    except Exception as e:
        log(f'❌ API 오류: {e}')
        return {'success': False, 'error': str(e)}


def post_from_file(session, filepath, board_key='free'):
    """JSON 파일에서 게시글 읽어서 발행"""
    with open(filepath, encoding='utf-8') as f:
        articles = json.load(f)
    
    if isinstance(articles, dict):
        articles = [articles]
    
    results = []
    for art in articles:
        title = art.get('title', art.get('subject', '제목없음'))
        body = art.get('body', art.get('content', art.get('summary', '')))
        result = post_article(session, title, body, art.get('board', board_key))
        results.append(result)
        time.sleep(2)  # 발행 간격
    
    return results


# ── 메인 CLI ──────────────────────────────────────────

def main():
    parser = argparse.ArgumentParser(description='Naver Cafe Auto Poster')
    parser.add_argument('--qr-login', action='store_true', help='QR 코드 로그인')
    parser.add_argument('--post', action='store_true', help='게시글 발행')
    parser.add_argument('--title', help='게시글 제목')
    parser.add_argument('--body', help='게시글 본문 (HTML)')
    parser.add_argument('--board', default='free', choices=list(BOARDS.keys()), help='게시판')
    parser.add_argument('--file', help='JSON 파일로부터 발행')
    parser.add_argument('--check', action='store_true', help='로그인 상태 확인')
    args = parser.parse_args()
    
    # QR 로그인
    if args.qr_login:
        qr_login()
        return
    
    # 로그인 상태 확인
    if args.check:
        session = load_session()
        if session and check_login(session):
            log('✅ 네이버 로그인 상태: 정상')
        else:
            log('❌ 로그인 필요: python naver_cafe_poster.py --qr-login')
        return
    
    # 게시글 발행
    if args.post:
        session = load_session()
        if not session:
            return
        
        if args.file:
            results = post_from_file(session, args.file, args.board)
            success = sum(1 for r in results if r['success'])
            log(f'📊 발행 결과: {success}/{len(results)} 성공')
        elif args.title and args.body:
            result = post_article(session, args.title, args.body, args.board)
        else:
            log('❌ --title 과 --body 를 함께 지정하거나 --file 을 사용하세요.')
            parser.print_help()
        return
    
    # 도움말 표시
    parser.print_help()
    print('\n\n📌 사용 예시:')
    print('  # 1. QR 로그인 (최초 1회)')
    print('  python naver_cafe_poster.py --qr-login')
    print()
    print('  # 2. 게시글 발행')
    print('  python naver_cafe_poster.py --post --title "바이올린 팝니다" --body "<p>상태 좋습니다</p>" --board free')
    print()
    print('  # 3. 중고 악기 팝니다 게시판에 발행')
    print('  python naver_cafe_poster.py --post --title "중고 첼로" --body "<p>판매합니다</p>" --board trade')
    print()
    print('  # 4. JSON 파일로 일괄 발행')
    print('  python naver_cafe_poster.py --post --file articles.json')
    print()
    print('  # 5. 로그인 상태 확인')
    print('  python naver_cafe_poster.py --check')


if __name__ == '__main__':
    main()
