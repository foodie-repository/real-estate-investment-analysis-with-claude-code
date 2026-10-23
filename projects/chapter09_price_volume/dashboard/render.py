"""탭이 보일 때 차트를 그리고 너비 변경에 대응하는 Plotly 렌더러."""
import streamlit.components.v1 as components
from plotly.offline import get_plotlyjs


_RESIZE_SCRIPT = r"""
const graph = document.getElementById('chart');
// 숨겨진 탭이 열리거나 사이드바 폭이 바뀌어도 실제 너비에 맞춘다.
new ResizeObserver(() => Plotly.Plots.resize(graph)).observe(document.body);
"""


def chart_html(fig):
    """설치된 Plotly를 포함하므로 외부 CDN 연결 없이 동작한다."""
    fig.update_layout(template="plotly_white", font=dict(family="Arial, sans-serif", size=12))
    figure = fig.to_json().replace("<", "\\u003c")
    return ("<!doctype html><html><head><meta charset='utf-8'>"
            "<style>body{margin:0;overflow:hidden}#chart{width:100%}</style></head><body>"
            "<div id='chart'></div><script>" + get_plotlyjs() + "</script><script>"
            "const figure=" + figure + ";"
            "function mount(){"
            "if(window.frameElement && !window.frameElement.getBoundingClientRect().width){"
            "requestAnimationFrame(mount);return;}"
            "Plotly.newPlot('chart',figure.data,figure.layout,{responsive:true,displaylogo:false})"
            ".then(()=>{" + _RESIZE_SCRIPT + "});}mount();</script></body></html>")


def render_chart(fig):
    components.html(chart_html(fig), height=int(fig.layout.height), scrolling=False)
