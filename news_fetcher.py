"""
semiconductor_scm_dashboard / backend / news_fetcher.py
뉴스 수집 · 번역 · SCM 리스크 분류 모듈

의존성:
    pip install requests feedparser python-dotenv

번역: Google 비공식 무료 번역 API (월 한도 없음)
LLM:  Gemini API 키 있으면 자동 활성화, 없으면 키워드+고정문구 사용

사용법:
    python news_fetcher.py              # 번역 + 분류 (LLM 없이 무료)
    python news_fetcher.py --no-llm     # LLM 비활성화 명시
    python news_fetcher.py --max 3      # 피드당 3개 기사만
"""

import json
import os
import re
import hashlib
import time
from datetime import datetime, timezone
from pathlib import Path

import feedparser
import requests
from dotenv import load_dotenv

load_dotenv()

# ─────────────────────────────────────────────
# 설정
# ─────────────────────────────────────────────
DATA_DIR   = Path(__file__).parent.parent / "data"
DATA_DIR.mkdir(exist_ok=True)
CACHE_FILE = DATA_DIR / "news_cache.json"

GEMINI_API_KEY = os.getenv("GEMINI_API_KEY", "")
GEMINI_MODEL   = os.getenv("GEMINI_MODEL", "gemini-2.0-flash-lite")

# ─────────────────────────────────────────────
# RSS 피드 목록 — 글로벌 반도체 공급망 특화
# ─────────────────────────────────────────────
RSS_FEEDS = [
    # 글로벌 종합
    {"url": "https://feeds.reuters.com/reuters/technologyNews",           "source": "Reuters Tech",      "lang": "en"},
    {"url": "https://feeds.reuters.com/reuters/businessNews",             "source": "Reuters Business",  "lang": "en"},
    {"url": "https://rss.nytimes.com/services/xml/rss/nyt/Technology.xml","source": "NYT Tech",          "lang": "en"},
    {"url": "https://feeds.bbci.co.uk/news/technology/rss.xml",          "source": "BBC Tech",          "lang": "en"},
    # 반도체 전문
    {"url": "https://semiengineering.com/feed/",                          "source": "SemiEngineering",   "lang": "en"},
    {"url": "https://www.eetimes.com/feed/",                              "source": "EE Times",          "lang": "en"},
    {"url": "https://www.electronicdesign.com/rss",                       "source": "Electronic Design", "lang": "en"},
    {"url": "https://semiwiki.com/feed/",                                  "source": "SemiWiki",          "lang": "en"},
    # 공급망·물류
    {"url": "https://www.supplychaindive.com/feeds/news/",                "source": "Supply Chain Dive", "lang": "en"},
    {"url": "https://theloadstar.com/feed/",                               "source": "The Loadstar",      "lang": "en"},
    # 지정학·무역
    {"url": "https://feeds.ft.com/rss/home/technology",                   "source": "FT Tech",           "lang": "en"},
    {"url": "https://www.theverge.com/rss/index.xml",                     "source": "The Verge",         "lang": "en"},
    # 한국
    {"url": "https://rss.etnews.com/Section901.xml",                      "source": "전자신문",           "lang": "ko"},
    {"url": "https://feeds.hankyung.com/news/it.xml",                     "source": "한국경제IT",         "lang": "ko"},
    {"url": "https://rss.chosun.com/site/data/rss/rss.xml",               "source": "조선일보",           "lang": "ko"},
]

# ─────────────────────────────────────────────
# SCM 리스크 분류 키워드
# ─────────────────────────────────────────────
RISK_KEYWORDS: dict[str, list[str]] = {
    "자연재해":            ["earthquake","flood","typhoon","hurricane","tsunami","wildfire","volcano",
                           "지진","홍수","태풍","산불","자연재해","기상이변","폭설"],
    "전쟁·분쟁":           ["war","conflict","military","invasion","ukraine","russia","taiwan strait",
                           "north korea","missile","전쟁","분쟁","군사","침공","긴장","북한","미사일"],
    "관세·무역정책":       ["tariff","trade war","sanction","export control","import ban","chip act",
                           "chips act","itar","ear","관세","무역전쟁","제재","수출규제","수입금지","반도체법"],
    "수출입 이슈":         ["export","import","customs","border","logistics","shipping delay","clearance",
                           "수출","수입","통관","항만","물류지연","세관"],
    "물동량 이슈":         ["freight","container","port congestion","shipping","vessel","bulk carrier",
                           "suez","panama","홍해","화물","컨테이너","항만적체","선박","운임","수에즈","파나마"],
    "공급 부족(Shortage)": ["shortage","supply crunch","capacity","wafer","chip shortage","lead time",
                           "allocation","부족","공급난","생산능력","웨이퍼","반도체 부족","리드타임","할당"],
    "가격 급변":           ["price surge","price hike","spike","inflation","cost increase","price drop",
                           "price cut","가격급등","가격급락","인상","인하","원가","급등","급락"],
    "공장·생산 이슈":      ["factory fire","plant shutdown","fab","production halt","yield","outage",
                           "maintenance","공장화재","생산중단","팹","수율","가동중단","정기보수"],
}

# ─────────────────────────────────────────────
# 지역 태깅 키워드 (지도 필터 연동)
# ─────────────────────────────────────────────
REGION_KEYWORDS: dict[str, list[str]] = {
    "taiwan":  ["taiwan","tsmc","hsinchu","tainan","대만","타이완"],
    "china":   ["china","chinese","beijing","shanghai","shenzhen","huawei","smic","중국","화웨이"],
    "usa":     ["united states","u.s.","america","washington","silicon valley",
                "intel","qualcomm","nvidia","미국","실리콘밸리","인텔","퀄컴","엔비디아"],
    "korea":   ["korea","korean","samsung","sk hynix","seoul","한국","삼성","SK하이닉스","서울"],
    "japan":   ["japan","japanese","tokyo","osaka","renesas","kioxia","일본","도쿄","르네사스","키옥시아"],
    "europe":  ["europe","european","asml","netherlands","germany","dutch","유럽","네덜란드","독일","ASML"],
    "mideast": ["red sea","suez","houthi","gulf","홍해","수에즈","후티","중동","걸프"],
    "sea":     ["southeast asia","vietnam","malaysia","thailand","philippines",
                "동남아","베트남","말레이시아","태국"],
}

# ─────────────────────────────────────────────
# 카테고리 메타데이터
# ─────────────────────────────────────────────
RISK_COLORS: dict[str, str] = {
    "자연재해":            "#ff3b5c",
    "전쟁·분쟁":           "#c0392b",
    "관세·무역정책":       "#f59e0b",
    "수출입 이슈":         "#f39c12",
    "물동량 이슈":         "#3b82f6",
    "공급 부족(Shortage)": "#8b5cf6",
    "가격 급변":           "#10b981",
    "공장·생산 이슈":      "#f97316",
    "일반":                "#4a6585",
}

RISK_SEVERITY: dict[str, int] = {
    "자연재해":            5,
    "전쟁·분쟁":           5,
    "관세·무역정책":       4,
    "수출입 이슈":         3,
    "물동량 이슈":         3,
    "공급 부족(Shortage)": 4,
    "가격 급변":           4,
    "공장·생산 이슈":      4,
    "일반":                1,
}

RISK_IMPACT_TEMPLATES: dict[str, str] = {
    "자연재해":            "생산거점 및 물류 경로 피해 가능성 점검 필요. 대체 소싱 및 재고 버퍼 확보 여부를 즉시 확인하십시오.",
    "전쟁·분쟁":           "분쟁 지역 관련 소재·부품 조달 경로 재검토 필요. 지정학적 리스크에 따른 공급망 다변화 방안을 수립하십시오.",
    "관세·무역정책":       "수출입 원가 구조 변동 가능성 검토 필요. 관세 영향 품목 리스트 업데이트 및 대응 전략을 수립하십시오.",
    "수출입 이슈":         "통관 및 물류 지연에 따른 납기 리스크 점검 필요. 주요 협력사 재고 현황 및 대체 경로를 확인하십시오.",
    "물동량 이슈":         "운임 상승 및 운송 지연에 따른 조달 일정 재검토 필요. 해상·항공 대체 운송 수단 가용성을 점검하십시오.",
    "공급 부족(Shortage)": "핵심 부품 공급 부족 심화 가능성 대비 필요. 장기 공급 계약(LTA) 협상 및 안전재고 수준을 재검토하십시오.",
    "가격 급변":           "원자재·부품 가격 변동에 따른 BOM 원가 영향 분석 필요. 구매 계약 조건 및 헤징 전략을 즉시 검토하십시오.",
    "공장·생산 이슈":      "주요 공급사 생산 차질 가능성 모니터링 필요. 2차 공급사 가용성 및 비상 조달 계획을 점검하십시오.",
    "일반":                "반도체 공급망 관련 동향을 지속 모니터링하고, 관련 부서와 정보를 공유하십시오.",
}


# ─────────────────────────────────────────────
# 번역 (Google 무료 비공식 API)
# ─────────────────────────────────────────────
def _translate_to_ko(text: str) -> str:
    """영어 → 한국어. 실패 시 원문 반환."""
    if not text or not text.strip():
        return text
    try:
        resp = requests.get(
            "https://translate.googleapis.com/translate_a/single",
            params={"client": "gtx", "sl": "en", "tl": "ko", "dt": "t", "q": text[:500]},
            timeout=8,
        )
        resp.raise_for_status()
        translated = "".join(part[0] for part in resp.json()[0] if part[0])
        return translated.strip() if translated else text
    except Exception:
        return text


# ─────────────────────────────────────────────
# 분류 유틸
# ─────────────────────────────────────────────
def _uid(url: str) -> str:
    return hashlib.md5(url.encode()).hexdigest()[:12]


def _classify_keyword(title: str, summary: str) -> str:
    """키워드 기반 카테고리 분류."""
    text = (title + " " + summary).lower()
    for category, keywords in RISK_KEYWORDS.items():
        for kw in keywords:
            if kw.lower() in text:
                return category
    return "일반"


def _detect_region(title: str, content: str) -> str:
    """뉴스 본문에서 지역 태그 추출 (첫 번째 매칭)."""
    text = (title + " " + content).lower()
    for region, keywords in REGION_KEYWORDS.items():
        for kw in keywords:
            if kw.lower() in text:
                return region
    return "global"


# ─────────────────────────────────────────────
# Gemini (선택 — 키 있을 때만 활성화)
# ─────────────────────────────────────────────
def _build_prompt(title_ko: str, content_ko: str) -> str:
    categories = list(RISK_KEYWORDS.keys()) + ["일반"]
    return f"""당신은 반도체 공급망(SCM) 전문 애널리스트입니다.
아래 뉴스를 읽고 JSON으로만 답하세요. 다른 텍스트 없이 JSON만 출력하세요.

제목: {title_ko}
내용: {content_ko[:600]}

{{
  "summary_ko": "경영진을 위한 3문장 이내 핵심 요약",
  "category": "<분류>",
  "impact": "SCM 책임자 관점 즉각 조치 사항 1~2문장"
}}

분류 선택지: {categories}"""


def _call_gemini(prompt: str) -> dict | None:
    if not GEMINI_API_KEY:
        return None
    url = (
        f"https://generativelanguage.googleapis.com/v1beta/models/"
        f"{GEMINI_MODEL}:generateContent?key={GEMINI_API_KEY}"
    )
    try:
        resp = requests.post(
            url,
            json={
                "contents": [{"role": "user", "parts": [{"text": prompt}]}],
                "generationConfig": {"temperature": 0.2, "maxOutputTokens": 400},
            },
            timeout=20,
        )
        resp.raise_for_status()
        raw = resp.json()["candidates"][0]["content"]["parts"][0]["text"]
        raw = re.sub(r"```(?:json)?", "", raw).strip().rstrip("`").strip()
        m = re.search(r"\{.*\}", raw, re.DOTALL)
        if m:
            return json.loads(m.group())
    except Exception as e:
        print(f"  [Gemini 오류] {e}")
    return None


# ─────────────────────────────────────────────
# 메인 수집 함수
# ─────────────────────────────────────────────
def fetch_news(max_per_feed: int = 10, use_llm: bool = True) -> list[dict]:
    llm_active = use_llm and bool(GEMINI_API_KEY)
    print(f"[모드] 번역=Google무료 | LLM={'Gemini 활성' if llm_active else '비활성(키워드 분류)'}")

    articles: list[dict] = []

    for feed_cfg in RSS_FEEDS:
        print(f"[수집] {feed_cfg['source']} ...")
        try:
            feed = feedparser.parse(feed_cfg["url"])
        except Exception as e:
            print(f"  ⚠ 피드 오류: {e}")
            continue

        is_english = feed_cfg.get("lang", "en") == "en"

        for entry in feed.entries[:max_per_feed]:
            title   = entry.get("title", "").strip()
            link    = entry.get("link", "")
            content = entry.get("summary", entry.get("description", ""))
            content = re.sub(r"<[^>]+>", " ", content)
            content = re.sub(r"\s+", " ", content).strip()

            # 날짜 파싱
            try:
                pub_dt  = datetime(*entry.published_parsed[:6], tzinfo=timezone.utc)
                pub_str = pub_dt.strftime("%Y-%m-%d %H:%M")
            except Exception:
                pub_str = datetime.now().strftime("%Y-%m-%d %H:%M")

            # 번역 (영어 피드만)
            if is_english:
                title_ko   = _translate_to_ko(title)
                content_ko = _translate_to_ko(content[:400])
                time.sleep(0.3)   # rate limit 방지
            else:
                title_ko   = title
                content_ko = content[:400]

            # 분류 & 요약
            if llm_active:
                result = _call_gemini(_build_prompt(title_ko, content_ko))
                if result:
                    valid = set(RISK_KEYWORDS.keys()) | {"일반"}
                    if result.get("category") not in valid:
                        result["category"] = _classify_keyword(title, content)
                    cat     = result.get("category", "일반")
                    summary = result.get("summary_ko", content_ko[:150] + "...")
                    impact  = result.get("impact", RISK_IMPACT_TEMPLATES.get(cat, ""))
                else:
                    cat     = _classify_keyword(title, content)
                    summary = content_ko[:150] + "..."
                    impact  = RISK_IMPACT_TEMPLATES.get(cat, "")
            else:
                cat     = _classify_keyword(title, content)
                summary = content_ko[:150] + "..."
                impact  = RISK_IMPACT_TEMPLATES.get(cat, "")

            articles.append({
                "id":         _uid(link),
                "title":      title_ko,
                "title_orig": title,
                "source":     feed_cfg["source"],
                "url":        link,
                "published":  pub_str,
                "summary_ko": summary,
                "category":   cat,
                "impact":     impact,
                "severity":   RISK_SEVERITY.get(cat, 1),
                "color":      RISK_COLORS.get(cat, "#4a6585"),
                "region":     _detect_region(title, content),
            })

    articles.sort(key=lambda x: x["published"], reverse=True)
    return articles


# ─────────────────────────────────────────────
# 캐시 I/O
# ─────────────────────────────────────────────
def save_cache(articles: list[dict]) -> None:
    payload = {
        "updated_at": datetime.now().strftime("%Y-%m-%d %H:%M"),
        "total":      len(articles),
        "articles":   articles,
    }
    CACHE_FILE.write_text(json.dumps(payload, ensure_ascii=False, indent=2), encoding="utf-8")
    print(f"[저장] {CACHE_FILE} ({len(articles)}건)")


def load_cache() -> dict:
    if CACHE_FILE.exists():
        return json.loads(CACHE_FILE.read_text(encoding="utf-8"))
    return {"updated_at": "", "total": 0, "articles": []}


# ─────────────────────────────────────────────
# CLI
# ─────────────────────────────────────────────
if __name__ == "__main__":
    import argparse
    parser = argparse.ArgumentParser(description="반도체 SCM 뉴스 수집기")
    parser.add_argument("--no-llm", action="store_true", help="LLM 비활성화 (키워드 분류만)")
    parser.add_argument("--max",    type=int, default=5, help="피드당 최대 기사 수")
    args = parser.parse_args()
    news = fetch_news(max_per_feed=args.max, use_llm=not args.no_llm)
    save_cache(news)
    print(f"\n✅ 완료: {len(news)}건 수집")
