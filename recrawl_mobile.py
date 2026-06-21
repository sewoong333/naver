#!/Users/se-ung/.hermes/hermes-agent/venv/bin/python3
"""
기존 게시글 모바일 URL로 이미지 재수집 (10장까지!)
"""
import json, os, sys, time, re, sqlite3, requests
from datetime import datetime
from playwright.sync_api import sync_playwright

BASE_DIR = os.path.dirname(os.path.abspath(__file__))
DB_PATH = os.path.join(BASE_DIR, 'cafe_articles.db')
CAFE_URLNAME = 'vintagemusic1'  # 빈티지뮤직

def log(msg):
    print(f'[{datetime.now().strftime("%H:%M:%S")}] {msg}', flush=True)

def recrawl_images_for_article(article_id):
    """모바일 URL로 접속해서 모든 이미지 수집"""
    mobile_url = f'https://m.cafe.naver.com/{CAFE_URLNAME}/{article_id}'
    try:
        with sync_playwright() as pw:
            br = pw.chromium.launch(headless=True)
            pg = br.new_page(viewport={'width': 1280, 'height': 900}, locale='ko-KR', timezone_id='Asia/Seoul')
            pg.goto(mobile_url, wait_until='domcontentloaded', timeout=20000)
            time.sleep(2)
            imgs = pg.evaluate("""() => {
                const imgs = Array.from(document.querySelectorAll('img'));
                return imgs.filter(i => i.src.includes('cafeptthumb')).map(i => i.src);
            }""")
            br.close()
            return imgs
    except Exception as e:
        log(f'  ❌ 오류: {e}')
        return []

def recrawl_all(limit=None, start_from=0):
    conn = sqlite3.connect(DB_PATH)
    # image_urls가 비었거나 1개만 있는 레코드
    rows = conn.execute("""
        SELECT id, article_id, title
        FROM articles
        WHERE status = 'collected'
        ORDER BY id
    """).fetchall()
    
    log(f'📊 재수집 대상: {len(rows)}개')
    if limit:
        rows = rows[start_from:start_from + limit]
    
    updated = 0
    total_imgs = 0
    
    for i, (rid, art_id, title) in enumerate(rows):
        log(f'[{i+1}/{len(rows)}] {title[:40]}... (article_id={art_id})')
        
        # 저장된 이미지 URL 수
        existing = conn.execute("SELECT image_urls FROM articles WHERE id=?", (rid,)).fetchone()[0] or '[]'
        try:
            existing_urls = json.loads(existing)
        except:
            existing_urls = []
        log(f'  기존: {len(existing_urls)}개')
        
        # 새로 수집
        new_imgs = recrawl_images_for_article(art_id)
        log(f'  수집: {len(new_imgs)}개')
        
        if len(new_imgs) > len(existing_urls):
            # representImage 유지 (첫 번째)
            rep_img = conn.execute("SELECT image_url FROM articles WHERE id=?", (rid,)).fetchone()[0]
            all_imgs = []
            if rep_img and rep_img not in new_imgs:
                all_imgs.append(rep_img)
            all_imgs.extend(new_imgs)
            
            urls_json = json.dumps(all_imgs, ensure_ascii=False)
            conn.execute("UPDATE articles SET image_urls=? WHERE id=?", (urls_json, rid))
            conn.commit()
            updated += 1
            total_imgs += len(all_imgs)
            log(f'  ✅ 저장: {len(all_imgs)}개')
        else:
            log(f'  ➡️ 변경 없음')
        
        time.sleep(1)  # 요청 간격
    
    conn.close()
    log(f'\n✅ 완료! {updated}개 업데이트, 총 {total_imgs}개 이미지')

if __name__ == '__main__':
    import argparse
    parser = argparse.ArgumentParser()
    parser.add_argument('--limit', type=int, default=None, help='처리 개수')
    parser.add_argument('--start', type=int, default=0, help='시작 위치')
    parser.add_argument('--one', action='store_true', help='1개만 테스트')
    args = parser.parse_args()
    
    if args.one:
        # 1개 테스트
        conn = sqlite3.connect(DB_PATH)
        row = conn.execute("SELECT id, article_id, title, image_urls FROM articles WHERE status='collected' LIMIT 1").fetchone()
        conn.close()
        if row:
            log(f'📦 [{row[0]}] {row[2]}')
            imgs = recrawl_images_for_article(row[1])
            log(f'🖼️ {len(imgs)}개 이미지:')
            for i, img in enumerate(imgs):
                log(f'  [{i+1}] {img[:100]}')
    else:
        recrawl_all(limit=args.limit, start_from=args.start)
