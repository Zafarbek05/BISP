import os
import sys
import time
import shutil
import subprocess
import urllib.request
from urllib.parse import urlparse

DEFAULT_OLLAMA_URL = "http://localhost:11434"


def _build_version_url(ollama_url: str | None) -> str:
    base = (ollama_url or DEFAULT_OLLAMA_URL).strip()
    if not base:
        base = DEFAULT_OLLAMA_URL
    return f"{base.rstrip('/')}/api/version"


def _build_ollama_host_env(ollama_url: str | None) -> str | None:
    if not ollama_url:
        return None
    try:
        parsed = urlparse(ollama_url)
    except Exception:
        return None
    if not parsed.netloc:
        return None
    return parsed.netloc


def is_ollama_running(ollama_url: str | None = None, timeout: float = 1.5) -> bool:
    url = _build_version_url(ollama_url)
    try:
        with urllib.request.urlopen(url, timeout=timeout) as response:
            return response.status < 400
    except Exception:
        return False


def ensure_ollama_running(
    ollama_url: str | None = None,
    startup_timeout: float = 15.0,
) -> tuple[bool, str]:
    if is_ollama_running(ollama_url):
        return True, "Ollama is already running."

    ollama_bin = shutil.which("ollama")
    if not ollama_bin:
        return False, "Ollama CLI not found in PATH. Install Ollama or add it to PATH."

    env = os.environ.copy()
    host_env = _build_ollama_host_env(ollama_url)
    if host_env:
        env["OLLAMA_HOST"] = host_env

    kwargs = {
        "stdout": subprocess.DEVNULL,
        "stderr": subprocess.DEVNULL,
        "env": env,
    }
    if sys.platform.startswith("win"):
        kwargs["creationflags"] = subprocess.CREATE_NO_WINDOW
    else:
        kwargs["start_new_session"] = True

    try:
        subprocess.Popen([ollama_bin, "serve"], **kwargs)
    except Exception as exc:
        return False, f"Failed to start Ollama: {exc}"

    deadline = time.time() + startup_timeout
    while time.time() < deadline:
        if is_ollama_running(ollama_url):
            return True, "Ollama started."
        time.sleep(0.5)

    return False, "Ollama did not start in time. Check the install and port availability."


def stop_ollama_server(
    ollama_url: str | None = None,
    shutdown_timeout: float = 10.0,
) -> tuple[bool, str]:
    if not is_ollama_running(ollama_url):
        return True, "Ollama is already stopped."

    errors: list[str] = []
    if sys.platform.startswith("win"):
        for name in ("ollama.exe", "Ollama.exe"):
            try:
                result = subprocess.run(
                    ["taskkill", "/IM", name, "/T", "/F"],
                    capture_output=True,
                    text=True,
                    check=False,
                )
                if result.returncode == 0:
                    errors.clear()
                    break
                if result.stderr:
                    errors.append(result.stderr.strip())
            except Exception as exc:
                errors.append(str(exc))
    else:
        for cmd in (["pkill", "-f", "ollama serve"], ["pkill", "-f", "ollama"]):
            try:
                subprocess.run(cmd, capture_output=True, text=True, check=False)
            except Exception as exc:
                errors.append(str(exc))

    deadline = time.time() + shutdown_timeout
    while time.time() < deadline:
        if not is_ollama_running(ollama_url):
            return True, "Ollama stopped."
        time.sleep(0.5)

    if errors:
        return False, "Failed to stop Ollama. " + "; ".join(errors)
    return False, "Ollama is still running. Stop it manually if needed."
