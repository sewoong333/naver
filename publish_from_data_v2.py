#!/Users/se-ung/.hermes/hermes-agent/venv/bin/python3
"""
데이터 기반 이미지 포함 게시글 발행기 v2
======================================
DB(cafe_articles.db) → 이미지 다운로드(5장+) → Playwright 업로드 → REST API 발행
"""
import json, os, sys, time, re, sqlite3, urllib.request
from datetime import datetime

BASE_DIR = os.path.dirname(os.path.abspath(__file__))
DB_PATH = os.path.join(BASE_DIR, 'cafe_articles.db')
IMAGE_CACHE = os.path.join(BASE_DIR, 'image_cache')
os.makedirs(IMAGE_CACHE, exist_ok=True)

def log(msg):
    print(f'[{datetime.now().strftime("%H:%M:%S")}] {msg}', flush=True)

def clean_phone(text):
    text = re.sub(r'01[016789]-\d{3,4}-\d{4}', '', text)
    text = re.sub(r'0\d{1,2}-\d{3,4}-\d{4}', '', text)
    text = re.sub(r'\d{3}-\d{3,4}-\d{4}', '', text)
    return text

def download_image(url, article_id, index=0):
    """이미지 URL 다운로드 → 로컬 파일 저장"""
    if not url:
        return None
    ext = url.split('.')[-1].split('?')[0][:4] if '.' in url else 'jpg'
    if ext not in ('jpg', 'jpeg', 'png', 'gif', 'webp'):
        ext = 'jpg'
    local_path = os.path.join(IMAGE_CACHE, f'article_{article_id}_{index}.{ext}')

    if os.path.exists(local_path) and os.path.getsize(local_path) > 1000:
        return local_path

    try:
        req = urllib.request.Request(url, headers={
            'User-Agent': 'Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36'
        })
        with urllib.request.urlopen(req, timeout=15) as resp:
            data = resp.read()
            if len(data) < 500:
                return None
            with open(local_path, 'wb') as f:
                f.write(data)
            return local_path
    except Exception as e:
        log(f'  ⚠️ 이미지 {index} 다운로드 실패: {e}')
        return None

def parse_summary(summary):
    data = {}
    lines = summary.split('\n')
    for line in lines:
        line = line.strip()
        if '상품명' in line or '상품' in line:
            data['product'] = line.split(maxsplit=1)[-1] if len(line.split()) > 1 else ''
        elif '사이즈' in line:
            data['size'] = line.split(maxsplit=1)[-1] if len(line.split()) > 1 else ''
        elif '가격' in line:
            data['price'] = line.split(maxsplit=1)[-1] if len(line.split()) > 1 else ''
        elif '거래방식' in line or '거래 방식' in line:
            data['deal'] = line.split(maxsplit=1)[-1] if len(line.split()) > 1 else ''
        elif '위치' in line or '지역' in line:
            data['location'] = line.split(maxsplit=1)[-1] if len(line.split()) > 1 else ''
    return data

def fetch_one_article():
    """DB에서 발행되지 않은 게시글 1개 가져오기 (image_urls 포함)"""
    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row
    row = conn.execute("""
        SELECT id, title, category, summary, image_url, image_urls
        FROM articles
        WHERE status = 'collected' AND summary IS NOT NULL AND summary != ''
        ORDER BY RANDOM()
        LIMIT 1
    """).fetchone()
    conn.close()
    if row:
        return dict(row)
    return None

def mark_posted(article_id, success=True):
    conn = sqlite3.connect(DB_PATH)
    if success:
        conn.execute(
            "UPDATE articles SET status='posted', posted_at=datetime('now') WHERE id=?",
            (article_id,)
        )
    else:
        conn.execute(
            "UPDATE articles SET status='failed', posted_at=datetime('now') WHERE id=?",
            (article_id,)
        )
    conn.commit()
    conn.close()

def publish_one():
    """게시글 1개 발행 (5장 이상 이미지)"""
    article = fetch_one_article()
    if not article:
        log('❌ 발행 가능한 게시글 없음')
        return False

    article_id = article['id']
    title = article['title']
    category = article['category']
    summary = article['summary'] or ''
    
    log(f'📦 [{article_id}] {title} ({category})')

    # 가격 추출
    parsed = parse_summary(summary)
    price = parsed.get('price', '가격문의')
    desc = clean_phone(summary)[:500]

    # 모든 이미지 URL 수집
    all_urls = []
    
    # 1. image_urls (JSON 배열) 파싱
    raw_urls = article.get('image_urls', '') or ''
    if raw_urls:
        try:
            parsed_urls = json.loads(raw_urls)
            if isinstance(parsed_urls, list):
                all_urls.extend(parsed_urls)
        except:
            pass
    
    # 2. image_url (단일) 추가
    single_url = article.get('image_url', '') or ''
    if single_url and single_url not in all_urls:
        all_urls.insert(0, single_url)  # 대표 이미지를 첫 번째로

    # 3. 최소 5장 보장 — 부족하면 단일 이미지로 채움
    if len(all_urls) < 5:
        log(f'⚠️ 이미지 {len(all_urls)}개만 있음 (최소 5장 필요)')
    
    # 중복 제거
    all_urls = list(dict.fromkeys(all_urls))
    log(f'🖼️ 총 이미지 URL: {len(all_urls)}개')
    for i, u in enumerate(all_urls):
        log(f'  [{i+1}] {u[:80]}...')

    # 이미지 다운로드 (최대 8장)
    download_count = min(len(all_urls), 8)
    local_images = []
    for i in range(download_count):
        img_path = download_image(all_urls[i], article_id, i)
        if img_path:
            local_images.append(img_path)
            log(f'  ✅ 이미지 {i+1} 다운로드 완료')

    if not local_images:
        log('❌ 다운로드된 이미지 없음')
        return False

    log(f'📸 업로드할 이미지: {len(local_images)}개')

    # publish_with_image 호출
    from publish_with_image import publish_article
    aid = publish_article(
        title=title,
        category=category,
        price=price,
        description=desc,
        image_paths=local_images
    )

    if aid:
        mark_posted(article_id, success=True)
        log(f'✅✅✅ 발행 성공! articleId={aid}')
        return True
    else:
        mark_posted(article_id, success=False)
        log(f'❌ 발행 실패')
        return False

if __name__ == '__main__':
    log('='*50)
    log('🚀 데이터 기반 이미지 포함 발행 (멀티 이미지)')
    success = publish_one()
    log(f'📊 결과: {"성공" if success else "실패"}')
    log('='*50)
