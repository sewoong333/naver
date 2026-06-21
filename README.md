# Naver Cafe Auto Poster 🚀

네이버 카페 게시글 자동 발행 도구. REST API 직접 호출 방식으로 Playwright 없이 동작합니다.

## 🚀 시작하기

### 1. 설치

```bash
# 필요 라이브러리 설치 (최초 1회)
pip install requests

# QR 로그인용 (최초 1회만 필요)
pip install playwright
playwright install chromium
```

### 2. QR 로그인 (최초 1회)

```bash
python naver_cafe_poster.py --qr-login
```

→ 네이버 로그인 창이 열리면 우측 상단 **QR 코드** 탭 클릭 후 네이버 앱으로 스캔

### 3. 발행 테스트

```bash
python naver_cafe_poster.py --check
```

→ `✅ 네이버 로그인 상태: 정상` 확인 후

```bash
python naver_cafe_poster.py --post --title "테스트 제목" --body "<p>테스트 본문입니다</p>" --board free
```

## 📋 사용법

### 게시판 선택

| 옵션 | 게시판 | 상태 |
|------|--------|------|
| `--board free` | 자유게시판 | ✅ 완벽 동작 |
| `--board trade` | 중고 악기 팝니다 | ⚠️ 추가 개발 필요 (N플리마켓) |

### 파일로 일괄 발행

```bash
python naver_cafe_poster.py --post --file articles.json
```

`articles.json` 예시:
```json
[
  {"title": "첼로 팝니다", "body": "<p>상태 좋습니다</p>", "board": "free"},
  {"title": "바이올린 팝니다", "body": "<p>2023년 구매</p>", "board": "trade"}
]
```

### 크롤링 → 발행 원클릭

```bash
python naver_cafe_poster.py --crawl --auto-post
```

## ⚙️ 설정 변경

`poster_config.py` 파일에서 다음 값 수정:

- `TARGET_CLUB_ID`: 발행할 카페 ID
- `SOURCE_CLUB_ID`: 크롤링할 카페 ID
- `POST_INTERVAL`: 발행 간격 (초)
- `MAX_POSTS_PER_DAY`: 하루 최대 발행 수

## 🔐 세션 관리

- 로그인 정보는 `naver_state.json`에 저장
- 세션 만료 시 `--qr-login` 재실행
- 한 번 로그인하면 Playwright 없이 REST API만으로 발행 가능

## 📁 파일 구조

```
cafe-crawler/
├── naver_cafe_poster.py    ← 메인 발행 스크립트 (이 파일만 있으면 됨)
├── poster_config.py        ← 설정 파일
├── crawler.py              ← 크롤러 (별도)
├── seo_optimizer.py        ← SEO 변환 (별도)
├── naver_state.json        ← 로그인 세션 (자동 생성)
└── cafe_articles.db        ← 게시글 DB (자동 생성)
```

## 💡 팁

- **발행 실패 시**: `--check`로 로그인 상태 확인 후 `--qr-login` 재실행
- **타 카페에도 적용**: `poster_config.py`에서 `TARGET_CLUB_ID`만 변경
- **Playwright 없이 발행**: QR 로그인 한 번만 하면 이후 Playwright 불필요
