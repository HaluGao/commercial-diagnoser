from pathlib import Path
import runpy

APP_PATH = Path(__file__).resolve().parent / "apps" / "streamlit_demo" / "app.py"
runpy.run_path(str(APP_PATH), run_name="__main__")
