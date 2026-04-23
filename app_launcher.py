import argparse
import os
import secrets
import subprocess
import sys
import time
import urllib.request

def _build_env(root_dir: str) -> dict:
    env = os.environ.copy()
    existing = env.get("PYTHONPATH", "")
    if root_dir not in existing.split(os.pathsep):
        env["PYTHONPATH"] = root_dir + (os.pathsep + existing if existing else "")
    return env


def _resolve_streamlit_port(env: dict) -> int:
    for key in ("STREAMLIT_PORT", "STREAMLIT_SERVER_PORT", "PORT"):
        value = env.get(key)
        if not value:
            continue
        try:
            port = int(value)
        except ValueError:
            print(f"[LAUNCHER] Invalid {key} value: {value}. Using default 8501.")
            break
        if 1 <= port <= 65535:
            return port
        print(f"[LAUNCHER] Invalid {key} value: {value}. Using default 8501.")
        break
    return 8501


def _wait_for_url(url: str, timeout: int, proc: subprocess.Popen | None = None) -> bool:
    deadline = time.time() + timeout
    while time.time() < deadline:
        if proc is not None and proc.poll() is not None:
            return False
        try:
            with urllib.request.urlopen(url, timeout=2) as response:
                if response.status < 500:
                    return True
        except Exception:
            time.sleep(0.5)
    return False


def _terminate_process(proc: subprocess.Popen | None, name: str) -> None:
    if proc is None:
        return
    if proc.poll() is None:
        proc.terminate()
        try:
            proc.wait(timeout=5)
        except Exception:
            try:
                proc.kill()
            except Exception:
                pass


def main() -> int:
    parser = argparse.ArgumentParser(description="Launch the app and pipeline.")
    parser.add_argument(
        "--generate-token",
        action="store_true",
        help="Print a random token and exit.",
    )
    args = parser.parse_args()
    if args.generate_token:
        print(secrets.token_urlsafe(48))
        return 0

    root_dir = os.path.dirname(os.path.abspath(__file__))
    pipeline_script = os.path.join(root_dir, "src", "pipeline.py")
    app_script = os.path.join(root_dir, "app.py")

    if not os.path.exists(pipeline_script):
        print(f"[LAUNCHER] Missing pipeline script: {pipeline_script}")
        return 1
    if not os.path.exists(app_script):
        print(f"[LAUNCHER] Missing app script: {app_script}")
        return 1

    env = _build_env(root_dir)
    python_exe = sys.executable
    port = _resolve_streamlit_port(env)
    url = f"http://127.0.0.1:{port}"

    print("[LAUNCHER] Starting pipeline watcher...")
    pipeline_proc = subprocess.Popen([python_exe, pipeline_script], cwd=root_dir, env=env)

    print("[LAUNCHER] Starting Streamlit app...")
    app_proc = subprocess.Popen(
        [
            python_exe,
            "-m",
            "streamlit",
            "run",
            app_script,
            "--server.headless=true",
            "--server.address=127.0.0.1",
            f"--server.port={port}",
            "--browser.gatherUsageStats=false",
        ],
        cwd=root_dir,
        env=env,
    )

    try:
        if not _wait_for_url(url, timeout=60, proc=app_proc):
            print("[LAUNCHER] Streamlit did not become ready.")
            if app_proc.poll() is not None:
                return app_proc.returncode or 1

        try:
            import webview
        except Exception as exc:
            print("[LAUNCHER] pywebview is not installed or failed to import.")
            print(f"[LAUNCHER] Open this URL in a browser: {url}")
            try:
                app_proc.wait()
                return app_proc.returncode or 0
            except KeyboardInterrupt:
                return 0

        print("[LAUNCHER] Opening native window...")
        webview.create_window("Semantic Search Assistant", url, width=1200, height=800, resizable=True)
        webview.start()
        return app_proc.poll() or 0
    except KeyboardInterrupt:
        print("\n[LAUNCHER] Shutting down...")
        return 0
    finally:
        _terminate_process(app_proc, "app")
        _terminate_process(pipeline_proc, "pipeline")
        print("[LAUNCHER] Exit complete.")


if __name__ == "__main__":
    raise SystemExit(main())
