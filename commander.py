#!/usr/bin/env python3
"""
Naver Cafe Team Commander v1.0
================================
팀 단위 카페 발행 관리자. 모든 작업을 여기서 처리합니다.

운영 방식:
  1. 내가 각 팀원의 QR 로그인 실행 → QR 코드가 화면에 뜸
  2. QR 코드 스크린샷을 텔레그램으로 팀원에게 전송
  3. 팀원이 네이버 앱으로 스캔
  4. 세션 저장 → 이후 내가 자동 발행

팀원이 해야 할 것: "QR 코드 한 번 스캔"  (그게 끝)
"""
import json, os, sys, time, re, sqlite3, argparse, uuid, subprocess, shutil
from datetime import datetime
from pathlib import Path

BASE_DIR = os.path.dirname(os.path.abspath(__file__))
SESSIONS_DIR = os.path.join(BASE_DIR, 'sessions')
DB_PATH = os.path.join(BASE_DIR, 'team_articles.db')

# ── 설정 ──────────────────────────────────────────────
TARGET_CLUB_ID = '31386031'
BOARDS = {
    'used': {'id': 11, 'name': '중고거래 게시판'},
    'free': {'id': 1, 'name': '자유게시판'},
}
API_BASE = 'https://apis.cafe.naver.com/editor/v2.0/cafes/{}/menus/{}/articles'
API_HEADERS = {
    'User-Agent': 'Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36',
    'Accept': 'application/json, text/plain, */*',
    'Content-Type': 'application/json;charset=UTF-8',
    'Origin': 'https://cafe.naver.com',
    'x-cafe-product': 'pc',
}

def log(msg): print(f'[{datetime.now().strftime("%H:%M:%S")}] {msg}', flush=True)


# ── DB ────────────────────────────────────────────────

def init_db():
    conn = sqlite3.connect(DB_PATH)
    conn.execute('''CREATE TABLE IF NOT EXISTS articles (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        source_id TEXT, title TEXT, summary TEXT, category TEXT,
        body_html TEXT, status TEXT DEFAULT 'collected',
        assigned_to TEXT, posted_at DATETIME, posted_id TEXT,
        board_key TEXT DEFAULT 'used', created_at DATETIME DEFAULT CURRENT_TIMESTAMP
    )''')
    conn.execute('''CREATE TABLE IF NOT EXISTS members (
        name TEXT PRIMARY KEY, post_count INTEGER DEFAULT 0,
        last_posted_at DATETIME, is_active INTEGER DEFAULT 1
    )''')
    conn.execute('''CREATE TABLE IF NOT EXISTS posting_log (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        member_name TEXT, article_id INTEGER, status TEXT,
        message TEXT, created_at DATETIME DEFAULT CURRENT_TIMESTAMP
    )''')
    conn.commit()
    conn.close()


# ── 세션 관리 ─────────────────────────────────────────

def get_member_session_path(name):
    """팀원의 세션 파일 경로"""
    return os.path.join(SESSIONS_DIR, f'{name}.json')


def add_member_qr(name):
    """
    팀원 추가 + QR 로그인
    - Playwright 실행 → QR 코드 화면
    - 스크린샷 저장 → 어디로 보낼지 안내
    - 팀원이 스캔하면 자동 저장
    """
    from playwright.sync_api import sync_playwright
    
    os.makedirs(SESSIONS_DIR, exist_ok=True)
    session_path = get_member_session_path(name)
    
    log(f'🔄 [{name}] QR 로그인 시작...')
    log('')
    log('='*60)
    log(f'  🔔 {name}님께 전달:')
    log('  "지금 QR 코드가 떴습니다. 네이버 앱 실행해서')
    log('   오른쪽 위 QR 스캔 버튼 누르고 이 코드를 찍어주세요!"')
    log('='*60)
    log('')
    
    with sync_playwright() as p:
        browser = p.chromium.launch(headless=False)
        ctx = browser.new_context(viewport={'width':1280,'height':900},
            locale='ko-KR', timezone_id='Asia/Seoul')
        page = ctx.new_page()
        page.goto('https://nid.naver.com/nidlogin.login?mode=qr', wait_until='networkidle')
        
        # QR 코드 화면 캡처 (텔레그램으로 보낼 수 있게)
        screenshot_path = os.path.join(BASE_DIR, f'qr_{name}.png')
        page.screenshot(path=screenshot_path)
        log(f'📸 QR 코드 스크린샷: {screenshot_path}')
        log(f'   (이 파일을 {name}님에게 보내주세요)')
        
        # 로그인 대기
        try:
            page.wait_for_url(lambda url: 'nidlogin' not in url, timeout=180000)
            log(f'✅ [{name}] 로그인 성공!')
        except:
            log(f'⏰ [{name}] 로그인 대기 시간 초과. Enter 누르면 다시 시도합니다.')
            input()
            browser.close()
            return add_member_qr(name)
        
        time.sleep(3)
        cookies = ctx.cookies()
        with open(session_path, 'w') as f:
            json.dump({'cookies': cookies, 'saved_at': time.time(), 'name': name}, f, ensure_ascii=False)
        
        log(f'✅ [{name}] 세션 저장 완료: {session_path}')
        browser.close()
    
    # DB에 멤버 등록
    conn = sqlite3.connect(DB_PATH)
    conn.execute('INSERT OR IGNORE INTO members (name) VALUES (?)', (name,))
    conn.commit()
    conn.close()
    log(f'👤 [{name}] 팀원 등록 완료')


def list_members():
    """등록된 팀원 목록"""
    conn = sqlite3.connect(DB_PATH)
    rows = conn.execute('SELECT name, post_count, last_posted_at FROM members WHERE is_active=1').fetchall()
    conn.close()
    
    result = []
    for r in rows:
        session_file = get_member_session_path(r[0])
        has_session = os.path.exists(session_file)
        result.append({
            'name': r[0], 'posts': r[1], 'last': r[2] or '-',
            'has_session': '✅' if has_session else '❌'
        })
    return result


# ── 게시글 발행 ───────────────────────────────────────

def make_se3_content(text):
    """SmartEditor 3 문서 포맷"""
    uid = uuid.uuid4().hex[:20].upper()
    clean = re.sub(r'<[^>]+>', ' ', text).strip()
    clean = re.sub(r'\s+', ' ', clean)
    return json.dumps({
        "document": {
            "version": "2.9.0", "theme": "default", "language": "ko-KR",
            "id": "SE-" + uid,
            "components": [{
                "id": "SE-" + uuid.uuid4().hex[:20].upper(), "layout": "default",
                "value": [{
                    "id": "SE-" + uuid.uuid4().hex[:20].upper(),
                    "nodes": [{"id": "SE-" + uuid.uuid4().hex[:20].upper(), "value": clean, "@ctype": "textNode"}],
                    "@ctype": "paragraph"
                }], "@ctype": "text"
            }],
            "di": {"dif": False, "dio": [
                {"dis": "N", "dia": {"t":0,"p":0,"st":1,"sk":0}},
                {"dis": "N", "dia": {"t":0,"p":0,"st":17,"sk":0}}
            ]}
        }, "documentId": ""
    }, ensure_ascii=False)


def post_for_member(member_name, board_key='used'):
    """
    특정 팀원 계정으로 게시글 1개 발행
    Returns: dict with result
    """
    session_path = get_member_session_path(member_name)
    if not os.path.exists(session_path):
        return {'success': False, 'error': f'{member_name}님 세션 없음. 먼저 QR 로그인이 필요합니다.'}
    
    board = BOARDS.get(board_key, BOARDS['used'])
    
    import requests
    with open(session_path) as f:
        state = json.load(f)
    
    s = requests.Session()
    for c in state.get('cookies', []):
        s.cookies.set(c['name'], c['value'], domain=c.get('domain', '.naver.com'))
    
    # DB에서 발행할 게시글 가져오기
    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row
    
    # 1) 이미 배정된 내 게시글 확인
    art = conn.execute(
        'SELECT * FROM articles WHERE assigned_to=? AND status="assigned" LIMIT 1',
        (member_name,)
    ).fetchone()
    
    # 2) 없으면 새로 배정
    if not art:
        art = conn.execute(
            'SELECT * FROM articles WHERE status="collected" ORDER BY id ASC LIMIT 1'
        ).fetchone()
        
        if art:
            conn.execute(
                'UPDATE articles SET status="assigned", assigned_to=? WHERE id=?',
                (member_name, art['id'])
            )
            conn.commit()
            art = conn.execute('SELECT * FROM articles WHERE id=?', (art['id'],)).fetchone()
    
    conn.close()
    
    if not art:
        return {'success': False, 'error': '발행할 게시글이 없습니다.'}
    
    art = dict(art)
    content = art.get('body_html', art.get('summary', art.get('title', '')))
    
    payload = {
        "article": {
            "cafeId": TARGET_CLUB_ID,
            "contentJson": make_se3_content(content),
            "from": "pc", "menuId": board['id'],
            "subject": art['title'][:80],
            "tagList": [], "editorVersion": 4, "parentId": 0,
            "open": False, "naverOpen": True, "externalOpen": True,
            "enableComment": True, "enableScrap": True, "enableCopy": False,
            "useAutoSource": True, "cclTypes": [], "useCcl": False
        }
    }
    
    url = API_BASE.format(TARGET_CLUB_ID, board['id'])
    headers = {**API_HEADERS,
        'Referer': f'https://cafe.naver.com/ca-fe/cafes/{TARGET_CLUB_ID}/articles/write'
    }
    
    log(f'📤 [{member_name}] {art["title"][:40]}... → {board["name"]}')
    
    try:
        resp = s.post(url, json=payload, headers=headers, timeout=30)
        
        # DB 업데이트
        conn = sqlite3.connect(DB_PATH)
        
        if resp.status_code == 200:
            data = resp.json()
            pid = data.get('result', {}).get('articleId', '?')
            
            conn.execute('UPDATE articles SET status="posted", posted_at=datetime("now","localtime"), posted_id=? WHERE id=?',
                        (str(pid), art['id']))
            conn.execute('UPDATE members SET post_count=post_count+1, last_posted_at=datetime("now","localtime") WHERE name=?',
                        (member_name,))
            conn.execute('INSERT INTO posting_log (member_name, article_id, status, message) VALUES (?,?,?,?)',
                        (member_name, art['id'], 'success', f'articleId={pid}'))
            conn.commit()
            conn.close()
            
            log(f'✅ [{member_name}] 성공! articleId={pid}')
            return {'success': True, 'article_id': pid}
        
        else:
            err = resp.text[:200]
            conn.execute('INSERT INTO posting_log (member_name, article_id, status, message) VALUES (?,?,?,?)',
                        (member_name, art['id'], 'failed', err))
            conn.commit()
            conn.close()
            
            log(f'❌ [{member_name}] 실패: {err[:80]}')
            return {'success': False, 'error': err}
    
    except Exception as e:
        conn = sqlite3.connect(DB_PATH)
        conn.execute('INSERT INTO posting_log (member_name, article_id, status, message) VALUES (?,?,?,?)',
                    (member_name, art['id'], 'error', str(e)[:200]))
        conn.commit()
        conn.close()
        return {'success': False, 'error': str(e)}


# ── 크롤링 ────────────────────────────────────────────

def add_article(title, body_html, category='', summary='', board='used'):
    """게시글을 DB에 수동 추가"""
    conn = sqlite3.connect(DB_PATH)
    # SEO 제목 생성
    seo_title = title.strip()
    seo_title = re.sub(r'^[#＃]\s*', '', seo_title)
    for brand, full in [("스즈키","스즈키 Suzuki"),("괴츠","괴츠 Goetz"),("반디니","반디니 Bandini")]:
        if brand in seo_title:
            seo_title = seo_title.replace(brand, full)
            break
    if len(seo_title) > 70:
        seo_title = seo_title[:67] + '...'
    
    conn.execute('''INSERT INTO articles (title, summary, category, body_html, status, board_key)
                    VALUES (?,?,?,?,'collected',?)''',
                (seo_title, summary, category, body_html, board))
    conn.commit()
    aid = conn.lastrowid
    conn.close()
    log(f'✅ 게시글 추가: #{aid} - {seo_title[:40]}')
    return aid


# ── 전체 실행 ─────────────────────────────────────────

def run_all_members(board='used', max_per_member=3):
    """모든 활성 팀원 순회하며 발행"""
    conn = sqlite3.connect(DB_PATH)
    members = conn.execute('SELECT name FROM members WHERE is_active=1').fetchall()
    conn.close()
    
    if not members:
        log('⚠️ 등록된 팀원이 없습니다.')
        return
    
    log(f'🚀 전체 발행 시작: {len(members)}명')
    
    for m in members:
        name = m[0]
        session_path = get_member_session_path(name)
        
        if not os.path.exists(session_path):
            log(f'⏭ [{name}] 세션 없음. 건너뜀.')
            continue
        
        # 오늘 발행 수 확인
        conn = sqlite3.connect(DB_PATH)
        today = conn.execute(
            'SELECT COUNT(*) FROM posting_log WHERE member_name=? AND status="success" AND date(created_at)=date("now")',
            (name,)
        ).fetchone()[0]
        conn.close()
        
        if today >= max_per_member:
            log(f'⏰ [{name}] 오늘 {today}회 이미 발행. 건너뜀.')
            continue
        
        log(f'▶ [{name}] 발행 시작 (오늘 {today}/{max_per_member})')
        result = post_for_member(name, board)
        log(f'  결과: {"✅" if result["success"] else "❌"} {result.get("article_id","")}')
        time.sleep(3)  # 발행 간격
    
    log('🏁 전체 발행 완료')


# ── 상태 ──────────────────────────────────────────────

def show_status():
    """전체 현황"""
    if not os.path.exists(DB_PATH):
        log('❌ DB 없음')
        return
    
    conn = sqlite3.connect(DB_PATH)
    cur = conn.cursor()
    
    total = cur.execute('SELECT COUNT(*) FROM articles').fetchone()[0]
    pending = cur.execute('SELECT COUNT(*) FROM articles WHERE status="collected"').fetchone()[0]
    posted = cur.execute('SELECT COUNT(*) FROM articles WHERE status="posted"').fetchone()[0]
    
    print(f'\n{"="*50}')
    print(f'📊 팀 발행 현황 (에코뮤직 중고악기백화점)')
    print(f'{"="*50}')
    print(f'  📦 전체 게시글:    {total}개')
    print(f'  ⏳ 발행 대기:      {pending}개')
    print(f'  ✅ 발행 완료:      {posted}개')
    
    print(f'\n👥 팀원 현황:')
    members = conn.execute(
        'SELECT m.name, m.post_count, m.last_posted_at, COUNT(l.id) as today_count '
        'FROM members m LEFT JOIN posting_log l ON m.name=l.member_name AND l.status="success" AND date(l.created_at)=date("now") '
        'WHERE m.is_active=1 GROUP BY m.name ORDER BY m.post_count DESC'
    ).fetchall()
    
    for m in members:
        sess = '✅' if os.path.exists(get_member_session_path(m[0])) else '❌'
        print(f'  {sess} {m[0]:8s} | 총 {m[1]:2d}회 | 오늘 {m[3]:1d}회 | 최근: {m[2] or "-"}')
    
    print()
    conn.close()


# ── CLI ───────────────────────────────────────────────

def main():
    parser = argparse.ArgumentParser(description='Naver Cafe Team Commander')
    parser.add_argument('--add', help='팀원 추가 (QR 로그인 실행)')
    parser.add_argument('--post', help='특정 팀원 발행 (이름 입력)')
    parser.add_argument('--all', action='store_true', help='전체 팀원 발행')
    parser.add_argument('--add-article', nargs=2, metavar=('TITLE', 'BODY'), help='게시글 수동 추가')
    parser.add_argument('--board', default='used', choices=BOARDS.keys())
    parser.add_argument('--status', action='store_true', help='현황 확인')
    args = parser.parse_args()
    
    if not os.path.exists(DB_PATH):
        init_db()
    
    # 팀원 추가
    if args.add:
        init_db()
        add_member_qr(args.add)
        return
    
    # 특정 팀원 발행
    if args.post:
        init_db()
        result = post_for_member(args.post, args.board)
        print(f'  → {"✅ 성공" if result["success"] else "❌ 실패"}: {result.get("article_id", result.get("error",""))}')
        return
    
    # 전체 발행
    if args.all:
        init_db()
        run_all_members(args.board)
        return
    
    # 게시글 추가
    if args.add_article:
        init_db()
        add_article(args.add_article[0], args.add_article[1], board=args.board)
        return
    
    # 상태
    if args.status:
        show_status()
        return
    
    parser.print_help()
    print()
    print('📌 사용 예시:')
    print('  # 팀원 등록 (QR 로그인 실행됨 → 팀원이 QR 스캔)')
    print('  python commander.py --add "최용현"')
    print()
    print('  # 게시글 수동 추가')
    print('  python commander.py --add-article "스즈키 바이올린 팝니다" "<p>상태 좋습니다</p>"')
    print()
    print('  # 특정 팀원 발행')
    print('  python commander.py --post "최용현"')
    print()
    print('  # 모든 팀원 발행')
    print('  python commander.py --all')
    print()
    print('  # 현황 확인')
    print('  python commander.py --status')


if __name__ == '__main__':
    main()
