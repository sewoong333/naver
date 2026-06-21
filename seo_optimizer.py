#!/usr/bin/env python3
"""
네이버 카페 SEO 변환 모듈
원본 게시글 → SEO 최적화된 게시글 포맷 변환
"""

import re
from datetime import datetime

# ── 악기 관련 키워드 사전 ──────────────────────────
BRAND_ALIASES = {
    "스즈키": "스즈키 Suzuki",
    "콘브리오": "콘브리오 Conbrío",
    "괴츠": "괴츠 Goetz",
    "반디니": "반디니 Bandini",
}

CATEGORY_KEYWORDS = {
    "바이올린": ["바이올린", "violin", "클래식악기", "현악기", "입문용바이올린"],
    "첼로": ["첼로", "cello", "현악기", "클래식악기"],
    "비올라": ["비올라", "viola", "현악기"],
    "통기타": ["통기타", "어쿠스틱기타", "acoustic"],
    "일렉기타": ["일렉기타", "electric guitar", "일렉"],
    "드럼": ["드럼", "drum", "전자드럼"],
    "건반": ["건반", "신디사이저", "keyboard", "디지털피아노"],
}

SIZE_TERMS = re.compile(r'(\d+)/(\d+)\s*사이즈|(\d+)/(\d+)')
PRICE_TERMS = re.compile(r'(\d+)\s*만\s*원|(\d+)\s*천\s*원')


# ── SEO 제목 생성 ─────────────────────────────────

def generate_seo_title(original_title: str, category: str = "") -> str:
    """SEO 최적화 제목 생성"""
    title = original_title.strip()
    
    # 불필요 접두사 제거
    title = re.sub(r'^[#＃]\s*', '', title)
    
    # 사이즈 정보 추출
    size_info = ""
    size_match = SIZE_TERMS.search(title)
    if size_match:
        groups = size_match.groups()
        if groups[0] and groups[1]:
            size_info = f"{groups[0]}/{groups[1]}"
        elif groups[2] and groups[3]:
            size_info = f"{groups[2]}/{groups[3]}"
    
    # 가격 정보 추출
    price_info = ""
    price_match = PRICE_TERMS.search(title)
    if price_match:
        if price_match.group(1):
            price_info = f"{price_match.group(1)}만원"
        elif price_match.group(2):
            price_info = f"{price_match.group(2)}천원"
    
    # 브랜드명 확장
    for brand_kr, brand_full in BRAND_ALIASES.items():
        if brand_kr in title:
            title = title.replace(brand_kr, brand_full)
            break
    
    # 카테고리 키워드 추가 (없으면)
    has_category_keyword = False
    for cat, keywords in CATEGORY_KEYWORDS.items():
        if category == cat or any(kw in title.lower() for kw in keywords[:2]):
            has_category_keyword = True
            break
    
    if not has_category_keyword and category:
        title = f"{title} | {category}"
    
    # 상태/특성 키워드 보강
    status_keywords = {
        "입문용": "입문용 초보자추천",
        "중급": "중급 중급자용",
        "초보": "입문용 초보자추천",
        "셋업": "셋업완료 관리완료",
        "올드": "올드 빈티지",
    }
    
    for kw, replacement in status_keywords.items():
        if kw in title and kw not in title:  # already has it
            pass
    
    # 최종 제목 길이 조정 (50~70자 권장)
    if len(title) > 70:
        title = title[:67] + "..."
    
    return title


# ── SEO 본문 생성 ──────────────────────────────────

def generate_seo_body(title: str, summary: str, category: str = "", 
                       author: str = "", image_url: str = "", 
                       read_count: int = 0) -> str:
    """SEO 최적화 본문 생성"""
    
    # 원본 요약 정리
    summary = summary.strip()
    
    # 상세 정보 추출
    details = []
    
    # 제목에서 정보 파싱
    size_match = SIZE_TERMS.search(title)
    size_info = f"{size_match.group(1)}/{size_match.group(2)}" if size_match else ""
    
    price_match = PRICE_TERMS.search(summary) or PRICE_TERMS.search(title)
    price_info = ""
    if price_match:
        if price_match.group(1):
            price_info = f"{price_match.group(1)}만원"
    
    # 상품명 추출
    product_name = title.split(",")[0].strip()
    product_name = re.sub(r'\s*\|\s*.*$', '', product_name)
    
    # 카테고리명 매핑
    category_korean = category if category else "악기"
    
    # SEO 본문 작성
    lines = []
    lines.append(f"## 🎵 {product_name}")
    lines.append("")
    lines.append(f"**카테고리:** {category_korean}")
    if size_info:
        lines.append(f"**사이즈:** {size_info}")
    if price_info:
        lines.append(f"**가격:** {price_info}")
    lines.append("")
    
    # 상세 설명
    if summary:
        # 요약문 정리 (중복 정보 제거)
        clean_summary = summary
        for prefix in ["-상품명", "-사이즈", "-가격", "-거래방식", "-전문", "-풀세트"]:
            clean_summary = re.sub(rf'\n{prefix}[^\n]*', '', clean_summary)
        clean_summary = clean_summary.strip()
        
        if clean_summary:
            lines.append("### 📋 상품 설명")
            lines.append("")
            lines.append(clean_summary)
            lines.append("")
    
    # 키워드 태그
    lines.append("---")
    lines.append("")
    
    # 관련 키워드 생성
    base_keywords = [category_korean, "중고악기", "악기판매"]
    if size_info:
        base_keywords.append(f"{size_info} {category_korean}")
    if "입문" in title or "초보" in title:
        base_keywords.append(f"입문용 {category_korean}")
    if "올드" in title or "빈티지" in title:
        base_keywords.append("올드악기 빈티지")
    
    keyword_str = " ".join(base_keywords)
    lines.append(f"# {category_korean} #중고악기 #악기구매 #{keyword_str.replace(' ', ' #')}")
    lines.append("")
    lines.append(f"📌 **에코뮤직 중고악기백화점**에서 소개합니다.")
    lines.append(f"🔗 원본: 빈티지뮤직")
    lines.append(f"📅 등록: {datetime.now().strftime('%Y년 %m월 %d일')}")
    
    return "\n".join(lines)


# ── 변환 실행 ──────────────────────────────────────

def optimize_article(title: str, summary: str, category: str = "",
                      author: str = "", image_url: str = "",
                      read_count: int = 0) -> dict:
    """게시글 SEO 최적화"""
    seo_title = generate_seo_title(title, category)
    seo_body = generate_seo_body(title, summary, category, author, image_url, read_count)
    
    return {
        "title": seo_title,
        "body": seo_body,
        "keywords": extract_keywords(seo_title, category),
    }


def extract_keywords(title: str, category: str = "") -> list:
    """키워드 추출"""
    keywords = set()
    
    # 카테고리 기반
    if category:
        keywords.add(category)
        for cat, kws in CATEGORY_KEYWORDS.items():
            if category == cat:
                keywords.update(kws[:3])
    
    # 브랜드
    for brand_kr, brand_full in BRAND_ALIASES.items():
        if brand_kr in title:
            keywords.add(brand_kr)
            break
    
    # 상태
    for status in ["입문용", "중급", "초보", "올드", "빈티지", "전문가용"]:
        if status in title:
            keywords.add(f"{status} {category}" if category else status)
    
    # 사이즈
    size_match = SIZE_TERMS.search(title)
    if size_match:
        groups = size_match.groups()
        size = f"{groups[0] or groups[2]}/{groups[1] or groups[3]}"
        keywords.add(size)
    
    return list(keywords)[:8]


# ── CLI 테스트 ─────────────────────────────────────

if __name__ == "__main__":
    # 테스트
    test_title = "스즈키 바이올린, 1/2사이즈, 입문용, 풀세트"
    test_summary = "스즈키 바이올린입니다. 소리와 상태 모두 최상급이며, 융, 송진, 활 등 부속품 모두 챙겨드립니다."
    
    result = optimize_article(test_title, test_summary, "바이올린")
    print("=== SEO 제목 ===")
    print(result["title"])
    print("\n=== SEO 본문 ===")
    print(result["body"])
    print("\n=== 키워드 ===")
    print(", ".join(result["keywords"]))
