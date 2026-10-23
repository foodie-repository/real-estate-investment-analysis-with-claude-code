"""실행: uv run streamlit run projects/chapter07_price_gap_table/dashboard/app.py"""
import sys
import math
from pathlib import Path
from datetime import date

ROOT=Path(__file__).resolve().parents[3]
if str(ROOT) not in sys.path: sys.path.insert(0,str(ROOT))
import duckdb
import pyarrow as pa
import pyarrow.compute as pc
import pyarrow.csv as arrow_csv
import streamlit as st
from projects.chapter07_price_gap_table.dashboard.analysis import BANDS, NUMERIC, Query, compare, database_path, filter_sort, inventory, floor_limits, area_limits, lease_label
from projects.chapter07_price_gap_table.dashboard.charts import render_charts
from projects.chapter07_price_gap_table.dashboard.linking import (
    destination_setting, selection_revision, selection_key, target_from_row, render_link,
)

SORT_LABELS = {
    '매매가격':'매매 (억원)', '전세가격':'신규 전세 (억원)', '갭':'갭 (억원)',
    '전세가율':'전세가율 (%)', '매매건수':'매매 건수', '전세건수':'전세 건수',
    '고점년월':'전고점년월', '월중앙값고점':'전고점 (억원)', '고점대비':'전고점 대비 (%)',
    '건축년도':'건축년도', '세대수':'세대수',
}

st.set_page_config(page_title='실거래가 가격·갭 비교',layout='wide')
st.markdown('''<style>
[data-testid="stMainBlockContainer"] { padding-top: 2.75rem; }
/* 캔버스로 그리는 비교표는 글자와 셀을 함께 소폭 축소한다. */
[data-testid="stDataFrame"] { zoom: 0.93; width: 100% !important; }
[data-testid="stSidebar"] [data-testid="stWidgetLabel"] p,
[data-testid="stSidebar"] [data-baseweb="select"],
[data-testid="stSidebar"] [data-baseweb="select"] input,
[data-testid="stSidebar"] [data-baseweb="tag"],
[data-testid="stSidebar"] [data-testid="stNumberInput"] input,
[data-testid="stSidebar"] [data-testid="stRadio"] p,
[data-testid="stSidebar"] [data-testid="stCaptionContainer"] p {
    font-size: 0.8125rem;
}
/* 선택 목록은 사이드바 바깥의 팝업에 렌더링된다. */
/* 가상 목록의 행 위치와 스크롤을 함께 축소하고, 글자 크기는 보정한다. */
body:has([data-testid="stSidebar"] [role="combobox"][aria-expanded="true"])
    [data-testid="stSelectboxVirtualDropdown"] {
    zoom: 0.64;
    width: 100%;
}
body:has([data-testid="stSidebar"] [role="combobox"][aria-expanded="true"])
    :is([role="option"], [role="option"] div) {
    font-size: calc(0.8125rem / 0.64);
    line-height: 1.4;
}
</style>''',unsafe_allow_html=True)
st.title('실거래가 가격·갭 비교')

@st.cache_data(ttl=600)
def load_inventory(path,stamp): return inventory(path)

@st.cache_data(ttl=600,max_entries=12)
def load_table(path,stamp,query): return compare(path,query)

@st.cache_data(ttl=600)
def load_floor_limits(path,stamp): return floor_limits(path)

@st.cache_data(ttl=600,max_entries=12)
def load_area_limits(path,stamp,query): return area_limits(path,query)

def price_range_slider(table,column,label,key):
    low=pc.min(table[column]).as_py()
    high=pc.max(table[column]).as_py()
    if low is None:
        st.caption(f'{label}: 선택 조건에 해당하는 가격 자료가 없습니다.')
        return None,None
    lower=math.floor(low/1000)/10
    upper=max(math.ceil(high/1000)/10,round(lower+0.1,1))
    bounds_key=f'_{key}_bounds'
    if key in st.session_state:
        old_low,old_high=st.session_state[key]
        if ((old_low,old_high)==st.session_state.get(bounds_key)
                or old_high<lower or old_low>upper):
            st.session_state[key]=(lower,upper)
        else:
            st.session_state[key]=(max(old_low,lower),min(old_high,upper))
    st.session_state[bounds_key]=(lower,upper)
    minimum,maximum=st.slider(label,min_value=lower,max_value=upper,
        value=(lower,upper),step=0.1,format='%.1f억원',key=key,
        help='선택한 지역·기간·평형·전용면적·층의 대표가격을 기준으로 비교표와 차트를 함께 필터링합니다.')
    return round(minimum*10000),round(maximum*10000)

path=database_path()
if not path.is_file():
    st.error('DB를 찾을 수 없습니다. 수집한 DB 경로를 GAP_DB_PATH로 지정한 뒤 다시 실행하세요.'); st.stop()
try:
    regions,(first,last)=load_inventory(str(path),path.stat().st_mtime_ns)
except (ValueError,duckdb.Error) as exc:
    st.error(f'데이터 구조를 확인하세요: {exc}'); st.stop()
if not first or not last:
    st.warning('분석 기준에 맞는 매매 또는 전세 자료가 없습니다. 계약 유형과 수집 범위를 확인하세요.'); st.stop()

months=[y*100+m for y in range(first//100,last//100+1) for m in range(1,13) if first<=y*100+m<=last]
today=date.today(); previous=today.year*100+today.month-1 if today.month>1 else (today.year-1)*100+12
end_default=max(first,min(previous,last))
end_idx=months.index(end_default)

with st.sidebar:
    st.header('비교 조건')
    sidos=sorted({r[0] for r in regions})
    selected=st.multiselect('시도',sidos,default=[s for s in ('서울특별시','경기도','인천광역시') if s in sidos],key='sidos')
    options=sorted({r[0]+' '+r[1] for r in regions if not selected or r[0] in selected})
    cities=st.multiselect('시군구',options,key='regions',placeholder='선택하지 않으면 전체')
    dong_options=sorted({' '.join(r) for r in regions if (not selected or r[0] in selected) and (not cities or r[0]+' '+r[1] in cities)})
    dongs=st.multiselect('읍면동',dong_options,key='dongs',placeholder='선택하지 않으면 전체')
    bands=st.multiselect('평형대',BANDS,default=['30평대'],key='bands')
    area_min=area_max=None
    if bands:
        try:
            area_query=Query(first,last,tuple(selected),tuple(cities),tuple(dongs),tuple(bands))
            low,high=load_area_limits(str(path),path.stat().st_mtime_ns,area_query)
        except (ValueError,duckdb.Error) as exc:
            st.error(f'전용면적 정보를 확인하세요: {exc}'); st.stop()
        if low is not None:
            lower=math.floor(low*10)/10
            upper=max(math.ceil(high*10)/10,round(lower+0.1,1))
            band_key=tuple(sorted(bands))
            if st.session_state.get('_area_bands') != band_key:
                st.session_state.pop('area_range',None)
            elif 'area_range' in st.session_state:
                old_low,old_high=st.session_state['area_range']
                if ((old_low,old_high)==st.session_state.get('_area_bounds')
                        or old_high<lower or old_low>upper):
                    st.session_state['area_range']=(lower,upper)
                else:
                    st.session_state['area_range']=(max(old_low,lower),min(old_high,upper))
            st.session_state['_area_bands']=band_key
            st.session_state['_area_bounds']=(lower,upper)
            area_min,area_max=st.slider('전용면적 (㎡)',min_value=lower,max_value=upper,
                value=(lower,upper),step=0.1,format='%.1f',key='area_range',
                help='선택한 평형대 안에서 면적을 좁힙니다. 매매·전세와 과거 고점에 같은 조건을 적용합니다.')
        else:
            st.caption('전용면적 (㎡): 선택한 지역·평형대에 면적 자료가 없습니다.')
            st.session_state.pop('area_range',None)
    else:
        st.session_state.pop('area_range',None)
        st.session_state.pop('_area_bands',None)
    start,end=st.select_slider('기간 (월)',options=months,
        value=(months[max(0,end_idx-2)],end_default),
        format_func=lambda x:f'{x//100}.{x%100:02}',key='period',disabled=len(months)==1)
    lease_name=lease_label(start)
    lease_column=f'{lease_name} (억원)'
    restrict_floor=st.checkbox('층 범위 적용',key='floor_enabled')
    floor_min=floor_max=None
    if restrict_floor:
        try:
            lowest,highest=load_floor_limits(str(path),path.stat().st_mtime_ns)
        except (ValueError,duckdb.Error) as exc:
            st.error(f'층 정보를 확인하세요: {exc}'); st.stop()
        floor_min,floor_max=st.slider('층 범위',min_value=lowest,max_value=highest,
                                     value=(2,100),step=1,format='%d층',key='floor_range')
    filter_controls=st.container()

link_destination=destination_setting()

if not bands:
    st.info('평형대를 하나 이상 선택하세요.'); st.stop()
try:
    query=Query(start,end,tuple(selected),tuple(cities),tuple(dongs),tuple(bands),floor_min,floor_max,
                area_min=area_min,area_max=area_max)
    with st.spinner('같은 주소·평형·기간으로 비교하고 있습니다…'):
        base=load_table(str(path),path.stat().st_mtime_ns,query)
except (ValueError,duckdb.Error) as exc:
    st.error(f'조회 조건과 데이터를 확인하세요: {exc}'); st.stop()

# 가격·건수 필터 이전의 조회 결과로 판단한다. 일부 단지의 전세 누락과 구분한다.
sales_only=base.num_rows>0 and pc.max(base['전세건수']).as_py()==0
lease_metrics=('전세가격','갭','전세가율','전세건수')
if sales_only:
    if '_comparison_controls' not in st.session_state:
        defaults={'min_lease':1,'lease_price_enabled':False,'gap_enabled':False,'gap_min':0.0,'gap_max':5.0,'sort':'고점대비'}
        st.session_state['_comparison_controls']={key:st.session_state.get(key,value) for key,value in defaults.items()}
        if 'lease_range' in st.session_state:
            st.session_state['_comparison_controls']['lease_range']=st.session_state['lease_range']
    st.session_state['min_lease']=0
    st.session_state['lease_price_enabled']=False
    st.session_state['gap_enabled']=False
    if st.session_state.get('sort') in lease_metrics:
        st.session_state['sort']='고점대비'
elif '_comparison_controls' in st.session_state:
    for key,value in st.session_state.pop('_comparison_controls').items():
        st.session_state[key]=value
sort_options=tuple(name for name in NUMERIC if not sales_only or name not in lease_metrics)

with filter_controls:
    st.divider()
    st.subheader('표 정렬·가격 조건')
    sort=st.selectbox('정렬 기준',sort_options,index=sort_options.index('고점대비'),format_func=lambda key: lease_column if key=='전세가격' else SORT_LABELS[key],key='sort')
    descending=st.radio('정렬 방향',['오름차순','내림차순'],horizontal=True,key='direction')=='내림차순'
    restrict_price=st.checkbox('매매가격 범위 적용',key='price_enabled')
    sale_min=sale_max=None
    if restrict_price:
        sale_min,sale_max=price_range_slider(base,'매매가격','매매가격 범위','sale_range')
    restrict_lease_price=st.checkbox('전세가격 범위 적용',key='lease_price_enabled',disabled=sales_only)
    lease_min=lease_max=None
    if restrict_lease_price:
        lease_min,lease_max=price_range_slider(base,'전세가격','전세가격 범위','lease_range')
    restrict_gap=st.checkbox('갭 범위 적용',key='gap_enabled',disabled=sales_only)
    gap_min=gap_max=None
    if restrict_gap:
        gap_min=st.number_input('갭 최소값 (억원)',value=0.0,step=0.5,key='gap_min')*10000
        gap_max=st.number_input('갭 최대값 (억원)',value=5.0,step=0.5,key='gap_max')*10000
    min_sale=st.number_input('최소 매매 건수',min_value=0,value=1,step=1,key='min_sale')
    min_lease=st.number_input(f'최소 {lease_name} 건수',min_value=0,value=0 if sales_only else 1,step=1,key='min_lease',disabled=sales_only)
    st.caption('한쪽 거래만 있는 단지도 보려면 두 최소 건수를 모두 0으로 설정하세요. 다른 필터 조건은 그대로 적용됩니다.')

if (sale_min is not None and sale_min>sale_max) or (gap_min is not None and gap_min>gap_max):
    st.warning('가격 범위의 최소값이 최대값보다 큽니다.'); st.stop()
try:
    result=filter_sort(base,sort=sort,descending=descending,sale_min=sale_min,sale_max=sale_max,lease_min=lease_min,lease_max=lease_max,gap_min=gap_min,gap_max=gap_max,min_sale=min_sale,min_lease=min_lease)
except (ValueError,duckdb.Error) as exc:
    st.error(f'조회 조건과 데이터를 확인하세요: {exc}'); st.stop()

area_summary=', '.join(dongs or cities or selected) or '전국'
missing=result.column('갭').null_count
count_summary=f'표시 {result.num_rows:,}개 / 전체 {base.num_rows:,}개'
if missing: count_summary+=f' · 갭 계산 불가 {missing:,}개'
size_summary=f' · {area_min:.1f}–{area_max:.1f}㎡' if area_min is not None else ''
st.markdown(f'{start//100}년 {start%100}월–{end//100}년 {end%100}월 · {area_summary} · {", ".join(bands)}{size_summary} · **{count_summary}**')
st.caption('매매는 2021.11 이전, 전세는 2021.06 이전의 구분 없는 거래도 포함합니다. 이후에는 중개 매매·신규 전세만 비교합니다. 전고점에도 같은 매매 기준을 적용합니다.')
if sales_only:
    st.info('선택한 지역·기간·평형·전용면적·층 조건에서 비교에 사용할 전세 거래가 없어 매매 정보를 표시합니다. 최소 전세 건수는 0건으로 적용하고 전세가격·갭 필터는 해제했습니다. 전세가격·갭·전세가율은 계산할 수 없어 비워둡니다.')
if end>previous:
    st.warning('진행 중인 달이 포함되어 있습니다. 월별 거래 건수를 완료된 달과 그대로 비교하지 마세요.')
if result.num_rows==0:
    st.info('선택 조건에 해당하는 결과가 없습니다. 기간·지역·가격·최소 거래 건수를 확인하세요.')
else:
    table_tab, chart_tab=st.tabs(['비교표','차트 분석'])
    display_connection=duckdb.connect(':memory:')
    try:
        display_connection.register('r',result)
        display=display_connection.execute(f'''SELECT 시도||' '||시군구 AS 지역,읍면동,단지명,평형대,
          매매가격/10000 AS "매매 (억원)",전세가격/10000 AS "{lease_column}",갭/10000 AS "갭 (억원)",
          전세가율 AS "전세가율 (%)",매매건수 AS "매매 건수",전세건수 AS "전세 건수",
          고점년월 AS 전고점년월,월중앙값고점/10000 AS "전고점 (억원)",고점대비 AS "전고점 대비 (%)",
          건축년도,세대수,주소 FROM r''').fetch_arrow_table()
        # Arrow 결과를 그대로 전달한다. 원천 거래를 Python 행 객체로 펼치지 않는다.
        link_revision=selection_revision(display,(query,str(path),path.stat().st_mtime_ns))
        link_context=dict(area=(area_min,area_max) if area_min is not None else None,
                          period=(start,end),floor=(floor_min,floor_max) if restrict_floor else None,
                          allowed={target_from_row(row) for row in display.select(['지역','읍면동','단지명','주소','평형대']).to_pylist()})
        table_event=table_tab.dataframe(display,key=selection_key('gap_table',link_revision),
            on_select='rerun',selection_mode='multi-row',hide_index=True,use_container_width=True,height=640,column_config={
            name:st.column_config.NumberColumn(name,format='%.2f')
            for name in ('매매 (억원)',lease_column,'갭 (억원)','전세가율 (%)')
        } | {
            '전고점년월':st.column_config.NumberColumn('전고점년월',format='%d',help='월별 매매 중앙값이 가장 높았던 계약년월입니다. 같은 고점이 여러 달이면 가장 최근 월을 표시합니다.'),
            '전고점 (억원)':st.column_config.NumberColumn('전고점 (억원)',format='%.2f',help='조회 종료월까지 기간별 거래 구분 기준을 적용한 매매의 월별 중앙값 중 최고값입니다. 개별 거래 최고가와 다릅니다.'),
            '전고점 대비 (%)':st.column_config.NumberColumn('전고점 대비 (%)',format='%.2f',help='선택 기간의 매매 중앙값 ÷ 전고점 × 100입니다. 80%이면 전고점 가격의 80% 수준이라는 뜻입니다.'),
        })
        with table_tab:
            selected_rows=table_event.selection.rows
            targets=[target_from_row(row) for row in display.take(pa.array(selected_rows,type=pa.int64())).to_pylist()] if selected_rows else []
            render_link(targets,link_destination,link_context,'gap_table')
            st.caption('왼쪽 체크박스로 여러 행을 선택할 수 있습니다. 표 정렬이나 조회 조건을 바꾸면 선택을 다시 확인하세요.')
        buffer=pa.BufferOutputStream()
        arrow_csv.write_csv(result,buffer)
        csv_data=b'\xef\xbb\xbf'+buffer.getvalue().to_pybytes()
        table_tab.download_button('현재 비교표 CSV 저장',csv_data,file_name=f'price_gap_{start}_{end}.csv',mime='text/csv')
    finally: display_connection.close()
    with chart_tab:
        render_charts(display,sales_only=sales_only,link=(link_destination,link_context,link_revision))
with st.expander('계산 기준과 빈칸 읽는 법'):
    st.markdown('''- 매매·전세는 선택 기간의 **중앙값**입니다. 갭은 두 대표가격의 차이이며 **실제 필요자금과 다릅니다**. 종료된 달도 신고·정정으로 수치가 바뀔 수 있습니다.
- 매매: **2021년 11월부터 중개거래만**, 그 이전에는 구분 없는 거래도 포함합니다. 직거래와 취소 거래는 전 기간 제외합니다.
- 전세: **2021년 6월부터 신규 계약만**, 그 이전에는 구분 없는 전세도 포함합니다. 갱신으로 명시된 계약은 전 기간 제외합니다. 구분 항목 제공 이후의 미상 거래는 포함하지 않습니다.
- 2021년 6월 이전이 포함된 기간에는 가격과 건수의 이름을 **전세**로 표시합니다. 과거의 구분 없는 전세를 신규 계약으로 확정한 것은 아니므로 기간을 넘나드는 비교에서는 표본 기준의 차이에 유의하세요.
- 전고점: **종료월까지 기간별 거래 구분 기준을 적용한 매매의 월별 중앙값 중 최고값**입니다. 개별 거래 최고가와 다릅니다. 검증에 필요한 **고점월건수·고점조회시작월은 CSV에 포함**되어 있습니다. 현재 가격과 같은 기간별 매매 기준을 과거 이력에도 적용합니다. 단지별 수집 범위와 거래 유무에 따라 고점 조회 시작월은 다를 수 있습니다.
- 매매·전세가 한쪽만 있으면 갭·전세가율은 빈칸입니다. 다른 기간 가격으로 채우지 않습니다. 선택 조건에 맞는 전세 거래가 전혀 없으면 최소 전세 건수와 전세가격·갭 필터를 자동으로 해제해 매매 정보를 보여줍니다. 전세 거래가 있는 조건으로 돌아오면 기존 적용 설정을 복원합니다.
- 갭을 계산할 수 있는 단지만 보려면 최소 매매 건수와 최소 전세 건수를 각각 1 이상으로 설정하세요. 전체·표시 건수는 단지·평형 단위이며, 전체 건수는 선택한 지역·기간·평형·전용면적·층에 맞는 거래가 한쪽이라도 있는 행의 수입니다.
- 평형대는 전용면적에 0.4를 곱한 추정평형 기준이며, 같은 평형대에도 다른 면적·타입이 섞입니다.
- 전용면적 범위는 선택한 지역·평형대에서 확인되는 전체 기간의 자료를 기준으로 하며, 평형대를 바꾸면 해당 면적 전체 범위로 초기화됩니다. 전용면적·층 조건은 현재 가격과 과거 고점 양쪽에 적용됩니다. 가격·최소 건수 조건은 집계한 표만 걸러냅니다.
- 세대수는 3장에서 수집한 공동주택 정보와 주소·단지명으로 연결합니다. 도로명주소만 있는 자료는 같은 법정동·단지명·건축연도가 일치하고 양쪽 주소 후보가 하나일 때 보완합니다. 연결할 수 없거나 후보가 여러 개면 비워두며, 빈칸은 0세대라는 뜻이 아닙니다.''')
