"""연결로 열었을 때의 대상 선택과 적용 조건 안내."""
import math

import streamlit as st

from src.utils.dashboard_link import target_label
from projects.chapter09_price_volume.dashboard.linked import linked_bounds


@st.cache_data(ttl=600, max_entries=24)
def _bounds(path, stamp, targets):
    return linked_bounds(path, targets)


def linked_sidebar(payload, token, path):
    if st.session_state.get('_link_token') != token:
        for key in list(st.session_state):
            if key.startswith('linked_'):
                del st.session_state[key]
        st.session_state['_link_token'] = token
        st.session_state['linked_targets'] = payload['targets']
        if payload['area'] is not None:
            st.session_state['linked_area'] = payload['area']
    with st.sidebar:
        st.header('연결된 비교 대상')
        if st.button('연결 해제 · 직접 조회', key='linked_release'):
            st.query_params.pop('selection', None)
            st.session_state.pop('_link_token', None)
            st.rerun()
        targets = st.multiselect('단지·평형대', payload['targets'], key='linked_targets',
                                format_func=lambda target: target_label(target, payload['targets']),
                                help='주소와 평형대가 묶인 대상입니다. 연결을 해제하면 다른 지역·단지를 직접 조회할 수 있습니다.')
        if not targets:
            st.info('연결된 대상을 하나 이상 선택하세요.')
            st.stop()
        first, last, low, high = _bounds(str(path),path.stat().st_mtime_ns,tuple(targets))
        if first is None:
            st.warning('이 DB에 선택한 주소·단지·평형대의 거래가 없습니다. 두 대시보드의 DB와 수집 범위를 확인하세요.')
            st.stop()
        requested = payload['area']
        lower = math.floor(min(low, requested[0] if requested else low)*10)/10
        upper = max(math.ceil(max(high, requested[1] if requested else high)*10)/10, lower+0.1)
        old = st.session_state.get('linked_area', (lower, upper))
        # 선택을 줄여도 전달된 면적을 넓혀서 조회하지 않는다.
        lower, upper = min(lower,old[0]), max(upper,old[1])
        st.session_state.setdefault('linked_area', (lower,upper))
        area = st.slider('전용면적 (㎡)', lower, upper, step=0.1, key='linked_area')
        trade_type = st.radio('거래유형', ['매매+전세','매매만','전세만'], key='linked_trade_type')
        min_year, max_year = first//100, last//100
        if min_year == max_year:
            years = (min_year,max_year)
            st.caption(f'기간 (연도): {min_year}년')
        else:
            old_years = st.session_state.get('linked_years', (min_year,max_year))
            if old_years[1] < min_year or old_years[0] > max_year:
                st.session_state['linked_years']=(min_year,max_year)
            else:
                st.session_state['linked_years']=(max(old_years[0],min_year),min(old_years[1],max_year))
            years = st.slider('기간 (연도)', min_year,max_year,key='linked_years')
        direct = st.checkbox('직거래 포함', key='linked_direct')
    st.caption(f'가격·갭 비교에서 연결한 대상 {len(targets)}개 · 주소·단지·평형대와 전용면적 범위를 적용합니다.')
    period = payload['period']
    source = f"출발 비교 기간 {period[0]//100}.{period[0]%100:02}–{period[1]//100}.{period[1]%100:02}. " if period else ''
    floor = payload['floor']
    floor_note = f'출발 화면의 {floor[0]:g}–{floor[1]:g}층 제한은 여기에서 적용하지 않습니다. ' if floor else ''
    st.caption(source+f'현재 조회 기간 {years[0]}–{years[1]}년. '+floor_note+
               '전세는 신규·갱신을 모두 포함하며, 월별 중위가는 비교 기간 전체의 중앙값과 다를 수 있습니다.')
    return dict(targets=targets,area=area,period=(years[0]*100+1,years[1]*100+12),trade_type=trade_type,direct=direct)
