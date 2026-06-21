#!/usr/bin/env python3
"""
Naver Cafe Team Poster v1.0
============================
팀 단위 네이버 카페 게시글 자동 발행 시스템

구조:
  [중앙 크롤러] → 공유 DB → [팀원1: naver_id1]
                           → [팀원2: naver_id2]
                           → [팀원3: naver_id3]

사용법:
  # 관리자: 크롤링 실행
  python team_poster.py --crawl

  # 팀원: 내 차례 게시글 발행 (본인 naver_state.json 필요)
  python team_poster.py --post --member "홍길동"

  # 관리자: 상태 확인
  python team_poster.py --status
"""
import json, os, sys, time, re, sqlite3, argparse, uuid
from datetime import datetime
from pathlib import Path

BASE_DIR = os.path.dirname(os.path.abspath(__file__))

# ── 설정 ──────────────────────────────────────────────
TARGET_CLUB_ID = '31386031'     # 에코뮤직 중고악기백화점
SOURCE_CLUB_ID = '30497286'     # 빈티지뮤직 (크롤링 대상)
DB_PATH = os.path.join(BASE_DIR, 'team_articles.db')
TEAM_CONFIG_PATH = os.path.join(BASE_DIR, 'team_config.json')

# 게시판 매핑 (타겟 카페 기준)
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


# ── 유틸리티 ──────────────────────────────────────────

def log(msg): print(f'[{datetime.now().strftime("%H:%M:%S")}] {msg}', flush=True)

def today_str(): return datetime.now().strftime('%Y-%m-%d')


# ── DB 관리 ──────────────────────────────────────────

def init_db():
    """팀 공유 DB 초기화"""
    conn = sqlite3.connect(DB_PATH)
    conn.execute('''
        CREATE TABLE IF NOT EXISTS articles (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            source_article_id TEXT,          -- 원본 게시글 ID (빈티지뮤직)
            title TEXT NOT NULL,
            summary TEXT,
            category TEXT,
            author TEXT,
            image_url TEXT,
            body_html TEXT,                  -- SEO 최적화된 본문
            status TEXT DEFAULT 'collected', -- collected | assigned | posted | skipped
            assigned_to TEXT,                -- 배정된 팀원 이름
            posted_at DATETIME,
            posted_article_id TEXT,          -- 발행된 게시글 ID
            board_key TEXT DEFAULT 'used',   -- 발행 게시판
            created_at DATETIME DEFAULT CURRENT_TIMESTAMP
        )
    ''')
    conn.execute('''
        CREATE TABLE IF NOT EXISTS members (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            name TEXT UNIQUE NOT NULL,
            naver_id TEXT,
            post_count INTEGER DEFAULT 0,
            last_posted_at DATETIME,
            is_active INTEGER DEFAULT 1
        )
    ''')
    conn.execute('''
        CREATE TABLE IF NOT EXISTS posting_log (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            article_id INTEGER,
            member_name TEXT,
            status TEXT,
            message TEXT,
            created_at DATETIME DEFAULT CURRENT_TIMESTAMP
        )
    ''')
    conn.commit()
    conn.close()
    log(f'✅ DB 준비 완료: {DB_PATH}')


def get_pending_articles(limit=5):
    """발행 대기 중인 게시글 조회"""
    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row
    rows = conn.execute(
        'SELECT * FROM articles WHERE status="collected" ORDER BY id ASC LIMIT ?',
        (limit,)
    ).fetchall()
    conn.close()
    return [dict(r) for r in rows]


def get_my_articles(member_name, limit=3):
    """내게 배정된 미발행 게시글 조회"""
    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row
    rows = conn.execute(
        'SELECT * FROM articles WHERE assigned_to=? AND status="assigned" ORDER BY id ASC LIMIT ?',
        (member_name, limit)
    ).fetchall()
    conn.close()
    return [dict(r) for r in rows]


def assign_article(article_id, member_name):
    """게시글을 특정 팀원에게 배정"""
    conn = sqlite3.connect(DB_PATH)
    conn.execute(
        'UPDATE articles SET status="assigned", assigned_to=? WHERE id=? AND status="collected"',
        (member_name, article_id)
    )
    affected = conn.total_changes
    conn.commit()
    conn.close()
    
    if affected > 0:
        log(f'📌 article#{article_id} → {member_name} 배정 완료')
        return True
    else:
        log(f'⚠️ article#{article_id} 배정 실패 (이미 배정됨)')
        return False


def mark_posted(article_id, member_name, posted_id, board_name):
    """발행 완료 처리"""
    conn = sqlite3.connect(DB_PATH)
    conn.execute(
        '''UPDATE articles SET status="posted", posted_at=datetime("now","localtime"),
           posted_article_id=? WHERE id=?''',
        (str(posted_id), article_id)
    )
    conn.execute(
        '''UPDATE members SET post_count=post_count+1, last_posted_at=datetime("now","localtime")
           WHERE name=?''', (member_name,)
    )
    conn.execute(
        'INSERT INTO posting_log (article_id, member_name, status, message) VALUES (?,?,?,?)',
        (article_id, member_name, 'success', f'→ {board_name} (articleId={posted_id})')
    )
    conn.commit()
    conn.close()
    log(f'✅ article#{article_id} 발행 완료 (ID: {posted_id})')


def mark_failed(article_id, member_name, error_msg):
    """발행 실패 기록"""
    conn = sqlite3.connect(DB_PATH)
    conn.execute(
        'INSERT INTO posting_log (article_id, member_name, status, message) VALUES (?,?,?,?)',
        (article_id, member_name, 'failed', error_msg[:200])
    )
    conn.commit()
    conn.close()
    log(f'❌ article#{article_id} 실패: {error_msg[:100]}')


# ── 멤버 관리 ─────────────────────────────────────────

def add_member(name, naver_id=''):
    """팀원 추가"""
    conn = sqlite3.connect(DB_PATH)
    try:
        conn.execute('INSERT INTO members (name, naver_id) VALUES (?, ?)', (name, naver_id))
        conn.commit()
        log(f'👤 팀원 추가: {name}')
    except sqlite3.IntegrityError:
        log(f'⚠️ 이미 등록된 팀원: {name}')
    conn.close()


def load_team_config():
    """팀 설정 로드"""
    default = {
        'team_name': '에코뮤직 마케팅팀',
        'target_club_id': TARGET_CLUB_ID,
        'source_club_id': SOURCE_CLUB_ID,
        'default_board': 'used',
        'daily_post_per_member': 3,
        'post_interval_seconds': 5,
        'members': []
    }
    if os.path.exists(TEAM_CONFIG_PATH):
        with open(TEAM_CONFIG_PATH) as f:
            return {**default, **json.load(f)}
    return default


# ── SE3 컨텐츠 포맷 ───────────────────────────────────

def make_se3_content(text):
    """HTML 텍스트 → SmartEditor 3 문서 포맷"""
    uid = uuid.uuid4().hex[:20].upper()
    clean = re.sub(r'<[^>]+>', ' ', text).strip()
    clean = re.sub(r'\s+', ' ', clean)
    
    return json.dumps({
        "document": {
            "version": "2.9.0", "theme": "default", "language": "ko-KR",
            "id": "SE-" + uid,
            "components": [{
                "id": "SE-" + uuid.uuid4().hex[:20].upper(),
                "layout": "default",
                "value": [{
                    "id": "SE-" + uuid.uuid4().hex[:20].upper(),
                    "nodes": [{
                        "id": "SE-" + uuid.uuid4().hex[:20].upper(),
                        "value": clean, "@ctype": "textNode"
                    }], "@ctype": "paragraph"
                }], "@ctype": "text"
            }],
            "di": {
                "dif": False,
                "dio": [
                    {"dis": "N", "dia": {"t": 0, "p": 0, "st": 1, "sk": 0}},
                    {"dis": "N", "dia": {"t": 0, "p": 0, "st": 17, "sk": 0}}
                ]
            }
        },
        "documentId": ""
    }, ensure_ascii=False)


# ── 크롤링 ────────────────────────────────────────────

def crawl_source_cafe():
    """빈티지뮤직에서 게시글 크롤링"""
    import requests
    
    url = f'https://apis.naver.com/cafe-web/cafe-boardlist-api/v1.0/cafes/{SOURCE_CLUB_ID}/menus/0/articles?page=1&perPage=10&orderBy=date'
    
    # 세션 로드
    state_file = os.path.join(BASE_DIR, 'naver_state.json')
    if not os.path.exists(state_file):
        log('❌ naver_state.json 없음. --qr-login 먼저 실행')
        return
    
    with open(state_file) as f:
        state = json.load(f)
    
    s = requests.Session()
    for c in state.get('cookies', []):
        s.cookies.set(c['name'], c['value'], domain=c.get('domain', '.naver.com'))
    
    headers = {
        'User-Agent': 'Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36',
        'Referer': f'https://cafe.naver.com/ca-fe/cafes/{SOURCE_CLUB_ID}',
    }
    
    resp = s.get(url, headers=headers, timeout=15)
    if resp.status_code != 200:
        log(f'❌ 크롤링 실패 ({resp.status_code})')
        return
    
    data = resp.json()
    items = data.get('result', {}).get('articleList', [])
    log(f'📡 빈티지뮤직에서 {len(items)}개 게시글 발견')
    
    conn = sqlite3.connect(DB_PATH)
    count = 0
    for item in items:
        title = item.get('subject', '')
        if not title:
            continue
        
        # 중복 확인
        existing = conn.execute(
            'SELECT id FROM articles WHERE source_article_id=?',
            (str(item.get('articleId', '')),)
        ).fetchone()
        if existing:
            continue
        
        # SEO 최적화 (간단 버전)
        body = item.get('contentPreview', '') or item.get('summary', '')
        category = item.get('menu', {}).get('menuName', '')
        author = item.get('writer', {}).get('nick', '')
        
        # SEO 제목 생성
        seo_title = title.strip()
        seo_title = re.sub(r'^[#＃]\s*', '', seo_title)
        for brand, full in [("스즈키","스즈키 Suzuki"),("괴츠","괴츠 Goetz"),("반디니","반디니 Bandini")]:
            if brand in seo_title:
                seo_title = seo_title.replace(brand, full)
                break
        if len(seo_title) > 70:
            seo_title = seo_title[:67] + '...'
        
        # SEO 본문
        seo_body = f'## 🎵 {title}\n\n'
        if category:
            seo_body += f'**카테고리:** {category}\n\n'
        if body:
            seo_body += f'{body}\n\n'
        seo_body += f'---\n#중고악기 #악기판매 #{category.replace(" ","")}\n📌 **에코뮤직 중고악기백화점**에서 소개합니다.\n📅 {datetime.now().strftime("%Y년 %m월 %d일")}'
        
        # HTML 변환
        body_html = seo_body.replace('\n', '<br>')
        
        conn.execute(
            '''INSERT INTO articles (source_article_id, title, summary, category, author, body_html, status)
               VALUES (?,?,?,?,?,?,'collected')''',
            (str(item.get('articleId','')), seo_title, body, category, author, body_html)
        )
        count += 1
    
    conn.commit()
    conn.close()
    log(f'✅ {count}개 신규 게시글 추가')


# ── 발행 (팀원용) ─────────────────────────────────────

def post_article(article, member_name, board_key='used'):
    """
    게시글 발행 (REST API 직접 호출)
    - naver_state.json 필요 (본인 계정)
    """
    if board_key not in BOARDS:
        return {'success': False, 'error': f'Unknown board: {board_key}'}
    
    board = BOARDS[board_key]
    state_file = os.path.join(BASE_DIR, 'naver_state.json')
    
    if not os.path.exists(state_file):
        return {'success': False, 'error': 'naver_state.json 없음. --qr-login 먼저 실행'}
    
    import requests
    with open(state_file) as f:
        state = json.load(f)
    
    s = requests.Session()
    for c in state.get('cookies', []):
        s.cookies.set(c['name'], c['value'], domain=c.get('domain', '.naver.com'))
    
    content_html = article.get('body_html', article.get('summary', article.get('title', '')))
    content_html = content_html.replace('<br>', '\n')
    
    payload = {
        "article": {
            "cafeId": TARGET_CLUB_ID,
            "contentJson": make_se3_content(content_html),
            "from": "pc",
            "menuId": board['id'],
            "subject": article['title'][:80],
            "tagList": [],
            "editorVersion": 4,
            "parentId": 0,
            "open": False, "naverOpen": True, "externalOpen": True,
            "enableComment": True, "enableScrap": True, "enableCopy": False,
            "useAutoSource": True, "cclTypes": [], "useCcl": False
        }
    }
    
    url = API_BASE.format(TARGET_CLUB_ID, board['id'])
    headers = {**API_HEADERS,
        'Referer': f'https://cafe.naver.com/ca-fe/cafes/{TARGET_CLUB_ID}/articles/write'
    }
    
    log(f'📤 [{member_name}] 발행 중: {article["title"][:40]}... → {board["name"]}')
    
    try:
        resp = s.post(url, json=payload, headers=headers, timeout=30)
        
        if resp.status_code == 200:
            data = resp.json()
            article_id = data.get('result', {}).get('articleId', '?')
            log(f'✅ 성공! articleId={article_id}')
            return {'success': True, 'article_id': article_id}
        else:
            error = resp.text[:300]
            log(f'❌ 실패 ({resp.status_code}): {error[:100]}')
            return {'success': False, 'error': error}
    
    except Exception as e:
        log(f'❌ 오류: {e}')
        return {'success': False, 'error': str(e)}


def run_member_post(member_name, board_key='used', max_posts=3):
    """
    팀원 발행 실행:
    1. 내게 배정된 게시글 확인
    2. 없으면 새 게시글 배정 받기
    3. 발행
    """
    # 1. 내 배정글 확인
    my_articles = get_my_articles(member_name, max_posts)
    
    if not my_articles:
        log(f'🔍 {member_name}님의 배정된 게시글이 없습니다. 새로 배정 받습니다.')
        pending = get_pending_articles(max_posts)
        
        for art in pending:
            assign_article(art['id'], member_name)
        
        my_articles = get_my_articles(member_name, max_posts)
    
    if not my_articles:
        log('📭 발행할 게시글이 없습니다.')
        return
    
    # 2. 발행
    log(f'📋 {member_name}님, {len(my_articles)}개 게시글 발행 시작')
    
    results = []
    for art in my_articles:
        time.sleep(2)  # 발행 간격
        
        result = post_article(art, member_name, board_key)
        
        if result['success']:
            mark_posted(art['id'], member_name, result['article_id'], BOARDS[board_key]['name'])
        else:
            mark_failed(art['id'], member_name, result.get('error', 'unknown'))
        
        results.append(result)
    
    success = sum(1 for r in results if r['success'])
    log(f'📊 [{member_name}] {success}/{len(results)} 발행 완료')
    return results


# ── 상태 확인 ─────────────────────────────────────────

def show_status():
    """전체 상태 보고"""
    if not os.path.exists(DB_PATH):
        log('❌ DB 없음. 먼저 --crawl 실행')
        return
    
    conn = sqlite3.connect(DB_PATH)
    cur = conn.cursor()
    
    total = cur.execute('SELECT COUNT(*) FROM articles').fetchone()[0]
    collected = cur.execute('SELECT COUNT(*) FROM articles WHERE status="collected"').fetchone()[0]
    assigned = cur.execute('SELECT COUNT(*) FROM articles WHERE status="assigned"').fetchone()[0]
    posted = cur.execute('SELECT COUNT(*) FROM articles WHERE status="posted"').fetchone()[0]
    
    print(f'\n{"="*50}')
    print(f'📊 팀 발행 현황')
    print(f'{"="*50}')
    print(f'  전체 게시글:   {total}개')
    print(f'  발행 대기:     {collected}개')
    print(f'  배정 완료:     {assigned}개')
    print(f'  ✅ 발행 완료:  {posted}개')
    
    # 팀원별 현황
    members = cur.execute(
        'SELECT name, post_count, last_posted_at FROM members WHERE is_active=1 ORDER BY post_count DESC'
    ).fetchall()
    
    if members:
        print(f'\n👥 팀원별 발행 현황:')
        for m in members:
            last = m[2] or '-'
            print(f'  {m[0]:10s}  {m[1]:3d}회 발행  (최근: {last})')
    
    # 최근 로그
    logs = cur.execute(
        'SELECT member_name, status, message, created_at FROM posting_log ORDER BY id DESC LIMIT 5'
    ).fetchall()
    
    if logs:
        print(f'\n📋 최근 발행 로그:')
        for l in logs:
            icon = '✅' if l[1] == 'success' else '❌'
            print(f'  {icon} {l[0]}: {l[2][:50]} ({l[3]})')
    
    conn.close()
    print()


# ── QR 로그인 ─────────────────────────────────────────

def qr_login():
    """네이버 QR 로그인"""
    try:
        from playwright.sync_api import sync_playwright
    except ImportError:
        log('❌ playwright 필요: pip install playwright && playwright install chromium')
        sys.exit(1)
    
    log('🔄 네이버 QR 로그인 시작...')
    log('📱 화면에 QR 코드가 표시됩니다. 네이버 앱으로 스캔해주세요.')
    
    state_file = os.path.join(BASE_DIR, 'naver_state.json')
    
    with sync_playwright() as p:
        browser = p.chromium.launch(headless=False)
        ctx = browser.new_context(viewport={'width':1280,'height':900},
            locale='ko-KR', timezone_id='Asia/Seoul')
        page = ctx.new_page()
        page.goto('https://nid.naver.com/nidlogin.login?mode=qr', wait_until='networkidle')
        
        try:
            page.wait_for_url(lambda url: 'nidlogin' not in url, timeout=180000)
            log('✅ QR 로그인 성공!')
        except:
            page.wait_for_timeout(30000)
        
        time.sleep(3)
        cookies = ctx.cookies()
        with open(state_file, 'w') as f:
            json.dump({'cookies': cookies, 'saved_at': time.time()}, f, ensure_ascii=False)
        
        log(f'✅ 세션 저장 완료 (쿠키 {len(cookies)}개)')
        browser.close()


# ── CLI ───────────────────────────────────────────────

def main():
    parser = argparse.ArgumentParser(description='Naver Cafe Team Poster')
    parser.add_argument('--crawl', action='store_true', help='크롤링 실행 (관리자용)')
    parser.add_argument('--post', action='store_true', help='게시글 발행 (팀원용)')
    parser.add_argument('--member', help='팀원 이름')
    parser.add_argument('--board', default='used', choices=BOARDS.keys(), help='게시판')
    parser.add_argument('--max', type=int, default=3, help='최대 발행 수')
    parser.add_argument('--add-member', help='팀원 추가 (관리자용)')
    parser.add_argument('--qr-login', action='store_true', help='QR 로그인')
    parser.add_argument('--init', action='store_true', help='DB 초기화')
    parser.add_argument('--status', action='store_true', help='현황 확인')
    parser.add_argument('--setup', action='store_true', help='팀 최초 설정')
    args = parser.parse_args()
    
    # DB 초기화
    if args.init or not os.path.exists(DB_PATH):
        init_db()
    
    # QR 로그인
    if args.qr_login:
        qr_login()
        return
    
    # 팀 최초 설정
    if args.setup:
        init_db()
        config = load_team_config()
        print(f'\n{"="*50}')
        print(f'🏢 팀 설정: {config["team_name"]}')
        print(f'{"="*50}')
        print(f'  타겟 카페 ID: {config["target_club_id"]}')
        print(f'  소스 카페 ID: {config["source_club_id"]}')
        print(f'  기본 게시판: {config["default_board"]}')
        print(f'  1인당 일일 발행: {config["daily_post_per_member"]}개')
        print(f'\n📋 팀원 등록:')
        print(f'  python team_poster.py --add-member "홍길동"')
        print(f'  python team_poster.py --add-member "김철수"')
        print(f'\n🔐 각 팀원은 QR 로그인 필요:')
        print(f'  python team_poster.py --qr-login')
        return
    
    # 팀원 추가
    if args.add_member:
        add_member(args.add_member)
        return
    
    # 크롤링
    if args.crawl:
        init_db()
        crawl_source_cafe()
        return
    
    # 발행
    if args.post:
        if not args.member:
            log('❌ --member 필수: python team_poster.py --post --member "홍길동"')
            return
        init_db()
        
        # 오늘 이미 발행한 횟수 확인
        conn = sqlite3.connect(DB_PATH)
        today_count = conn.execute(
            'SELECT COUNT(*) FROM posting_log WHERE member_name=? AND status="success" AND date(created_at)=date("now")',
            (args.member,)
        ).fetchone()[0]
        conn.close()
        
        config = load_team_config()
        max_today = config.get('daily_post_per_member', 3)
        
        if today_count >= max_today:
            log(f'⏰ 오늘 {args.member}님 이미 {today_count}회 발행 (최대 {max_today}회). 내일 다시 시도하세요.')
            return
        
        remaining = max_today - today_count
        log(f'📅 오늘 {args.member}님: {today_count}/{max_today}회 발행 완료, {remaining}회 가능')
        
        run_member_post(args.member, args.board, min(args.max, remaining))
        return
    
    # 상태 확인
    if args.status:
        show_status()
        return
    
    parser.print_help()
    print(f'\n📌 사용 예시:')
    print(f'  # 1. 최초 설정')
    print(f'  python team_poster.py --setup')
    print(f'  python team_poster.py --add-member "홍길동"')
    print(f'  python team_poster.py --add-member "김철수"')
    print(f'\n  # 2. 각 팀원 QR 로그인 (1회)')
    print(f'  python team_poster.py --qr-login')
    print(f'\n  # 3. 관리자: 크롤링')
    print(f'  python team_poster.py --crawl')
    print(f'\n  # 4. 팀원: 발행 실행')
    print(f'  python team_poster.py --post --member "홍길동"')
    print(f'\n  # 5. 현황 확인')
    print(f'  python team_poster.py --status')


if __name__ == '__main__':
    main()
