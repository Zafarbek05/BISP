import os
import sys
import streamlit.web.cli as stcli
import subprocess
import time
import urllib.request
import threading
import webview

def _wait_for_url(url, timeout=60):
    deadline = time.time() + timeout
    while time.time() < deadline:
        try:
            with urllib.request.urlopen(url, timeout=2) as response:
                if response.status < 500:
                    return True
        except Exception:
            time.sleep(0.5)
    return False

def run_pipeline(root_dir):
    pipeline_script = os.path.join(root_dir, "src", "pipeline.py")
    if os.path.exists(pipeline_script):
        # In a frozen app, we might need to use sys.executable
        subprocess.Popen([sys.executable, pipeline_script], cwd=root_dir)

def main():
    # Resolve root directory for both dev and frozen (PyInstaller)
    if getattr(sys, 'frozen', False):
        root_dir = sys._MEIPASS
    else:
        root_dir = os.path.dirname(os.path.abspath(__file__))

    app_script = os.path.join(root_dir, "app.py")
    port = 8501
    url = f"http://127.0.0.1:{port}"

    # Start pipeline in a separate process
    threading.Thread(target=run_pipeline, args=(root_dir,), daemon=True).start()

    # Launch streamlit in a separate thread
    # Note: stcli.main() takes a list of arguments
    st_args = [
        "run", app_script,
        "--server.headless=true",
        "--server.address=127.0.0.1",
        f"--server.port={port}",
        "--browser.gatherUsageStats=false",
    ]
    
    st_thread = threading.Thread(target=stcli.main, args=(st_args,), daemon=True)
    st_thread.start()

    if _wait_for_url(url):
        webview.create_window("AI Semantic Search", url, width=1280, height=800)
        webview.start()
    else:
        print("Failed to start Streamlit server")

if __name__ == "__main__":
    main()
