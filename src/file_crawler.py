import json
import os
from docx import Document
from pypdf import PdfReader

# --- CONFIGURATION ---
CHUNK_SIZE = 1000  # Characters per chunk
CHUNK_OVERLAP = 200  # Characters to repeat between chunks


def read_pdf(filepath):
    try:
        reader = PdfReader(filepath)
        text = ""
        for page in reader.pages:
            extract = page.extract_text()
            if extract: text += extract + "\n"
        return text
    except Exception as e:
        return ""


def read_docx(filepath):
    try:
        doc = Document(filepath)
        text = ""
        for paragraph in doc.paragraphs:
            if paragraph.text: text += paragraph.text + "\n"
        return text
    except Exception as e:
        return ""


def read_text_file(filepath):
    try:
        with open(filepath, 'r', encoding='utf-8', errors='ignore') as f:
            return f.read()
    except Exception as e:
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
    else:
        return None


# --- NEW: CHUNKING LOGIC ---
def recursive_chunk_text(text, chunk_size, overlap):
    """
    Splits text into chunks using an iterative sliding window.
    This avoids RecursionErrors and ensures consistent chunk sizes.
    """
    if not text or chunk_size <= 0:
        return []

    # If the text is smaller than the chunk size, return it as one chunk
    if len(text) <= chunk_size:
        return [text]

    chunks = []
    start = 0

    # Iterate through the text with a step size of (chunk_size - overlap)
    while start < len(text):
        end = start + chunk_size
        chunk = text[start:end]
        chunks.append(chunk)

        # Move the start pointer forward, but subtract overlap to keep context
        start += (chunk_size - overlap)

        # Safety break: if we aren't moving forward, stop to avoid infinite loop
        if chunk_size <= overlap:
            break

    return chunks

def scan_directory(path):
    node = {"name": os.path.basename(path), "path": path}

    if os.path.isfile(path):
        node["type"] = "file"
        content = get_file_content(path)

        if content:
            # Save raw content (optional, good for debugging)
            # node["content_raw"] = content[:100] + "..."

            # --- APPLY CHUNKING ---
            node["chunks"] = recursive_chunk_text(content, CHUNK_SIZE, CHUNK_OVERLAP)
            node["chunk_count"] = len(node["chunks"])
        else:
            node["chunks"] = []
            node["chunk_count"] = 0

    elif os.path.isdir(path):
        node["type"] = "directory"
        node["children"] = []
        try:
            entries = sorted(os.scandir(path), key=lambda e: e.name)
            for entry in entries:
                if not entry.name.startswith('.'):
                    node["children"].append(scan_directory(entry.path))
        except PermissionError:
            pass

    return node


def save_structure(data, root_dir):
    data_dir = os.path.join(root_dir, "data")
    if not os.path.exists(data_dir): os.makedirs(data_dir)
    output_file = os.path.join(data_dir, "file_index_chunked.json")
    with open(output_file, "w", encoding='utf-8') as f:
        json.dump(data, f, indent=4)
    print(f"Saved chunked data to: {output_file}")


if __name__ == "__main__":
    folder_to_scan = "C:\\Users\Zafarbek\Desktop\BISP"
    print(f"Scanning, Reading, and Chunking files in: {folder_to_scan}...")
    file_tree = scan_directory(folder_to_scan)
    save_structure(file_tree, os.getcwd())