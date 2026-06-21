#!/Users/se-ung/.hermes/hermes-agent/venv/bin/python3
"""
정보/SEO 게시글 완전 자동 발행기
=================================
1. 주제 기반 정보글 작성 (악기·음악 관련)
2. 주제 관련 이미지 웹검색 → 다운로드
3. Playwright SE3 업로드 → getDocumentData() → REST API 발행
4. 이미지-글 적절히 배치된 레이아웃
"""
import json, os, sys, time, re, uuid, urllib.request, urllib.parse, sqlite3
from datetime import datetime

BASE_DIR = os.path.dirname(os.path.abspath(__file__))
DB_PATH = os.path.join(BASE_DIR, 'info_articles.db')
IMAGE_CACHE = os.path.join(BASE_DIR, 'image_cache')
os.makedirs(IMAGE_CACHE, exist_ok=True)

def log(msg):
    print(f'[{datetime.now().strftime("%H:%M:%S")}] {msg}', flush=True)

# ── 주제 템플릿 DB ──
INFO_TOPICS = [
    {
        "keyword": "통기타 입문 추천",
        "title_prefix": "🎸 통기타 처음 시작하는 분들께",
        "sections": [
            ("입문용 통기타, 무엇을 골라야 할까?", 
             "통기타를 처음 시작하는 분들이 가장 많이 고민하는 것은 '어떤 기타를 사야 하느냐'입니다. "
             "비싼 기타가 무조건 좋은 건 아니에요. 입문자에게 가장 중요한 것은 '편하게 잡히는가', '꾸준히 칠 의욕이 생기는가'입니다."),
            ("통기타 입문자를 위한 3가지 팁",
             "1. 바디 사이즈: 작은 바디(00, 000, OM)가 초보자에게 편합니다.\n"
             "2. 넥 두께: 너무 두꺼우면 코드 잡기 어려워요. 얇은 C형 넥 추천.\n"
             "3. 액션(줄 높이): 낮을수록 초보자에게 유리합니다. 구매 후 세팅 필수!"),
            ("가성비 좋은 입문용 통기타 브랜드",
             "• 야마하 F310 / F800: 전세계 입문용 스테디셀러\n"
             "• 콜트 AD810 / AF510: 가성비 최강\n"
             "• 에피폰 DR-100: 따뜻한 소리\n"
             "• Recording King RO-06: 올솔리드 입문용으로 인기\n\n"
             "중고로 구매하면 더 합리적인 가격에 좋은 악기를 구할 수 있어요!",
             True),  # has_image
        ],
        "hashtags": "#통기타 #통기타입문 #입문용기타 #어쿠스틱기타 #기타추천 #중고악기 #에코뮤직"
    },
    {
        "keyword": "바이올린 사이즈 선택",
        "title_prefix": "🎻 바이올린, 내게 맞는 사이즈는?",
        "sections": [
            ("바이올린 사이즈, 왜 중요할까?",
             "바이올린은 악기 중에서도 사이즈 선택이 가장 중요한 악기 중 하나입니다. "
             "잘못된 사이즈의 바이올린은 연주 자세를 망가뜨리고, 손목이나 어깨에 무리를 줄 수 있어요."),
            ("연령별·신체별 추천 사이즈",
             "• 4/4 (풀사이즈) - 팔길이 60cm 이상 / 만 12세~성인\n"
             "• 3/4 - 팔길이 56~60cm / 만 9~12세\n"
             "• 1/2 - 팔길이 51~56cm / 만 6~9세\n"
             "• 1/4 - 팔길이 46~51cm / 만 4~6세\n"
             "• 1/8 이하 - 팔길이 46cm 미만 / 유아용\n\n"
             "팔길이는 왼쪽 어깨부터 손바닥 중앙까지 측정합니다."),
            ("중고 바이올린 구매 시 체크포인트",
             "1. 사이즈부터 확인하세요 (라벨에 적혀있음)\n"
             "2. 줄감개(tuning peg)가 잘 돌아가는지 확인\n"
             "3. 브릿지가 휘어지지 않았는지 체크\n"
             "4. 울림주(rattle) 없는지 음 확인\n\n"
             "입문용이라면 10~30만원대 중고 바이올린으로 시작해도 충분합니다!",
             True),
        ],
        "hashtags": "#바이올린 #바이올린사이즈 #클래식악기 #현악기 #입문바이올린 #중고악기 #에코뮤직"
    },
    {
        "keyword": "일렉기타 입문 가이드",
        "title_prefix": "⚡ 일렉기타, 처음 사는 당신을 위한 가이드",
        "sections": [
            ("일렉기타, 통기타와 뭐가 다를까?", 
             "일렉기타는 통기타와 달리 앰프를 통해 소리를 내는 악기입니다. "
             "덜덜거리는 금속 줄의 진동을 픽업이 전기신호로 바꾸고, 앰프가 증폭하는 원리예요. "
             "줄이 가볍고 넥이 얇아서 통기타보다 초보자가 코드 잡기 더 편합니다."),
            ("입문자에게 추천하는 일렉기타 스펙",
             "• 바디: 솔리드 바디 (울림 없어 연습에 좋음)\n"
             "• 픽업: 싱글코일 or 험버커 — 험버커가 잡음 적고 초보자에게 편함\n"
             "• 넥: 로즈우드 지판 + C형 넥 (가장 무난)\n"
             "• 스케일: 25.5인치(스트랫 계열) 또는 24.75인치(레스폴 계열)\n\n"
             "중고로 20~50만원대면 좋은 입문용 일렉기타를 구할 수 있습니다."),
            ("일렉기타 필수 악세서리",
             "• 앰프: 입문용 소형 앰프(15W 미만)면 충분\n"
             "• 튜너: 클립온 튜너 필수\n"
             "• 케이블: 3~5m, 노이즈 쉴딩 된 것\n"
             "• 스트랩: 넓은 것이 어깨에 편함\n"
             "• 피크: 0.7~1.0mm 사이, 여러 두께로 준비",
             True),
        ],
        "hashtags": "#일렉기타 #일렉기타입문 #일렉기타추천 #일렉입문 #기타추천 #중고악기 #에코뮤직"
    },
    {
        "keyword": "중고악기 구매 시 주의사항",
        "title_prefix": "🔍 중고악기, 현명하게 사는 꿀팁",
        "sections": [
            ("중고악기, 왜 사야 할까?", 
             "중고악기는 새 악기에 비해 30~60% 저렴한 가격이 가장 큰 장점입니다. "
             "특히 입문용으로 시작할 때는 새 악기를 사기보다 중고로 시작해서 "
             "악기에 재미를 붙인 후 업그레이드하는 전략이 현명합니다."),
            ("악기별 체크리스트",
             "🎸 **기타류**\n"
             "• 프렛 마모 확인 (1~6프렛 위주)\n"
             "• 헤드와 넥 연결부 균열 확인\n"
             "• 줄 높이(액션) 체크\n"
             "• 튜닝 peg가 잘 돌아가는지\n\n"
             "🎻 **현악기**\n"
             "• 상판 균열 유무\n"
             "• 브릿지 상태\n"
             "• 울림주 확인\n"
             "• 활 털 상태\n\n"
             "🎹 **건반악기**\n"
             "• 모든 건반이 정상 소리 나는지\n"
             "• 페달 작동 확인\n"
             "• AUX/헤드폰 단자 확인"),
            ("직거래 vs 택배, 뭐가 좋을까?",
             "직거래가 가장 안전합니다. 직접 보고, 만져보고, 소리를 들어볼 수 있으니까요. "
             "특히 기타나 바이올린은 상태를 눈으로 확인하는 것이 중요합니다. "
             "에코뮤직 중고악기백화점은 직접 방문해 다양한 악기를 비교 체험할 수 있어요!",
             True),
        ],
        "hashtags": "#중고악기 #중고악기구매 #중고악기팁 #악기거래 #중고거래 #에코뮤직 #중고악기백화점"
    },
    {
        "keyword": "드럼 입문 세트",
        "title_prefix": "🥁 드럼 처음 시작하는 분들께 드리는 가이드",
        "sections": [
            ("드럼, 혼자서도 배울 수 있을까?", 
             "드럼은 처음에 리듬감만 조금 있으면 혼자서도 충분히 배울 수 있는 악기입니다. "
             "요즘은 유튜브에 무료 강좌가 정말 많아서 기초 테크닉부터 "
             "좋아하는 노래 커버까지 독학으로 가능한 시대예요."),
            ("입문용 드럼 세트 추천",
             "• 전자드럼: 소음 걱정 없어 아파트에서 연습 가능 (입문용 50~100만원)\n"
             "• 어쿠스틱 드럼: 실제 타격감 중요시한다면 (입문용 80~150만원)\n"
             "• 연습용 패드: 입문자에게 강력 추천! 저렴하게 리듬감 훈련\n\n"
             "중고로 구매하면 새 제품의 50~70% 가격에 구입 가능합니다."),
            ("드럼 입문자에게 꼭 필요한 아이템",
             "1. 메트로놈 (필수!) - 박자 감각의 기본\n"
             "2. 드럼 의자 (스툴) - 높낮이 조절 가능한 것\n"
             "3. 드럼스틱 - 5A 또는 5B 사이즈로 시작\n"
             "4. 방음 매트 - 층간소음 방지\n"
             "5. 이어플러그 - 청력 보호 필수!",
             True),
        ],
        "hashtags": "#드럼 #드럼입문 #전자드럼 #어쿠스틱드럼 #드럼추천 #중고악기 #에코뮤직"
    },
    {
        "keyword": "키보드 신디사이저 차이",
        "title_prefix": "🎹 키보드 vs 신디사이저 vs 디지털피아노, 뭘 살까?",
        "sections": [
            ("비슷해 보이지만 전혀 다른 악기들", 
             "'키보드'라는 말 하나로 뭉뚱그려 부르지만, 사실 전자건반악기에는 세 가지 종류가 있습니다. "
             "용도가 완전히 다르니 내게 맞는 악기를 선택하는 것이 중요해요."),
            ("세 가지 악기 비교",
             "🎹 **신디사이저**\n"
             "• 목적: 사운드 디자인, 연주용\n"
             "• 특징: 소리를 합성하고 변조하는 악기\n"
             "• 건반: 가벼운 신디건반(보통 49/61키)\n"
             "• 추천: 신스 리드, 패드 사운드 원할 때\n\n"
             "🎼 **디지털피아노**\n"
             "• 목적: 피아노 연습, 클래식 연주\n"
             "• 특징: 실제 그랜드피아노 터치감 재현\n"
             "• 건반: 해머액션 무거운 건반(88키)\n"
             "• 추천: 피아노곡 연습, 클래식 전공 희망\n\n"
             "🎵 **워크스테이션/편곡키보드**\n"
             "• 목적: 작곡, 라이브 연주, 반주\n"
             "• 특징: 다양한 악기음 + 자동반주 기능\n"
             "• 건반: 반무건 또는 해머(61/76/88키)\n"
             "• 추천: 혼자서 여러 악기 연주하고 싶을 때"),
            ("초보자에게 딱 좋은 선택",
             "딱 하나만 고르라면? **용도에 따라 다릅니다.**\n\n"
             "• 피아노 배우고 싶다 → 디지털피아노 (중고 30~80만원)\n"
             "• 밴드에서 키보드 연주 → 신디사이저 (중고 40~100만원)\n"
             "• 혼자 작곡/연주 즐기기 → 워크스테이션 (중고 50~150만원)\n\n"
             "에코뮤직 중고악기백화점에는 세 종류 모두 준비되어 있습니다!",
             True),
        ],
        "hashtags": "#키보드 #신디사이저 #디지털피아노 #건반악기 #전자악기 #입문추천 #중고악기 #에코뮤직"
    },
    {
        "keyword": "악기 보관 관리법",
        "title_prefix": "🌡️ 악기 오래 쓰는 보관 & 관리 꿀팁",
        "sections": [
            ("악기의 가장 큰 적, 온도와 습도", 
             "악기는 살아있는 나무로 만들어집니다. 온도와 습도 변화에 민감하게 반응해요. "
             "특히 겨울철 난방으로 건조해진 실내에서는 악기 표면에 균열이 생길 수 있습니다. "
             "적정 온도 20~25°C, 적정 습도 40~60%를 유지하는 것이 중요합니다."),
            ("악기별 관리법",
             "🎸 **기타/통기타**\n"
             "• 사용 후 헝겊으로 줄 닦기 (땀과 기름 제거)\n"
             "• 습도 40~60% 유지 (가습기 또는 악기용 가습제)\n"
             "• 케이스 보관 필수\n"
             "• 3~6개월에 한 번 줄 교체\n\n"
             "🎻 **바이올린/첼로**\n"
             "• 연주 후 활 털 풀어주기\n"
             "• 줄감개가 잘 돌아가는지 주기적 확인\n"
             "• 브릿지 기울기 체크\n"
             "• 습도 관리 (특히 겨울철 균열 주의)\n\n"
             "🎹 **건반악기**\n"
             "• 먼지 덮개 덮어두기\n"
             "• 직사광선 피할 것 (건반 변색)\n"
             "• 에어컨 직통 바람 피하기"),
            ("계절별 특별 관리법",
             "❄️ **겨울**\n"
             "• 난방으로 인한 건조가 가장 위험한 시기\n"
             "• 악기 케이스 안에 가습제 필수\n"
             "• 외출 후 바로 케이스 열지 말고 30분 후에\n\n"
             "☀️ **여름**\n"
             "• 장마철 습도 80%↑ → 곰팡이 주의\n"
             "• 제습기 또는 실리카겔 활용\n"
             "• 직사광선 노출 금지\n\n"
             "이 모든 관리 용품은 에코뮤직에서 구매 가능합니다!",
             True),
        ],
        "hashtags": "#악기관리 #악기보관 #통기타관리 #바이올린관리 #악기팁 #중고악기 #에코뮤직"
    },
    {
        "keyword": "어쿠스틱 통기타 차이",
        "title_prefix": "🎶 어쿠스틱기타 vs 통기타, 다른 게 아니었어?",
        "sections": [
            ("어쿠스틱기타 = 통기타?", 
             "결론부터 말하면, 우리나라에서 '통기타'와 '어쿠스틱기타'는 같은 악기를 가리킵니다. "
             "정확히는 어쿠스틱기타(Acoustic Guitar)가 원래 명칭이고, "
             "'통'이라는 표현은 속이 빈 몸체(공명통)에서 나온 우리나라식 줄임말이에요."),
            ("어쿠스틱기타의 다양한 종류",
             "🎵 **드레드노트 (D 타입)**\n"
             "• 가장 대중적인 모양, 굵고 웅장한 소리\n"
             "• 야마하 F310, 콜트 AD810 등 입문용 대부분\n\n"
             "🎵 **OM / 000 타입**\n"
             "• 바디가 작아 초보자에게 편함\n"
             "• 핑거스타일 주법에 최적화\n"
             "• Recording King RO-06 등\n\n"
             "🎵 **커터웨이**\n"
             "• 바디 상단이 움푹 파인 디자인\n"
             "• 높은 프렛(12프렛 이상) 연주 편리\n"
             "• 컷어웨이 유무는 취향 차이\n\n"
             "🎵 **일렉트릭 어쿠스틱**\n"
             "• 픽업 내장으로 앰프 연결 가능\n"
             "• 공연이나 합주 시 필수"),
            ("내게 맞는 통기타 고르는 법",
             "처음이라면 이렇게 골라보세요!\n\n"
             "1. 예산 정하기: 중고 기준 15~40만원대면 충분한 입문용 가능\n"
             "2. 사이즈: 키 작거나 손 작으면 OM/000 타입 추천\n"
             "3. 브랜드: 야마하, 콜트, 에피폰, Recording King\n"
             "4. 꼭 직접 잡아보세요! (에코뮤직 매장 방문 환영)\n\n"
             "처음부터 비싼 기타는 NO! 중고로 시작해서 실력 키우고 업그레이드 하세요 🎸",
             True),
        ],
        "hashtags": "#통기타 #어쿠스틱기타 #통기타추천 #입문기타 #기타고르는법 #중고악기 #에코뮤직"
    },
]


def get_random_topic():
    """랜덤 주제 선택"""
    import random
    topic = random.choice(INFO_TOPICS)
    # 시드 변경으로 진정한 랜덤 보장
    random.seed(None)
    return topic


def search_images(keyword, max_results=5):
    """웹에서 키워드 관련 이미지 검색 (무료 공개 API)"""
    images = []
    # Try multiple free image sources
    sources = [
        f'https://source.unsplash.com/400x300/?{urllib.parse.quote(keyword)},music',
    ]
    for src_url in sources:
        try:
            req = urllib.request.Request(src_url, headers={
                'User-Agent': 'Mozilla/5.0'
            })
            with urllib.request.urlopen(req, timeout=10) as resp:
                final_url = resp.geturl()
                if final_url and 'images.unsplash.com' in final_url:
                    images.append(final_url)
                    break
        except:
            pass
    
    if not images:
        log('  ℹ️ 웹 이미지 검색 생략 (템플릿 기반 발행)')
    return images


def download_image(url, keyword, index=0):
    """이미지 URL 다운로드 → 로컬 파일"""
    if not url:
        return None
    safe_keyword = re.sub(r'[^\w]', '_', keyword)[:20]
    local_path = os.path.join(IMAGE_CACHE, f'info_{safe_keyword}_{index}.jpg')
    
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
            ext = url.split('.')[-1].split('?')[0][:4] if '.' in url else 'jpg'
            if ext not in ('jpg', 'jpeg', 'png', 'gif', 'webp'):
                ext = 'jpg'
            local_path = os.path.join(IMAGE_CACHE, f'info_{safe_keyword}_{index}.{ext}')
            with open(local_path, 'wb') as f:
                f.write(data)
            return local_path
    except Exception as e:
        log(f'  ⚠️ 이미지 {index} 다운로드 실패: {e}')
        return None


def make_info_article_layout(topic, image_count):
    """
    정보글 SE3 레이아웃 생성
    구조: 제목소개 → 이미지1 → 섹션1 → 이미지2 → 섹션2 → 이미지3 → 섹션3 → 마무리 → 해시태그
    """
    import uuid
    
    title = topic['title_prefix']
    sections = topic['sections']
    hashtags = topic['hashtags']
    keyword = topic['keyword']
    
    # Base document
    uid = 'SE-' + uuid.uuid4().hex[:20].upper()
    doc = {
        "document": {
            "version": "2.9.0",
            "theme": "default",
            "language": "ko-KR",
            "id": uid,
            "components": [],
            "di": {"dif": False, "dio": [{"dis": "N", "dia": {"t": 0, "p": 0, "st": 1, "sk": 0}}]}
        },
        "documentId": ""
    }
    
def make_text_comp(text):
    """SE3 text 컴포넌트 생성 (모듈 레벨)"""
    import uuid
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


def make_info_article_layout(topic, image_count):
    """
    정보글 SE3 레이아웃 생성
    구조: 제목소개 → 이미지1 → 섹션1 → 이미지2 → 섹션2 → 이미지3 → 섹션3 → 마무리 → 해시태그
    """
    import uuid
    
    title = topic['title_prefix']
    sections = topic['sections']
    hashtags = topic['hashtags']
    keyword = topic['keyword']
    
    # Base document
    uid = 'SE-' + uuid.uuid4().hex[:20].upper()
    doc = {
        "document": {
            "version": "2.9.0",
            "theme": "default",
            "language": "ko-KR",
            "id": uid,
            "components": [],
            "di": {"dif": False, "dio": [{"dis": "N", "dia": {"t": 0, "p": 0, "st": 1, "sk": 0}}]}
        },
        "documentId": ""
    }
    
    components = []
    
    # 1. 인트로
    intro = f'{title}\n\n에코뮤직 중고악기백화점입니다! 🙌\n\n오늘은 "{keyword}"에 대해 알려드릴게요.\n꼼꼼히 읽어보시고 악기 선택에 도움되세요 😊'
    components.append(make_text_comp(intro))
    
    # 2. 섹션들 (텍스트만, 이미지는 SE3 업로드 후 자동 추가됨)
    for i, section in enumerate(sections):
        if len(section) == 3:
            heading, body, *_ = section
        else:
            heading, body = section
        section_text = f'📌 {heading}\n\n{body}'
        components.append(make_text_comp(section_text))
        
        # 마지막 섹션이 아닌 경우 이미지 구분선
        if i < len(sections) - 1:
            sep_text = '\n━━━━━━━━━━━━━━━━━━━━━━\n'
            components.append(make_text_comp(sep_text))
    
    # 3. 마무리
    closing = (
        '🌟 에코뮤직 중고악기백화점에서는\n'
        '다양한 중고 악기를 직접 보고 구매할 수 있습니다.\n\n'
        '📍 경기도 소재\n'
        '📞 010-8622-0611\n'
        '💬 방문 전 전화주시면 상담해드립니다!\n\n'
        f'{hashtags}'
    )
    components.append(make_text_comp(closing))
    
    doc['document']['components'] = components
    return json.dumps(doc, ensure_ascii=False)


def publish_info_article(topic=None, custom_title=None, custom_content=None, custom_hashtags=None):
    """
    정보글 발행 메인 함수
    - topic: INFO_TOPICS 중 하나 (None이면 랜덤)
    - custom_title: 직접 제목 지정
    - custom_content: 직접 본문 지정
    - custom_hashtags: 직접 해시태그 지정
    """
    if topic is None:
        topic = get_random_topic()
    
    keyword = topic['keyword']
    title = custom_title or topic['title_prefix']
    sections = topic['sections']
    hashtags = custom_hashtags or topic['hashtags']
    
    log(f'📝 주제: {keyword}')
    log(f'📰 제목: {title}')
    
    # ── 이미지 검색 및 다운로드 ──
    search_keywords = [keyword]
    for heading, body, *_ in sections[:2]:
        search_keywords.append(heading[:20])
    
    all_images = []
    for sk in search_keywords:
        imgs = search_images(sk, max_results=3)
        all_images.extend(imgs)
    
    # 중복 제거
    seen = set()
    unique_images = []
    for url in all_images:
        if url not in seen:
            seen.add(url)
            unique_images.append(url)
    
    # 최대 5개
    unique_images = unique_images[:5]
    log(f'🔍 검색된 이미지: {len(unique_images)}개')
    
    # 다운로드
    local_images = []
    for i, img_url in enumerate(unique_images):
        path = download_image(img_url, keyword, i)
        if path:
            local_images.append(path)
    
    log(f'📸 다운로드 완료: {len(local_images)}개 이미지')
    
    # ── Playwright + REST API 발행 ──
    STORAGE_FILE = os.path.join(BASE_DIR, 'naver_storage.json')
    if not os.path.exists(STORAGE_FILE):
        log('❌ naver_storage.json 없음')
        return None
    
    TARGET_CLUB_ID = '31386031'
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
                title_ta.fill(f'📚 {title[:70]} 📖')
            time.sleep(1)
            
            # ── 2. 게시판 선택 (정보글은 같은 중고악기 게시판) ──
            page.evaluate('''() => {
                for (const b of document.querySelectorAll("button"))
                    if (b.textContent.includes("게시판을 선택") || b.className.includes("button")) { b.click(); break; }
            }''')
            time.sleep(1.5)
            target = page.locator('text=중고악기 팝니다(자유게시판)').first
            if target.count() > 0: target.click()
            time.sleep(2)
            
            # ── 3. 이미지 업로드 (여러 장 순차) ──
            if local_images:
                for idx, img_path in enumerate(local_images):
                    log(f'  📸 [{idx+1}/{len(local_images)}] 업로드 중...')
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
                        if idx < len(local_images) - 1:
                            time.sleep(10)
                        else:
                            time.sleep(20)
            else:
                time.sleep(3)
            
            # ── 4. SE3 문서 추출 및 재구성 ──
            log('📊 SE3 문서 데이터 추출...')
            doc_json = page.evaluate('''() => {
                const editor = window.SmartEditor._editors.cafepc001;
                if (!editor || !editor._documentService) return null;
                try {
                    return JSON.stringify(editor._documentService.getDocumentData());
                } catch(e) { return null; }
            }''')
            
            if not doc_json:
                log('❌ SE3 문서 없음, 템플릿 사용')
                doc_json = make_info_article_layout(topic, len(local_images))
            else:
                log(f'📄 SE3 문서 추출 완료: {len(doc_json)} chars')
                # SE3에서 추출된 문서에 이미지 컴포넌트가 있으면 보존해야 함
                # 이미지가 자동으로 SE3에 추가되었으므로, 텍스트만 재구성
                # -> text components의 value를 우리 내용으로 교체
                try:
                    se3_doc = json.loads(doc_json)
                    components = se3_doc.get('document', {}).get('components', [])
                    text_comps = [c for c in components if c.get('@ctype') == 'text']
                    image_comps = [c for c in components if c.get('@ctype') == 'image']
                    
                    log(f'  SE3 내 이미지 컴포넌트: {len(image_comps)}개')
                    
                    # 새 문서 구성: 인트로 텍스트 → 이미지들 → 섹션 텍스트 → 이미지들 → 마무리
                    topic_data = topic
                    new_components = []
                    
                    intro = f'{title}\n\n에코뮤직 중고악기백화점입니다! 🙌\n\n오늘은 "{keyword}"에 대해 알려드릴게요.\n꼼꼼히 읽어보시고 악기 선택에 도움되세요 😊'
                    new_components.append(make_text_comp(intro))
                    
                    if image_comps:
                        new_components.append(image_comps[0])
                    
                    for i, section in enumerate(sections[:3]):
                        if len(section) == 3:
                            heading, body, *_ = section
                        else:
                            heading, body = section
                        section_text = f'📌 {heading}\n\n{body}'
                        new_components.append(make_text_comp(section_text))
                        
                        if i == 0 and len(image_comps) > 1:
                            new_components.append(image_comps[1])
                        elif i == 1 and len(image_comps) > 2:
                            new_components.append(image_comps[2])
                        elif i == 2 and len(image_comps) > 3:
                            new_components.append(image_comps[3])
                        elif len(image_comps) > i + 1:
                            new_components.append(image_comps[i + 1])
                    
                    closing = (
                        '🌟 에코뮤직 중고악기백화점에서는\n'
                        '다양한 중고 악기를 직접 보고 구매할 수 있습니다.\n\n'
                        '📍 경기도 소재\n'
                        '📞 010-8622-0611\n'
                        '💬 방문 전 전화주시면 상담해드립니다!\n\n'
                        f'{hashtags}'
                    )
                    new_components.append(make_text_comp(closing))
                    
                    # 남은 이미지들 추가
                    for img_comp in image_comps[3:]:
                        new_components.append(img_comp)
                    
                    se3_doc['document']['components'] = new_components
                    doc_json = json.dumps(se3_doc, ensure_ascii=False)
                    log(f'📝 레이아웃 재구성 완료: 텍스트+이미지 혼합 배치')
                    
                except Exception as e:
                    log(f'  ⚠️ 레이아웃 재구성 실패: {e}, 템플릿 사용')
                    doc_json = make_info_article_layout(topic, len(local_images))
            
            # ── 5. REST API 발행 ──
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
                        "subject": f'📚 {title[:70]} 📖',
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
                log(f'✅✅✅ 정보글 발행 성공! articleId={article_id}')
                log(f'📌 주제: {keyword}')
                log(f'📰 제목: {title}')
                log(f'🖼️ 이미지: {len(local_images)}장')
            else:
                log(f'❌ 발행 실패: {resp_text}')
                
        except Exception as e:
            log(f'❌ 오류: {e}')
            import traceback
            log(traceback.format_exc())
        
        finally:
            browser.close()
    
    return article_id


if __name__ == '__main__':
    import argparse
    parser = argparse.ArgumentParser(description='정보글 자동 발행')
    parser.add_argument('--keyword', default='', help='특정 키워드 지정 (비우면 랜덤)')
    parser.add_argument('--title', default='', help='제목 직접 지정')
    parser.add_argument('--content', default='', help='본문 직접 지정')
    parser.add_argument('--hashtags', default='', help='해시태그 직접 지정')
    args = parser.parse_args()
    
    topic = None
    if args.keyword:
        # 키워드에 맞는 토픽 찾기 (또는 새로 생성)
        for t in INFO_TOPICS:
            if args.keyword.lower() in t['keyword'].lower():
                topic = t
                break
        if not topic:
            # 키워드 커스텀 — 기본 템플릿 생성
            topic = {
                "keyword": args.keyword,
                "title_prefix": args.title or f'🎵 {args.keyword} 완벽 가이드',
                "sections": [
                    (f'{args.keyword}의 모든 것', 
                     f'{args.keyword}에 대해 자세히 알아보겠습니다. 에코뮤직 중고악기백화점이 알려드립니다.'),
                ],
                "hashtags": args.hashtags or f'#{args.keyword} #중고악기 #에코뮤직'
            }
    
    aid = publish_info_article(
        topic=topic,
        custom_title=args.title if args.title else None,
        custom_content=args.content if args.content else None,
        custom_hashtags=args.hashtags if args.hashtags else None
    )
    
    if aid:
        print(f'✅✅✅ 정보글 발행 성공! articleId={aid}')
    else:
        print('❌ 정보글 발행 실패')
        sys.exit(1)
