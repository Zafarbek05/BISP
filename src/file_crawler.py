import json
import os
from docx import Document
from pypdf import PdfReader

# --- ANCHOR PATHING ---
BASE_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
RAW_DATA_DIR = os.path.join(BASE_DIR, "data", "raw")
PROCESSED_DATA_DIR = os.path.join(BASE_DIR, "data", "processed")

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


def scan_directory(path):
    node = {"name": os.path.basename(path), "path": path}
    if os.path.isfile(path):
        node["type"] = "file"
        content = get_file_content(path)
        node["chunks"] = recursive_chunk_text(content, CHUNK_SIZE, CHUNK_OVERLAP) if content else []
        node["chunk_count"] = len(node["chunks"])
    elif os.path.isdir(path):
        node["type"] = "directory"
        node["children"] = []
        try:
            entries = sorted(os.scandir(path), key=lambda e: e.name)
            for entry in entries:
                if not entry.name.startswith(('.', '~')):  # Ignore hidden and temp files
                    node["children"].append(scan_directory(entry.path))
        except PermissionError:
            pass
    return node


if __name__ == "__main__":
    # Ensure processed directory exists
    if not os.path.exists(PROCESSED_DATA_DIR):
        os.makedirs(PROCESSED_DATA_DIR)

    print(f"Scanning folder: {RAW_DATA_DIR}...")
    file_tree = scan_directory(RAW_DATA_DIR)

    output_file = os.path.join(PROCESSED_DATA_DIR, "file_index_chunked.json")
    with open(output_file, "w", encoding='utf-8') as f:
        json.dump(file_tree, f, indent=4)

    print(f"Saved chunked data to: {output_file}")