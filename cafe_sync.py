#!/usr/bin/env python3
"""
네이버 카페 크롤러 — Naver Cafe REST API 기반
타겟: 빈티지뮤직 (clubid=30497286)
"""

import os
import sys
import re
import sqlite3
import time
import json
from datetime import datetime, timezone
from typing import Optional

import requests

# SEO 변환 모듈
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from seo_optimizer import optimize_article

# ── 설정 ──────────────────────────────────────────────
TARGET_CLUB_ID = "30497286"
OUR_CLUB_ID = "31386031"
# 모바일 URL용 카페 URL명 (빈티지뮤직)
TARGET_CAFE_URLNAME = "vintagemusic1"
ARTICLE_API = "https://apis.naver.com/cafe-web/cafe-boardlist-api/v1/cafes/{clubid}/menus/{menuid}/articles"
ARTICLE_DETAIL_API = "https://apis.naver.com/cafe-web/cafe-article-api/v1.1/cafes/{clubid}/articles/{articleid}"
DB_PATH = os.path.join(os.path.dirname(os.path.abspath(__file__)), "cafe_articles.db")
PAGE_SIZE = 50      # 한 페이지에 가져올 글 수
MAX_PAGES = 10      # 최대 페이지 수 (50*10=500개)
DELAY = 0.5         # 요청 간격 (초)

HEADERS = {
    "User-Agent": (
        "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) "
        "AppleWebKit/537.36 (KHTML, like Gecko) "
        "Chrome/125.0.0.0 Safari/537.36"
    ),
    "Referer": "https://cafe.naver.com/",
    "Accept": "application/json",
}


# ── DB ────────────────────────────────────────────────

def get_db():
    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row
    conn.execute("""
        CREATE TABLE IF NOT EXISTS articles (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            article_id TEXT UNIQUE NOT NULL,
            title TEXT NOT NULL,
            category TEXT DEFAULT '',
            author TEXT DEFAULT '',
            published_at TEXT DEFAULT '',
            published_ts INTEGER DEFAULT 0,
            url TEXT NOT NULL,
            summary TEXT DEFAULT '',
            image_url TEXT DEFAULT '',
            read_count INTEGER DEFAULT 0,
            comment_count INTEGER DEFAULT 0,
            crawled_at TEXT DEFAULT (datetime('now', 'localtime')),
            status TEXT DEFAULT 'collected',
            posted_at TEXT,
            posted_article_id TEXT
        )
    """)
    conn.execute("""
        CREATE TABLE IF NOT EXISTS crawl_log (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            crawled_at TEXT DEFAULT (datetime('now', 'localtime')),
            new_count INTEGER DEFAULT 0,
            total_count INTEGER DEFAULT 0,
            pages_scanned INTEGER DEFAULT 0,
            errors TEXT DEFAULT ''
        )
    """)
    conn.commit()
    return conn


# ── API 호출 ──────────────────────────────────────────

def fetch_articles_page(clubid: str, menuid: str, page: int, page_size: int = PAGE_SIZE) -> list[dict]:
    """카페 게시글 목록 한 페이지 조회"""
    url = ARTICLE_API.format(clubid=clubid, menuid=menuid)
    params = {
        "page": page,
        "pageSize": page_size,
        "sortBy": "TIME",
        "viewType": "L",
    }
    try:
        resp = requests.get(url, headers=HEADERS, params=params, timeout=15)
        resp.raise_for_status()
        data = resp.json()
        return data.get("result", {}).get("articleList", [])
    except Exception as e:
        print(f"  ⚠️  API 오류 (페이지 {page}): {e}", file=sys.stderr)
        return []


def fetch_article_detail(clubid: str, article_id: int, session: Optional[requests.Session] = None):
    """게시글 상세 내용 조회"""
    url = ARTICLE_DETAIL_API.format(clubid=clubid, articleid=article_id)
    try:
        if session:
            resp = session.get(url, headers=HEADERS, timeout=15)
        else:
            resp = requests.get(url, headers=HEADERS, timeout=15)
        resp.raise_for_status()
        data = resp.json()
        return data.get("result", {})
    except Exception as e:
        print(f"  ⚠️  상세 조회 실패 ({article_id}): {e}", file=sys.stderr)
        return None


def parse_timestamp(ts_ms: int) -> str:
    """밀리초 타임스탬프 → YYYY-MM-DD 문자열"""
    if not ts_ms:
        return ""
    return datetime.fromtimestamp(ts_ms / 1000, tz=timezone.utc).strftime("%Y-%m-%d")


def crawl_target_cafe(max_pages=MAX_PAGES) -> dict:
    """타겟 카페 전체 크롤링"""
    conn = get_db()
    cursor = conn.cursor()
    
    new_count = total_found = pages_scanned = 0
    errors = []
    
    for pn in range(1, max_pages + 1):
        print(f"📄 페이지 {pn}...", end=" ", flush=True)
        articles = fetch_articles_page(TARGET_CLUB_ID, "0", pn)
        
        if not articles:
            print("→ 완료 (더 이상 없음)")
            break
        
        pages_scanned += 1
        total_found += len(articles)
        print(f"{len(articles)}개")
        
        for art in articles:
            item = art.get("item", {})
            if not item:
                continue
            
            article_id = str(item.get("articleId", ""))
            if not article_id:
                continue
            
            title = item.get("subject", "").strip()
            author = item.get("writerInfo", {}).get("nickName", "")
            category = item.get("menuName", "")
            ts = item.get("writeDateTimestamp", 0)
            pub_date = parse_timestamp(ts)
            summary = item.get("summary", "")[:500]
            image_url = item.get("representImage", "")
            read_count = item.get("readCount", 0)
            comment_count = item.get("commentCount", 0)
            
            url = (
                f"https://cafe.naver.com/f-e/cafes/{TARGET_CLUB_ID}"
                f"/articles/{article_id}?referrerAllArticles=true"
            )
            
            # 모든 이미지 URL 수집: representImage를 기본으로
            all_images = [image_url] if image_url else []

            # 신규 글에 한해 Playwright로 모바일 URL 접속 → 모든 이미지 수집
            if new_count < 5:
                try:
                    from playwright.sync_api import sync_playwright as pw_launch
                    with pw_launch() as pw_ctx:
                        br = pw_ctx.chromium.launch(headless=True)
                        bp = br.new_page(viewport={'width': 1280, 'height': 900},
                                         locale='ko-KR', timezone_id='Asia/Seoul')
                        # 모바일 URL 사용 (로그인 불필요, 이미지 정상 로딩)
                        mobile_url = f'https://m.cafe.naver.com/{TARGET_CAFE_URLNAME}/{article_id}'
                        bp.goto(mobile_url, wait_until='domcontentloaded', timeout=20000)
                        import time as _time
                        _time.sleep(2)
                        # 페이지 내 모든 cafeptthumb 이미지 src 수집
                        pw_imgs = bp.evaluate("""() => {
                            const imgs = Array.from(document.querySelectorAll('img'));
                            return imgs.filter(i => i.src.includes('cafeptthumb')).map(i => i.src);
                        }""")
                        br.close()
                        if pw_imgs:
                            for img in pw_imgs:
                                if img not in all_images:
                                    all_images.append(img)
                            print(f"  🖼️ 모바일 수집: {len(pw_imgs)}개 이미지", file=sys.stderr)
                except Exception as e:
                    print(f"  ⚠️ 모바일 이미지 수집 실패: {e}", file=sys.stderr)
            
            image_urls_json = json.dumps(all_images, ensure_ascii=False) if all_images else ''
            
            try:
                cursor.execute(
                    """INSERT OR IGNORE INTO articles 
                    (article_id, title, category, author, published_at, published_ts, 
                     url, summary, image_url, image_urls, read_count, comment_count)
                    VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)""",
                    (article_id, title, category, author, pub_date, ts,
                     url, summary, image_url, image_urls_json, read_count, comment_count)
                )
                if cursor.rowcount > 0:
                    new_count += 1
                # 기존 레코드 업데이트 (image_urls가 비어있는 경우)
                else:
                    cursor.execute(
                        "UPDATE articles SET image_urls=? WHERE article_id=? AND (image_urls IS NULL OR image_urls='')",
                        (image_urls_json, article_id)
                    )
            except Exception as e:
                errors.append(f"{article_id}:{e}")
        
        conn.commit()
        time.sleep(DELAY)
    
    cursor.execute(
        "INSERT INTO crawl_log (new_count, total_count, pages_scanned, errors) VALUES (?, ?, ?, ?)",
        (new_count, total_found, pages_scanned, ",".join(errors[:5]))
    )
    conn.commit()
    conn.close()
    
    return {"new": new_count, "total": total_found, "pages": pages_scanned, "errors": errors}


def get_new_articles(limit=10):
    conn = get_db()
    c = conn.cursor()
    c.execute(
        "SELECT * FROM articles WHERE status='collected' ORDER BY published_ts DESC, id DESC LIMIT ?",
        (limit,)
    )
    rows = [dict(r) for r in c.fetchall()]
    conn.close()
    return rows


def get_stats():
    conn = get_db()
    c = conn.cursor()
    c.execute("SELECT status, COUNT(*) as cnt FROM articles GROUP BY status")
    stats = {r["status"]: r["cnt"] for r in c.fetchall()}
    c.execute("SELECT COUNT(*) as total FROM articles")
    stats["total"] = c.fetchone()["total"]
    c.execute("SELECT * FROM crawl_log ORDER BY id DESC LIMIT 3")
    stats["logs"] = [dict(r) for r in c.fetchall()]
    conn.close()
    return stats


def mark_posted(article_id, posted_id=""):
    conn = get_db()
    conn.execute(
        "UPDATE articles SET status='posted', posted_at=datetime('now','localtime'), posted_article_id=? WHERE article_id=?",
        (posted_id, article_id)
    )
    conn.commit()
    conn.close()
    print(f"  ✅ 게시 완료 처리: {article_id}")


# ── CLI ───────────────────────────────────────────────

def cmd_crawl():
    print(f"\n🔍 타겟 카페 크롤링 시작... ({datetime.now().strftime('%H:%M')})")
    r = crawl_target_cafe()
    s = get_stats()
    print(f"\n✅ 완료!")
    print(f"   페이지 {r['pages']} | {r['total']}개 발견 | {r['new']}개 신규 저장")
    print(f"   DB: 총 {s['total']}개 (📥대기 {s.get('collected',0)} / ✅게시 {s.get('posted',0)})")
    return r


def cmd_list(limit=10):
    arts = get_new_articles(limit)
    if not arts:
        print("📭 게시 대기 중인 글이 없습니다.")
        return
    print(f"\n📋 게시 대기 ({len(arts)}개):")
    for i, a in enumerate(arts, 1):
        cat = f"[{a['category']}] " if a['category'] else ""
        print(f"\n  {i:2d}. {cat}{a['title']}")
        print(f"      🆔 {a['article_id']} | 📅 {a['published_at']} | ✍️ {a['author']}")
        if a.get('read_count'):
            print(f"      👁️ {a['read_count']} | 💬 {a['comment_count']}")
        if a.get('summary'):
            print(f"      📝 {a['summary'][:80]}...")
        print(f"      🔗 {a['url']}")


def cmd_status():
    s = get_stats()
    print(f"\n📊 DB 현황")
    print(f"   총 게시글: {s['total']}개")
    print(f"   📥 게시 대기: {s.get('collected',0)}개")
    print(f"   ✅ 게시 완료: {s.get('posted',0)}개")
    print(f"   ⏭️  건너뜀: {s.get('skipped',0)}개")
    for log in s.get("logs", []):
        print(f"   📋 {log['crawled_at']} | {log['new_count']}개 신규 / {log['total_count']}개 발견 / {log['pages_scanned']}페이지")


def cmd_report():
    cmd_status()
    print()
    cmd_list(20)


def cmd_seo_preview(article_id: str):
    """SEO 변환 미리보기"""
    conn = get_db()
    c = conn.cursor()
    c.execute("SELECT * FROM articles WHERE article_id=?", (article_id,))
    row = c.fetchone()
    conn.close()
    
    if not row:
        print(f"❌ article_id={article_id}를 찾을 수 없습니다.")
        return
    
    art = dict(row)
    print(f"\n{'='*50}")
    print(f"🔍 SEO 변환 미리보기")
    print(f"{'='*50}")
    print(f"\n📌 원본: {art['title']}")
    
    result = optimize_article(
        art["title"], art.get("summary", ""),
        art.get("category", ""), art.get("author", ""),
        art.get("image_url", "")
    )
    
    print(f"\n✅ SEO 제목:\n{result['title']}")
    print(f"\n✅ SEO 본문:\n{result['body']}")
    print(f"\n🏷️ 키워드: {', '.join(result['keywords'])}")
    print(f"{'='*50}")
    print(f"게시하려면: cafe_sync.py confirm {article_id}")


def main():
    if len(sys.argv) < 2:
        print("사용법:")
        print("  cafe_sync.py crawl          # 크롤링 실행")
        print("  cafe_sync.py list [N]       # 미게시글 목록")
        print("  cafe_sync.py status         # 통계")
        print("  cafe_sync.py report         # 현황 리포트")
        print("  cafe_sync.py seo <id>       # SEO 변환 미리보기")
        print("  cafe_sync.py confirm <id>   # 게시 완료 처리")
        return
    
    cmd = sys.argv[1]
    if cmd == "crawl":
        cmd_crawl()
    elif cmd == "list":
        cmd_list(int(sys.argv[2]) if len(sys.argv) > 2 else 10)
    elif cmd == "status":
        cmd_status()
    elif cmd == "report":
        cmd_report()
    elif cmd == "confirm" and len(sys.argv) > 2:
        mark_posted(sys.argv[2])
    elif cmd == "seo" and len(sys.argv) > 2:
        cmd_seo_preview(sys.argv[2])
    else:
        print(f"알 수 없는 명령: {cmd}")


if __name__ == "__main__":
    main()
