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
    """NID_SES activity 기반 세션 갱신. QR 불필요.
    네이버 메인 방문 → 기존 NID_SES로 로그인 상태 유지 + storage 갱신
    Returns: True if refresh succeeded, False if NID_SES도 만료됨.
    """
    state = load_session_storage()
    if not state:
        log('❌ 저장된 세션 없음.')
        return False

    has_ses = any(c['name'] == 'NID_SES' for c in state.get('cookies', []))
    if not has_ses:
        log('⚠️ NID_SES 없음. QR 로그인 필요.')
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

            # 네이버 메인 방문 → NID_SES가 유효하면 로그인 상태 유지
            log('🔄 NID_SES 상태 확인 + activity 갱신...')
            page.goto('https://www.naver.com/',
                      wait_until='networkidle', timeout=30000)
            page.wait_for_timeout(3000)

            # 로그인 상태 확인 (gnb_login_button 유무)
            login_btn = page.query_selector('#gnb_login_button')
            refresh_ok = login_btn is None

            if refresh_ok:
                # 새 storage_state 저장 (갱신된 NID_SES 포함)
                new_state = context.storage_state()
                new_cookies = new_state.get('cookies', [])
                new_ses = any(c['name'] == 'NID_SES' for c in new_cookies)

                if new_ses:
                    with open(STORAGE_FILE, 'w') as f:
                        json.dump(new_state, f, ensure_ascii=False)
                    meta = {'saved_at': time.time(), 'date': datetime.now().isoformat(),
                            'cookie_count': len(new_cookies),
                            'auto_refreshed': True}
                    with open(SESSION_META, 'w') as f:
                        json.dump(meta, f, ensure_ascii=False)
                    log(f'✅ 세션 갱신 완료 (NID_SES 유지, 쿠키 {len(new_cookies)}개)')
                else:
                    # ★ 중요: NID_SES가 없으면 기존 storage 보존 (덮어쓰지 않음)
                    log('❌ 갱신 후 NID_SES 없음 — 기존 storage 보존')
                    refresh_ok = False
            else:
                log('❌ 로그인 상태 아님. QR 로그인 필요.')

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
        page.goto('https://nid.naver.com/nidlogin.login', wait_until='domcontentloaded', timeout=20000)
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
        # ★ 개선: 로그인 후 네이버 메인 방문 → NID_SES 확정 후 저장
        page.goto('https://www.naver.com/', wait_until='networkidle', timeout=30000)
        page.wait_for_timeout(3000)
        save_session_storage(context)
        # ★ 저장 후 NID_SES 존재 확인
        saved = load_session_storage()
        saved_ses = any(c['name'] == 'NID_SES' for c in saved.get('cookies', [])) if saved else False
        if not saved_ses:
            log('⚠️ NID_SES 미확인 — 재시도 (추가 대기)')
            page.wait_for_timeout(5000)
            save_session_storage(context)
            saved = load_session_storage()
            saved_ses = any(c['name'] == 'NID_SES' for c in saved.get('cookies', [])) if saved else False
        browser.close()
        if saved_ses:
            log(f'✅ 로그인 완료 → NID_SES 저장 확인됨: {STORAGE_FILE}')
        else:
            log(f'⚠️ 로그인됐지만 NID_SES 미저장 — storage 파일에 NID_SES 없음')
            sys.exit(1)


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

DB_PATH = os.path.join(BASE_DIR, 'cafe_articles.db')


def _remove_emoji(text):
    """이모지 및 특수문자 제거 (Korean/CJK 문자는 보존)"""
    # Emoji 블록: Supplementary Symbols, Dingbats 등 (Hangul/CJK와 겹치지 않는 범위)
    emoji_ranges = (
        "\U0001F300-\U0001F6FF"  # Misc Symbols + Emoticons + Transport
        "\U0001F900-\U0001F9FF"  # Supplemental Symbols
        "\U0001FA00-\U0001FA6F"  # Chess Symbols
        "\U0001FA70-\U0001FAFF"  # Symbols Extended-A
        "\U00002702-\U000027B0"  # Dingbats
        "\U0000FE00-\U0000FE0F"  # Variation Selectors
    )
    text = re.sub(f'[{emoji_ranges}]', '', text, flags=re.UNICODE)
    # Zero Width Joiner
    text = re.sub('\U0000200D', '', text)
    # 흔히 쓰는 특수 이모지 문자들 (non-raw string으로 Unicode escape 처리)
    text = re.sub('[\u2600-\u27BF\u2B50\u2934\u2935\u25AA\u25AB\u25B6\u25C0\u25FB-\u25FE\u3030\u303D\u3297\u3299]', '', text)
    # 개별 특수문자 제거
    text = re.sub(r'[⭐✅♻️🔄⏳🛒]', '', text)
    text = re.sub(r'\s+', ' ', text).strip()
    return text


def _optimize_title(title, max_chars=15):
    """
    제목 15자 이내 최적화
    1. 이모지 제거
    2. "악기명 + 상태/가격" 형식
    3. 15자 초과 시 의미 단위로 절삭
    """
    # 1. 이모지 제거
    title = _remove_emoji(title)

    # 2. 공백 정리
    title = re.sub(r'\s+', ' ', title).strip()

    # 3. 불필요한 접두사/접미사 제거
    title = re.sub(r'^[\[\(]\s*(구매|판매|정보|팁|할인|특가|급처)\s*[\]\)]\s*', '', title)
    title = re.sub(r'\s*[-–—]+\s*', ' ', title)  # dash-like separators
    title = re.sub(r'\s*[\[\(].*?[\]\)]\s*$', '', title)  # trailing brackets
    title = title.strip()

    # 4. 15자 이내로 절삭 (한글 기준)
    if len(title) <= max_chars:
        return title

    # 의미 단위로 자르기: , . / 공백 기준 앞부분 우선
    # 쉼표/공백 기준으로 앞부분만 취하고 15자 이내가 되는 최대 조각 찾기
    candidates = []
    for sep in [',', '。', '/', ' ', '·']:
        if sep in title:
            parts = title.split(sep)
            acc = ''
            for p in parts:
                test = (acc + sep + p).strip().strip(sep).strip()
                if len(test) <= max_chars:
                    acc = test
                else:
                    break
            if acc and len(acc) <= max_chars and len(acc) > len(candidates):
                candidates = acc

    if candidates and len(candidates) <= max_chars:
        return candidates

    # 마지막 수단: 앞에서 15자
    return title[:max_chars].rstrip(' ,.-–—')


def _fetch_db_articles(count=3):
    """
    DB에서 status='collected' 데이터를 가져옴
    Returns: list of dicts with title, body, board, db_id
    """
    try:
        import sqlite3
        conn = sqlite3.connect(DB_PATH)
        conn.row_factory = sqlite3.Row
        cur = conn.cursor()

        cur.execute(
            "SELECT id, title, summary, image_url, image_urls, category "
            "FROM articles WHERE status='collected' "
            "ORDER BY RANDOM() LIMIT ?",
            (count,)
        )
        rows = cur.fetchall()
        conn.close()

        articles = []
        for r in rows:
            d = dict(r)
            # 제목 최적화
            opt_title = _optimize_title(d.get('title', '') or '')

            # 본문 구성
            summary = (d.get('summary') or '').strip()
            body = _build_body_from_db(summary, d.get('image_url', ''), d.get('image_urls', ''))

            # 게시판 분류 (카테고리 기반)
            cat = (d.get('category') or '').strip()
            if cat in ('팁', '정보', 'tip', 'info'):
                board = 'tip'
            else:
                board = 'used'

            articles.append({
                'title': opt_title,
                'body': body,
                'board': board,
                'db_id': d['id'],
            })

        return articles

    except Exception as e:
        log(f'⚠️ DB 조회 오류: {e}')
        return []


def _build_body_from_db(summary, image_url, image_urls_json):
    """
    DB 데이터 기반 본문 HTML 생성
    - summary를 본문에 사용
    - image_urls가 있으면 하단에 이미지 링크 추가
    """
    # 요약 정리: 여러 줄 텍스트를 <p>로 변환
    if summary:
        lines = summary.strip().split('\n')
        body_parts = []
        for line in lines:
            line = line.strip()
            if line:
                body_parts.append(f'<p>{line}</p>')
        body_html = ''.join(body_parts)
    else:
        body_html = '<p>상품 설명이 없습니다. 문의주세요.</p>'

    body_html += '<p><br></p>'

    # 가격 정보 (summary에 가격이 이미 포함되어 있을 수 있음)
    body_html += '<p><b>💰 가격: 문의 주세요</b></p>'
    body_html += '<p><br></p>'

    # 이미지 URL 처리
    image_urls = []
    # image_urls JSON 배열
    if image_urls_json and image_urls_json not in ('[]', '', 'null'):
        try:
            parsed = json.loads(image_urls_json)
            if isinstance(parsed, list):
                image_urls.extend(parsed)
        except (json.JSONDecodeError, TypeError):
            pass

    # 단일 image_url (중복 방지)
    if image_url and image_url not in image_urls:
        image_urls.insert(0, image_url)

    # 중복 제거
    seen = set()
    unique_urls = []
    for u in image_urls:
        u_stripped = u.strip()
        if u_stripped and u_stripped not in seen:
            seen.add(u_stripped)
            unique_urls.append(u_stripped)

    if unique_urls:
        body_html += '<p>📷 <b>상품 이미지</b></p>'
        for idx, url in enumerate(unique_urls[:10], 1):
            body_html += f'<p><a href="{url}">📷 이미지 {idx} 보기</a></p>'
        body_html += '<p><br></p>'

    body_html += '<p>---</p>'
    body_html += '<p>본 상품은 에코뮤직 중고악기백화점 매물입니다.</p>'
    body_html += '<p>문의는 댓글 또는 쪽지로 남겨주세요.</p>'

    return body_html


def _make_dummy_article(article_type='sell', used_instr=None, used_brand=None):
    """
    DB 데이터 부족 시 사용할 개선된 더미 게시글 생성
    - 15자 제목 규칙 적용
    - 이모지 최소화
    - 진정성 있는 본문
    """
    if not used_instr:
        used_instr = random.choice(INSTRUMENTS)
    instr_name = used_instr[0]
    instr_en = used_instr[1]

    if not used_brand:
        brands_short = list(set(b.split('(')[0] for b in BRANDS))
        used_brand = random.choice(brands_short)

    if article_type == 'sell':
        title_raw = f"{used_brand} {instr_name} 판매"
        title = _optimize_title(title_raw)
        body = (
            f"<p>{used_brand} {instr_name} 판매합니다.</p>"
            f"<p><br></p>"
            f"<p><b>상품 정보</b></p>"
            f"<p>• 브랜드: {used_brand}</p>"
            f"<p>• 모델: {instr_name}</p>"
            f"<p>• 상태: 전체적으로 깨끗하며 사용감 적음</p>"
            f"<p>• 구성품: 본체 + 케이스 + 액세서리</p>"
            f"<p><br></p>"
            f"<p><b>거래 정보</b></p>"
            f"<p>• 가격: 협의 가능 (문의주세요)</p>"
            f"<p>• 거래 방식: 직거래 / 택배</p>"
            f"<p>• 위치: 경기도 (에코뮤직 매장)</p>"
            f"<p><br></p>"
            f"<p>관심 있으신 분은 댓글 또는 쪽지 부탁드립니다.</p>"
            f"<p><br></p>"
            f"<p>#에코뮤직 #중고악기 #{instr_name} #{used_brand} #악기판매 #중고거래</p>"
        )
        return {'title': title, 'body': body, 'board': 'used'}

    elif article_type == 'buy':
        title_raw = f"{instr_name} 구합니다"
        title = _optimize_title(title_raw)
        body = (
            f"<p>{instr_name} 구매 원합니다.</p>"
            f"<p><br></p>"
            f"<p><b>찾는 악기</b></p>"
            f"<p>• 종류: {instr_name}</p>"
            f"<p>• 예산: 협의 가능</p>"
            f"<p>• 상태: 연습용 가능 / 연주용 선호</p>"
            f"<p><br></p>"
            f"<p>쪽지나 댓글 주시면 감사하겠습니다.</p>"
            f"<p><br></p>"
            f"<p>#중고악기 #{instr_name} #악기구매 #에코뮤직 #직거래</p>"
        )
        return {'title': title, 'body': body, 'board': 'used'}

    elif article_type == 'bargain':
        price = random.choice(['급처', '특가'])
        title_raw = f"{instr_name} {price}"
        title = _optimize_title(title_raw)
        body = (
            f"<p>{used_brand} {instr_name} {price} 판매합니다.</p>"
            f"<p><br></p>"
            f"<p>상태 좋고 사용감 거의 없습니다.</p>"
            f"<p>가격도 합리적으로 책정했으니 관심 있으신 분 연락주세요.</p>"
            f"<p><br></p>"
            f"<p>• 브랜드: {used_brand}</p>"
            f"<p>• 모델: {instr_name}</p>"
            f"<p><br></p>"
            f"<p>#중고악기 #{instr_name} #{used_brand} #악기판매 #에코뮤직 #할인</p>"
        )
        return {'title': title, 'body': body, 'board': 'used'}

    return None


def _make_dummy_tip():
    """꿀팁 게시글 생성 (tip 게시판용, 15자 제목)"""
    today = date.today()
    tips_pool = [
        {
            'title_raw': '중고악기 구매 체크리스트',
            'body': (
                f'<p>중고악기 구매 시 꼭 확인할 사항을 정리했습니다.</p>'
                f'<p><br></p>'
                f'<p>1. 외관 상태 확인 (균열, 들뜸, 마모)</p>'
                f'<p>2. 음정 안정성 테스트</p>'
                f'<p>3. 일련번호로 정품 확인</p>'
                f'<p>4. 수리 이력 확인</p>'
                f'<p>5. 유사 모델 가격 비교</p>'
                f'<p><br></p>'
                f'<p>에코뮤직 중고악기백화점에서 직접 보고 구매하세요.</p>'
                f'<p><br></p>'
                f'<p>#중고악기 #악기구매팁 #에코뮤직 #중고악기백화점 #악기정보</p>'
            ),
        },
        {
            'title_raw': '악기 보관 및 관리 요령',
            'body': (
                f'<p>악기 오래 쓰는 관리법을 소개합니다.</p>'
                f'<p><br></p>'
                f'<p>• 연주 후 부드러운 천으로 닦기</p>'
                f'<p>• 사용 후 케이스 보관 필수</p>'
                f'<p>• 직사광선 피하고 적정 습도 유지 (40-60%)</p>'
                f'<p>• 현은 3-6개월 주기 교체</p>'
                f'<p>• 6개월에 한 번 전문가 점검</p>'
                f'<p><br></p>'
                f'<p>#악기관리 #악기보관 #에코뮤직 #중고악기백화점 #음악꿀팁</p>'
            ),
        },
        {
            'title_raw': f'{today.month}월 악기 시세 동향',
            'body': (
                f'<p>{today.month}월 중고악기 시세 동향을 알려드립니다.</p>'
                f'<p><br></p>'
                f'<p>최근 에코뮤직 매장 기준 인기 악기와 가격대를 정리했습니다.</p>'
                f'<p>방문 전 미리 전화 주시면 원하시는 악기 준비해드립니다.</p>'
                f'<p><br></p>'
                f'<p>#중고악기 #악기시세 #에코뮤직 #중고악기백화점 #{today.month}월시세</p>'
            ),
        },
        {
            'title_raw': '초보자 악기 선택 가이드',
            'body': (
                f'<p>악기 처음 시작하는 분들을 위한 선택 가이드입니다.</p>'
                f'<p><br></p>'
                f'<p>1. 예산 설정 (중고 10-50만원)</p>'
                f'<p>2. 배우고 싶은 악기 결정</p>'
                f'<p>3. 상태 좋은 중고 악기 추천</p>'
                f'<p>4. 매장 방문해서 직접 연주해보기</p>'
                f'<p>5. AS 가능 여부 확인</p>'
                f'<p><br></p>'
                f'<p>에코뮤직에서는 초보자 맞춤 상담도 가능합니다.</p>'
                f'<p><br></p>'
                f'<p>#초보자악기 #악기선택 #중고악기 #에코뮤직 #악기추천</p>'
            ),
        },
    ]
    choice = random.choice(tips_pool)
    return {
        'title': _optimize_title(choice['title_raw']),
        'body': choice['body'],
        'board': 'tip',
    }


def generate_daily_articles():
    """
    일일 게시글 생성 (3-4개) - DB 기반
    - 메인: 중고악기거래 게시판 (used) — 2-3개 (DB 우선, 부족 시 더미 폴백)
    - 보조: 꿀팁 게시판 (tip) — 1개
    - 제목 15자 이내 최적화
    - 이미지 링크 포함
    """
    articles = []

    # ── Phase 1: DB에서 collected 데이터 가져오기 ──
    db_articles = _fetch_db_articles(count=3)

    # ── Phase 2: DB 기사 사용 후 status 업데이트 ──
    if db_articles:
        db_ids = [a['db_id'] for a in db_articles]
        try:
            import sqlite3
            conn = sqlite3.connect(DB_PATH)
            cur = conn.cursor()
            now_iso = datetime.now().isoformat()
            for db_id in db_ids:
                cur.execute(
                    "UPDATE articles SET status='posted', posted_at=? WHERE id=? AND status='collected'",
                    (now_iso, db_id)
                )
            conn.commit()
            conn.close()
            log(f'✅ DB 기사 {len(db_ids)}개 status=posted 업데이트 완료')
        except Exception as e:
            log(f'⚠️ DB status 업데이트 실패: {e}')

        for art in db_articles:
            # db_id 필드는 내부용, post_article에 전달하지 않음
            articles.append({
                'title': art['title'],
                'body': art['body'],
                'board': art['board'],
            })

    # ── Phase 3: 부족분을 개선된 더미로 채움 ──
    used_count = sum(1 for a in articles if a['board'] == 'used')
    tip_count = sum(1 for a in articles if a['board'] == 'tip')

    # used 게시글: 최소 2개, 최대 3개
    while used_count < 2:
        instr = random.choice(INSTRUMENTS)
        brands_short = list(set(b.split('(')[0] for b in BRANDS))
        brand = random.choice(brands_short)
        art_type = random.choice(['sell', 'buy', 'bargain'])
        dummy = _make_dummy_article(article_type=art_type, used_instr=instr, used_brand=brand)
        if dummy:
            articles.append(dummy)
            used_count += 1

    # 꿀팁 게시글: 1개
    if tip_count < 1:
        articles.append(_make_dummy_tip())

    # 섞기 (같은 게시판 연속 방지)
    random.shuffle(articles)

    return articles[:4]  # 최대 4개


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
            print(f'\n❌ Keepalive 실패 — NID_SES 만료. QR 로그인 필요.')
            sys.exit(1)
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
