import streamlit as st
import streamlit.components.v1 as components
import os

# 1. 화면 설정 (반드시 모든 st 함수 중 가장 위에 와야 함)
st.set_page_config(page_title="SCM 리스크 대시보드", layout="wide")

# 2. 여백 제거 (지도를 화면에 꽉 채우기 위함)
st.markdown("""
    <style>
    .main .block-container {
        padding: 0rem !important;
    }
    iframe {
        width: 100vw !important;
        height: 100vh !important;
    }
    </style>
    """, unsafe_allow_html=True)

# 3. HTML 출력
try:
    # 파일이 있는지 먼저 확인 (안전장치)
    if os.path.exists("index.html"):
        with open("index.html", "r", encoding="utf-8") as f:
            html_content = f.read()
        
        # 높이를 100vh(화면 꽉 차게) 혹은 고정 숫자로 설정
        components.html(html_content, height=1200, scrolling=True)
    else:
        st.error("index.html 파일을 찾을 수 없습니다. 파일 이름을 확인해 주세요.")

except Exception as e:
    st.error(f"에러 발생: {e}")

# 4. 여기서 실행 중단 (아래의 Flask 코드 실행 방지)
st.stop()

# --- 이 아래로는 기존 소스가 있어도 상관없습니다 ---

import streamlit as st
import streamlit.components.v1 as components

# index.html 파일을 읽어서 화면에 뿌려줍니다.
try:
    with open("index.html", "r", encoding="utf-8") as f:
        html_code = f.read()
    components.html(html_code, height=1200, scrolling=True)
except Exception as e:
    st.error(f"index.html 파일을 읽을 수 없습니다: {e}")

# 중요: 여기서 멈춰야 아래에 있는 무한대기 소스까지 내려가지 않습니다.
st.stop()

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
# 진입점 (Streamlit 배포용 수정)
# ─────────────────────────────────────────────
import streamlit as st
import streamlit.components.v1 as components

# 1. 화면 설정
st.set_page_config(page_title="SCM 리스크 대시보드", layout="wide")

# 2. 기획하신 index.html 파일 읽기
try:
    # app.py와 같은 위치에 있는 index.html을 읽습니다.
    with open("index.html", "r", encoding="utf-8") as f:
        html_content = f.read()
    
    # 3. HTML 화면 출력 (높이는 대시보드 길이에 맞춰 조정 가능)
    components.html(html_content, height=1200, scrolling=True)

except Exception as e:
    st.error(f"index.html 파일을 찾을 수 없거나 읽는데 실패했습니다: {e}")

# 4. 중요: Streamlit은 여기서 실행을 멈춰야 합니다.
# 아래의 app.run()이 실행되면 서버가 무한 루프에 빠집니다.
if __name__ == "__main__":
    # 로컬 테스트용 출력은 남겨두되, 실제 서버 실행(app.run)은 하지 않습니다.
    print("Streamlit 환경에서 대시보드가 실행 중입니다.")
    # app.run(debug=True, port=5000, use_reloader=False) # 이 줄은 절대 실행되면 안 됨
    
import streamlit as st
import streamlit.components.v1 as components

# 1. 같은 위치에 있는 index.html 파일을 읽어옵니다
with open("index.html", "r", encoding="utf-8") as f:
    html_code = f.read()

# 2. 그 HTML을 화면에 꽉 차게 보여줍니다
components.html(html_code, height=1000, scrolling=True)

# 3. 중요: 아래의 Flask 코드들이 실행되지 않도록 여기서 멈춥니다
st.stop()
