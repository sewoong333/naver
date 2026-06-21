#!/Users/se-ung/.hermes/hermes-agent/venv/bin/python3
"""
Playwright 이미지 포함 게시글 자동 발행기
=========================================
- execCommand로 본문+이미지 삽입
- SE3 setComponentList로 내부 상태 동기화
- 등록 버튼 멀티 fallback 클릭
"""
import json, os, sys, time, uuid, re
from datetime import datetime

BASE_DIR = os.path.dirname(os.path.abspath(__file__))
STORAGE_FILE = os.path.join(BASE_DIR, 'naver_storage.json')
TARGET_CLUB_ID = '31386031'
SCRIPT_LOG = os.path.join(BASE_DIR, 'auto_poster.log')

def log(msg):
    ts = f'[{datetime.now().strftime("%Y-%m-%d %H:%M:%S")}] {msg}'
    print(ts, flush=True)
    with open(SCRIPT_LOG, 'a') as f:
        f.write(ts + '\n')

def build_article_html(title, category, price, description, image_url):
    """게시글 HTML 생성 (블로그 스타일)"""
    parts = []
    parts.append(f'안녕하세요! 에코뮤직 중고악기백화점입니다 🙌')
    parts.append(f'<br><br>')
    parts.append(f'오늘 소개해드릴 매물은 <b>{title}</b> 입니다.')
    parts.append(f'<br><br>')
    if image_url:
        parts.append(f'<img src="{image_url}" width="500" /><br><br>')
    parts.append(f'📌 <b>상품 정보</b><br>')
    parts.append(f'• 상품명: {title}<br>')
    parts.append(f'• 카테고리: {category}<br>')
    parts.append(f'• 가격: {price}원<br>')
    parts.append(f'<br>')
    parts.append(f'📌 <b>거래 정보</b><br>')
    parts.append(f'• 거래 방식: 직거래 / 택배<br>')
    parts.append(f'• 위치: 경기도 (에코뮤직 매장)<br>')
    parts.append(f'• 연락: 쪽지 또는 댓글 남겨주세요<br>')
    parts.append(f'<br>')
    if description:
        parts.append(f'📌 <b>상세 설명</b><br>')
        parts.append(f'{description}<br>')
        parts.append(f'<br>')
    parts.append(f'📍 매장 방문도 가능합니다. 직접 보고 구매하세요!<br>')
    parts.append(f'에코뮤직 중고악기백화점에서 기다리겠습니다 😊<br>')
    parts.append(f'<br>')
    parts.append(f'📞 문의처<br>')
    parts.append(f'PURE GOLD x ECHO<br>')
    parts.append(f'010-8622-0611<br>')
    parts.append(f'[ OFFICIAL CONTACT CHANNEL - TEXT ONLY ]<br>')
    parts.append(f'<br>')
    parts.append(f'#에코뮤직 #중고악기 #중고악기백화점 #악기판매 #중고거래')
    return ''.join(parts)

def publish_with_image(title, price, category, description='', image_url=''):
    """Playwright로 이미지 포함 게시글 발행"""
    if not os.path.exists(STORAGE_FILE):
        log('❌ naver_storage.json 없음. --login 먼저 실행')
        return False

    from playwright.sync_api import sync_playwright

    success = False
    with sync_playwright() as p:
        browser = p.chromium.launch(
            headless=True,
            args=['--disable-blink-features=AutomationControlled']
        )
        ctx = browser.new_context(
            storage_state=STORAGE_FILE,
            viewport={'width': 1920, 'height': 1080},
            locale='ko-KR', timezone_id='Asia/Seoul'
        )
        page = ctx.new_page()

        try:
            log('📄 글쓰기 페이지 이동...')
            page.goto(
                f'https://cafe.naver.com/ca-fe/cafes/{TARGET_CLUB_ID}/articles/write?boardType=L',
                wait_until='networkidle', timeout=20000
            )
            time.sleep(5)

            if 'nidlogin' in page.url.lower():
                log('❌ 로그인 세션 만료')
                browser.close()
                return False

            # ── 1. 제목 ──
            title_ta = page.query_selector('textarea.textarea_input')
            if title_ta:
                safe_title = re.sub(r'["\']', '', title)[:80]
                title_ta.fill(f'🎵 {safe_title} ✨')
                log(f'✅ 제목 입력: {safe_title}')
            time.sleep(1)

            # ── 2. 게시판 선택 ──
            page.evaluate('''() => {
                for (const b of document.querySelectorAll("button"))
                    if (b.textContent.includes("게시판을 선택") || b.className.includes("button")) {
                        b.click(); break;
                    }
            }''')
            time.sleep(1.5)
            target = page.locator('text=중고악기 팝니다(자유게시판)').first
            if target.count() > 0:
                target.click()
                log('✅ 게시판: 중고악기거래')
            time.sleep(2)

            # ── 3. 본문 HTML 생성 및 execCommand 삽입 ──
            html = build_article_html(title, category, price, description, image_url)
            log(f'📝 본문 생성 ({len(html)} chars)')

            page.evaluate('''(html) => {
                const ce = document.querySelector('[contenteditable=true]');
                if (!ce) return;
                ce.focus();
                document.execCommand('insertHTML', false, html);
                ce.dispatchEvent(new Event('input', {bubbles: true, cancelable: true}));
            }''', html)
            time.sleep(1)

            # ── 4. SE3 setComponentList로 내부 동기화 ──
            page.evaluate('''(html) => {
                const editor = window.SmartEditor?._editors?.cafepc001;
                if (!editor) return;
                const ds = editor._documentService;
                if (!ds || typeof ds.setComponentList !== 'function') return;
                const comp = {
                    type: 'text', id: 'SE-' + crypto.randomUUID(),
                    layout: 'default',
                    value: [{
                        id: 'SE-' + crypto.randomUUID(),
                        nodes: [{
                            id: 'SE-' + crypto.randomUUID(),
                            value: html, '@ctype': 'textNode'
                        }],
                        '@ctype': 'paragraph'
                    }],
                    '@ctype': 'text'
                };
                try { ds.setComponentList([comp]); } catch(e) {}
            }''', html)
            log('✅ SE3 internal state sync')

            # ── 5. 등록 버튼 클릭 (멀티 fallback) ──
            log('🚀 등록 버튼 클릭 시도...')

            registered = False

            # 방법 A: locator click
            try:
                btn = page.locator('a.BaseButton.BaseButton--skinGreen').first
                if btn.count() > 0:
                    # Wait for potential navigation after click
                    with page.expect_navigation(timeout=8000) as nav:
                        btn.click(timeout=5000)
                    nav.value  # navigation happened
                    registered = True
                    log('✅ 방법A: locator click + navigation 감지!')
            except:
                log('⚠️ 방법A 실패')

            # 방법 B: mouse click at coordinates
            if not registered:
                try:
                    rect = page.evaluate('''() => {
                        const all = document.querySelectorAll('a.BaseButton');
                        for (const a of all) {
                            const span = a.querySelector('.BaseButton__txt');
                            if (span && span.textContent.trim() === '등록') {
                                const r = a.getBoundingClientRect();
                                return {x: r.x + r.width/2, y: r.y + r.height/2};
                            }
                        }
                        return null;
                    }''')
                    if rect:
                        with page.expect_navigation(timeout=8000) as nav:
                            page.mouse.click(rect['x'], rect['y'])
                        nav.value
                        registered = True
                        log('✅ 방법B: mouse 좌표 클릭 성공!')
                except:
                    log('⚠️ 방법B 실패')

            # 방법 C: evaluate 강제 click + Vue 이벤트
            if not registered:
                try:
                    with page.expect_navigation(timeout=8000) as nav:
                        page.evaluate('''() => {
                            const all = document.querySelectorAll('a.BaseButton');
                            for (const a of all) {
                                const span = a.querySelector('.BaseButton__txt');
                                if (span && span.textContent.trim() === '등록') {
                                    // 1) native click
                                    a.click();
                                    // 2) dispatchEvent
                                    setTimeout(() => a.dispatchEvent(new MouseEvent('click', {bubbles:true})), 100);
                                    return 'CLICKED';
                                }
                            }
                            return 'NOT_FOUND';
                        }''')
                    nav.value
                    registered = True
                    log('✅ 방법C: evaluate click 성공!')
                except:
                    log('⚠️ 방법C 실패')

            # 결과
            if registered:
                log(f'✅✅✅ 발행 성공! URL: {page.url}')
                success = True
            else:
                log('❌ 모든 방법 실패. 등록되지 않음.')
                # 스크린샷 저장
                ss_path = os.path.join(BASE_DIR, f'fail_{int(time.time())}.png')
                page.screenshot(path=ss_path)
                log(f'📸 스크린샷: {ss_path}')

        except Exception as e:
            log(f'❌ 오류: {e}')
            try:
                ss_path = os.path.join(BASE_DIR, f'error_{int(time.time())}.png')
                page.screenshot(path=ss_path)
                log(f'📸 스크린샷: {ss_path}')
            except:
                pass

        finally:
            browser.close()

    return success

if __name__ == '__main__':
    # 테스트 실행
    import argparse
    parser = argparse.ArgumentParser(description='Playwright 이미지 포함 게시글 발행')
    parser.add_argument('--title', default='테스트 악기', help='게시글 제목')
    parser.add_argument('--price', default='100,000', help='가격')
    parser.add_argument('--category', default='바이올린', help='카테고리')
    parser.add_argument('--desc', default='', help='상세 설명')
    parser.add_argument('--image', default='', help='이미지 URL')
    args = parser.parse_args()

    log('='*50)
    log(f'🚀 발행 시작: {args.title}')
    result = publish_with_image(args.title, args.price, args.category, args.desc, args.image)
    log(f'📊 결과: {"성공" if result else "실패"}')
    log('='*50)
