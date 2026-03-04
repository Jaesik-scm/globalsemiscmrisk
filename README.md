# 글로벌 반도체 SCM 리스크 브리핑 대시보드
### MVP v2.0 — 다크 네이비 · 인터랙티브 지도 · 지역 클릭 필터

---

## 📁 프로젝트 구조

```
semiconductor-scm-dashboard/
├── backend/
│   ├── app.py              # Flask 웹 서버 (API + 스케줄러)
│   └── news_fetcher.py     # 뉴스 수집 · 번역 · 분류 모듈
├── frontend/
│   └── index.html          # 대시보드 UI (단일 파일)
├── data/
│   └── news_cache.json     # 수집된 뉴스 캐시 (자동 생성)
├── requirements.txt
└── .env                    # API 키 (선택, 직접 생성)
```

---

## ⚡ 빠른 시작

### 1. 패키지 설치
```powershell
pip install -r requirements.txt
```

### 2. (선택) .env 파일 생성 — Gemini LLM 요약 사용 시
```
GEMINI_API_KEY=your_key_here
GEMINI_MODEL=gemini-2.0-flash-lite
```
> 키 없으면 키워드 분류+고정 시사점으로 자동 대체됩니다.

### 3-A. 뉴스 먼저 수집 (테스트 권장)
```powershell
cd backend
python news_fetcher.py --no-llm --max 3
```

### 3-B. 서버 실행
```powershell
cd backend
python app.py
```

### 4. 브라우저 접속
```
http://localhost:5000
```

> 서버 없이 `index.html`을 직접 브라우저에서 열면 **데모 모드(목업 데이터)**로 동작합니다.

---

## 🔌 API 엔드포인트

| Method | Path | 설명 |
|--------|------|------|
| GET | `/api/news` | 뉴스 목록. `?category=관세·무역정책&severity=4&region=taiwan` 필터 지원 |
| GET | `/api/stats` | KPI·카테고리·심각도·소스·지역 통계 |
| GET | `/api/categories` | 카테고리 목록·색상·심각도 |
| POST | `/api/refresh` | 수동 뉴스 갱신 |

---

## 🖥 화면 구성

| 섹션 | 기능 |
|------|------|
| **상단 Topbar** | Critical/High/Total 실시간 카운터, 시계, 업데이트 시각 |
| **긴급 배너** | 심각도 5 뉴스 자동 표시 — 클릭 시 해당 뉴스 카드로 스크롤 |
| **KPI 카드** | Critical/High/Medium/Total — 클릭 시 해당 심각도 필터 |
| **카테고리 바** | 카테고리별 건수 시각화 |
| **리스크 레이더** | 7개 카테고리 레이더 차트 |
| **글로벌 지도** | D3.js 실제 세계지도 + 지역별 리스크 핀 (파동 애니메이션) |
| **지역 그리드** | 8개 지역 클릭 → 해당 국가 뉴스 필터링 |
| **타임라인** | 최신 15건 목록 — 클릭 시 카드로 이동 |
| **뉴스 카드** | 카테고리·지역 뱃지, 심각도 pip, 원문 링크 |

---

## 📡 RSS 피드 소스 (16개)

| 분류 | 소스 |
|------|------|
| 글로벌 종합 | Reuters Tech, Reuters Business, NYT Tech, BBC Tech |
| 반도체 전문 | SemiEngineering, EE Times, Electronic Design, SemiWiki |
| 공급망·물류 | Supply Chain Dive, The Loadstar |
| 지정학·무역 | FT Tech, The Verge |
| 한국 | 전자신문, 한국경제IT, 조선일보 |

---

## 🗺 지역 태깅 체계

| 지역 ID | 국가/지역 | 주요 키워드 |
|---------|-----------|------------|
| `taiwan` | 대만 | TSMC, 신주, 타이난 |
| `china` | 중국 | Huawei, SMIC, 베이징 |
| `usa` | 미국 | Intel, NVIDIA, CHIPS법 |
| `korea` | 한국 | 삼성, SK하이닉스 |
| `japan` | 일본 | Renesas, Kioxia |
| `europe` | 유럽 | ASML, 네덜란드, 독일 |
| `mideast` | 중동·홍해 | 홍해, 후티, 수에즈 |
| `sea` | 동남아 | 베트남, 말레이시아 |

---

## 🧩 SCM 리스크 분류 체계

| 카테고리 | 심각도 | 주요 키워드 |
|---------|--------|------------|
| 자연재해 | ★★★★★ | 지진, 홍수, 태풍, 산불 |
| 전쟁·분쟁 | ★★★★★ | 전쟁, 침공, 군사 긴장, 북한 |
| 관세·무역정책 | ★★★★ | 관세, 수출규제, 제재, CHIPS법 |
| 공급 부족 | ★★★★ | 부족, 공급난, 웨이퍼, 리드타임 |
| 가격 급변 | ★★★★ | 가격급등, 원가 상승, 급락 |
| 공장·생산 이슈 | ★★★★ | 공장화재, 생산 중단, 팹, 수율 |
| 수출입 이슈 | ★★★ | 통관, 물류 지연, 세관 |
| 물동량 이슈 | ★★★ | 운임, 컨테이너, 홍해, 수에즈 |
| 일반 | ★ | 기타 |

---

## 🗺 로드맵

### Phase 2 — 데이터 강화
- [ ] SQLite 히스토리 저장 + 트렌드 차트
- [ ] Bloomberg/Naver 뉴스 API 추가
- [ ] 지역별 리스크 점수 자동 산출

### Phase 3 — 분석 심화
- [ ] 주간 SCM 리스크 리포트 자동 생성 (PDF)
- [ ] 이메일/Slack 알림 (심각도 5 즉시 발송)
- [ ] 리스크 트렌드 예측

### Phase 4 — 운영
- [ ] 사용자 인증 (임원별 접근 권한)
- [ ] Docker 배포
- [ ] 모바일 PWA 지원
