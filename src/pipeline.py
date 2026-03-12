import time
import os
import threading
import subprocess
import sys
from watchdog.observers import Observer
from watchdog.events import FileSystemEventHandler
try:
    from . import env_loader  # noqa: F401
except ImportError:
    import env_loader  # noqa: F401
try:
    from . import processed_storage as storage
except ImportError:
    import processed_storage as storage

# --- SMART PATH LOGIC ---
# 1. Get the directory where THIS script is (the 'src' folder)
current_script_dir = os.path.dirname(os.path.abspath(__file__))

# 2. Get the Parent directory (the 'Root' folder)
root_dir = os.path.dirname(current_script_dir)

# 3. Define the path to data/raw in the root
WATCH_DIRECTORY = os.path.normpath(os.path.join(root_dir, "data", "raw"))

# Paths to the scripts we want to run (also in src)
CRAWLER_SCRIPT = os.path.join(current_script_dir, "file_crawler.py")
VECTOR_DB_SCRIPT = os.path.join(current_script_dir, "build_vector_db.py")
VECTORS_PATH = os.path.normpath(os.path.join(root_dir, "data", "processed", "vector_storage.npy"))


def should_build_vectors():
    if not os.path.exists(VECTORS_PATH):
        return True
    db_path = storage.get_db_path()
    if not os.path.exists(db_path):
        return True
    try:
        changed = storage.get_crawl_state()
        if changed is None:
            return True
        return changed
    except Exception:
        return True


def run_pipeline(trigger_label=None, filepath=None):
    if trigger_label:
        label = f"{trigger_label}"
        if filepath:
            label += f": {os.path.basename(filepath)}"
        print(f"\n[PIPELINE] Triggered by {label}")

    try:
        print("--- Running Crawler ---")
        subprocess.run([sys.executable, CRAWLER_SCRIPT], check=True)

        if should_build_vectors():
            print("--- Running Vector Builder ---")
            subprocess.run([sys.executable, VECTOR_DB_SCRIPT], check=True)
        else:
            print("--- Skipping Vector Builder (no content changes) ---")

        print(">>> [SUCCESS] Pipeline update complete!")
        return True
    except Exception as e:
        print(f"[ERROR] Pipeline failed: {e}")
        return False


class PipelineHandler(FileSystemEventHandler):
    def __init__(self):
        self.last_trigger_time = 0
        self.debounce_seconds = 5
        self.pending_paths = set()
        self.timer = None
        self.lock = threading.Lock()

    def on_any_event(self, event):
        if event.is_directory:
            return

        # Filter out temporary Word files
        if os.path.basename(event.src_path).startswith("~$"):
            return

        if event.event_type in ['created', 'modified', 'moved', 'deleted']:
            self.queue_event(event)

    def queue_event(self, event):
        filepath = getattr(event, "dest_path", None) or event.src_path
        with self.lock:
            self.pending_paths.add(filepath)
            if self.timer:
                self.timer.cancel()
            self.timer = threading.Timer(self.debounce_seconds, self.flush)
            self.timer.daemon = True
            self.timer.start()

    def flush(self):
        with self.lock:
            pending = list(self.pending_paths)
            self.pending_paths.clear()
            self.timer = None

        label = f"batched update ({len(pending)} changes)"
        if run_pipeline(label):
            self.last_trigger_time = time.time()


if __name__ == "__main__":
    if not os.path.exists(WATCH_DIRECTORY):
        print(f"Error: Directory NOT found at {WATCH_DIRECTORY}")
        # Create it if it's missing
        os.makedirs(WATCH_DIRECTORY)
        print(f"Created folder at: {WATCH_DIRECTORY}")

    print("--- Running initial pipeline update ---")
    run_pipeline("startup")

    event_handler = PipelineHandler()
    observer = Observer()
    observer.schedule(event_handler, WATCH_DIRECTORY, recursive=False)

    print(f"--- RAG Pipeline Watcher Active ---")
    print(f"Watching: {WATCH_DIRECTORY}")

    observer.start()
    try:
        while True:
            time.sleep(1)
    except KeyboardInterrupt:
        observer.stop()
    observer.join()
