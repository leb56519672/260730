import streamlit as st
import pandas as pd
import requests
from datetime import datetime, timedelta
from zoneinfo import ZoneInfo

# 1. 페이지 및 기본 레이아웃 설정
st.set_page_config(page_title="박스오피스 대시보드", layout="wide")
st.title("🎬 기간별 박스오피스 대시보드")

# Secrets에서 KOBIS API 키 불러오기
KOBIS_KEY = st.secrets.get("KOBIS_KEY")

if not KOBIS_KEY:
    st.error("KOBIS_KEY가 설정되지 않았습니다. Streamlit Secrets를 확인해 주세요.")
    st.stop()

# 2. 사이드바: 기간 범위 선택기 (Date Range Input)
st.sidebar.header("🗓️ 조회 옵션")
yesterday_dt = datetime.now(ZoneInfo("Asia/Seoul")) - timedelta(days=1)
default_start_dt = yesterday_dt - timedelta(days=6)  # 기본값: 최근 7일간

# date_input에 튜플을 전달하면 기간 범위 선택 모드가 됩니다.
date_range = st.sidebar.date_input(
    "조회 기간 선택",
    value=(default_start_dt, yesterday_dt),
    max_value=yesterday_dt
)

# 시작일과 종료일이 모두 선택되었는지 확인
if isinstance(date_range, tuple) and len(date_range) == 2:
    start_date, end_date = date_range
else:
    st.info("💡 사이드바에서 종료일을 선택해 주세요.")
    st.stop()

st.caption(f"📌 **조회 기간:** {start_date.strftime('%Y년 %m월 %d일')} ~ {end_date.strftime('%Y년 %m월 %d일')}")

# 3. KOBIS API로 기간 내 일별 데이터 반복 수집 및 합산
@st.cache_data(ttl=3600)
def fetch_box_office_range(start_dt, end_dt, api_key):
    """선택한 기간 동안의 박스오피스 데이터를 일별로 수집하여 합산합니다."""
    current_dt = start_dt
    all_records = []
    
    # 로딩 프로그레스 바
    progress_text = "선택하신 기간의 박스오피스 데이터를 불러오는 중입니다..."
    progress_bar = st.progress(0, text=progress_text)
    total_days = (end_dt - start_dt).days + 1
    
    day_count = 0
    while current_dt <= end_dt:
        target_str = current_dt.strftime("%Y%m%d")
        url = "https://www.kobis.or.kr/kobisopenapi/webservice/rest/boxoffice/searchDailyBoxOfficeList.json"
        
        try:
            res = requests.get(url, params={"key": api_key, "targetDt": target_str}, timeout=10)
            if res.status_code == 200:
                data = res.json()
                if "faultInfo" in data:
                    st.error("인증키가 올바르지 않습니다. KOBIS_KEY를 확인해 주세요.")
                    return None
                
                daily_list = data.get("boxOfficeResult", {}).get("dailyBoxOfficeList", [])
                for item in daily_list:
                    item["date"] = target_str
                    all_records.append(item)
        except Exception as e:
            pass
        
        day_count += 1
        progress_bar.progress(day_count / total_days, text=progress_text)
        current_dt += timedelta(days=1)
        
    progress_bar.empty()
    return pd.DataFrame(all_records)

raw_df = fetch_box_office_range(start_date, end_date, KOBIS_KEY)

if raw_df is None or raw_df.empty:
    st.warning("해당 기간의 박스오피스 데이터가 없습니다. 다른 기간을 선택해 보세요.")
    st.stop()

# 4. 데이터 전처리 및 기간 내 통합 집계
for col in ["audiCnt", "audiAcc", "scrnCnt", "showCnt"]:
    raw_df[col] = pd.to_numeric(raw_df[col])

# 영화별로 그룹화하여 기간 내 total 지표 계산
grouped = raw_df.groupby(["movieCd", "movieNm"]).agg(
    period_audiCnt=("audiCnt", "sum"),       # 기간 내 선택된 일수의 총 관객수
    latest_audiAcc=("audiAcc", "max"),       # 가장 최근 일자의 누적 관객수
    max_scrnCnt=("scrnCnt", "max"),          # 기간 중 최대 스크린수
    openDt=("openDt", "first")               # 개봉일
).reset_index()

# 기간 내 총 관객수 기준으로 순위 재정렬
grouped = grouped.sort_values("period_audiCnt", ascending=False).reset_index(drop=True)
grouped["rank"] = grouped.index + 1

# 5. 상단 기간 내 1위 영화 지표 카드
top = grouped.iloc[0]
c1, c2, c3 = st.columns(3)
c1.metric("기간 내 1위 영화", top["movieNm"])
c2.metric("기간 내 총 관객수", f"{top['period_audiCnt']:,}명")
c3.metric("최신 누적 관객수", f"{top['latest_audiAcc']:,}명")

st.markdown("---")

# 6. 박스오피스 표 데이터 정리 (TOP 10)
table_display = grouped[["rank", "movieNm", "openDt", "period_audiCnt", "latest_audiAcc", "max_scrnCnt"]].head(10).copy()
table_display.columns = ["순위", "영화명", "개봉일", "기간내 관객수", "최신 누적관객", "최대 스크린수"]

st.subheader("📋 선택 기간 박스오피스 TOP 10")
st.dataframe(table_display, use_container_width=True)

# 7. 관객수 상위 5편 차트
st.subheader("📈 기간 내 관객수 상위 5편")
top5 = table_display.head(5)
st.bar_chart(top5.set_index("영화명")["기간내 관객수"])
