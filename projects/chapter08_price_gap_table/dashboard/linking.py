"""비교표와 차트에서 선택한 최종 집계 행을 상세 대시보드 링크로 변환한다."""
import hashlib
import os

import pyarrow as pa
import streamlit as st

from src.utils.dashboard_link import MAX_TARGETS, encode_selection, selection_url


def selection_revision(table, context):
    sink = pa.BufferOutputStream()
    with pa.ipc.new_stream(sink, table.schema) as writer:
        writer.write_table(table)
    return hashlib.sha256(str(context).encode()+sink.getvalue().to_pybytes()).hexdigest()[:16]


def target_from_row(row):
    sido, gu = row['지역'].split(' ', 1)
    return sido, gu, row['읍면동'] or '', row['단지명'], row['주소'], row['평형대']


def targets_from_points(points):
    targets = []
    for point in points:
        detail = point.get('customdata')
        if detail is None or len(detail) < 7:
            continue  # 상자 통계나 빈 배경은 단지 선택이 아니다.
        sido, gu = str(detail[2]).split(' ', 1)
        target = (sido, gu, str(detail[3]), str(detail[0]), str(detail[6]), str(detail[1]))
        if target not in targets:
            targets.append(target)
    return targets


def destination_setting():
    with st.sidebar.expander('가격·거래량 대시보드 연결'):
        base = st.text_input('가격·거래량 대시보드 주소', value=os.getenv('PRICE_VOLUME_URL', ''),
                             key='price_volume_url', placeholder='http://localhost:8529')
        st.caption('가격·거래량 대시보드를 먼저 실행하고 접속 주소를 입력하세요. 두 대시보드는 같은 수집 DB를 사용해야 합니다.')
    return base


def selection_key(source, revision):
    return f'{source}_selection:{revision}:{st.session_state.get(source+"_selection_reset", 0)}'


def _clear(source):
    key = source+'_selection_reset'
    st.session_state[key] = st.session_state.get(key, 0)+1


def render_link(targets, base, context, source):
    targets = list(dict.fromkeys(targets))
    # 화면에 없는 과거 선택이 넘어오더라도 링크로 보내지 않는다.
    allowed = context['allowed']
    targets = [t for t in targets if t in allowed]
    count = len(targets)
    if count:
        names = ' / '.join(f'{t[3]} · {t[5]} ({t[1]} {t[2]})' for t in targets[:MAX_TARGETS])
        st.caption(f'선택한 대상 {count}개 · {names}')
        st.button('선택 해제', key=source+'_clear', on_click=_clear, args=(source,))
    if count > MAX_TARGETS:
        st.info(f'가격·거래량 비교는 한 번에 {MAX_TARGETS}개까지 연결합니다. 선택 범위를 줄여주세요.')
    url = None
    if base and 0 < count <= MAX_TARGETS:
        try:
            token = encode_selection(targets, context['area'], context['period'], context['floor'])
            url = selection_url(base, token)
        except ValueError as exc:
            st.warning(str(exc))
    if not base and count:
        st.info('사이드바의 ‘가격·거래량 대시보드 연결’에서 실행 중인 대시보드 주소를 입력하세요.')
    st.link_button(f'선택한 {count}개 대상의 가격·거래량 보기' if count else '대상을 선택하면 가격·거래량을 볼 수 있습니다',
                   url or '#', disabled=url is None)
