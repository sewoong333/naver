#!/Users/se-ung/.hermes/hermes-agent/venv/bin/python3
"""
Playwright + REST API 이미지 포함 게시글 완전 자동 발행기 v3
========================================================
1. Playwright로 이미지 업로드 (SE3)
2. getDocumentData() 추출
3. textNode value를 직접 설정
4. REST API 발행
"""
import json, os, sys, time, re
from datetime import datetime

BASE_DIR = os.path.dirname(os.path.abspath(__file__))
STORAGE_FILE = os.path.join(BASE_DIR, 'naver_storage.json')
TARGET_CLUB_ID = '31386031'

def log(msg):
    print(f'[{datetime.now().strftime("%H:%M:%S")}] {msg}', flush=True)

def clean_phone(text):
    text = re.sub(r'01[016789]-\d{3,4}-\d{4}', '', text)
    text = re.sub(r'0\d{1,2}-\d{3,4}-\d{4}', '', text)
    text = re.sub(r'\d{3}-\d{3,4}-\d{4}', '', text)
    return text

def make_body_html(title, category, price, description=''):
    """본문 HTML 생성"""
    safe_desc = clean_phone(description)[:500] if description else ''
    parts = [
        f'안녕하세요! 에코뮤직 중고악기백화점입니다 🙌',
        '<br><br>',
        f'오늘 소개해드릴 매물은 <b>{title}</b> 입니다.',
        '<br><br>',
        f'📌 <b>상품 정보</b><br>',
        f'• 상품명: {title}<br>',
        f'• 카테고리: {category}<br>',
        f'• 가격: {price}원<br>',
        '<br>',
        f'📌 <b>거래 정보</b><br>',
        '• 거래 방식: 직거래 / 택배<br>',
        '• 위치: 경기도 (에코뮤직 매장)<br>',
        '• 연락: 쪽지 또는 댓글 남겨주세요<br>',
        '<br>',
    ]
    if safe_desc:
        parts += [
            f'📌 <b>상세 설명</b><br>',
            f'{safe_desc}<br>',
            '<br>',
        ]
    parts += [
        '📍 매장 방문도 가능합니다. 직접 보고 구매하세요!<br>',
        '에코뮤직 중고악기백화점에서 기다리겠습니다 😊<br>',
        '<br>',
        '📞 문의처<br>',
        'PURE GOLD x ECHO<br>',
        '010-8622-0611<br>',
        '[ OFFICIAL CONTACT CHANNEL - TEXT ONLY ]<br>',
        '<br>',
        '#에코뮤직 #중고악기 #중고악기백화점 #악기판매 #중고거래'
    ]
    return ''.join(parts)

def make_content_json(html_body):
    """HTML → SE3 document 포맷 (단일 textNode, 줄바꿈 \\n)"""
    text = html_body
    text = re.sub(r'<p[^>]*>', '', text)
    text = re.sub(r'</p>', '\n', text)
    text = re.sub(r'<br\s*/?>', '\n', text)
    text = re.sub(r'<[^>]+>', '', text)
    text = re.sub(r'\n{3,}', '\n\n', text)
    text = text.strip()

    uid = 'SE-' + os.urandom(10).hex().upper()
    doc = {
        "document": {
            "version": "2.9.0",
            "theme": "default",
            "language": "ko-KR",
            "id": uid,
            "components": [{
                "id": "SE-" + os.urandom(18).hex().upper(),
                "layout": "default",
                "value": [{
                    "id": "SE-" + os.urandom(18).hex().upper(),
                    "nodes": [{
                        "id": "SE-" + os.urandom(18).hex().upper(),
                        "value": text or ' ',
                        "@ctype": "textNode"
                    }],
                    "@ctype": "paragraph"
                }],
                "@ctype": "text"
            }],
            "di": {
                "dif": False,
                "dio": [{"dis": "N", "dia": {"t": 0, "p": 0, "st": 1, "sk": 0}}]
            }
        },
        "documentId": ""
    }
    return json.dumps(doc, ensure_ascii=False)

def rebuild_doc_with_layout(doc_json_str, title, category, price, description, image_count):
    """
    SE3 문서 재구성: 인사말 → 이미지 갤러리 → 상품정보 순서
    이미지가 다 보인 후에 글이 나오는 구조 → 이미지 사이에 텍스트 배치
    """
    import uuid
    doc = json.loads(doc_json_str)
    uid = 'SE-' + uuid.uuid4().hex[:20].upper()
    doc['document']['id'] = uid

    components = doc.get('document', {}).get('components', [])

    # 1. 이미지 컴포넌트 추출 (보존)
    image_comps = [c for c in components if c.get('@ctype') == 'image']

    def make_text_comp(text):
        cid = 'SE-' + uuid.uuid4().hex[:36].upper()
        pid = 'SE-' + uuid.uuid4().hex[:36].upper()
        nid = 'SE-' + uuid.uuid4().hex[:36].upper()
        return {
            "id": cid, "layout": "default",
            "value": [{
                "id": pid,
                "nodes": [{"id": nid, "value": text or ' ', "@ctype": "textNode"}],
                "@ctype": "paragraph"
            }],
            "@ctype": "text"
        }

    # 2. 상품 정보 텍스트 생성
    clean_desc = re.sub(r'<[^>]+>', '', description)[:500] if description else ''
    info_lines = [
        f'안녕하세요! 에코뮤직 중고악기백화점입니다 🙌',
        '',
        f'오늘 소개해드릴 매물은 {title} 입니다.',
        '',
        '▼ 아래에서 실제 상품 사진을 확인해주세요 ▼',
    ]
    info_top = '\n'.join(info_lines)

    info_bottom_lines = [
        '',
        f'📌 상품 정보',
        f'• 상품명: {title}',
        f'• 카테고리: {category}',
        f'• 가격: {price}원',
        '',
        f'📌 거래 정보',
        '• 거래 방식: 직거래 / 택배',
        '• 위치: 경기도 (에코뮤직 매장)',
        '• 연락: 쪽지 또는 댓글 남겨주세요',
        '',
    ]
    if clean_desc:
        info_bottom_lines += ['📌 상세 설명', clean_desc, '']
    info_bottom_lines += [
        '📍 매장 방문도 가능합니다. 직접 보고 구매하세요!',
        '에코뮤직 중고악기백화점에서 기다리겠습니다 😊',
        '',
        '📞 문의처',
        'PURE GOLD x ECHO',
        '010-8622-0611',
        '[ OFFICIAL CONTACT CHANNEL - TEXT ONLY ]',
        '',
        '#에코뮤직 #중고악기 #중고악기백화점 #악기판매 #중고거래'
    ]
    info_bottom = '\n'.join(info_bottom_lines)

    # 3. 새 components 배열 구성
    new_components = [
        make_text_comp(info_top),          # 인사말 + 이미지 안내
    ]
    new_components.extend(image_comps)     # 이미지 갤러리
    new_components.append(make_text_comp(info_bottom))  # 상품 정보 + 연락처

    # di 유지
    old_di = doc['document'].get('di', {"dif": False, "dio": [{"dis":"N","dia":{"t":0,"p":0,"st":1,"sk":0}}]})
    doc['document']['components'] = new_components
    doc['document']['di'] = old_di

    result = json.dumps(doc, ensure_ascii=False)
    log(f'📝 레이아웃 재구성: 인사말({len(info_top)}c) + 이미지({len(image_comps)}장) + 정보({len(info_bottom)}c) = {len(result)} chars')
    return result

def publish_article(title, category, price, description='', image_paths=None):
    """Playwright + REST API 이미지 포함 게시글 발행 (여러 이미지 지원)"""
    if not os.path.exists(STORAGE_FILE):
        log('❌ naver_storage.json 없음')
        return None

    from playwright.sync_api import sync_playwright
    article_id = None

    with sync_playwright() as p:
        browser = p.chromium.launch(headless=True)
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
                return None

            # ── 1. 제목 ──
            title_ta = page.query_selector('textarea.textarea_input')
            if title_ta:
                title_ta.fill(f'🎵 {title[:80]} ✨')
            time.sleep(1)

            # ── 2. 게시판 선택 ──
            page.evaluate('''() => {
                for (const b of document.querySelectorAll("button"))
                    if (b.textContent.includes("게시판을 선택") || b.className.includes("button")) { b.click(); break; }
            }''')
            time.sleep(1.5)
            target = page.locator('text=중고악기 팝니다(자유게시판)').first
            if target.count() > 0: target.click()
            time.sleep(2)

            # ── 3. 여러 이미지 업로드 ──
            if image_paths:
                if not isinstance(image_paths, list):
                    image_paths = [image_paths]
                # 실제 존재하는 파일만 필터링
                valid_paths = [p for p in image_paths if p and os.path.exists(p)]
                log(f'📸 업로드할 이미지: {len(valid_paths)}개')
                
                for idx, img_path in enumerate(valid_paths):
                    log(f'  [{idx+1}/{len(valid_paths)}] {os.path.basename(img_path)}')
                    # SE3 file input 찾기
                    fi = page.query_selector('input[type="file"]')
                    if not fi:
                        page.evaluate('''() => {
                            const btn = document.querySelector('button.se-image-toolbar-button');
                            if (btn) btn.click();
                        }''')
                        time.sleep(3)
                        fi = page.query_selector('input[type="file"]')

                    if fi:
                        fi.set_input_files(img_path)
                        # 마지막 이미지만 길게 대기, 나머지는 짧게
                        if idx < len(valid_paths) - 1:
                            log('  ⏳ 10초 대기...')
                            time.sleep(10)
                        else:
                            log('  ⏳ 20초 대기 (마지막)...')
                            time.sleep(20)
            
            # 이미지가 없으면 짧게 대기 (SE3 초기화)
            if not image_paths:
                time.sleep(3)

            # ── 4. 본문 HTML 생성 ──
            body_html = make_body_html(title, category, price, description)

            # ── 5. SE3 문서 데이터 추출 → textNode 교체 ──
            log('📊 SE3 문서 데이터 추출...')
            doc_json = page.evaluate('''() => {
                const editor = window.SmartEditor._editors.cafepc001;
                if (!editor || !editor._documentService) return null;
                try {
                    return JSON.stringify(editor._documentService.getDocumentData());
                } catch(e) { return null; }
            }''')

            if not doc_json:
                log('❌ SE3 문서 없음, 순수 text-only contentJson 사용')
                doc_json = make_content_json(body_html)
            else:
                log(f'📄 SE3 문서: {len(doc_json)} chars, 이미지 {len([c for c in json.loads(doc_json).get("document",{}).get("components",[]) if c.get("@ctype")=="image"])}장')
                # 레이아웃 재구성: 인사말 → 이미지 → 상세정보
                doc_json = rebuild_doc_with_layout(doc_json, title, category, price, description, len(image_paths or []))

            # ── 6. REST API 발행 ──
            log('🚀 REST API 발행...')
            resp = page.context.request.post(
                f'https://apis.cafe.naver.com/editor/v2.0/cafes/{TARGET_CLUB_ID}/menus/11/articles',
                headers={
                    'Content-Type': 'application/json;charset=UTF-8',
                    'Origin': 'https://cafe.naver.com',
                    'Referer': f'https://cafe.naver.com/ca-fe/cafes/{TARGET_CLUB_ID}/articles/write',
                    'x-cafe-product': 'pc',
                },
                data=json.dumps({
                    "article": {
                        "cafeId": TARGET_CLUB_ID,
                        "contentJson": doc_json,
                        "from": "pc",
                        "menuId": 11,
                        "subject": f"🎵 {title[:80]} ✨",
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
                })
            )

            resp_text = resp.text()[:500]
            m = re.search(r'"articleId":(\d+)', resp_text)
            if m:
                article_id = int(m.group(1))
                log(f'✅✅✅ 발행 성공! articleId={article_id}')
            else:
                log(f'❌ 발행 실패: {resp_text}')

        except Exception as e:
            log(f'❌ 오류: {e}')

        finally:
            browser.close()

    return article_id

if __name__ == '__main__':
    import argparse
    parser = argparse.ArgumentParser()
    parser.add_argument('--title', default='테스트 악기')
    parser.add_argument('--price', default='100,000')
    parser.add_argument('--category', default='바이올린')
    parser.add_argument('--desc', default='')
    parser.add_argument('--image', default='')
    args = parser.parse_args()

    aid = publish_article(args.title, args.category, args.price, args.desc,
                          args.image if args.image else None)
    print(f'✅ articleId={aid}' if aid else '❌ 실패')
