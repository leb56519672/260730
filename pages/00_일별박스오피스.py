import streamlit as st
import pandas as pd
import requests
from datetime import datetime, timedelta
from zoneinfo import ZoneInfo

# 1. 페이지 및 기본 레이아웃 설정
st.set_page_config(page_title="박스오피스 대시보드", layout="wide")
st.title("🎬 박스오피스 대시보드")

# Secrets에서 KOBIS API 키 불러오기
KOBIS_KEY = st.secrets.get("KOBIS_KEY")

if not KOBIS_KEY:
    st.error("KOBIS_KEY가 설정되지 않았습니다. Streamlit Secrets를 확인해 주세요.")
    st.stop()

# 2. 사이드바: 날짜 선택기 기능 구현
st.sidebar.header("🗓️ 조회 옵션")
yesterday_dt = datetime.now(ZoneInfo("Asia/Seoul")) - timedelta(days=1)

selected_date = st.sidebar.date_input(
    "조회 날짜 선택",
    value=yesterday_dt,
    max_value=yesterday_dt
)

target_dt = selected_date.strftime("%Y%m%d")
formatted_date = selected_date.strftime("%Y년 %m월 %d일")
st.caption(f"📌 **조회 기준일:** {formatted_date}")

# 3. KOBIS 일별 박스오피스 데이터 수집
kobis_url = "https://www.kobis.or.kr/kobisopenapi/webservice/rest/boxoffice/searchDailyBoxOfficeList.json"
res = requests.get(kobis_url, params={"key": KOBIS_KEY, "targetDt": target_dt}, timeout=10)

if res.status_code != 200:
    st.error(f"요청이 실패했습니다 (상태코드: {res.status_code})")
    st.stop()

data = res.json()

if "faultInfo" in data:
    st.error("인증키가 올바르지 않습니다. 금고(Secrets)의 KOBIS_KEY를 확인해 주세요.")
    st.stop()

box_list = data.get("boxOfficeResult", {}).get("dailyBoxOfficeList", [])
if not box_list:
    st.warning("해당 일자의 박스오피스 데이터가 없습니다. 다른 날짜를 선택해 보세요.")
    st.stop()

df = pd.DataFrame(box_list)

# 숫자형 칼럼 캐스팅 (순위 변동값 rankInten 포함)
for col in ["rank", "audiCnt", "audiAcc", "scrnCnt", "showCnt", "rankInten"]:
    df[col] = pd.to_numeric(df[col])

# 4. 상단 1위 영화 지표 카드 (순위 변동 delta 반영)
top = df.sort_values("rank").iloc[0]

# 순위 변동 레이블 생성 (1위 카드용)
if top["rankOldAndNew"] == "NEW":
    rank_delta = "🆕 NEW"
else:
    inten = top["rankInten"]
    rank_delta = f"{inten:+d}위" if inten != 0 else "변동 없음"

c1, c2, c3 = st.columns(3)
c1.metric("1위 영화", top["movieNm"], delta=rank_delta)
c2.metric("당일 관객수", f"{top['audiCnt']:,}명")
c3.metric("누적 관객수", f"{top['audiAcc']:,}명")

st.markdown("---")

# 5. 박스오피스 표 데이터 정리 & 변동사항 표기
table = df[["rank", "rankOldAndNew", "rankInten", "movieNm", "openDt", "audiCnt", "audiAcc", "scrnCnt"]].copy()

# 표에 표시할 변동 문자열 생성 함수
def format_rank_change(row):
    if row["rankOldAndNew"] == "NEW":
        return "🆕 NEW"
    inten = row["rankInten"]
    if inten > 0:
        return f"▲ {inten}"
    elif inten < 0:
        return f"▼ {abs(inten)}"
    return "-"

table["순위변동"] = table.apply(format_rank_change, axis=1)

# 보기 좋게 칼럼 구성 및 이름 변경
table_display = table[["rank", "순위변동", "movieNm", "openDt", "audiCnt", "audiAcc", "scrnCnt"]].copy()
table_display.columns = ["순위", "변동", "영화명", "개봉일", "관객수", "누적관객", "스크린수"]
table_display = table_display.sort_values("순위").reset_index(drop=True)

st.subheader("📋 일별 박스오피스 TOP 10")
st.dataframe(table_display, use_container_width=True)

# 6. 관객수 상위 5편 차트
st.subheader("📈 관객수 상위 5편")
top5 = table_display.sort_values("관객수", ascending=False).head(5)
st.bar_chart(top5.set_index("영화명")["관객수"])
