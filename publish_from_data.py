#!/usr/bin/env python3
"""
빈티지뮤직 데이터 → 에코뮤직 중고악기백화점 게시글 발행
블로그 스타일 포맷팅 + 실제 데이터 기반
"""
import sqlite3, json, sys, os, re, random
from datetime import date

# 상대 경로 설정
BASE_DIR = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, BASE_DIR)

DB_PATH = os.path.join(BASE_DIR, 'cafe_articles.db')

# naver_session_manager에서 post_article 임포트
from naver_session_manager import post_article, STORAGE_FILE, check_session

def fetch_real_articles(limit=10):
    """DB에서 발행되지 않은 실제 악기 데이터 가져오기"""
    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row
    
    # status가 collected인 것만 (아직 발행 안 됨)
    rows = conn.execute("""
        SELECT id, title, category, summary, image_url 
        FROM articles 
        WHERE status = 'collected' AND summary IS NOT NULL AND summary != ''
        ORDER BY RANDOM()
        LIMIT ?
    """, (limit,)).fetchall()
    
    conn.close()
    return [dict(r) for r in rows]

def parse_summary(summary):
    """summary 텍스트에서 상품명, 사이즈, 가격, 거래방식 등 추출"""
    data = {}
    data['original'] = summary
    
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

def make_blog_style_body(article, include_contact=True):
    """블로그 스타일 본문 생성"""
    title = article['title']
    category = article['category']
    summary = article['summary'] or ''
    parsed = parse_summary(summary)
    
    today = date.today()
    
    # 본문 빌드 - 블로그 스타일
    parts = []
    
    # 인사말
    parts.append(f"<p>안녕하세요! 에코뮤직 중고악기백화점입니다 🙌</p>")
    parts.append(f"<p><br></p>")
    parts.append(f"<p>오늘 소개해드릴 매물은 <b>{title}</b> 입니다.</p>")
    parts.append(f"<p><br></p>")
    
    # 상품 정보 섹션
    parts.append(f"<p>📌 <b>상품 정보</b></p>")
    
    if parsed.get('product'):
        parts.append(f"<p>• 상품명: {parsed['product']}</p>")
    if parsed.get('size'):
        parts.append(f"<p>• 사이즈: {parsed['size']}</p>")
    parts.append(f"<p>• 카테고리: {category}</p>")
    if parsed.get('price'):
        parts.append(f"<p>• 가격: {parsed['price']}</p>")
    else:
        parts.append(f"<p>• 가격: 협의 가능 (문의주세요)</p>")
    parts.append(f"<p><br></p>")
    
    # 거래 정보
    parts.append(f"<p>📌 <b>거래 정보</b></p>")
    if parsed.get('deal'):
        parts.append(f"<p>• 거래 방식: {parsed['deal']}</p>")
    else:
        parts.append(f"<p>• 거래 방식: 직거래 / 택배</p>")
    if parsed.get('location'):
        parts.append(f"<p>• 위치: {parsed['location']}</p>")
    else:
        parts.append(f"<p>• 위치: 경기도 (에코뮤직 매장)</p>")
    parts.append(f"<p>• 연락: 쪽지 또는 댓글 남겨주세요</p>")
    parts.append(f"<p><br></p>")
    
    # 상세 설명 (원문 요약 활용)
    desc = summary[:300] if len(summary) > 0 else "상세 설명은 쪽지로 문의주세요!"
    # 줄바꿈 처리
    desc_paragraphs = desc.replace('\n', '<br>')
    parts.append(f"<p>📌 <b>상세 설명</b></p>")
    parts.append(f"<p>{desc_paragraphs}</p>")
    parts.append(f"<p><br></p>")
    
    # 이미지 안내 (원본 링크)
    if article.get('image_url'):
        parts.append(f"<p>📸 <b>실물 사진</b></p>")
        parts.append(f"<p>아래 링크에서 실제 상품 사진을 확인하세요:</p>")
        parts.append(f"<p><a href='{article['image_url']}'>📷 상품 이미지 보기</a></p>")
        parts.append(f"<p><br></p>")
    
    # 매장 안내
    parts.append(f"<p>📍 매장 방문도 가능합니다. 직접 보고 구매하세요!</p>")
    parts.append(f"<p>에코뮤직 중고악기백화점에서 기다리겠습니다 😊</p>")
    parts.append(f"<p><br></p>")
    
    # 연락처 카드
    if include_contact:
        parts.append(f"<p>📞 <b>문의처</b></p>")
        parts.append(f"<p>PURE GOLD x ECHO</p>")
        parts.append(f"<p>010-8622-0611</p>")
        parts.append(f"<p>[ OFFICIAL CONTACT CHANNEL - TEXT ONLY ]</p>")
        parts.append(f"<p><br></p>")
    
    # 해시태그
    tag_keywords = {
        '바이올린': ['바이올린', '현악기', '클래식', '입문용', '중고악기'],
        '첼로': ['첼로', '현악기', '클래식', '중고악기'],
        '통기타/베이스/일렉': ['기타', '통기타', '일렉기타', '베이스', '악기판매'],
        '기타악기': ['악기', '중고악기', '악기판매'],
    }
    tags = ['에코뮤직', '중고악기', '중고악기백화점', '악기판매', '중고거래']
    if category in tag_keywords:
        tags.extend(tag_keywords[category])
    tags = list(set(tags))[:8]
    tag_str = ' '.join(f'#{t}' for t in tags)
    parts.append(f"<p>{tag_str}</p>")
    
    return '\n'.join(parts)

def publish_from_data():
    """DB 데이터로 게시글 발행"""
    # 세션 확인
    if not os.path.exists(STORAGE_FILE):
        print("❌ naver_storage.json 없음. 먼저 --login 실행하세요.")
        return
    
    articles = fetch_real_articles(limit=5)
    if not articles:
        print("❌ 발행 가능한 게시글이 없습니다. 먼저 crawl을 실행하세요.")
        return
    
    print(f"📦 총 {len(articles)}개 게시글 준비 완료")
    
    success = 0
    fail = 0
    
    for i, article in enumerate(articles):
        # 제목: 말머리+이모지+실제 제목
        title = f"🎵 {article['title']} ✨"
        
        # 본문 생성
        body_html = make_blog_style_body(article, include_contact=True)
        
        print(f"\n📝 [{i+1}/{len(articles)}] 발행 중: {title}")
        print(f"   카테고리: {article['category']}")
        
        # 발행
        result = post_article(title, body_html, board_key='used')
        
        if result.get('success'):
            print(f"   ✅ 성공! articleId={result.get('articleId', '?')}")
            success += 1
            
            # DB 상태 업데이트
            conn = sqlite3.connect(DB_PATH)
            conn.execute(
                "UPDATE articles SET status='posted', posted_at=datetime('now') WHERE id=?",
                (article['id'],)
            )
            conn.commit()
            conn.close()
            
            # 발행 간격 (15초)
            if i < len(articles) - 1:
                import time
                time.sleep(15)
        else:
            print(f"   ❌ 실패: {result.get('error', '알 수 없는 오류')}")
            fail += 1
    
    print(f"\n{'='*40}")
    print(f"📊 발행 결과: ✅ {success}개 성공 | ❌ {fail}개 실패")
    print(f"{'='*40}")

if __name__ == '__main__':
    publish_from_data()
