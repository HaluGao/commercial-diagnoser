from pathlib import Path
import runpy
import sys

ROOT = Path(__file__).resolve().parent
APP_DIR = ROOT / "apps" / "streamlit_demo"
APP_PATH = APP_DIR / "app.py"

if str(APP_DIR) not in sys.path:
    sys.path.insert(0, str(APP_DIR))

runpy.run_path(str(APP_PATH), run_name="__main__")
