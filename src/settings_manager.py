import copy
import json
import os
import time

# --- SETTINGS PATH ---
BASE_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
SETTINGS_PATH = os.path.join(BASE_DIR, "settings.json")

DEFAULT_SETTINGS = {
    "version": 1,
    "rag": {
        "engine": "cloud",
        "cloud_model": "gemini-2.5-flash",
        "local_model": "gemma2:2b",
        "ollama_url": "http://localhost:11434"
    },
    "crawler": {
        "folders": []
    },
    "pipeline": {
        "refresh_request_id": 0,
        "last_refresh_id": 0,
        "last_refresh_at": None,
        "last_refresh_status": None,
        "last_refresh_error": None,
        "refresh_requested_by": None,
        "refresh_requested_at": None
    }
}


def _atomic_write(path, data):
    temp_path = f"{path}.tmp"
    with open(temp_path, "w", encoding="utf-8") as f:
        json.dump(data, f, indent=2, ensure_ascii=True)
    os.replace(temp_path, path)


def _merge_defaults(target, defaults):
    changed = False
    for key, value in defaults.items():
        if key not in target:
            target[key] = copy.deepcopy(value)
            changed = True
        elif isinstance(value, dict) and isinstance(target[key], dict):
            if _merge_defaults(target[key], value):
                changed = True
    return changed


def _deep_merge(target, patch):
    for key, value in patch.items():
        if isinstance(value, dict) and isinstance(target.get(key), dict):
            _deep_merge(target[key], value)
        else:
            target[key] = value


def load_settings():
    if not os.path.exists(SETTINGS_PATH):
        settings = copy.deepcopy(DEFAULT_SETTINGS)
        _atomic_write(SETTINGS_PATH, settings)
        return settings

    try:
        with open(SETTINGS_PATH, "r", encoding="utf-8") as f:
            settings = json.load(f)
    except Exception:
        backup_path = f"{SETTINGS_PATH}.bak.{int(time.time())}"
        try:
            os.replace(SETTINGS_PATH, backup_path)
        except Exception:
            pass
        settings = copy.deepcopy(DEFAULT_SETTINGS)
        _atomic_write(SETTINGS_PATH, settings)
        return settings

    if _merge_defaults(settings, DEFAULT_SETTINGS):
        _atomic_write(SETTINGS_PATH, settings)
    return settings


def save_settings(settings):
    _atomic_write(SETTINGS_PATH, settings)
    return settings


def update_settings(patch):
    settings = load_settings()
    _deep_merge(settings, patch)
    return save_settings(settings)


def normalize_folder_path(path, base_dir=None):
    if path is None:
        return None
    cleaned = str(path).strip()
    if not cleaned:
        return None
    cleaned = os.path.expandvars(os.path.expanduser(cleaned))
    if not os.path.isabs(cleaned):
        base_dir = base_dir or BASE_DIR
        cleaned = os.path.abspath(os.path.join(base_dir, cleaned))
    return os.path.normpath(cleaned)


def clean_crawler_folders(folders, base_dir=None):
    seen = set()
    cleaned = []
    for folder in folders or []:
        normalized = normalize_folder_path(folder, base_dir=base_dir)
        if not normalized:
            continue
        if normalized in seen:
            continue
        seen.add(normalized)
        cleaned.append(normalized)
    return cleaned


def get_default_raw_folder(base_dir=None):
    base_dir = base_dir or BASE_DIR
    return os.path.join(base_dir, "data", "raw")


def get_configured_crawler_folders(settings, base_dir=None):
    folders = settings.get("crawler", {}).get("folders", [])
    return clean_crawler_folders(folders, base_dir=base_dir)


def get_effective_crawler_folders(settings, default_raw=None, base_dir=None):
    base_dir = base_dir or BASE_DIR
    configured = get_configured_crawler_folders(settings, base_dir=base_dir)
    if configured:
        return configured
    default_raw = default_raw or get_default_raw_folder(base_dir)
    default_raw = normalize_folder_path(default_raw, base_dir=base_dir)
    return [default_raw] if default_raw else []


def request_pipeline_refresh(requested_by=None):
    settings = load_settings()
    pipeline_settings = settings.setdefault("pipeline", {})
    current = pipeline_settings.get("refresh_request_id", 0) or 0
    next_id = int(current) + 1
    pipeline_settings["refresh_request_id"] = next_id
    pipeline_settings["refresh_requested_by"] = requested_by
    pipeline_settings["refresh_requested_at"] = int(time.time())
    save_settings(settings)
    return next_id
