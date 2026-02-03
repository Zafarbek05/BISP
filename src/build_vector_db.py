import json
import os
import numpy as np
from sentence_transformers import SentenceTransformer

# --- ANCHOR PATHING ---
BASE_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
PROCESSED_DATA_DIR = os.path.join(BASE_DIR, "data", "processed")

print("Loading AI Embedding Model...")
model = SentenceTransformer('all-MiniLM-L6-v2')


def extract_chunks(node, flat_list):
    if node.get("type") == "file" and "chunks" in node:
        for i, text in enumerate(node["chunks"]):
            flat_list.append({
                "source": node["name"],
                "path": node["path"],
                "chunk_index": i,
                "content": text
            })
    elif node.get("type") == "directory" and "children" in node:
        for child in node["children"]:
            extract_chunks(child, flat_list)


def build_vectors():
    input_path = os.path.join(PROCESSED_DATA_DIR, "file_index_chunked.json")

    if not os.path.exists(input_path):
        print(f"Error: Could not find {input_path}. Run file_crawler.py first.")
        return

    with open(input_path, "r", encoding='utf-8') as f:
        tree_data = json.load(f)

    all_chunks = []
    extract_chunks(tree_data, all_chunks)

    if not all_chunks:
        print("No text chunks found to embed.")
        return

    print(f"Embedding {len(all_chunks)} chunks...")
    text_contents = [item["content"] for item in all_chunks]
    embeddings = model.encode(text_contents, show_progress_bar=True)

    # Define output paths
    output_data_path = os.path.join(PROCESSED_DATA_DIR, "processed_chunks.json")
    output_vectors_path = os.path.join(PROCESSED_DATA_DIR, "vector_storage.npy")

    with open(output_data_path, "w", encoding='utf-8') as f:
        json.dump(all_chunks, f, indent=4)

    np.save(output_vectors_path, embeddings)
    print(f"Success! Vectors and Chunks saved in: {PROCESSED_DATA_DIR}")


if __name__ == "__main__":
    build_vectors()