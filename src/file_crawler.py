import json
import os
import hashlib
from docx import Document
from pypdf import PdfReader

# --- ANCHOR PATHING ---
BASE_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
RAW_DATA_DIR = os.path.join(BASE_DIR, "data", "raw")
PROCESSED_DATA_DIR = os.path.join(BASE_DIR, "data", "processed")
CHUNK_DIR = os.path.join(PROCESSED_DATA_DIR, "chunks")
MANIFEST_PATH = os.path.join(PROCESSED_DATA_DIR, "file_manifest.json")
CRAWL_STATE_PATH = os.path.join(PROCESSED_DATA_DIR, "crawl_state.json")

# --- CONFIGURATION ---
CHUNK_SIZE = 1000
CHUNK_OVERLAP = 200


def read_pdf(filepath):
    try:
        reader = PdfReader(filepath)
        text = ""
        for page in reader.pages:
            extract = page.extract_text()
            if extract: text += extract + "\n"
        return text
    except Exception:
        return ""


def read_docx(filepath):
    try:
        doc = Document(filepath)
        text = ""
        for paragraph in doc.paragraphs:
            if paragraph.text: text += paragraph.text + "\n"
        return text
    except Exception:
        return ""


def read_text_file(filepath):
    try:
        with open(filepath, 'r', encoding='utf-8', errors='ignore') as f:
            return f.read()
    except Exception:
        return ""


def get_file_content(filepath):
    _, ext = os.path.splitext(filepath)
    ext = ext.lower()
    if ext == ".pdf":
        return read_pdf(filepath)
    elif ext == ".docx":
        return read_docx(filepath)
    elif ext in [".txt", ".md", ".py", ".json", ".csv"]:
        return read_text_file(filepath)
    return None


def recursive_chunk_text(text, chunk_size, overlap):
    if not text or chunk_size <= 0: return []
    if len(text) <= chunk_size: return [text]
    chunks = []
    start = 0
    while start < len(text):
        end = start + chunk_size
        chunks.append(text[start:end])
        start += (chunk_size - overlap)
        if chunk_size <= overlap: break
    return chunks


def sha256_text(text):
    return hashlib.sha256(text.encode("utf-8", errors="ignore")).hexdigest()


def file_id_from_path(path):
    return hashlib.sha1(path.lower().encode("utf-8", errors="ignore")).hexdigest()


def load_manifest():
    if not os.path.exists(MANIFEST_PATH):
        return {"files": {}}
    with open(MANIFEST_PATH, "r", encoding="utf-8") as f:
        return json.load(f)


def save_manifest(manifest):
    if not os.path.exists(PROCESSED_DATA_DIR):
        os.makedirs(PROCESSED_DATA_DIR)
    with open(MANIFEST_PATH, "w", encoding="utf-8") as f:
        json.dump(manifest, f, indent=4)


def save_crawl_state(changed):
    state = {"changed": changed}
    with open(CRAWL_STATE_PATH, "w", encoding="utf-8") as f:
        json.dump(state, f, indent=4)


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


if __name__ == "__main__":
    # Ensure processed directory exists
    if not os.path.exists(PROCESSED_DATA_DIR):
        os.makedirs(PROCESSED_DATA_DIR)

    if not os.path.exists(CHUNK_DIR):
        os.makedirs(CHUNK_DIR)

    print(f"Scanning folder: {RAW_DATA_DIR}...")
    manifest = load_manifest()
    existing_files = manifest.get("files", {})
    new_manifest = {"files": {}}
    changed = False

    current_paths = set()
    for filepath in iter_raw_files(RAW_DATA_DIR):
        current_paths.add(filepath)
        stat = os.stat(filepath)
        existing_entry = existing_files.get(filepath)

        if existing_entry and existing_entry.get("mtime") == stat.st_mtime and existing_entry.get("size") == stat.st_size:
            new_manifest["files"][filepath] = existing_entry
            continue

        content = get_file_content(filepath)
        if content is None:
            new_manifest["files"][filepath] = {
                "path": filepath,
                "name": os.path.basename(filepath),
                "mtime": stat.st_mtime,
                "size": stat.st_size,
                "content_hash": None,
                "chunk_file": None
            }
            if not existing_entry:
                changed = True
            continue

        content_hash = sha256_text(content)
        if existing_entry and existing_entry.get("content_hash") == content_hash:
            existing_entry["mtime"] = stat.st_mtime
            existing_entry["size"] = stat.st_size
            new_manifest["files"][filepath] = existing_entry
            continue

        chunk_records = build_chunk_records(filepath, content)
        chunk_file = (existing_entry or {}).get("chunk_file") or os.path.join("chunks", f"{file_id_from_path(filepath)}.json")
        chunk_path = os.path.join(PROCESSED_DATA_DIR, chunk_file)

        with open(chunk_path, "w", encoding="utf-8") as f:
            json.dump(chunk_records, f, indent=4)

        new_manifest["files"][filepath] = {
            "path": filepath,
            "name": os.path.basename(filepath),
            "mtime": stat.st_mtime,
            "size": stat.st_size,
            "content_hash": content_hash,
            "chunk_file": chunk_file
        }
        changed = True

    for filepath, entry in existing_files.items():
        if filepath in current_paths:
            continue
        chunk_file = entry.get("chunk_file")
        if chunk_file:
            chunk_path = os.path.join(PROCESSED_DATA_DIR, chunk_file)
            if os.path.exists(chunk_path):
                os.remove(chunk_path)
        changed = True

    save_manifest(new_manifest)
    save_crawl_state(changed)

    if changed:
        print("Detected content changes. Updated manifest and chunk files.")
    else:
        print("No content changes detected. Manifest refreshed.")
