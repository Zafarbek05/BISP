import time
import os
import subprocess
import sys
from watchdog.observers import Observer
from watchdog.events import FileSystemEventHandler

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


class PipelineHandler(FileSystemEventHandler):
    def __init__(self):
        self.last_trigger_time = 0
        self.debounce_seconds = 2

    def on_any_event(self, event):
        if event.is_directory:
            return

        # Filter out temporary Word files
        if os.path.basename(event.src_path).startswith("~$"):
            return

        if event.event_type in ['created', 'modified', 'moved']:
            self.trigger_pipeline(event.src_path)

    def trigger_pipeline(self, filepath):
        current_time = time.time()
        if current_time - self.last_trigger_time < self.debounce_seconds:
            return

        print(f"\n[WATCHDOG] Valid change detected: {os.path.basename(filepath)}")

        # Run scripts using sys.executable to maintain the environment
        try:
            print(f"--- Running Crawler ---")
            subprocess.run([sys.executable, CRAWLER_SCRIPT], check=True)

            print(f"--- Running Vector Builder ---")
            subprocess.run([sys.executable, VECTOR_DB_SCRIPT], check=True)

            self.last_trigger_time = time.time()
            print(">>> [SUCCESS] Pipeline automated update complete!")
        except Exception as e:
            print(f"[ERROR] Pipeline failed: {e}")


if __name__ == "__main__":
    if not os.path.exists(WATCH_DIRECTORY):
        print(f"Error: Directory NOT found at {WATCH_DIRECTORY}")
        # Create it if it's missing
        os.makedirs(WATCH_DIRECTORY)
        print(f"Created folder at: {WATCH_DIRECTORY}")

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