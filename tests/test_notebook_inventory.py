import json
from pathlib import Path


PROJECTS = Path("projects")


def _notebook_names(part_path: str) -> list[str]:
    return sorted(path.name for path in (PROJECTS / part_path / "notebooks").glob("*.ipynb"))


def test_part08_to_part10_notebook_inventory():
    expected = {
        "part08_kb_dashboard": [
            "01_eda.ipynb",
            "02_preprocessing.ipynb",
            "03_chart_prototype.ipynb",
        ],
        "part09_trade_map": [
            "01_eda.ipynb",
            "02_preprocessing.ipynb",
            "03_map_prototype.ipynb",
        ],
        "part10_price_volume": [
            "01_eda.ipynb",
            "02_preprocessing.ipynb",
            "03_chart_prototype.ipynb",
        ],
    }

    for part_path, notebook_names in expected.items():
        assert _notebook_names(part_path) == notebook_names


def test_part08_visualization_notebook_is_valid_json():
    path = PROJECTS / "part08_kb_dashboard" / "notebooks" / "03_chart_prototype.ipynb"
    notebook = json.loads(path.read_text(encoding="utf-8"))

    assert notebook["nbformat"] == 4
    assert notebook["cells"][0]["cell_type"] == "markdown"
    assert "시각화 프로토타입" in "".join(notebook["cells"][0]["source"])
