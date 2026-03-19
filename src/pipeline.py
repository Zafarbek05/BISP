import time
import os
import threading
import hashlib
from watchdog.observers import Observer
from watchdog.events import FileSystemEventHandler
try:
    from . import processed_storage as storage
except ImportError:
    import processed_storage as storage
try:
    from . import settings_manager as settings_manager
except ImportError:
    import settings_manager as settings_manager

# --- SMART PATH LOGIC ---
# 1. Get the directory where THIS script is (the 'src' folder)
current_script_dir = os.path.dirname(os.path.abspath(__file__))

# 2. Get the Parent directory (the 'Root' folder)
root_dir = os.path.dirname(current_script_dir)

# 3. Define the path to data/raw in the root
DEFAULT_WATCH_DIRECTORY = os.path.normpath(os.path.join(root_dir, "data", "raw"))
PROCESSED_DATA_DIR = os.path.normpath(os.path.join(root_dir, "data", "processed"))

VECTORS_PATH = os.path.normpath(os.path.join(root_dir, "data", "processed", "vector_storage.npy"))
CHUNK_SIZE = 1000
CHUNK_OVERLAP = 200
EMBEDDING_MODEL_NAME = "all-MiniLM-L6-v2"

DEFAULT_RAW_DATA_DIR = DEFAULT_WATCH_DIRECTORY


def read_pdf(filepath):
    from pypdf import PdfReader
    try:
        reader = PdfReader(filepath)
        text = ""
        for page in reader.pages:
            extract = page.extract_text()
            if extract:
                text += extract + "\n"
        return text
    except Exception:
        return ""


def read_docx(filepath):
    from docx import Document
    try:
        doc = Document(filepath)
        text = ""
        for paragraph in doc.paragraphs:
            if paragraph.text:
                text += paragraph.text + "\n"
        return text
    except Exception:
        return ""


def read_text_file(filepath):
    try:
        with open(filepath, "r", encoding="utf-8", errors="ignore") as f:
            return f.read()
    except Exception:
        return ""


def get_file_content(filepath):
    _, ext = os.path.splitext(filepath)
    ext = ext.lower()
    if ext == ".pdf":
        return read_pdf(filepath)
    if ext == ".docx":
        return read_docx(filepath)
    if ext in [".txt", ".md", ".py", ".json", ".csv"]:
        return read_text_file(filepath)
    return None


def recursive_chunk_text(text, chunk_size, overlap):
    if not text or chunk_size <= 0:
        return []
    if len(text) <= chunk_size:
        return [text]
    chunks = []
    start = 0
    while start < len(text):
        end = start + chunk_size
        chunks.append(text[start:end])
        start += (chunk_size - overlap)
        if chunk_size <= overlap:
            break
    return chunks


def sha256_text(text):
    return hashlib.sha256(text.encode("utf-8", errors="ignore")).hexdigest()


def load_manifest():
    return storage.load_manifest()


def save_manifest(manifest):
    storage.save_manifest(manifest)


def save_crawl_state(changed):
    storage.save_crawl_state(changed)


def iter_raw_files(root_dir):
    for root, dirs, files in os.walk(root_dir):
        dirs[:] = [d for d in dirs if not d.startswith((".", "~"))]
        for filename in files:
            if filename.startswith((".", "~")) or filename.startswith("~$"):
                continue
            yield os.path.join(root, filename)


def build_chunk_records(filepath, content):
    chunks = recursive_chunk_text(content, CHUNK_SIZE, CHUNK_OVERLAP) if content else []
    records = []
    for i, text in enumerate(chunks):
        records.append({
            "source": os.path.basename(filepath),
            "path": filepath,
            "chunk_index": i,
            "content": text,
            "chunk_hash": sha256_text(text)
        })
    return records


def get_crawl_roots():
    settings = settings_manager.load_settings()
    return settings_manager.get_effective_crawler_folders(settings, DEFAULT_RAW_DATA_DIR, base_dir=root_dir)


def run_crawler():
    from docx import Document  # noqa: F401
    from pypdf import PdfReader  # noqa: F401
    storage.init_db()

    roots = get_crawl_roots()
    valid_roots = []
    for root in roots:
        if os.path.exists(root):
            valid_roots.append(root)
        else:
            print(f"Warning: folder not found, skipping: {root}")

    if not valid_roots:
        os.makedirs(DEFAULT_RAW_DATA_DIR, exist_ok=True)
        valid_roots = [DEFAULT_RAW_DATA_DIR]

    print("Scanning folder(s):")
    for root in valid_roots:
        print(f"- {root}")
    manifest = load_manifest()
    existing_files = manifest.get("files", {})
    new_manifest = {"files": {}}
    changed = False

    current_paths = set()
    for root_dir in valid_roots:
        for filepath in iter_raw_files(root_dir):
            current_paths.add(filepath)
            stat = os.stat(filepath)
            existing_entry = existing_files.get(filepath)

            if (existing_entry
                    and existing_entry.get("mtime") == stat.st_mtime
                    and existing_entry.get("size") == stat.st_size):
                new_manifest["files"][filepath] = existing_entry
                continue

            content = get_file_content(filepath)
            if content is None:
                storage.delete_chunks_for_file(filepath)
                new_manifest["files"][filepath] = {
                    "path": filepath,
                    "name": os.path.basename(filepath),
                    "mtime": stat.st_mtime,
                    "size": stat.st_size,
                    "content_hash": None
                }
                if not existing_entry or existing_entry.get("content_hash") is not None:
                    changed = True
                continue

            content_hash = sha256_text(content)
            if existing_entry and existing_entry.get("content_hash") == content_hash:
                existing_entry["mtime"] = stat.st_mtime
                existing_entry["size"] = stat.st_size
                new_manifest["files"][filepath] = existing_entry
                continue

            chunk_records = build_chunk_records(filepath, content)
            storage.save_chunks_for_file(filepath, chunk_records)

            new_manifest["files"][filepath] = {
                "path": filepath,
                "name": os.path.basename(filepath),
                "mtime": stat.st_mtime,
                "size": stat.st_size,
                "content_hash": content_hash
            }
            changed = True

    for filepath in existing_files.keys():
        if filepath in current_paths:
            continue
        changed = True

    save_manifest(new_manifest)
    save_crawl_state(changed)

    if changed:
        print("Detected content changes. Updated manifest and chunk files.")
    else:
        print("No content changes detected. Manifest refreshed.")
    return changed


def build_vectors():
    import numpy as np
    from sentence_transformers import SentenceTransformer

    def load_vector_cache():
        cache = {}
        for chunk_hash, blob, dim, dtype in storage.load_vector_cache_rows():
            if not chunk_hash or blob is None:
                continue
            try:
                vec = np.frombuffer(blob, dtype=np.dtype(dtype))
                if dim and vec.size != dim:
                    continue
                cache[chunk_hash] = vec
            except Exception:
                continue
        return cache

    print("Loading AI Embedding Model...")
    model = SentenceTransformer(EMBEDDING_MODEL_NAME)

    storage.init_db()
    all_chunks = storage.get_all_chunks()

    if not all_chunks:
        print("No text chunks found to embed.")
        return

    vector_cache = load_vector_cache()
    missing_texts = []
    missing_hashes = []

    for chunk in all_chunks:
        chunk_content = chunk.get("content") or ""
        chunk_hash = chunk.get("chunk_hash") or sha256_text(chunk_content)
        chunk["chunk_hash"] = chunk_hash
        if not chunk_hash or chunk_hash not in vector_cache:
            missing_texts.append(chunk_content)
            missing_hashes.append(chunk_hash)

    new_cache_rows = []
    if missing_texts:
        print(f"Embedding {len(missing_texts)} new chunks...")
        embeddings = model.encode(missing_texts, show_progress_bar=True)
        embeddings = np.asarray(embeddings, dtype=np.float32)
        for chunk_hash, vector in zip(missing_hashes, embeddings):
            if chunk_hash:
                vector_cache[chunk_hash] = vector
                new_cache_rows.append((chunk_hash, vector.tobytes(), vector.shape[0], "float32"))
    else:
        print("No new chunks to embed. Reusing existing vectors.")

    vectors = np.stack([vector_cache[chunk["chunk_hash"]] for chunk in all_chunks])

    storage.upsert_vector_cache_rows(new_cache_rows)
    np.save(VECTORS_PATH, vectors)
    print(f"Success! Vectors saved in: {PROCESSED_DATA_DIR}")


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
        run_crawler()

        if should_build_vectors():
            print("--- Running Vector Builder ---")
            build_vectors()
        else:
            print("--- Skipping Vector Builder (no content changes) ---")

        print(">>> [SUCCESS] Pipeline update complete!")
        return True, None
    except Exception as e:
        print(f"[ERROR] Pipeline failed: {e}")
        return False, str(e)


def get_watch_directories():
    settings = settings_manager.load_settings()
    return settings_manager.get_effective_crawler_folders(
        settings,
        DEFAULT_WATCH_DIRECTORY,
        base_dir=root_dir
    )


def ensure_watch_directories(directories):
    valid = []
    for directory in directories:
        if os.path.exists(directory):
            valid.append(directory)
        else:
            print(f"Warning: watch directory not found, skipping: {directory}")

    if not valid:
        os.makedirs(DEFAULT_WATCH_DIRECTORY, exist_ok=True)
        valid = [DEFAULT_WATCH_DIRECTORY]
    return valid


def apply_watch_directories(observer, handler, directories):
    observer.unschedule_all()
    for directory in directories:
        observer.schedule(handler, directory, recursive=True)


def handle_refresh_request(settings):
    pipeline_settings = settings.get("pipeline", {})
    request_id = int(pipeline_settings.get("refresh_request_id") or 0)
    last_id = int(pipeline_settings.get("last_refresh_id") or 0)
    if request_id <= last_id:
        return False

    success, error = run_pipeline("manual refresh")
    status_patch = {
        "pipeline": {
            "last_refresh_id": request_id,
            "last_refresh_at": int(time.time()),
            "last_refresh_status": "success" if success else "error",
            "last_refresh_error": error,
        }
    }
    settings_manager.update_settings(status_patch)
    return True


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
        success, _ = run_pipeline(label)
        if success:
            self.last_trigger_time = time.time()


if __name__ == "__main__":
    event_handler = PipelineHandler()
    observer = Observer()
    watch_directories = ensure_watch_directories(get_watch_directories())
    apply_watch_directories(observer, event_handler, watch_directories)

    print("--- Running initial pipeline update ---")
    run_pipeline("startup")

    print("--- RAG Pipeline Watcher Active ---")
    for directory in watch_directories:
        print(f"Watching: {directory}")

    observer.start()
    try:
        while True:
            time.sleep(1)
            settings = settings_manager.load_settings()
            desired_directories = ensure_watch_directories(
                settings_manager.get_effective_crawler_folders(
                    settings,
                    DEFAULT_WATCH_DIRECTORY,
                    base_dir=root_dir
                )
            )
            if desired_directories != watch_directories:
                watch_directories = desired_directories
                apply_watch_directories(observer, event_handler, watch_directories)
                print("--- Watch folders updated ---")
                for directory in watch_directories:
                    print(f"Watching: {directory}")
                run_pipeline("watch folders updated")

            handle_refresh_request(settings)
    except KeyboardInterrupt:
        observer.stop()
    observer.join()
