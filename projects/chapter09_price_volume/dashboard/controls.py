"""월별 비교 차트의 기준월 선택 UI."""
import streamlit as st


def select_base_month(observed_months: list[int], default_month: int) -> int:
    """거래가 없는 달도 포함해 기준월을 한 달씩 이동한다."""
    first, last = min(observed_months), max(observed_months)
    months = [
        year * 100 + month
        for year in range(first // 100, last // 100 + 1)
        for month in range(1, 13)
        if first <= year * 100 + month <= last
    ]
    if st.session_state.get("base_month") not in months:
        st.session_state["base_month"] = default_month
    index = months.index(st.session_state["base_month"])

    def move_month(offset):
        current = months.index(st.session_state["base_month"])
        st.session_state["base_month"] = months[max(0, min(len(months) - 1, current + offset))]

    st.markdown("기준월")
    previous, slider, following = st.columns([1, 8, 1], vertical_alignment="center")
    with previous:
        st.button("◀", key="base_month_prev", help="이전 달", disabled=index == 0,
                  on_click=move_month, args=(-1,), use_container_width=True)
    with slider:
        if len(months) == 1:
            st.caption(f"{first // 100}-{first % 100:02d} (선택 가능한 유일한 달)")
        else:
            st.select_slider(
                "기준월", months, key="base_month", label_visibility="collapsed",
                format_func=lambda month: f"{month // 100}-{month % 100:02d}",
            )
    with following:
        st.button("▶", key="base_month_next", help="다음 달", disabled=index == len(months) - 1,
                  on_click=move_month, args=(1,), use_container_width=True)
    return st.session_state["base_month"]
