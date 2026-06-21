#!/usr/bin/env python3
"""
네이버 카페 게시글 작성기 — Playwright 기반
- 최초 1회: 사용자 QR 로그인 → 상태 저장
- 이후: 저장된 상태로 자동 게시 (로그인 불필요)
- 세션 만료 시: 텔레그램 알림 → 재로그인
"""

import os
import sys
import sqlite3
import time
import json
from datetime import datetime

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from seo_optimizer import optimize_article

from playwright.sync_api import sync_playwright

OUR_CLUB_ID = "31386031"
STATE_FILE = os.path.join(os.path.dirname(os.path.abspath(__file__)), "naver_state.json")
DB_PATH = os.path.join(os.path.dirname(os.path.abspath(__file__)), "cafe_articles.db")
UA = "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/125.0.0.0 Safari/537.36"


# ── 상태 관리 ──────────────────────────────────────

def save_state(context):
    """로그인 상태 저장 (쿠키 + localStorage)"""
    state = context.storage_state()
    with open(STATE_FILE, "w") as f:
        json.dump(state, f)
    print(f"  ✅ 상태 저장 완료 ({len(state.get('cookies',[]))}개 쿠키)")


def load_state(context) -> bool:
    """저장된 상태 복원"""
    if not os.path.exists(STATE_FILE):
        return False
    try:
        with open(STATE_FILE) as f:
            state = json.load(f)
        context.add_cookies(state.get("cookies", []))
        print(f"  ✅ 상태 복원 ({len(state.get('cookies',[]))}개 쿠키)")
        return True
    except:
        return False


# ── 로그인 ──────────────────────────────────────────

def qr_login(page) -> bool:
    """QR코드 로그인 (사용자 개입 필요)"""
    print("\n🔐 QR코드 로그인이 필요합니다!")
    page.goto("https://nid.naver.com/nidlogin.login?mode=qr", timeout=15000)
    page.wait_for_timeout(2000)
    
    # QR코드 스크린샷 저장
    qr_path = "/Users/se-ung/.hermes/profiles/choi-yonghyun/image_cache/naver_qr.png"
    page.screenshot(path=qr_path)
    print(f"  📸 QR코드 저장됨: {qr_path}")
    print(f"  ⏳ 120초 동안 로그인 대기 중...")
    
    # 120초 대기
    for i in range(60):
        time.sleep(2)
        current_url = page.url.lower()
        if "login" not in current_url and "nid" not in current_url:
            print(f"  ✅ 로그인 성공! ({i*2+2}초)")
            return True
        if i % 10 == 0:
            print(f"  {i*2+2}초...")
    
    print("  ⚠️ 로그인 시간 초과")
    return False


def ensure_logged_in(page, context) -> bool:
    """로그인 상태 확인 및 필요시 로그인"""
    # 저장된 상태로 로그인 시도
    if load_state(context):
        page.goto("https://www.naver.com/", wait_until="domcontentloaded", timeout=15000)
        page.wait_for_timeout(2000)
        body = page.inner_text("body")
        if "메일" in body or "내정보" in body or "로그아웃" in body:
            print("  ✅ 저장된 세션으로 로그인 성공!")
            return True
        print("  ⚠️ 저장된 세션 만료 — 재로그인 필요")
    
    # QR 로그인
    if qr_login(page):
        save_state(context)
        return True
    
    return False


# ── 게시글 작성 ────────────────────────────────────

def write_article(page, title: str, body: str) -> bool:
    """네이버 카페에 게시글 작성"""
    print(f"\n📝 게시글 작성 중...")
    
    # 글쓰기 페이지 이동
    page.goto(
        f"https://cafe.naver.com/f-e/cafes/{OUR_CLUB_ID}/menus/0/write",
        wait_until="domcontentloaded", timeout=20000
    )
    page.wait_for_timeout(3000)
    print(f"  URL: {page.url}")
    
    # cafe_main iframe 찾기
    target = page
    for f in page.frames:
        if f.name == "cafe_main":
            target = f
            break
    
    # 제목 입력
    try:
        inp = target.query_selector('input[name="subject"]')
        if inp:
            inp.fill(title)
            print("  ✅ 제목 입력 완료")
        else:
            print("  ⚠️ 제목 입력창 못 찾음")
    except Exception as e:
        print(f"  ⚠️ 제목 오류: {e}")
    
    # 본문 입력 (SmartEditor)
    body_written = False
    try:
        # SmartEditor iframe 찾기
        for f in page.frames:
            url = f.url.lower()
            if "editor" in url or "smart" in url or "se2" in url:
                f.evaluate("document.body.innerHTML = arguments[0];", body)
                print("  ✅ 본문 입력 완료 (SmartEditor)")
                body_written = True
                break
        
        if not body_written:
            # cafe_main 안에서 찾기
            se = target.query_selector('iframe[title*="내용"], iframe.se2_input')
            if se:
                se.content_frame.evaluate("document.body.innerHTML = arguments[0];", body)
                print("  ✅ 본문 입력 완료 (내부 iframe)")
                body_written = True
            else:
                # 콘솔로 본문 삽입 시도
                page.evaluate("""
                    () => {
                        const editors = document.querySelectorAll('[contenteditable="true"]');
                        if (editors.length > 0) {
                            editors[0].innerHTML = arguments[0];
                            return true;
                        }
                        return false;
                    }
                """, body)
                print("  ✅ 본문 입력 완료 (contenteditable)")
                body_written = True
    except Exception as e:
        print(f"  ⚠️ 본문 오류: {e}")
    
    if not body_written:
        print("  ⚠️ 본문 입력 실패!")
        return False
    
    return True


def submit_article(page) -> bool:
    """등록 버튼 클릭"""
    try:
        # cafe_main iframe 안에서 찾기
        target = page
        for f in page.frames:
            if f.name == "cafe_main":
                target = f
                break
        
        # 등록 버튼
        btn = target.query_selector(
            'button:has-text("등록"), a:has-text("등록"), '
            'input[value*="등록"], button[class*="submit"]'
        )
        if not btn:
            btn = page.query_selector(
                'button:has-text("등록"), a:has-text("등록"), '
                'input[value*="등록"]'
            )
        
        if btn:
            btn.click()
            time.sleep(3)
            print(f"  ✅ 게시글 등록 완료!")
            return True
        else:
            print("  ⚠️ 등록 버튼 못 찾음")
            return False
    except Exception as e:
        print(f"  ⚠️ 등록 오류: {e}")
        return False


# ── 메인 ────────────────────────────────────────────

def post_article_by_id(article_id: str, auto_submit: bool = True) -> bool:
    """article_id로 게시글 작성"""
    # DB 조회
    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row
    c = conn.cursor()
    c.execute("SELECT * FROM articles WHERE article_id=? AND status='collected'", (article_id,))
    row = c.fetchone()
    conn.close()
    
    if not row:
        print(f"❌ article_id={article_id}를 찾을 수 없거나 이미 게시됨")
        return False
    
    art = dict(row)
    result = optimize_article(
        art["title"], art.get("summary", ""),
        art.get("category", ""), art.get("author", ""),
        art.get("image_url", "")
    )
    
    print(f"\n{'='*50}")
    print(f"📤 게시글: {result['title']}")
    print(f"{'='*50}")
    
    if not auto_submit:
        print(f"\n📝 본문 미리보기:\n{result['body'][:200]}...")
        confirm = input("\n게시할까요? (y/N): ")
        if confirm.lower() != 'y':
            print("  게시 취소")
            return False
    
    # Playwright 실행
    with sync_playwright() as p:
        browser = p.chromium.launch(
            headless=True,  # 백그라운드 실행
            args=['--disable-blink-features=AutomationControlled'],
        )
        context = browser.new_context(
            viewport={"width": 1280, "height": 900},
            user_agent=UA,
        )
        page = context.new_page()
        
        # 로그인
        if not ensure_logged_in(page, context):
            print("❌ 로그인 실패 — 게시 중단")
            browser.close()
            return False
        
        # 글쓰기
        if not write_article(page, result["title"], result["body"]):
            browser.close()
            return False
        
        # 등록
        success = submit_article(page)
        
        # 게시 완료 처리
        if success:
            conn = sqlite3.connect(DB_PATH)
            conn.execute(
                "UPDATE articles SET status='posted', posted_at=datetime('now','localtime') WHERE article_id=?",
                (article_id,)
            )
            conn.commit()
            conn.close()
            print(f"  ✅ DB 상태 업데이트 완료")
        
        context.close()
        browser.close()
        return success


# ── CLI ────────────────────────────────────────────

if __name__ == "__main__":
    if len(sys.argv) < 2:
        print("사용법:")
        print("  python cafe_poster.py <article_id>   # 게시글 작성")
        print("  python cafe_poster.py login           # 로그인만 수행 (상태 저장)")
        print("  python cafe_poster.py test <id>       # 미리보기만 (게시 안 함)")
        sys.exit(1)
    
    if sys.argv[1] == "login":
        # 로그인만 수행 (상태 저장 목적)
        with sync_playwright() as p:
            browser = p.chromium.launch(headless=False)
            context = browser.new_context(viewport={"width": 1280, "height": 900}, user_agent=UA)
            page = context.new_page()
            if qr_login(page):
                save_state(context)
                print("✅ 로그인 완료! 이제 자동 게시 가능합니다.")
            context.close()
            browser.close()
    
    elif sys.argv[1] == "test" and len(sys.argv) > 2:
        # 미리보기 (headless=False)
        post_article_by_id(sys.argv[2], auto_submit=False)
    
    else:
        # 실제 게시 (headless=True, 자동)
        post_article_by_id(sys.argv[1], auto_submit=True)
