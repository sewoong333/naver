# 📘 네이버 카페 자동 발행기 사용 메뉴얼

> 누구나 자기 네이버 계정으로 게시글을 자동 발행할 수 있습니다.
> **최초 1회만 QR 로그인**하면 이후에는 Playwright 없이 REST API만으로 동작합니다.

---

## 📦 준비물

| 항목 | 필수 | 비고 |
|------|------|------|
| **Python 3.8+** | ✅ | 대부분의 Mac/PC에 기본 설치됨 |
| **네이버 계정** | ✅ | 카페 매니저 권한 권장 |
| **인터넷 연결** | ✅ | - |

---

## 🚀 설치 방법 (5분)

### 1. 필요한 라이브러리 설치

터미널을 열고 아래 명령어를 순서대로 실행하세요.

```bash
# 1) requests 라이브러리 설치 (API 호출용)
pip install requests

# 2) QR 로그인용 라이브러리 (최초 1회만 필요)
pip install playwright
playwright install chromium
```

> 💡 **Mac 사용자 팁**: `pip` 대신 `pip3`를 사용해야 할 수 있습니다.
> 에러 나면 `pip3 install requests` 로 시도해보세요.

### 2. 스크립트 다운로드

아래 파일들을 한 폴더에 다운로드하세요:

```
naver_cafe_poster.py   ← 메인 스크립트 (이것만 있으면 됨)
```

> `poster_config.py`는 선택 사항입니다. 기본 설정으로도 동작합니다.

---

## 🔐 로그인 (최초 1회, 1분 소요)

가장 중요한 단계입니다. 네이버 QR 코드로 로그인합니다.

```bash
python naver_cafe_poster.py --qr-login
```

**화면에 QR 코드가 나타나면:**

```
① 네이버 앱 실행
② 우측 상단 "QR 코드 스캔" 아이콘 탭
③ 화면의 QR 코드 스캔
```

✅ **"로그인 성공"** 메시지가 뜨면 완료입니다.
→ `naver_state.json` 파일이 자동 생성됩니다.

> ⚠️ **주의**: 이 파일이 없으면 발행이 안 됩니다. 절대 삭제하지 마세요.

---

## ✅ 로그인 확인

```bash
python naver_cafe_poster.py --check
```

```
✅ 세션 로드 완료 (쿠키 10개)
✅ 네이버 로그인 상태: 정상
```

---

## 📝 게시글 발행하기

### 기본 명령어

```bash
python naver_cafe_poster.py --post --title "제목" --body "<p>본문</p>" --board used
```

### 게시판 선택 옵션

| 옵션 | 게시판 | 용도 |
|------|--------|------|
| `--board free` | 자유게시판 | 일반 게시글 |
| `--board used` | **중고거래 게시판** | **✅ 중고 악기 거래 추천** |
| `--board trade` | 중고 악기 팝니다 | N플리마켓 (별도 개발중) |

### 예시

```bash
# 중고 악기 거래 게시판에 올리기 (추천)
python naver_cafe_poster.py --post \
  --title "스즈키 바이올린 1/2사이즈 팝니다" \
  --body "<p>스즈키 바이올린 1/2 사이즈입니다.</p><p>상태 최상급, 구성품 모두 포함</p>" \
  --board used

# 자유게시판에 올리기
python naver_cafe_poster.py --post \
  --title "공연 후기" \
  --body "<p>어제 공연 정말 좋았습니다</p>" \
  --board free
```

---

## 📋 여러 게시글 한 번에 발행하기

`articles.json` 파일을 만들고:

```json
[
  {
    "title": "이시환 첼로 4/4 팝니다",
    "body": "<p>이시환 2000호 첼로입니다. 상태 좋습니다.</p>",
    "board": "used"
  },
  {
    "title": "괴츠 바이올린 1/2 팝니다",
    "body": "<p>괴츠 바이올린, 입문용으로 좋습니다.</p>",
    "board": "used"
  }
]
```

아래 명령어로 한 번에 발행:

```bash
python naver_cafe_poster.py --post --file articles.json
```

---

## ⚙️ 다른 카페에 적용하기

### 설정 파일 수정

폴더에 있는 `poster_config.py` 파일을 열어서 아래 값을 수정하세요:

```python
# ── 타겟 카페 정보 ──────────────────
TARGET_CLUB_ID = '31386031'     # ← 이 값을 바꾸면 됨
TARGET_CAFE_NAME = '에코뮤직 중고악기백화점'
```

**카페 ID 확인 방법:**
```
https://cafe.naver.com/f-e/cafes/31386031/menus/0
                                 ^^^^^^^^
                                  이 숫자
```

### 게시판 ID 확인 방법

카페마다 게시판 ID(menuId)가 다릅니다. 확인하려면:

```bash
# 방법 1: 해당 카페 글쓰기 페이지에서 개발자도구 콘솔에 입력
# document.querySelector('#app').__vue__.$store.state.cafe.menus

# 방법 2: 저에게 물어보세요 (제가 분석해드림)
```

일반적으로 자유게시판은 **1**, 첫 번째 일반 게시판은 대부분 **11**입니다.

---

## 🔄 세션 만료 시 대처

네이버 세션은 보통 **몇 주~몇 달** 지속됩니다. 만약 아래 에러가 나면:

```
❌ 네이버 로그인 상태: 비정상
```

**다시 로그인하세요:**

```bash
python naver_cafe_poster.py --qr-login
```

→ 기존 `naver_state.json`은 자동으로 덮어써집니다.

---

## ⚠️ 자주 묻는 질문

### Q. Playwright가 없는데요?
→ 처음 **QR 로그인할 때만 필요**합니다. 그 이후에는 Playwright 없이도 발행됩니다.
다른 사람이 로그인해준 `naver_state.json` 파일만 복사해도 사용 가능합니다.

### Q. "Post only by members" 에러가 나요?
→ 카페에 가입되어 있는지 확인하세요. 매니저 권한이 있어야 합니다.

### Q. "연속 등록 불가" 에러가 나요?
→ 잠시 기다렸다가 다시 시도하세요 (3분 이상 간격)

### Q. Windows에서도 되나요?
→ 네, Python만 설치되어 있으면 Windows/Mac/Linux 모두 됩니다.

### Q. 해킹 위험은 없나요?
→ `naver_state.json`에는 **로그인 쿠키만 저장**됩니다. 비밀번호는 저장되지 않습니다.
다만 이 파일이 유출되면 타인이 로그인할 수 있으니 **공유 시 주의**하세요.

---

## 📁 파일 구조 설명

```
cafe-crawler/
├── naver_cafe_poster.py    ← 메인 스크립트 (이것만 있으면 발행 가능)
├── poster_config.py         ← 설정 파일 (카페/게시판 변경 시)
├── naver_state.json         ← 로그인 세션 (자동 생성, 절대 삭제 금지)
├── articles.json            ← 일괄 발행용 파일 (직접 만듦)
├── README.md                ← 간단 설명서
├── MANUAL.md                ← 지금 보고 있는 상세 메뉴얼
└── seo_optimizer.py         ← SEO 변환기 (선택)
```

## 🎯 요약: 3단계로 끝내기

```
1️⃣ pip install requests playwright
    playwright install chromium

2️⃣ python naver_cafe_poster.py --qr-login
    (QR 코드 스캔)

3️⃣ python naver_cafe_poster.py --post --title "제목" --body "<p>본문</p>" --board used

                    ✅  끝!
```
