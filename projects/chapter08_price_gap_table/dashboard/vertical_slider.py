"""차트 옆에 배치하는 두 손잡이 세로 범위 조절기."""
from pathlib import Path
from math import isfinite

import streamlit.components.v1 as components

_component = components.declare_component('vertical_range', path=Path(__file__).with_name('vertical_range'))


def vertical_range(lower, upper, step, metric, key, height, top, bottom):
    # 지표나 데이터 범위가 달라지면 새 범위를 사용하고, 다른 축 조작에는 선택을 유지한다.
    selected = _component(lower=lower, upper=upper, step=step, metric=metric,
                          height=height, top=top, bottom=bottom,
                          default=[lower, upper], key=f'{key}:{metric}:{lower}:{upper}')
    if not isinstance(selected, (list, tuple)) or len(selected) != 2:
        return lower, upper
    try:
        low, high = map(float, selected)
    except (ValueError, TypeError):
        return lower, upper
    if not all(isfinite(value) for value in (low, high)):
        return lower, upper
    return max(lower, min(low, upper-step)), min(upper, max(high, low+step, lower+step))
