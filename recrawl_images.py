#!/Users/se-ung/.hermes/hermes-agent/venv/bin/python3
"""
기존 게시글 상세 페이지에서 모든 이미지 재수집
"""
import json, os, sys, re, sqlite3, requests, time
from datetime import datetime

BASE_DIR = os.path.dirname(os.path.abspath(__file__))
DB_PATH = os.path.join(BASE_DIR, 'cafe_articles.db')

HEADERS = {
    'User-Agent': 'Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36',
}

def extract_images_from_page(url, article_id):
    """게시글 페이지에서 모든 cafeptthumb 이미지 URL 추출"""
    try:
        resp = requests.get(url, headers=HEADERS, timeout=15)
        if resp.status_code != 200:
            return []
        
        # 모든 cafeptthumb URL 찾기
        imgs = re.findall(r'https?://cafeptthumb[^"\'\\,<>\s]+', resp.text)
        # 중복 제거
        unique = []
        for img in imgs:
            # URL 정규화 (쿼리스트링 제거)
            clean_url = img.split('?')[0] if '?' in img else img
            if clean_url not in [u.split('?')[0] if '?' in u else u for u in unique]:
                unique.append(img)
        
        # representImage와 일치하는 URL을 첫 번째로 정렬
        return unique
    except Exception as e:
        print(f'  ⚠️ 오류: {e}')
        return []

def recrawl_single(article_id, url):
    """1개 게시글 재수집"""
    print(f'📄 article_id={article_id}')
    print(f'   URL: {url[:100]}...')
    
    images = extract_images_from_page(url, article_id)
    print(f'   🖼️ 이미지: {len(images)}개')
    for i, img in enumerate(images[:8]):
        print(f'      [{i+1}] {img[:100]}')
    
    return images

def recrawl_all(limit=None, start_from=0):
    """전체 게시글 재수집"""
    conn = sqlite3.connect(DB_PATH)
    
    query = "SELECT id, article_id, url FROM articles WHERE image_urls IS NULL OR image_urls = ''"
    if limit:
        query += f" LIMIT {limit}"
    
    rows = conn.execute(query).fetchall()
    print(f'📊 재수집 대상: {len(rows)}개')
    
    updated = 0
    for i, (rid, art_id, url) in enumerate(rows):
        if i < start_from:
            continue
        print(f'\n[{i+1}/{len(rows)}] ', end='')
        images = recrawl_single(art_id, url)
        
        if images:
            urls_json = json.dumps(images, ensure_ascii=False)
            conn.execute("UPDATE articles SET image_urls=? WHERE id=?", (urls_json, rid))
            conn.commit()
            updated += 1
        
        time.sleep(0.5)  # 요청 간격
    
    conn.close()
    print(f'\n✅ {updated}개 업데이트 완료')

if __name__ == '__main__':
    import argparse
    parser = argparse.ArgumentParser()
    parser.add_argument('--one', action='store_true', help='1개만 테스트')
    parser.add_argument('--limit', type=int, default=None, help='최대 재수집 개수')
    parser.add_argument('--start', type=int, default=0, help='시작 위치')
    args = parser.parse_args()
    
    if args.one:
        # 1개 테스트
        conn = sqlite3.connect(DB_PATH)
        row = conn.execute("SELECT id, article_id, url FROM articles WHERE image_urls IS NULL OR image_urls = '' LIMIT 1").fetchone()
        conn.close()
        if row:
            recrawl_single(row[1], row[2])
        else:
            print('❌ 대상 없음')
    else:
        recrawl_all(limit=args.limit, start_from=args.start)
