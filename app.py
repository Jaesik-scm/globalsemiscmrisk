"""
semiconductor_scm_dashboard / backend / app.py
Flask 웹 서버 — API + 프론트엔드 정적 서빙 + 스케줄러

의존성:
    pip install flask flask-cors apscheduler

실행:
    cd backend
    python app.py
    → http://localhost:5000
"""

import json
from pathlib import Path
from datetime import datetime

from flask import Flask, jsonify, send_from_directory, request
from flask_cors import CORS
from apscheduler.schedulers.background import BackgroundScheduler

from news_fetcher import (
    fetch_news, save_cache, load_cache,
    RISK_COLORS, RISK_SEVERITY,
)

# ─────────────────────────────────────────────
app = Flask(
    __name__,
    static_folder=str(Path(__file__).parent.parent / "frontend"),
    static_url_path="",
)
CORS(app)


# ─────────────────────────────────────────────
# 스케줄러: 1시간마다 자동 수집
# ─────────────────────────────────────────────
def scheduled_fetch():
    print(f"[{datetime.now():%H:%M}] 자동 수집 시작...")
    try:
        articles = fetch_news(max_per_feed=5, use_llm=True)
        save_cache(articles)
        print(f"[{datetime.now():%H:%M}] 자동 수집 완료 — {len(articles)}건")
    except Exception as e:
        print(f"  ⚠ 자동 수집 오류: {e}")


scheduler = BackgroundScheduler(timezone="Asia/Seoul")
scheduler.add_job(scheduled_fetch, "interval", hours=1, id="news_fetch")
scheduler.start()


# ─────────────────────────────────────────────
# API
# ─────────────────────────────────────────────
@app.route("/api/news")
def api_news():
    """뉴스 목록 반환.
    Query params:
        category  — 카테고리 필터 (예: 관세·무역정책)
        severity  — 최소 심각도 (1~5)
        region    — 지역 필터 (taiwan, china, usa, korea, japan, europe, mideast, sea, global)
    """
    data     = load_cache()
    articles = data.get("articles", [])

    cat    = request.args.get("category")
    sev    = request.args.get("severity")
    region = request.args.get("region")

    if cat and cat != "전체":
        articles = [a for a in articles if a.get("category") == cat]
    if sev:
        try:
            min_sev  = int(sev)
            articles = [a for a in articles if a.get("severity", 1) >= min_sev]
        except ValueError:
            pass
    if region and region != "global":
        articles = [a for a in articles if a.get("region") == region]

    return jsonify({
        "updated_at": data.get("updated_at", ""),
        "total":      len(articles),
        "articles":   articles,
    })


@app.route("/api/stats")
def api_stats():
    """통계 반환 (KPI·카테고리·심각도·소스·지역 분포)."""
    data     = load_cache()
    articles = data.get("articles", [])

    category_count: dict[str, int] = {}
    severity_dist:  dict[str, int] = {"1": 0, "2": 0, "3": 0, "4": 0, "5": 0}
    source_count:   dict[str, int] = {}
    region_count:   dict[str, int] = {}

    for a in articles:
        cat = a.get("category", "일반")
        category_count[cat] = category_count.get(cat, 0) + 1

        sev = str(a.get("severity", 1))
        severity_dist[sev] = severity_dist.get(sev, 0) + 1

        src = a.get("source", "Unknown")
        source_count[src] = source_count.get(src, 0) + 1

        reg = a.get("region", "global")
        region_count[reg] = region_count.get(reg, 0) + 1

    return jsonify({
        "updated_at":     data.get("updated_at", ""),
        "total":          len(articles),
        "category_count": category_count,
        "category_colors": RISK_COLORS,
        "severity_dist":  severity_dist,
        "source_count":   source_count,
        "region_count":   region_count,
    })


@app.route("/api/categories")
def api_categories():
    """카테고리 목록 + 색상 + 심각도 반환."""
    return jsonify({
        "categories": ["전체"] + list(RISK_SEVERITY.keys()),
        "colors":     RISK_COLORS,
        "severity":   RISK_SEVERITY,
    })


@app.route("/api/refresh", methods=["POST"])
def api_refresh():
    """수동 갱신 트리거."""
    try:
        articles = fetch_news(max_per_feed=5, use_llm=True)
        save_cache(articles)
        return jsonify({"status": "ok", "count": len(articles)})
    except Exception as e:
        return jsonify({"status": "error", "message": str(e)}), 500


# ─────────────────────────────────────────────
# 프론트엔드 서빙
# ─────────────────────────────────────────────
@app.route("/")
def index():
    return send_from_directory(app.static_folder, "index.html")


# ─────────────────────────────────────────────
# 진입점
# ─────────────────────────────────────────────
if __name__ == "__main__":
    print("=" * 52)
    print("  글로벌 반도체 SCM 리스크 브리핑 대시보드")
    print("  http://localhost:5000")
    print("=" * 52)

    # 캐시 없으면 시작 시 1회 수집
    if not load_cache()["articles"]:
        print("[초기화] 뉴스 최초 수집 중...")
        scheduled_fetch()

    app.run(debug=True, port=5000, use_reloader=False)
