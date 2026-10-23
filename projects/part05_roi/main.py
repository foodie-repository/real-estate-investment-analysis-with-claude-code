"""이전 실행 경로 호환: projects/chapter05_roi/main.py를 사용하세요."""
import runpy
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

if __name__ == "__main__":
    runpy.run_path(str(ROOT / "projects/chapter05_roi/main.py"), run_name="__main__")
