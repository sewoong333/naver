#!/usr/bin/env python3
"""
네이버 카페 자동 발행기 - 설정 파일
각자 환경에 맞게 수정해서 사용하세요.
"""
import os

BASE_DIR = os.path.dirname(os.path.abspath(__file__))

# ── 타겟 카페 정보 ──────────────────────────────────
# 네이버 카페 URL에서 확인 가능 (f-e/cafes/{clubId})
# 예: https://cafe.naver.com/f-e/cafes/31386031/menus/0
TARGET_CLUB_ID = '31386031'     # ← 여기를 바꾸면 다른 카페에도 발행 가능
TARGET_CAFE_NAME = '에코뮤직 중고악기백화점'

# ── 소스 카페 (크롤링 대상) ─────────────────────────
SOURCE_CLUB_ID = '30497286'     # 빈티지뮤직
SOURCE_CAFE_NAME = '빈티지뮤직'

# ── 게시판 매핑 ─────────────────────────────────────
# 해당 카페의 실제 menuId로 설정 (자유게시판이 1이 아닐 수 있음)
# 확인 방법: python naver_cafe_poster.py --check-menus
BOARDS = {
    'free':  {'id': 1, 'name': '자유게시판'},
    'trade': {'id': 2, 'name': '중고 악기 팝니다'},
}

# ── 발행 설정 ───────────────────────────────────────
POST_INTERVAL = 3        # 발행 간격 (초)
MAX_POSTS_PER_DAY = 3    # 하루 최대 발행 수
DEFAULT_BOARD = 'free'   # 기본 게시판

# ── 파일 경로 ───────────────────────────────────────
STATE_FILE = os.path.join(BASE_DIR, 'naver_state.json')
DB_PATH = os.path.join(BASE_DIR, 'cafe_articles.db')
