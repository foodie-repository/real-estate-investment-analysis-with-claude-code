import numpy as np
import pyarrow as pa
import pytest

from projects.chapter07_price_gap_table.dashboard.charts import (
    METRICS, chart_rows, distribution_figure, scatter_figure, y_axis_bounds,
)


@pytest.fixture
def table():
    return pa.table({
        '지역': ['서울특별시 중구', '부산광역시 중구', '서울특별시 중구', '경기도 수원시'],
        '읍면동': ['가동']*4, '단지명': ['같은이름']*4, '평형대': ['30평대']*4,
        '주소': ['주소1', '주소2', '주소3', '주소4'],
        '갭 (억원)': [-1., 0., None, 3.], '전고점 대비 (%)': [80., 90., 70., None],
        '매매 (억원)': [4., 5., None, 7.], '신규 전세 (억원)': [5., 5., 3., 4.],
        '전세가율 (%)': [125., 100., None, 57.14],
        '매매 건수': [2, 3, 0, 1], '전세 건수': [1, 2, 1, 1],
        '건축년도': [2020, None, 1995, 2001], '세대수': [1200, None, 800, 120],
    })


def test_scatter_preserves_values_units_and_identity(table):
    fig, count = scatter_figure(table, '갭 (억원)', '전고점 대비 (%)')
    assert count == 2
    assert sorted((float(x), float(y)) for t in fig.data for x, y in zip(t.x, t.y)) == [(-1., 80.), (0., 90.)]
    assert {row[6] for t in fig.data for row in t.customdata} == {'주소1', '주소2'}
    assert fig.layout.xaxis.title.text == '갭 (억원)'


@pytest.mark.parametrize('kind', ['scatter', 'box'])
def test_hover_prices_match_rows_and_missing_prices_stay_missing(table, kind):
    table = table.set_column(table.schema.get_field_index('신규 전세 (억원)'),
                             '신규 전세 (억원)', pa.array([5., 5., 3., None]))
    if kind == 'scatter':
        fig, count = scatter_figure(table, '매매 건수', '전세 건수')
    else:
        fig, count, _ = distribution_figure(table, '전고점 대비 (%)')
    rows = {r[6]: list(r[7:9]) for t in fig.data if t.type == 'scattergl' for r in t.customdata}
    assert rows['주소1'] == ['4.00', '5.00']
    assert rows['주소3'] == ['자료 없음', '3.00']
    if kind == 'scatter':
        assert count == 4 and rows['주소4'] == ['7.00', '자료 없음']
    else:
        assert count == 3


@pytest.mark.parametrize('kind', ['scatter', 'box'])
def test_hover_complex_metadata_is_not_split_by_area_and_preserves_missing(table, kind):
    rows = pa.concat_tables([table.slice(0, 1), table.slice(0, 1), table.slice(1, 1)])
    rows = rows.set_column(rows.schema.get_field_index('평형대'), '평형대',
                           pa.array(['20평대', '30평대', '40평대']))
    if kind == 'scatter':
        fig, count = scatter_figure(rows, '갭 (억원)', '전고점 대비 (%)')
    else:
        fig, count, _ = distribution_figure(rows, '갭 (억원)')
    details = {r[1]: list(r[9:11]) for t in fig.data if t.type == 'scattergl' for r in t.customdata}
    assert count == 3
    assert details['20평대'] == details['30평대'] == ['2020년', '1200세대']
    assert details['40평대'] == ['자료 없음', '자료 없음']
    assert all('단지 전체 세대수:' in t.hovertemplate for t in fig.data if t.type == 'scattergl')


@pytest.mark.parametrize('kind', ['scatter', 'box'])
def test_price_axes_do_not_duplicate_prices_in_hover(table, kind):
    if kind == 'scatter':
        fig, _ = scatter_figure(table, '매매 (억원)', '신규 전세 (억원)')
    else:
        fig, _, _ = distribution_figure(table, '매매 (억원)')
    for trace in fig.data:
        if trace.type == 'scattergl':
            assert trace.hovertemplate.count('매매 (억원)') == 1
            assert trace.hovertemplate.count('신규 전세 (억원)') == 1
            assert '%{x:' not in trace.hovertemplate and '%{y:' not in trace.hovertemplate


@pytest.mark.parametrize('grouping', ['시도', '시군구', '읍면동'])
def test_scatter_legend_keeps_region_identity_and_points(table, grouping):
    fig, count = scatter_figure(table, '매매 건수', '신규 전세 (억원)', grouping)
    assert count == sum(len(t.x) for t in fig.data) == 4
    assert len(fig.data) == 3
    assert len({t.marker.color for t in fig.data}) == 3
    assert {row[6] for t in fig.data for row in t.customdata} == {'주소1', '주소2', '주소3', '주소4'}
    if grouping == '읍면동':
        assert {t.name for t in fig.data} == {'서울특별시 중구 가동', '부산광역시 중구 가동', '경기도 수원시 가동'}


@pytest.mark.parametrize('x', METRICS)
@pytest.mark.parametrize('y', METRICS)
def test_every_axis_pair_reconciles_with_rows(table, x, y):
    fig, count = scatter_figure(table, x, y)
    assert sum(len(t.x) for t in fig.data) == count == chart_rows(table, (x, y)).num_rows


def test_box_all_points_once_and_district_names_distinct(table):
    fig, count, groups = distribution_figure(table, '갭 (억원)')
    assert count == 3 and groups == 3
    boxes = [t for t in fig.data if t.type == 'box']
    assert {t.name for t in boxes} == {'서울특별시 중구', '부산광역시 중구', '경기도 수원시'}
    assert all(t.boxpoints is False for t in boxes)
    assert sorted(fig.data[-1].y) == [-1., 0., 3.]
    assert len(fig.data[-1].y) == count


def test_box_province_grouping_keeps_all_rows(table):
    fig, count, groups = distribution_figure(table, '신규 전세 (억원)', '시도')
    assert count == 4 and groups == 3
    assert next(t for t in fig.data if t.name == '서울특별시').median[0] == 4


def test_box_dong_grouping_keeps_district_identity(table):
    rows = table.set_column(table.schema.get_field_index('읍면동'), '읍면동', pa.array(['가동', '가동', '나동', '가동']))
    fig, count, groups = distribution_figure(rows, '신규 전세 (억원)', '읍면동')
    expected = {f'{region} {dong}' for region, dong in zip(rows['지역'].to_pylist(), rows['읍면동'].to_pylist())}
    assert count == 4 and groups == len(expected) == 4
    assert {t.name for t in fig.data if t.type == 'box'} == expected
    assert len(fig.data[-1].y) == count


def test_box_whiskers_use_iqr_and_keep_outlying_point(table):
    many = pa.concat_tables([table.slice(0, 1)]*5)
    many = many.set_column(many.schema.get_field_index('갭 (억원)'), '갭 (억원)', pa.array([1., 2., 3., 4., 100.]))
    fig, count, _ = distribution_figure(many, '갭 (억원)')
    box = fig.data[0]
    assert (box.q1[0], box.median[0], box.q3[0]) == (2., 3., 4.)
    assert (box.lowerfence[0], box.upperfence[0]) == (1., 4.)
    assert count == 5 and max(fig.data[-1].y) == 100.


def test_empty_null_and_nonfinite_values(table):
    for empty in (table.slice(0, 0), table.set_column(table.schema.get_field_index('갭 (억원)'), '갭 (억원)', pa.array([None, float('nan'), float('inf'), -float('inf')], type=pa.float64()))):
        fig, count = scatter_figure(empty, '갭 (억원)', '전고점 대비 (%)')
        assert count == 0 and len(fig.data) == 0
        fig, count, groups = distribution_figure(empty, '갭 (억원)')
        assert count == groups == len(fig.data[-1].y) == 0


def test_box_never_truncates_many_regions(table):
    many = pa.concat_tables([table.slice(0, 1)]*15)
    many = many.set_column(0, '지역', pa.array([f'서울특별시 지역{i:02}' for i in range(15)]))
    fig, count, groups = distribution_figure(many, '갭 (억원)')
    assert count == groups == 15
    assert list(fig.layout.xaxis.range) == [-0.5, 14.5]
    assert len(fig.data[-1].y) == 15
    assert fig.layout.xaxis.rangeslider.visible is False
    assert fig.layout.xaxis.tickangle == -90
    assert np.all(np.isfinite(fig.data[-1].x))


@pytest.mark.parametrize('metric', METRICS)
def test_y_axis_bounds_include_all_values_and_constant(table, metric):
    for rows in (table, table.slice(0, 1)):
        lower, upper, step = y_axis_bounds(rows, metric)
        values = chart_rows(rows, (metric,))[metric].to_pylist()
        assert lower < min(values) <= max(values) < upper
        assert step > 0
