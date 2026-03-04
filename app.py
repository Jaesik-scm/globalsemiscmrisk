import streamlit as st
import pandas as pd
from datetime import datetime
from news_fetcher import (
    fetch_news, save_cache, load_cache,
    RISK_COLORS, RISK_SEVERITY
)

# 1. 페이지 설정 및 제목
st.set_page_config(page_title="SCM 리스크 대시보드", layout="wide")
st.title("📡 글로벌 반도체 SCM 리스크 브리핑")

# 2. 사이드바 - 설정 및 필터
st.sidebar.header("⚙️ 설정 및 필터")

if st.sidebar.button("🔄 뉴스 즉시 업데이트"):
    with st.spinner("최신 뉴스를 가져오는 중..."):
        try:
            articles = fetch_news(max_per_feed=5, use_llm=True)
            save_cache(articles)
            st.sidebar.success(f"업데이트 완료! ({len(articles)}건)")
            st.rerun()
        except Exception as e:
            st.sidebar.error(f"오류 발생: {e}")

# 필터 옵션
data = load_cache()
articles = data.get("articles", [])
updated_at = data.get("updated_at", "기록 없음")

st.sidebar.write(f"**최종 업데이트:** {updated_at}")

all_categories = ["전체"] + list(RISK_SEVERITY.keys())
selected_cat = st.sidebar.selectbox("카테고리 필터", all_categories)

all_regions = ["global", "taiwan", "china", "usa", "korea", "japan", "europe"]
selected_region = st.sidebar.selectbox("지역 필터", all_regions)

# 3. 데이터 필터링 로직
filtered_articles = articles
if selected_cat != "전체":
    filtered_articles = [a for a in filtered_articles if a.get("category") == selected_cat]
if selected_region != "global":
    filtered_articles = [a for a in filtered_articles if a.get("region") == selected_region]

# 4. 메인 화면 - 통계 요약 (KPI)
col1, col2, col3 = st.columns(3)
col1.metric("전체 뉴스", f"{len(articles)}건")
col2.metric("필터링된 뉴스", f"{len(filtered_articles)}건")
col3.metric("최고 심각도", f"{max([a.get('severity', 1) for a in filtered_articles] + [1])} / 5")

st.markdown("---")

# 5. 뉴스 목록 출력
if not filtered_articles:
    st.info("해당 조건에 맞는 뉴스가 없습니다.")
else:
    for a in filtered_articles:
        # 심각도에 따른 색상 아이콘 설정
        severity = a.get("severity", 1)
        sev_icon = "🔴" if severity >= 4 else "🟡" if severity >= 3 else "🟢"
        
        with st.container():
            col_main, col_side = st.columns([4, 1])
            
            with col_main:
                st.subheader(f"{sev_icon} {a.get('title', '제목 없음')}")
                st.write(f"**요약:** {a.get('summary', '내용 없음')}")
                st.write(f"**지역:** {a.get('region', 'N/A').upper()} | **카테고리:** {a.get('category', '일반')}")
                
            with col_side:
                st.write(f"**심각도:** {severity}/5")
                if a.get('url'):
                    st.link_button("원문 읽기", a.get('url'))
            
            st.divider()

# Flask 관련 @app.route 코드들은 Streamlit Cloud에서 필요 없으므로 삭제하거나 무시됩니다.
