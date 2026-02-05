import json
import os
import hashlib
import numpy as np
from sentence_transformers import SentenceTransformer

# --- ANCHOR PATHING ---
BASE_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
PROCESSED_DATA_DIR = os.path.join(BASE_DIR, "data", "processed")
MANIFEST_PATH = os.path.join(PROCESSED_DATA_DIR, "file_manifest.json")
CHUNKS_OUTPUT_PATH = os.path.join(PROCESSED_DATA_DIR, "processed_chunks.json")
VECTORS_OUTPUT_PATH = os.path.join(PROCESSED_DATA_DIR, "vector_storage.npy")

print("Loading AI Embedding Model...")
model = SentenceTransformer('all-MiniLM-L6-v2')


def load_manifest():
    if not os.path.exists(MANIFEST_PATH):
        return None
    with open(MANIFEST_PATH, "r", encoding="utf-8") as f:
        return json.load(f)


def load_existing_vectors():
    if not os.path.exists(CHUNKS_OUTPUT_PATH) or not os.path.exists(VECTORS_OUTPUT_PATH):
        return {}, None

    with open(CHUNKS_OUTPUT_PATH, "r", encoding="utf-8") as f:
        old_chunks = json.load(f)
    old_vectors = np.load(VECTORS_OUTPUT_PATH)

    if len(old_chunks) != len(old_vectors):
        return {}, None

    cache = {}
    for i, chunk in enumerate(old_chunks):
        chunk_hash = chunk.get("chunk_hash")
        if chunk_hash and chunk_hash not in cache:
            cache[chunk_hash] = old_vectors[i]
    return cache, old_vectors


def sha256_text(text):
    return hashlib.sha256(text.encode("utf-8", errors="ignore")).hexdigest()


def build_vectors():
    manifest = load_manifest()
    if not manifest:
        print(f"Error: Could not find {MANIFEST_PATH}. Run file_crawler.py first.")
        return

    all_chunks = []
    files = manifest.get("files", {})
    for filepath in sorted(files.keys()):
        entry = files[filepath]
        chunk_file = entry.get("chunk_file")
        if not chunk_file:
            continue
        chunk_path = os.path.join(PROCESSED_DATA_DIR, chunk_file)
        if not os.path.exists(chunk_path):
            continue
        with open(chunk_path, "r", encoding="utf-8") as f:
            chunk_records = json.load(f)
        all_chunks.extend(chunk_records)

    if not all_chunks:
        print("No text chunks found to embed.")
        return

    vector_cache, _ = load_existing_vectors()
    missing_texts = []
    missing_hashes = []

    for chunk in all_chunks:
        chunk_hash = chunk.get("chunk_hash") or sha256_text(chunk.get("content", ""))
        chunk["chunk_hash"] = chunk_hash
        if not chunk_hash or chunk_hash not in vector_cache:
            missing_texts.append(chunk["content"])
            missing_hashes.append(chunk_hash)

    if missing_texts:
        print(f"Embedding {len(missing_texts)} new chunks...")
        embeddings = model.encode(missing_texts, show_progress_bar=True)
        for chunk_hash, vector in zip(missing_hashes, embeddings):
            if chunk_hash:
                vector_cache[chunk_hash] = vector
    else:
        print("No new chunks to embed. Reusing existing vectors.")

    vectors = np.stack([vector_cache[chunk["chunk_hash"]] for chunk in all_chunks])

    with open(CHUNKS_OUTPUT_PATH, "w", encoding="utf-8") as f:
        json.dump(all_chunks, f, indent=4)
    np.save(VECTORS_OUTPUT_PATH, vectors)
    print(f"Success! Vectors and Chunks saved in: {PROCESSED_DATA_DIR}")


if __name__ == "__main__":
    build_vectors()
