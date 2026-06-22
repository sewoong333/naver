#!/Users/se-ung/.hermes/hermes-agent/venv/bin/python3
"""
Naver Session Manager v2.1
=============================
네이버 카페 세션 관리자 + 일일 게시글 자동 발행
- 중고악기거래 게시판(used, menuId=11) 메인
- 꿀팁 게시판(tip, menuId=5) 보조
- 하루 3-4개 발행
"""

import json, os, sys, time, re, uuid, argparse, pickle, random
from datetime import datetime, date
from pathlib import Path

# ── 설정 ──────────────────────────────────────────────
BASE_DIR = os.path.dirname(os.path.abspath(__file__))
STORAGE_FILE = os.path.join(BASE_DIR, 'naver_storage.json')
SESSION_META = os.path.join(BASE_DIR, 'naver_session_meta.json')

TARGET_CLUB_ID = '31386031'  # 에코뮤직 중고악기백화점

# 게시판 매핑 (중고악기거래 게시판=메인, 꿀팁=보조)
BOARDS = {
    'used': {'id': 11, 'name': '중고악기거래 게시판', 'boardType': 'L'},  # ★ 메인
    'free': {'id': 1, 'name': '자유게시판', 'boardType': 'L'},
    'tip':  {'id': 5, 'name': '꿀팁 게시판', 'boardType': 'L'},           # ★ 꿀팁/정보
    'trade': {'id': 2, 'name': '중고 악기 팝니다', 'boardType': 'T'},
}

API_BASE = 'https://apis.cafe.naver.com/editor/v2.0/cafes/{}/menus/{}/articles'
QR_TIMEOUT = 180

# ── 악기 데이터 ──────────────────────────────────────

INSTRUMENTS = [
    ("바이올린", "violin"), ("첼로", "cello"), ("비올라", "viola"),
    ("더블베이스", "doublebass"), ("기타", "guitar"), ("일렉기타", "electricguitar"),
    ("베이스기타", "bassguitar"), ("우쿨렐레", "ukulele"), ("클라리넷", "clarinet"),
    ("플루트", "flute"), ("색소폰", "saxophone"), ("트럼펫", "trumpet"),
    ("트롬본", "trombone"), ("피아노", "piano"), ("키보드", "keyboard"),
    ("신디사이저", "synth"), ("드럼", "drum"), ("전자드럼", "electronicdrum"),
    ("실로폰", "xylophone"), ("마림바", "marimba"), ("하프", "harp"),
    ("아코디언", "accordion"), ("밴조", "banjo"), ("만돌린", "mandolin"),
]

BRANDS = [
    "야마하", "야마하(YAMAHA)", "스즈키", "스즈키(SUZUKI)", "괴츠",
    "괴츠(Goetz)", "반디니", "반디니(Bandini)", "깁슨", "깁슨(Gibson)",
    "펜더", "펜더(Fender)", "아이바네즈", "아이바네즈(Ibanez)",
    "마틴", "마틴(Martin)", "테일러", "테일러(Taylor)",
    "로렌디", "로렌디(Lorendi)", "자이렉스", "자이렉스(Zynex)",
]

# ── 유틸리티 ──────────────────────────────────────────

def log(msg):
    print(f'[{datetime.now().strftime("%H:%M:%S")}] {msg}', flush=True)


CONTACT_IMAGE_URL = 'https://files.catbox.moe/ka3sz9.jpg'
CONTACT_IMAGE_LOCAL = '/Users/se-ung/.hermes/profiles/choi-yonghyun/image_cache/img_341fd7362983.jpg'
CONTACT_IMAGE_CACHE = os.path.join(BASE_DIR, 'contact_image_cache.json')

# ── 이미지 업로드 API ──────────────────────────────────

def get_naver_session_key():
    """SE3 photo-uploader session-key 획득 (GET)"""
    state = load_session_storage()
    if not state:
        return None

    import requests as req
    s = req.Session()
    for c in state.get('cookies', []):
        s.cookies.set(c['name'], c['value'],
                      domain=c.get('domain', '.naver.com'),
                      path=c.get('path', '/'))

    url = 'https://platform.editor.naver.com/api/cafepc001/v1/photo-uploader/session-key'
    headers = {
        'User-Agent': 'Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36',
        'Origin': 'https://cafe.naver.com',
        'Referer': f'https://cafe.naver.com/ca-fe/cafes/{TARGET_CLUB_ID}/articles/write',
        'Accept': 'application/json',
    }
    try:
        resp = s.get(url, headers=headers, timeout=15)  # GET!
        if resp.status_code == 200:
            data = resp.json()
            if data.get('isSuccess'):
                sk = data['sessionKey']
                log(f'✅ Session-key 획득 ({len(sk)} chars)')
                return sk
        log(f'❌ Session-key 실패 ({resp.status_code}): {resp.text[:200]}')
        return None
    except Exception as e:
        log(f'❌ Session-key 오류: {e}')
        return None


def upload_image_to_naver(image_path, session_key=None):
    """
    Naver Cafe CDN에 이미지 업로드
    1. session-key 획득 (없으면 자동)
    2. upload URL 구성
    3. POST multipart → XML 응답
    4. CDN URL 반환
    """
    # 1. session-key
    if not session_key:
        session_key = get_naver_session_key()
    if not session_key:
        return None

    # session-key decode → userid 추출
    import base64
    try:
        pad = 4 - (len(session_key) % 4)
        if pad != 4:
            sk_padded = session_key + '=' * pad
        else:
            sk_padded = session_key
        decoded = base64.b64decode(sk_padded).decode('utf-8')
        fields = decoded.split('\x07')
        userid = fields[3] if len(fields) > 3 else 'sewoong333'
    except:
        userid = 'sewoong333'

    # 2. Upload URL 구성
    upload_url = f'https://cafe.upphoto.naver.com/{session_key}/simpleUpload/0'
    upload_url += f'?userId={userid}'
    upload_url += '&extractExif=true&extractAnimatedCnt=false&extractAnimatedInfo=true'
    upload_url += '&autorotate=true&extractDominantColor=false&type='
    upload_url += '&customQuery=&denyAnimatedImage=false&skipXcamFiltering=false'

    # 3. 이미지 POST
    state = load_session_storage()
    if not state:
        return None

    import requests as req
    s = req.Session()
    for c in state.get('cookies', []):
        s.cookies.set(c['name'], c['value'],
                      domain=c.get('domain', '.naver.com'),
                      path=c.get('path', '/'))

    headers = {
        'User-Agent': 'Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36',
        'Origin': 'https://cafe.naver.com',
        'Referer': f'https://cafe.naver.com/ca-fe/cafes/{TARGET_CLUB_ID}/articles/write',
    }

    log(f'📤 이미지 업로드 중... ({os.path.basename(image_path)})')
    try:
        with open(image_path, 'rb') as f:
            files = {'file': (os.path.basename(image_path), f, 'image/jpeg')}
            resp = s.post(upload_url, files=files, headers=headers, timeout=30)

        if resp.status_code != 200:
            log(f'❌ 업로드 실패 ({resp.status_code}): {resp.text[:200]}')
            return None

        # 4. XML 파싱 → CDN URL 추출
        text = resp.text
        import re as re_xml
        m = re_xml.search(r'<url>(.*?)</url>', text)
        if m:
            cdn_path = m.group(1).strip()
            # cdn_path 예: /MjAyNjA2MjBfNTUg/MDAxNzgxOTE5ODU2MTU4....JPEG/img.jpg
            # CDN 도메인 조합
            full_url = f'https://cafeptthumb-phinf.pstatic.net{cdn_path}'
            log(f'✅ CDN URL 획득: {full_url[:80]}...')
            return full_url
        else:
            log(f'❌ XML 파싱 실패: {text[:200]}')
            return None

    except Exception as e:
        log(f'❌ 업로드 오류: {e}')
        return None


def ensure_contact_image():
    """
    연락처 이미지를 Naver CDN에 업로드하고 URL 반환
    1. Playwright로 se-authorization 토큰 캡처
    2. REST API로 session-key 획득
    3. REST API로 이미지 업로드 → CDN URL
    4. 캐시 저장 (24시간)
    """
    # 캐시 확인
    if os.path.exists(CONTACT_IMAGE_CACHE):
        with open(CONTACT_IMAGE_CACHE) as f:
            cache = json.load(f)
        url = cache.get('cdn_url', '')
        if url and (time.time() - cache.get('cached_at', 0)) < 86400:
            log('♻️ 캐시된 연락처 이미지 사용')
            return url

    log('🔄 이미지 업로드 시작...')
    cdn_url = _upload_via_playwright(CONTACT_IMAGE_LOCAL)
    if cdn_url:
        with open(CONTACT_IMAGE_CACHE, 'w') as f:
            json.dump({'cdn_url': cdn_url, 'cached_at': time.time()}, f)
        log(f'✅ 이미지 캐시 완료')
        return cdn_url

    log('⚠️ 업로드 실패, 텍스트 문의처 사용')
    return None


def _upload_via_playwright(image_path):
    """
    Playwright로 se-authorization 토큰 캡처 → REST API 이미지 업로드
    """
    try:
        from playwright.sync_api import sync_playwright
    except ImportError:
        return None

    auth_token = [None]
    cdn_url = [None]

    with sync_playwright() as p:
        browser = p.chromium.launch(headless=True)
        state = load_session_storage()
        if not state:
            browser.close()
            return None

        ctx = browser.new_context(storage_state=state, viewport={'width':1920,'height':1080},
                                   locale='ko-KR', timezone_id='Asia/Seoul')
        page = ctx.new_page()

        # service_config 요청에서 se-authorization 헤더 캡처
        resp_texts = []

        def on_req(req):
            if 'service_config' in req.url:
                h = req.headers.get('se-authorization', '')
                if h:
                    auth_token[0] = h

        # 응답 body를 핸들러 내에서 바로 읽기 (browser close 문제 해결)
        def capture_upload_resp(resp):
            if 'upphoto.naver.com' in resp.url and resp.status == 200:
                try:
                    text = resp.text()
                    resp_texts.append(text)
                    m = re.search(r'<url>(.*?)</url>', text)
                    if m:
                        cdn_url[0] = f'https://cafeptthumb-phinf.pstatic.net{m.group(1).strip()}'
                except:
                    pass

        page.on('request', on_req)
        page.on('response', capture_upload_resp)

        page.goto(f'https://cafe.naver.com/ca-fe/cafes/{TARGET_CLUB_ID}/articles/write?boardType=L',
                  wait_until='networkidle', timeout=20000)
        time.sleep(3)

        if 'nidlogin' in page.url.lower():
            browser.close()
            return None

        # se-authorization 토큰 획득
        token = auth_token[0]
        if not token:
            # fallback: fetch intercept로 재시도
            token = page.evaluate('''() => new Promise((resolve) => {
                const orig = window.fetch;
                window.fetch = function(url, opts) {
                    if (typeof url === 'string' && url.includes('service_config')) {
                        const auth = (opts && opts.headers && opts.headers['se-authorization']) || 'NOT_FOUND';
                        window.fetch = orig;
                        resolve(auth);
                    }
                    return orig.apply(this, arguments);
                };
                setTimeout(() => { window.fetch = orig; resolve('TIMEOUT'); }, 5000);
            })''')

        if not token or token == 'TIMEOUT' or token == 'NOT_FOUND':
            log('❌ se-authorization 토큰 획득 실패')
            browser.close()
            return None

        log(f'🔑 se-authorization 토큰 획득 ({len(token)} chars)')

        # SE3 에디터에서 직접 이미지 업로드 (file input → SE3 upload pipeline)
        page.evaluate("document.querySelector('[contenteditable=true]')?.focus()")
        page.keyboard.type(' ')
        time.sleep(1)

        page.evaluate('''() => {
            for (const b of document.querySelectorAll("button"))
                if (b.textContent.includes("사진") && b.textContent.includes("추가")) { b.click(); break; }
        }''')
        time.sleep(2)

        fi = page.query_selector('input[type="file"]')
        if fi:
            fi.set_input_files(image_path)
            log('⏳ SE3 업로드 대기 (최대 60초)...')

            for i in range(20):
                time.sleep(3)
                if cdn_url[0]:
                    log(f'✅ CDN URL 획득!')
                    break
                if i == 6:
                    page.keyboard.press('Tab')
                    page.keyboard.press('Enter')
                if i == 12:
                    page.evaluate("document.querySelector('[contenteditable=true]')?.click()")
        else:
            log('❌ file input 없음')

        if not cdn_url[0]:
            log('❌ 업로드 타임아웃')
            # REST API fallback 시도
            cdn_url[0] = _upload_via_rest_api(token, image_path)

        browser.close()
        return cdn_url[0]


def _upload_via_rest_api(token, image_path):
    """REST API로 이미지 업로드 (se-authorization 토큰 필요)"""
    import requests as req, base64, re, time

    state = load_session_storage()
    if not state:
        return None

    s = req.Session()
    for c in state.get('cookies', []):
        s.cookies.set(c['name'], c['value'],
                      domain=c.get('domain', '.naver.com'),
                      path=c.get('path', '/'))

    headers = {
        'User-Agent': 'Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36',
        'se-authorization': token,
        'Origin': 'https://cafe.naver.com',
        'Referer': f'https://cafe.naver.com/ca-fe/cafes/{TARGET_CLUB_ID}/articles/write',
        'Accept': 'application/json',
    }

    resp = s.get(
        'https://platform.editor.naver.com/api/cafepc001/v1/photo-uploader/session-key',
        headers=headers, timeout=15
    )
    if resp.status_code != 200:
        return None

    sk_data = resp.json()
    if not sk_data.get('isSuccess'):
        return None

    session_key = sk_data['sessionKey']
    try:
        pad = 4 - (len(session_key) % 4)
        sk_padded = session_key + ('=' * pad) if pad != 4 else session_key
        decoded = base64.b64decode(sk_padded).decode('utf-8')
        fields = decoded.split('\x07')
        userid = fields[3] if len(fields) > 3 else 'sewoong333'
    except:
        userid = 'sewoong333'

    upload_url = f'https://cafe.upphoto.naver.com/{session_key}/simpleUpload/0'
    upload_url += f'?userId={userid}'
    upload_url += '&extractExif=true&extractAnimatedCnt=false&extractAnimatedInfo=true'
    upload_url += '&autorotate=true&extractDominantColor=false&type='
    upload_url += '&customQuery=&denyAnimatedImage=false&skipXcamFiltering=false'

    with open(image_path, 'rb') as f:
        files = {'file': (os.path.basename(image_path), f, 'image/jpeg')}
        resp = s.post(upload_url, files=files, headers={
            'User-Agent': 'Mozilla/5.0',
            'Origin': 'https://cafe.naver.com',
            'Referer': f'https://cafe.naver.com/ca-fe/cafes/{TARGET_CLUB_ID}/articles/write',
        }, timeout=30)

    if resp.status_code != 200:
        return None

    m = re.search(r'<url>(.*?)</url>', resp.text)
    if m:
        return f'https://cafeptthumb-phinf.pstatic.net{m.group(1).strip()}'
    return None


def make_se3_content(html_text, include_contact_card=False):
    """
    HTML 본문 → SmartEditor 3 문서 포맷
    - 모든 텍스트를 하나의 paragraph로 통합
    - <p>, <br> 태그는 \n 줄바꿈으로 변환
    - include_contact_card=True 시 하단에 PURE GOLD x ECHO 연락처 추가
    """
    uid = uuid.uuid4().hex[:20].upper()

    # HTML 처리: p와 br 태그를 \n\n으로 변환
    text = html_text
    # 전화번호 제거 (PURE GOLD x ECHO 외 모든 전화번호)
    text = re.sub(r'01[016789]-\d{3,4}-\d{4}', '', text)
    text = re.sub(r'0\d{1,2}-\d{3,4}-\d{4}', '', text)
    text = re.sub(r'\d{3}-\d{3,4}-\d{4}', '', text)
    text = re.sub(r'<p[^>]*>', '', text)
    text = re.sub(r'</p>', '\n', text)
    text = re.sub(r'<br\s*/?>', '\n', text)
    text = re.sub(r'<img[^>]*alt="([^"]*)"[^>]*>', r'\1', text)
    text = re.sub(r'<img[^>]*>', '[이미지]', text)
    text = re.sub(r'<a\s+[^>]*href="([^"]*)"[^>]*>(.*?)</a>', r'\2 (\1)', text)
    text = re.sub(r'<[^>]+>', '', text)
    text = re.sub(r'<img[^>]*alt="([^"]*)"[^>]*>', r'\1', text)
    text = re.sub(r'<img[^>]*>', '[이미지]', text)
    text = re.sub(r'<a\s+[^>]*href="([^"]*)"[^>]*>(.*?)</a>', r'\2 (\1)', text)
    text = re.sub(r'<[^>]+>', '', text)
    # 연속 줄바꿈 정리 (2개 이상의 \n은 2개로)
    text = re.sub(r'\n{3,}', '\n\n', text)
    text = text.strip()

    # 연락처 카드 추가
    if include_contact_card:
        text += '\n\n📞 문의처\nPURE GOLD x ECHO\n010-8622-0611\n[ OFFICIAL CONTACT CHANNEL - TEXT ONLY ]'

    comp_id = 'SE-' + uuid.uuid4().hex[:20].upper()
    para_id = 'SE-' + uuid.uuid4().hex[:20].upper()
    text_id = 'SE-' + uuid.uuid4().hex[:20].upper()

    components = [{
        "id": comp_id, "layout": "default",
        "value": [{
            "id": para_id,
            "nodes": [{"id": text_id, "value": text or ' ', "@ctype": "textNode"}],
            "@ctype": "paragraph"
        }], "@ctype": "text"
    }]

    return json.dumps({
        "document": {
            "version": "2.9.0", "theme": "default", "language": "ko-KR",
            "id": "SE-" + uid, "components": components,
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


# ── 세션 저장/복원 ────────────────────────────────────

def save_session_storage(context):
    state = context.storage_state()
    with open(STORAGE_FILE, 'w') as f:
        json.dump(state, f, ensure_ascii=False)
    meta = {'saved_at': time.time(), 'date': datetime.now().isoformat(),
            'cookie_count': len(state.get('cookies', []))}
    with open(SESSION_META, 'w') as f:
        json.dump(meta, f, ensure_ascii=False)
    log(f'💾 Storage state 저장 완료 (쿠키 {meta["cookie_count"]}개)')


def load_session_storage():
    if not os.path.exists(STORAGE_FILE):
        return None
    with open(STORAGE_FILE) as f:
        return json.load(f)


def get_session_age():
    # 1차: meta.json (정확한 저장 시각)
    if os.path.exists(SESSION_META):
        with open(SESSION_META) as f:
            meta = json.load(f)
        saved_at = meta.get('saved_at')
        if saved_at:
            return time.time() - saved_at
    # 2차: storage file mtime (fallback)
    if os.path.exists(STORAGE_FILE):
        return time.time() - os.path.getmtime(STORAGE_FILE)
    return None


def is_session_expired(max_age_hours=20):
    age = get_session_age()
    return age is None or age > max_age_hours * 3600


# ── 세션 자동 갱신 ────────────────────────────────────

def refresh_session():
    """NID_AUT(자동로그인)으로 NID_SES를 자동 갱신. QR 불필요.
    nid.naver.com 방문 → NID_AUT 있으면 Naver가 자동으로 새 NID_SES 발급.
    Returns: True if refresh succeeded, False if NID_AUT도 만료됨.
    """
    state = load_session_storage()
    if not state:
        log('❌ 저장된 세션 없음.')
        return False

    has_aut = any(c['name'] == 'NID_AUT' for c in state.get('cookies', []))
    if not has_aut:
        log('⚠️ NID_AUT 없음. QR 로그인 필요.')
        return False

    try:
        from playwright.sync_api import sync_playwright
        with sync_playwright() as p:
            browser = p.chromium.launch(headless=True)
            context = browser.new_context(
                storage_state=STORAGE_FILE,
                viewport={'width': 1280, 'height': 900},
                locale='ko-KR', timezone_id='Asia/Seoul'
            )
            page = context.new_page()

            # 네이버 메인 방문 → NID_AUT 있으면 자동으로 NID_SES 갱신됨
            log('🔄 NID_AUT → NID_SES 갱신 시도...')
            page.goto('https://www.naver.com/',
                      wait_until='networkidle', timeout=30000)
            page.wait_for_timeout(3000)

            # 네이버 메인에서 로그인 상태 확인 (gnb_login_button 유무)
            login_btn = page.query_selector('#gnb_login_button')
            refresh_ok = login_btn is None

            if refresh_ok:
                # 새 storage_state 저장 (갱신된 NID_SES 포함)
                new_state = context.storage_state()
                with open(STORAGE_FILE, 'w') as f:
                    json.dump(new_state, f, ensure_ascii=False)
                meta = {'saved_at': time.time(), 'date': datetime.now().isoformat(),
                        'cookie_count': len(new_state.get('cookies', [])),
                        'auto_refreshed': True}
                with open(SESSION_META, 'w') as f:
                    json.dump(meta, f, ensure_ascii=False)
                log('✅ 세션 자동 갱신 완료 (NID_AUT → 새 NID_SES)')
            else:
                log('❌ NID_AUT 만료됨. QR 로그인 필요.')

            browser.close()
            return refresh_ok

    except Exception as e:
        log(f'⚠️ 세션 갱신 실패: {e}')
        return False


# ── QR 로그인 ──────────────────────────────────────────

def qr_login():
    log('🔄 네이버 QR 로그인 시작...')
    try:
        from playwright.sync_api import sync_playwright
    except ImportError:
        log('❌ playwright 필요')
        sys.exit(1)

    with sync_playwright() as p:
        browser = p.chromium.launch(headless=True)
        context = browser.new_context(viewport={'width':1280,'height':900},
                                       locale='ko-KR', timezone_id='Asia/Seoul')
        page = context.new_page()
        page.goto('https://nid.naver.com/nidlogin.login', wait_until='networkidle')
        page.wait_for_timeout(2000)
        qr_btn = page.query_selector('a:has-text("QR")')
        if qr_btn:
            qr_btn.click()
            page.wait_for_timeout(2000)
        qr_path = os.path.join(BASE_DIR, 'naver_qr_login.png')
        page.screenshot(path=qr_path, full_page=True)
        log(f'📸 QR 코드 저장: {qr_path}')
        print(f'MEDIA:{qr_path}', flush=True)
        log('⏳ QR 로그인 대기 중... (최대 3분)')
        for i in range(60):
            time.sleep(3)
            cookies = context.cookies()
            if any(c['name'] in ('NID_SES','NID_AUT') for c in cookies):
                break
            if 'nidlogin' not in page.url.lower():
                break
        else:
            log('❌ 시간 초과')
            browser.close()
            sys.exit(1)
        log('✅ QR 로그인 성공!')
        save_session_storage(context)
        browser.close()
        log(f'✅ 로그인 완료 → {STORAGE_FILE}')


# ── 세션 유효성 검사 ──────────────────────────────────

def check_session():
    state = load_session_storage()
    if not state:
        log('❌ 저장된 세션 없음. --login 으로 로그인 먼저 해주세요.')
        return False

    try:
        # ★ Playwright로 실 카페 글쓰기 페이지 접속 확인 (로그인 필수)
        from playwright.sync_api import sync_playwright
        with sync_playwright() as p:
            browser = p.chromium.launch(headless=True)
            context = browser.new_context(
                storage_state=STORAGE_FILE,
                viewport={'width': 1280, 'height': 900},
                locale='ko-KR', timezone_id='Asia/Seoul'
            )
            page = context.new_page()
            page.goto(f'https://cafe.naver.com/ca-fe/cafes/{TARGET_CLUB_ID}/articles/write',
                      wait_until='networkidle', timeout=15000)
            time.sleep(2)
            redirected_to_login = 'nidlogin' in page.url.lower()
            browser.close()

        age = get_session_age()
        age_str = f'{age/3600:.1f}시간' if age else '알 수 없음'

        if redirected_to_login:
            log(f'❌ 세션 만료됨 (경과: {age_str})')
            return False
        else:
            log(f'✅ 세션 정상 (경과: {age_str})')
            return True

    except Exception as e:
        log(f'⚠️ Playwright 확인 실패, fallback 검증 시도: {e}')
        # Fallback: requests + Cafe API 직접 호출
        try:
            import requests as req
            s = req.Session()
            for c in state.get('cookies', []):
                s.cookies.set(c['name'], c['value'],
                              domain=c.get('domain', '.naver.com'),
                              path=c.get('path', '/'))
            headers = {
                'User-Agent': 'Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36',
                'Accept': 'application/json',
                'Referer': f'https://cafe.naver.com/ca-fe/cafes/{TARGET_CLUB_ID}',
            }
            # Cafe API로 실제 인증 확인
            resp = s.get(
                f'https://apis.cafe.naver.com/cafe-web/cafeinfo/v1.0/cafes/{TARGET_CLUB_ID}',
                headers=headers, timeout=10
            )
            data = resp.json()
            is_valid = data.get('message') != 'unauthorized' and 'cafe' in data

            age = get_session_age()
            age_str = f'{age/3600:.1f}시간' if age else '알 수 없음'
            if is_valid:
                log(f'✅ 세션 정상 (경과: {age_str})')
            else:
                log(f'❌ 세션 만료됨 (경과: {age_str})')
            return is_valid
        except Exception as e2:
            log(f'❌ 세션 확인 완전 실패: {e2}')
            return False


# ── REST API 발행 ──────────────────────────────────────

def post_article(title, body_html, board_key='used'):
    """게시글 발행 (requests)"""
    if board_key not in BOARDS:
        return {'success': False, 'error': f'알 수 없는 게시판: {board_key}'}

    board = BOARDS[board_key]
    state = load_session_storage()
    if not state:
        return {'success': False, 'error': '저장된 세션 없음'}

    import requests as req
    session = req.Session()
    for c in state.get('cookies', []):
        session.cookies.set(c['name'], c['value'],
                            domain=c.get('domain', '.naver.com'),
                            path=c.get('path', '/'))

    content_json = make_se3_content(body_html, include_contact_card=(board_key in ('used', 'trade')))
    payload = {
        "article": {
            "cafeId": TARGET_CLUB_ID,
            "contentJson": content_json,
            "from": "pc",
            "menuId": board['id'],
            "subject": title[:80],
            "tagList": [],
            "editorVersion": 4,
            "parentId": 0,
            "open": False, "naverOpen": True, "externalOpen": True,
            "enableComment": True, "enableScrap": True, "enableCopy": False,
            "useAutoSource": True, "cclTypes": [], "useCcl": False
        }
    }

    url = API_BASE.format(TARGET_CLUB_ID, board['id'])
    headers = {
        'User-Agent': 'Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36',
        'Accept': 'application/json, text/plain, */*',
        'Content-Type': 'application/json;charset=UTF-8',
        'Origin': 'https://cafe.naver.com',
        'Referer': f'https://cafe.naver.com/ca-fe/cafes/{TARGET_CLUB_ID}/articles/write',
        'x-cafe-product': 'pc',
    }

    log(f'📤 [{board["name"]}] 발행 중: {title[:40]}...')

    try:
        resp = session.post(url, json=payload, headers=headers, timeout=30)
        if resp.status_code == 200:
            data = resp.json()
            article_id = data.get('result', {}).get('articleId', '?')
            log(f'✅ 성공! articleId={article_id}')
            return {'success': True, 'article_id': article_id, 'board': board['name']}
        else:
            error = resp.text[:300]
            log(f'❌ 실패 ({resp.status_code}): {error[:100]}')
            return {'success': False, 'error': error}
    except Exception as e:
        log(f'❌ 오류: {e}')
        return {'success': False, 'error': str(e)}


# ── 게시글 생성 ────────────────────────────────────────

def generate_daily_articles():
    """
    일일 게시글 생성 (3-4개)
    - 메인: 중고악기거래 게시판 (used) — 2-3개
    - 보조: 꿀팁 게시판 (tip) — 1개
    """
    today = date.today()
    weekday_list = ['월', '화', '수', '목', '금', '토', '일']
    weekday = weekday_list[today.weekday()]
    
    # 랜덤 악기 선택
    instr = random.choice(INSTRUMENTS)
    brand = random.choice(BRANDS)
    brands_short = list(set(b.split('(')[0] for b in BRANDS))
    brand_s = random.choice(brands_short)
    
    # 악기 거래 게시글 (used 게시판) — 2-3개
    articles = []
    
    # ── 1. 악기 판매 정보글 ──
    a1_title = f"🎵 [{today.month}/{today.day}] {brand} {instr[0]} 판매 — 상태 좋습니다 ✨"
    a1_body = (
        f"<p>안녕하세요! 에코뮤직 중고악기백화점입니다 🙌</p>"
        f"<p><br></p>"
        f"<p>오늘 소개해드릴 악기는 <b>{brand} {instr[0]}</b>입니다.</p>"
        f"<p><br></p>"
        f"<p>📌 <b>상품 정보</b></p>"
        f"<p>• 브랜드: {brand}</p>"
        f"<p>• 모델: {instr[0]} (중고)</p>"
        f"<p>• 상태: 전체적으로 깨끗하며 사용감 적음</p>"
        f"<p>• 구성품: 본체 + 케이스 + 액세서리</p>"
        f"<p><br></p>"
        f"<p>📌 <b>거래 정보</b></p>"
        f"<p>• 가격: 협의 가능 (문의주세요)</p>"
        f"<p>• 거래 방식: 직거래 / 택배</p>"
        f"<p>• 위치: 경기도 (에코뮤직 매장)</p>"
        f"<p>• 연락: 쪽지 또는 댓글 남겨주세요</p>"
        f"<p><br></p>"
        f"<p>📌 <b>상세 설명</b></p>"
        f"<p>작년에 구매하여 연습용으로 사용하던 악기입니다.</p>"
        f"<p>업그레이드로 인해 내놓게 되었네요ㅎㅎ</p>"
        f"<p>음색도 좋고 상태도 나쁘지 않으니 관심 있으신 분은 연락주세요!</p>"
        f"<p><br></p>"
        f"<p>📍 매장 방문도 가능합니다. 직접 보고 구매하세요!</p>"
        f"<p><br></p>"
        f"<p>#에코뮤직 #중고악기 #{instr[0]} #{brand.replace(' ','')} #악기판매 #중고거래 #경기도악기 #{' #'.join(brands_short[:3])}</p>"
    )
    articles.append({'title': a1_title, 'body': a1_body, 'board': 'used'})
    
    # ── 2. 중고악기 구매/교환 글 ──
    a2_title = f"🔍 [구매] {instr[0]} 구합니다 — 예산 협의 가능 💬"
    a2_body = (
        f"<p>안녕하세요! {instr[0]} 구매 원합니다 🙋</p>"
        f"<p><br></p>"
        f"<p>🎯 <b>찾는 악기</b></p>"
        f"<p>• 종류: {instr[0]}</p>"
        f"<p>• 예산: 협의 가능</p>"
        f"<p>• 선호 브랜드: {brand_s} 외 전체</p>"
        f"<p>• 상태: 연습용 가능 / 연주용 선호</p>"
        f"<p><br></p>"
        f"<p>💡 <b>조건</b></p>"
        f"<p>• 합리적인 가격에 거래해주실 분</p>"
        f"<p>• 직거래 가능하면 더 좋습니다</p>"
        f"<p>• 사진 미리 보내주시면 감사하겠습니다</p>"
        f"<p><br></p>"
        f"<p>쪽지나 댓글 주시면 빠르게 연락드릴게요! 😊</p>"
        f"<p><br></p>"
        f"<p>#중고악기 #{instr[0]} #악기구매 #에코뮤직 #중고악기백화점 #직거래 #악기거래</p>"
    )
    articles.append({'title': a2_title, 'body': a2_body, 'board': 'used'})
    
    # ── 3. 꿀팁/정보 (tip 게시판) ──
    tips = [
        {
            'title': f"💡 중고악기 구매 시 꼭 확인해야 할 5가지 — {today.month}월 업데이트",
            'body': (
                f"<p>🎯 중고악기, 처음 사시는 분들 많죠? 오늘은 꿀팁 대방출합니다!</p>"
                f"<p><br></p>"
                f"<p>✅ <b>1. 상태 확인은 직접!</b></p>"
                f"<p>사진만 보고 판단하지 마세요. 특히 현의 상태, 프렛 마모, 음정 안정성은 직접 봐야 합니다.</p>"
                f"<p><br></p>"
                f"<p>✅ <b>2. 일련번호 체크</b></p>"
                f"<p>브랜드 정품 확인은 필수! 일련번호로 제조년도와 정품 여부를 확인하세요.</p>"
                f"<p><br></p>"
                f"<p>✅ <b>3. 수리 이력 확인</b></p>"
                f"<p>\"수리한 적 없음\" vs \"전문가 수리 완료\"는 완전히 다릅니다. 꼭 물어보세요.</p>"
                f"<p><br></p>"
                f"<p>✅ <b>4. 계절별 관리법</b></p>"
                f"<p>{today.month}월에는 습도 관리가 중요! 케이스 안에 습도조절제 필수입니다.</p>"
                f"<p><br></p>"
                f"<p>✅ <b>5. 가격 비교</b></p>"
                f"<p>같은 모델도 상태에 따라 천차만별. 에코뮤직에서 직접 비교해보세요!</p>"
                f"<p><br></p>"
                f"<p>📌 이 팁들이 도움되셨다면 공감/댓글 부탁드려요~ 😊</p>"
                f"<p><br></p>"
                f"<p>#중고악기 #악기구매팁 #악기관리 #에코뮤직 #중고악기백화점 #{instr[0]} #악기정보 #음악꿀팁</p>"
            ),
            'board': 'tip'
        },
        {
            'title': f"🎻 {instr[0]} 관리법 — 초보자도 쉽게 따라하는 가이드",
            'body': (
                f"<p>안녕하세요! 에코뮤직입니다 🎶</p>"
                f"<p><br></p>"
                f"<p>오늘은 <b>{instr[0]}</b> 관리 꿀팁을 알려드릴게요.</p>"
                f"<p><br></p>"
                f"<p>🌟 <b>기본 관리 수칙</b></p>"
                f"<p>1️⃣ 연주 후 항상 부드러운 천으로 닦아주세요 (땀과 먼지 제거)</p>"
                f"<p>2️⃣ 사용 후에는 반드시 케이스에 보관하세요</p>"
                f"<p>3️⃣ 직사광선과 온도 변화가 심한 곳은 피해주세요</p>"
                f"<p>4️⃣ 6개월에 한 번 정도는 전문가 점검을 받으세요</p>"
                f"<p><br></p>"
                f"<p>💧 <b>습도 관리 (필수!)</b></p>"
                f"<p>악기는 적정 습도(40-60%) 유지가 가장 중요합니다.</p>"
                f"<p>특히 여름 장마철과 겨울 건조한 시기에 주의하세요!</p>"
                f"<p><br></p>"
                f"<p>✏️ <b>주의할 점</b></p>"
                f"<p>• 줄(현)은 3-6개월 주기로 교체 권장</p>"
                f"<p>• 튜닝은 연주 전후로 천천히</p>"
                f"<p>• 균열이나 들뜸 발견 시 즉시 수리</p>"
                f"<p><br></p>"
                f"<p>매장에 방문하시면 더 자세한 상담도 가능합니다! 😊</p>"
                f"<p><br></p>"
                f"<p>#{instr[0]} #악기관리 #악기관리법 #에코뮤직 #중고악기백화점 #음악꿀팁 #악기튜닝 #악기보관</p>"
            ),
            'board': 'tip'
        }
    ]
    
    # 랜덤으로 꿀팁 1개 선택
    articles.append(random.choice(tips))
    
    # ── 4. 추가 거래글 (3-4개 맞추기) ──
    if random.random() < 0.7:  # 70% 확률로 4번째 글 추가
        instr2 = random.choice(INSTRUMENTS)
        while instr2 == instr:
            instr2 = random.choice(INSTRUMENTS)
        a4_title = f"⚡ {random.choice(['급처','할인','특가'])}! {instr2[0]} 상태 미사용급 판매합니다"
        a4_body = (
            f"<p>안녕하세요! 🙋</p>"
            f"<p><br></p>"
            f"<p><b>{instr2[0]}</b> 판매합니다!</p>"
            f"<p>거의 사용하지 않아 상태 아주 좋아요.</p>"
            f"<p><br></p>"
            f"<p>📌 <b>상세 정보</b></p>"
            f"<p>• 브랜드: {random.choice(BRANDS)}</p>"
            f"<p>• 상태: 사용감 거의 없음 (미사용급)</p>"
            f"<p>• 구매시기: {random.randint(2022, 2024)}년</p>"
            f"<p>• 구성: 본체 + 기본 구성품</p>"
            f"<p><br></p>"
            f"<p>💰 가격: 협의 가능 (쪽지 주세요)</p>"
            f"<p>📍 직거래: 경기도 (에코뮤직)</p>"
            f"<p>📦 택배: 선불/착불 협의</p>"
            f"<p><br></p>"
            f"<p>관심 있으신 분은 편하게 연락주세요! 😊</p>"
            f"<p><br></p>"
            f"<p>#중고악기 #{instr2[0]} #악기판매 #에코뮤직 #중고악기백화점 #직거래 #할인판매 #경기도악기</p>"
        )
        articles.append({'title': a4_title, 'body': a4_body, 'board': 'used'})
    
    return articles


# ── CLI ────────────────────────────────────────────────

def main():
    parser = argparse.ArgumentParser(description='Naver Session Manager v2.2')
    parser.add_argument('--login', action='store_true', help='QR 로그인 (60일 주기 1회)')
    parser.add_argument('--check', action='store_true', help='세션 상태 확인 + 필요시 자동 갱신')
    parser.add_argument('--refresh', action='store_true', help='NID_AUT로 NID_SES 자동 갱신 (QR 불필요)')
    parser.add_argument('--keepalive', action='store_true', help='세션 유지용 keepalive (12h 크론용)')
    parser.add_argument('--post', action='store_true', help='테스트 게시글 1개 발행')
    parser.add_argument('--post-daily', action='store_true', help='일일 게시글 발행 (3-4개)')
    parser.add_argument('--title', help='게시글 제목')
    parser.add_argument('--body', help='게시글 본문')
    parser.add_argument('--board', default='used', choices=list(BOARDS.keys()), help='게시판')
    args = parser.parse_args()

    if args.login:
        qr_login()
        return

    if args.check:
        # 1. 먼저 자동 갱신 시도 (NID_AUT 있으면 NID_SES 갱신됨)
        refresh_session()
        # 2. 갱신 후 확인
        valid = check_session()
        if valid:
            age = get_session_age()
            age_h = age / 3600 if age else 0
            print(f'\n✅ 세션 정상')
            print(f'   저장 위치: {STORAGE_FILE}')
            print(f'   경과: {age_h:.1f}시간')
            print(f'   만료 예정: 약 {max(0, 20 - age_h):.1f}시간 후')
        else:
            print(f'\n❌ 세션 만료')
            print(f'   → python naver_session_manager.py --login')
        return

    if args.refresh:
        ok = refresh_session()
        print(f'\n{"✅ 자동 갱신 성공" if ok else "❌ 자동 갱신 실패 (QR 로그인 필요)"}')
        return

    if args.keepalive:
        # 12시간마다 실행하는 keepalive 크론용
        ok = refresh_session()
        if ok:
            age = get_session_age()
            age_h = age / 3600 if age else 0
            print(f'\n✅ Keepalive 성공 (세션 {age_h:.1f}시간 경과)')
        else:
            print(f'\n❌ Keepalive 실패 — NID_AUT 만료. QR 로그인 필요.')
        return

    if args.post:
        if not args.title or not args.body:
            log('❌ --title 과 --body 필요')
            return
        refresh_session()  # 자동 갱신 먼저 시도
        valid = check_session()
        if not valid:
            log('⚠️ 세션 만료')
            return
        result = post_article(args.title, args.body, args.board)
        if result['success']:
            print(f'\n✅ 발행 완료! articleId={result["article_id"]}')
        else:
            print(f'\n❌ 발행 실패: {result.get("error","")}')
        return

    if args.post_daily:
        refresh_session()  # 자동 갱신 먼저 시도
        valid = check_session()
        if not valid:
            log('❌ 세션 만료. --login 필요')
            return

        articles = generate_daily_articles()
        log(f'📋 오늘 {len(articles)}개 게시글 발행 예정')

        results = []
        for i, art in enumerate(articles):
            log(f'📄 [{i+1}/{len(articles)}] [{art["board"]}] {art["title"][:40]}...')
            result = post_article(art['title'], art['body'], art['board'])
            results.append(result)
            if result['success']:
                log(f'   ✅ 성공 (ID: {result["article_id"]})')
            else:
                log(f'   ❌ 실패: {result.get("error","")[:80]}')
            if i < len(articles) - 1:
                time.sleep(15)  # 발행 간격 (네이버 연속 등록 제한 회피)

        success = sum(1 for r in results if r['success'])
        print(f'\n{"="*50}')
        print(f'📊 일일 발행 결과')
        print(f'{"="*50}')
        print(f'  성공: {success}/{len(results)}')
        for art, result in zip(articles, results):
            icon = '✅' if result['success'] else '❌'
            print(f'  {icon} [{art["board"]}] {art["title"][:50]}')
            if result.get('article_id'):
                print(f'     → articleId: {result["article_id"]}')
            if result.get('error'):
                print(f'     → 오류: {result["error"][:80]}')
        print(f'\n📅 다음 발행: 내일 오전 10시 자동 실행')
        return

    parser.print_help()


if __name__ == '__main__':
    main()
