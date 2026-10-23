"""비교표와 동일한 단지·평형 집계 결과를 그리는 차트."""
import numpy as np
import pyarrow as pa
import pyarrow.compute as pc
import plotly.graph_objects as go
from plotly.colors import qualitative
import streamlit as st
from projects.chapter07_price_gap_table.dashboard.vertical_slider import vertical_range
from projects.chapter07_price_gap_table.dashboard.linking import selection_key, targets_from_points, render_link

METRICS = ('갭 (억원)', '전고점 대비 (%)', '매매 (억원)', '신규 전세 (억원)',
           '전세가율 (%)', '매매 건수', '전세 건수')
DISTRIBUTIONS = ('갭 (억원)', '전세가율 (%)', '매매 (억원)', '신규 전세 (억원)', '전고점 대비 (%)')
COLORS = qualitative.Safe


def chart_rows(table, metrics):
    """선택한 지표에 유한한 값이 있는 행만 사용한다. 0과 음수는 보존한다."""
    mask = pa.array(np.ones(table.num_rows, dtype=bool))
    for metric in metrics:
        mask = pc.and_(mask, pc.fill_null(pc.is_finite(table[metric]), False))
    return table.filter(mask)


def _values(table, name):
    return table[name].to_numpy(zero_copy_only=False)


def _lease_column(table):
    return '신규 전세 (억원)' if '신규 전세 (억원)' in table.column_names else '전세 (억원)'


def _details(table):
    # 최종 집계 결과의 차트 툴팁에 필요한 열만 변환한다.
    columns = [_values(table, name) for name in
               ('단지명', '평형대', '지역', '읍면동', '매매 건수', '전세 건수', '주소')]
    for name in ('매매 (억원)', _lease_column(table)):
        values = _values(table, name)
        columns.append(np.where(np.isfinite(values), np.char.mod('%.2f', values), '자료 없음'))
    for name, unit in (('건축년도', '년'), ('세대수', '세대')):
        values = _values(table, name)
        columns.append(np.where(np.isfinite(values), np.char.mod('%.0f'+unit, values), '자료 없음'))
    return np.column_stack(columns)


def _hover_template(axes, lease_column='신규 전세 (억원)'):
    lease_name = lease_column.removesuffix(' (억원)')
    text = ('<b>%{customdata[0]}</b> · %{customdata[1]}<br>'
            '%{customdata[2]} %{customdata[3]}<br>'
            '건축년도: %{customdata[9]}<br>'
            '단지 전체 세대수: %{customdata[10]}<br>'
            '매매 (억원): %{customdata[7]}<br>' +
            lease_column + ': %{customdata[8]}<br>')
    # 가격과 건수는 공통으로 표시하므로 선택한 축에서 다시 표시하지 않는다.
    shown = {'매매 (억원)', lease_column, '매매 건수', '전세 건수'}
    for axis, metric in axes:
        if metric not in shown:
            text += metric + ': %{' + axis + ':,.2f}<br>'
            shown.add(metric)
    return text + ('매매 %{customdata[4]}건 · '+lease_name+' %{customdata[5]}건<extra></extra>')


def _region_labels(table, grouping):
    regions = table['지역'].to_pylist()
    if grouping == '시도':
        return np.array([region.split()[0] for region in regions])
    if grouping == '읍면동':
        return np.array([f'{region} {dong or "읍면동 미상"}'
                         for region, dong in zip(regions, table['읍면동'].to_pylist())])
    return np.array(regions)


def scatter_figure(table, x, y, grouping='시도'):
    rows = chart_rows(table, (x, y))
    fig = go.Figure()
    # 같은 이름의 다른 지역을 합치지 않고, 축 변경에도 지역별 색상을 유지한다.
    names = sorted(set(_region_labels(table, grouping)))
    colors = COLORS if len(names) <= len(COLORS) else qualitative.Alphabet
    palette = {name: colors[i % len(colors)] for i, name in enumerate(names)}
    regions = _region_labels(rows, grouping)
    details = _details(rows)
    for region in sorted(set(regions)):
        mask = regions == region
        fig.add_trace(go.Scattergl(
            x=_values(rows, x)[mask], y=_values(rows, y)[mask],
            customdata=details[mask], mode='markers', name=region,
            marker=dict(size=7, opacity=0.65, color=palette[region]),
            hovertemplate=_hover_template((('x', x), ('y', y)), _lease_column(table)),
        ))
    legend = (dict(orientation='v', x=1.02, y=1, yanchor='top', font=dict(size=11))
              if len(set(regions)) > 6 else dict(orientation='h', y=1.08))
    fig.update_layout(template='plotly_white', height=520, margin=dict(l=20, r=20, t=20, b=20),
                      xaxis_title=x, yaxis_title=y, legend=legend,
                      hovermode='closest')
    return fig, rows.num_rows


def distribution_figure(table, metric, grouping='시군구'):
    rows = chart_rows(table, (metric,))
    regions = _region_labels(rows, grouping)
    names = sorted(set(regions))
    fig = go.Figure()
    values = _values(rows, metric)
    positions = np.empty(rows.num_rows)
    for index, name in enumerate(names):
        mask = regions == name
        positions[mask] = index
        group_values = values[mask]
        q1, median, q3 = np.quantile(group_values, [0.25, 0.5, 0.75], method='linear')
        spread = 1.5 * (q3-q1)
        lower = group_values[group_values >= q1-spread].min()
        upper = group_values[group_values <= q3+spread].max()
        # 점을 별도로 그리더라도 수염은 최소값·최대값 대신 1.5 IQR 기준을 유지한다.
        fig.add_trace(go.Box(x=[index], q1=[q1], median=[median], q3=[q3],
                             lowerfence=[lower], upperfence=[upper], name=name,
                             boxpoints=False, width=0.55,
                             fillcolor='rgba(65,105,180,0.12)', line=dict(color='#5478a5', width=1),
                             showlegend=False, hoverinfo='skip'))
    # 박스와 별도의 점 레이어를 사용해 이상치를 중복 표시하지 않는다.
    jitter = np.random.default_rng(7).uniform(-0.22, 0.22, rows.num_rows)
    fig.add_trace(go.Scattergl(x=positions+jitter, y=values, mode='markers',
                              customdata=_details(rows), showlegend=False,
                              marker=dict(size=4, color='#3569a8', opacity=0.55),
                              hovertemplate=_hover_template((('y', metric),), _lease_column(table))))
    fig.update_layout(template='plotly_white', height=600, margin=dict(l=20, r=20, t=20, b=30),
                      yaxis_title=metric, hovermode='closest',
                      xaxis=dict(tickmode='array', tickvals=list(range(len(names))), ticktext=names,
                                 tickangle=-90, automargin=True, range=[-0.5, len(names)-0.5],
                                 rangeslider=dict(visible=False),
                                 title='지역'))
    return fig, rows.num_rows, len(names)


def y_axis_bounds(table, metric):
    """전체 값이 들어가고 단일 값에도 여유가 있는 축 범위를 반환한다."""
    values = _values(chart_rows(table, (metric,)), metric)
    low, high = float(values.min()), float(values.max())
    step = 1.0 if metric.endswith('건수') else 0.01
    padding = max((high-low)*0.05, abs(low)*0.01, step)
    lower = round(float(np.floor((low-padding)/step)*step), 2)
    upper = round(float(np.ceil((high+padding)/step)*step), 2)
    return lower, upper, step


def _plot_with_y_slider(fig, rows, metric, key, regions=None, x_metric=None, link=None):
    mode = st.radio('선택 방식', ('클릭 선택','드래그 선택'), horizontal=True,
                    key=key+'_selection_mode', help='클릭 선택에서는 Shift와 클릭으로 여러 점을 고릅니다. 드래그 선택에서는 사각형 영역 안의 점을 함께 고릅니다.') if link else None
    layout = st.container(key=f'{key}_layout')
    side, main = layout.columns([1, 9], gap='small')
    lower, upper, step = y_axis_bounds(rows, metric)
    with side:
        selected = vertical_range(lower, upper, step, metric, f'{key}_y_range',
                                  int(fig.layout.height), top=65 if x_metric else 40,
                                  bottom=65 if x_metric else 180)
    fig.update_yaxes(range=selected, autorange=False)
    with main:
        chart = st.container()
        if regions and len(regions) > 12:
            start, end = st.select_slider('X축 범위 · 지역', options=regions,
                                         value=(regions[0], regions[-1]), key=f'{key}_x_range')
            fig.update_xaxes(range=[regions.index(start)-0.5, regions.index(end)+0.5])
        if x_metric:
            x_low, x_high, x_step = y_axis_bounds(rows, x_metric)
            x_range = st.slider(f'X축 범위 · {x_metric}', min_value=x_low, max_value=x_high,
                                value=(x_low, x_high), step=x_step, format='%.2f', key=f'{key}_x_range')
            if x_range[0] == x_range[1]:
                x_range = (x_range[0]-x_step, x_range[1]+x_step)
            fig.update_xaxes(range=x_range, autorange=False)
        if link:
            base, context, revision = link
            identity = f'{revision}:{metric}:{x_metric}:{regions}:{tuple(t.name for t in fig.data)}:{mode}'
            widget_key = selection_key(key, identity)
            fig.update_layout(dragmode='pan' if mode=='클릭 선택' else 'select',clickmode='event+select',uirevision=widget_key)
            fig.update_traces(selected=dict(marker=dict(opacity=1)),
                              unselected=dict(marker=dict(opacity=0.2)),selector=dict(type='scattergl'))
            event = chart.plotly_chart(fig,use_container_width=True,key=widget_key,
                                      on_select='rerun',selection_mode=('points','box','lasso'),
                                      config={'modeBarButtonsToRemove':['pan2d','zoom2d']+(['select2d','lasso2d'] if mode=='클릭 선택' else [])})
            render_link(targets_from_points(event.selection.points),base,context,key)
            st.caption('클릭 선택에서는 Shift를 누른 채 클릭하면 여러 점을 고를 수 있습니다. 드래그 선택에서는 사각형으로 둘러싸세요. 자유 영역은 차트 도구모음에서 선택할 수 있습니다. 선택 방식을 바꾸면 선택은 초기화됩니다.')
        else:
            chart.plotly_chart(fig, use_container_width=True, key=key)


def render_charts(table, sales_only=False, link=None):
    lease_column = _lease_column(table)
    metrics = tuple(lease_column if name == '신규 전세 (억원)' else name for name in METRICS)
    distributions = tuple(lease_column if name == '신규 전세 (억원)' else name for name in DISTRIBUTIONS)
    if sales_only:
        metrics = ('매매 (억원)', '전고점 대비 (%)', '매매 건수')
        distributions = ('매매 (억원)', '전고점 대비 (%)')
        defaults = {'scatter_x':'갭 (억원)', 'scatter_y':'전고점 대비 (%)', 'distribution_metric':'갭 (억원)'}
        if '_comparison_chart_choices' not in st.session_state:
            st.session_state['_comparison_chart_choices'] = {key:st.session_state.get(key,value) for key,value in defaults.items()}
        for key, choices in (('scatter_x',metrics), ('scatter_y',metrics), ('distribution_metric',distributions)):
            if st.session_state.get(key) not in choices:
                st.session_state[key] = '전고점 대비 (%)' if key=='scatter_y' else '매매 (억원)'
    elif '_comparison_chart_choices' in st.session_state:
        for key, value in st.session_state.pop('_comparison_chart_choices').items():
            st.session_state[key] = value
    for key in ('scatter_x', 'scatter_y', 'distribution_metric'):
        if st.session_state.get(key) in ('신규 전세 (억원)', '전세 (억원)'):
            st.session_state[key] = lease_column
    st.html('''<style>
    :is(.st-key-gap_scatter_layout, .st-key-gap_distribution_layout) [data-testid="stHorizontalBlock"] {
        gap: 4px; flex-wrap: nowrap;
    }
    :is(.st-key-gap_scatter_layout, .st-key-gap_distribution_layout) [data-testid="stHorizontalBlock"] > [data-testid="stColumn"]:first-child {
        flex: 0 0 48px; width: 48px; min-width: 48px;
    }
    :is(.st-key-gap_scatter_layout, .st-key-gap_distribution_layout) [data-testid="stHorizontalBlock"] > [data-testid="stColumn"]:last-child {
        flex: 1 1 0; min-width: 0;
    }
    :is(.st-key-gap_scatter_x_range, .st-key-gap_distribution_x_range) [data-baseweb="slider"] {
        filter: grayscale(1);
    }
    :is(.st-key-gap_scatter_x_range, .st-key-gap_distribution_x_range) [data-baseweb="slider"] div:has(> [role="slider"]) + div {
        opacity: 0.5;
    }
    :is(.st-key-gap_scatter_x_range, .st-key-gap_distribution_x_range) [role="slider"] {
        background-color: #b8b8b8;
    }
    :is(.st-key-scatter_x, .st-key-scatter_y, .st-key-scatter_group,
        .st-key-distribution_metric, .st-key-distribution_group) [data-testid="stSelectbox"] {
        display: flex; align-items: center; gap: 8px 12px; flex-wrap: wrap;
    }
    :is(.st-key-scatter_x, .st-key-scatter_y, .st-key-scatter_group,
        .st-key-distribution_metric, .st-key-distribution_group) [data-testid="stWidgetLabel"] {
        flex: 0 0 auto; margin-bottom: 0; min-height: 0; white-space: nowrap;
    }
    :is(.st-key-scatter_x, .st-key-scatter_y, .st-key-scatter_group,
        .st-key-distribution_metric, .st-key-distribution_group) [data-baseweb="select"] {
        flex: 1 1 130px; min-width: 0;
    }
    :is(.st-key-scatter_x, .st-key-scatter_y, .st-key-scatter_group,
        .st-key-distribution_metric, .st-key-distribution_group)
        :is([data-testid="stWidgetLabel"] p, [data-baseweb="select"], [data-baseweb="select"] input) {
        font-size: 0.8125rem;
    }
    /* 선택 목록은 위젯 바깥의 팝업에 렌더링된다. */
    /* 가상 목록의 행 위치와 스크롤을 함께 축소하고, 글자 크기는 보정한다. */
    body:has(:is(.st-key-scatter_x, .st-key-scatter_y, .st-key-scatter_group,
        .st-key-distribution_metric, .st-key-distribution_group) [role="combobox"][aria-expanded="true"])
        [data-testid="stSelectboxVirtualDropdown"] {
        zoom: 0.64;
        width: 100%;
    }
    body:has(:is(.st-key-scatter_x, .st-key-scatter_y, .st-key-scatter_group,
        .st-key-distribution_metric, .st-key-distribution_group) [role="combobox"][aria-expanded="true"])
        :is([role="option"], [role="option"] div) {
        font-size: calc(0.8125rem / 0.64);
        line-height: 1.4;
    }
    </style>''')
    st.subheader('두 지표 함께 비교하기')
    left, right, color = st.columns(3)
    x = left.selectbox('가로축', metrics, index=0, key='scatter_x')
    y = right.selectbox('세로축', metrics, index=1, key='scatter_y')
    grouping = color.selectbox('범례 색상 기준', ('시도', '시군구', '읍면동'), key='scatter_group')
    if x == y:
        st.info('두 지표의 관계를 살펴보려면 서로 다른 축을 선택하세요.')
    fig, count = scatter_figure(table, x, y, grouping)
    st.caption(f'단지·평형 {count:,}개 표시 · 선택 지표 결측 {table.num_rows-count:,}개 제외')
    if count:
        _plot_with_y_slider(fig, chart_rows(table, (x, y)), y, 'gap_scatter', x_metric=x, link=link)
    else:
        st.info('선택한 두 지표를 함께 확인할 수 있는 단지·평형이 없습니다.')
    st.caption(f'점 하나는 비교표의 단지·평형 한 행입니다. 색상은 {grouping}을 구분합니다. 범례를 클릭하면 해당 지역을 숨기거나 다시 표시하고, 두 번 클릭하면 해당 지역만 볼 수 있습니다.')
    if len(set(_region_labels(table, grouping))) > len(qualitative.Alphabet):
        st.caption('지역이 많아 일부 색상이 반복됩니다. 사이드바에서 지역 범위를 좁히거나 범례와 점의 상세 정보를 함께 확인하세요.')
    st.caption('갭·전세가율처럼 같은 가격에서 계산한 지표는 계산식에 의해 관계가 나타날 수 있습니다. 점의 배치만으로 원인이나 매수 적합성을 판단하지 마세요.')

    st.divider()
    st.subheader('지역별 분포 비교하기')
    left, right = st.columns(2)
    metric = left.selectbox('분포 지표', distributions, key='distribution_metric')
    grouping = right.selectbox('지역 구분', ('시도', '시군구', '읍면동'), index=1, key='distribution_group')
    fig, count, region_count = distribution_figure(table, metric, grouping)
    st.caption(f'단지·평형 {count:,}개 표시 · 선택 지표 결측 {table.num_rows-count:,}개 제외 · {region_count:,}개 지역')
    if count:
        if region_count > 12:
            st.caption('기본으로 전체 지역을 보여줍니다. 차트 아래 X축 범위의 양쪽 손잡이를 움직이면 비교할 지역 범위를 좁힐 수 있습니다.')
        _plot_with_y_slider(fig, chart_rows(table, (metric,)), metric, 'gap_distribution',
                            list(fig.layout.xaxis.ticktext), link=link)
    else:
        st.info('선택한 지표를 확인할 수 있는 단지·평형이 없습니다.')
    st.caption('점 하나는 개별 거래가 아닌 단지·평형 하나이며, 거래 건수에 관계없이 같은 비중으로 표시합니다. 점의 좌우 위치는 겹침을 줄이기 위한 것으로 별도의 의미는 없습니다.')
    with st.expander('상자그림 읽는 법'):
        st.markdown('상자는 값의 가운데 50%가 모인 범위이며, 상자 안의 선은 중앙값입니다. 점들이 세로로 넓게 퍼져 있을수록 단지·평형 사이의 차이가 큽니다. 수염은 상자 높이의 1.5배 범위 안에 있는 가장 바깥 관측값까지 이어집니다. 수염 밖의 점도 실제 관측값이며, 그 자체로 잘못된 데이터라는 뜻은 아닙니다. 단지·평형이 적은 지역은 박스가 선이나 점처럼 보일 수 있습니다.')
