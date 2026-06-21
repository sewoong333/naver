# 👥 네이버 카페 팀 발행 시스템 사용 메뉴얼

> 여러 명이 각자 네이버 아이디로 같은 카페에 게시글을 발행합니다.
> 하나의 DB를 공유해서 중복 발행을 방지합니다.

---

## 🏗️ 시스템 구조

```
                    ┌─ [관리자] 크롤링
                    │
[공유 DB] ──────────┼─ [팀원1] 최용현 → 자신의 계정으로 발행
                    │─ [팀원2] 김봉엽 → 자신의 계정으로 발행
                    │─ [팀원3] 오세웅 → 자신의 계정으로 발행
```

- **DB 파일** (`team_articles.db`)을 모두가 접근 가능한 곳에 둠
- 각 팀원은 **자기 컴퓨터**에서 `team_poster.py` 실행
- **본인의 `naver_state.json`** 으로 로그인
- 게시글은 **자동 배정**되어 중복 발행 없음

---

## 📦 설치 (각 팀원 공통)

```bash
# 1. 파일 다운로드 (1개)
# team_poster.py 파일을 받아서 원하는 폴더에 저장

# 2. 필수 라이브러리 설치
pip install requests
pip install playwright
playwright install chromium
```

---

## 🔐 1단계: QR 로그인 (각 팀원, 최초 1회)

```bash
python team_poster.py --qr-login
```

- 네이버 로그인 창이 열리면 **QR 코드 탭** 클릭
- 네이버 앱으로 QR 스캔
- `naver_state.json` 파일이 자동 생성됨
- **본인 계정**으로 로그인해야 함 (각자 다른 계정)

> ⚠️ `naver_state.json`은 각자 컴퓨터에 생성됩니다.
> 공유DB와 달리 이 파일은 공유하지 않습니다.

---

## 📋 2단계: 발행 실행 (매일)

### 수동 실행

```bash
python team_poster.py --post --member "자기이름"
```

예시:
```bash
python team_poster.py --post --member "최용현"
```

실행하면:
1. DB에서 발행할 게시글 자동 배정
2. SEO 최적화된 제목/본문으로 발행
3. 중고거래 게시판(menuId=11)에 등록
4. DB에 발행 기록 저장 (중복 방지)

### 자동 실행 (cron)

매일 특정 시간에 자동 발행하려면:

**Mac/Linux:**
```bash
crontab -e
```
아래 내용 추가:
```
# 매일 오전 10시에 발행
0 10 * * * cd /team_poster/폴더 && python3 team_poster.py --post --member "최용현"
```

---

## 👑 관리자용 명령어

### 최초 설정
```bash
python team_poster.py --setup
```
→ 팀명, 카페 ID, 게시판, 일일 발행량 확인

### 팀원 추가
```bash
python team_poster.py --add-member "최용현"
python team_poster.py --add-member "김봉엽"
python team_poster.py --add-member "오세웅"
```

### 게시글 수동 추가
`articles.json` 파일을 만들고:
```bash
python team_poster.py --import articles.json
```

### 전체 현황 확인
```bash
python team_poster.py --status
```

출력 예시:
```
📊 팀 발행 현황
==================================================
  전체 게시글:   50개
  발행 대기:     32개
  배정 완료:     3개
  ✅ 발행 완료:  15개

👥 팀원별 발행 현황:
  최용현           7회 발행
  김봉엽           5회 발행
  오세웅           3회 발행
```

---

## 📁 공유 폴더 구성

```
[공유 폴더 (Dropbox/Google Drive/NAS)]
├── team_poster.py        ← 모두가 사용하는 스크립트 (1개)
├── team_articles.db      ← 공유 DB (게시글 + 발행 기록)
└── team_config.json      ← 팀 설정

[팀원1 컴퓨터]
└── naver_state.json      ← 본인 네이버 로그인 세션 (개인)

[팀원2 컴퓨터]
└── naver_state.json      ← 본인 네이버 로그인 세션 (개인)
```

---

## ❓ 자주 묻는 질문

**Q. DB는 어디에 둬야 하나요?**
→ 모두 접근 가능한 곳이면 됩니다.
  - Dropbox/Google Drive 폴더
  - 회사 NAS
  - GitHub (보안 주의)
  - 한 명의 컴퓨터에서 실행하고 다른 사람은 수동 대기

**Q. 크롤링은 누가 하나요?**
→ 관리자(오세웅 님)가 수동으로 실행:
```bash
python team_poster.py --crawl
```

**Q. 같은 게시글을 두 명이 발행할 수 있나요?**
→ **없습니다.** DB가 배정 상태를 관리해서 중복 발행을 방지합니다.

**Q. 하루 최대 발행 수는?**
→ 기본 3개 (`team_config.json`에서 `daily_post_per_member` 수정)

**Q. 세션이 만료되면?**
→ 다시 `--qr-login` 실행 (1년에 몇 번 없음)
