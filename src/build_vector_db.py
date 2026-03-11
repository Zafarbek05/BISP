import os
import hashlib
import numpy as np
from sentence_transformers import SentenceTransformer
try:
    from . import processed_storage as storage
except ImportError:
    import processed_storage as storage

# --- ANCHOR PATHING ---
BASE_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
PROCESSED_DATA_DIR = os.path.join(BASE_DIR, "data", "processed")
VECTORS_OUTPUT_PATH = os.path.join(PROCESSED_DATA_DIR, "vector_storage.npy")

print("Loading AI Embedding Model...")
model = SentenceTransformer('all-MiniLM-L6-v2')


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


def sha256_text(text):
    return hashlib.sha256(text.encode("utf-8", errors="ignore")).hexdigest()


def build_vectors():
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
    np.save(VECTORS_OUTPUT_PATH, vectors)
    print(f"Success! Vectors saved in: {PROCESSED_DATA_DIR}")


if __name__ == "__main__":
    build_vectors()
