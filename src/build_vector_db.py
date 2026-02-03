import json
import os
import numpy as np
from sentence_transformers import SentenceTransformer

# 1. Load the Model
print("Loading AI Embedding Model...")
model = SentenceTransformer('all-MiniLM-L6-v2')

def extract_chunks(node, flat_list):
    """Recursively pulls all chunks out of your tree structure"""
    if node["type"] == "file" and "chunks" in node:
        for i, text in enumerate(node["chunks"]):
            flat_list.append({
                "source": node["name"],
                "path": node["path"],
                "chunk_index": i,
                "content": text
            })
    elif node["type"] == "directory" and "children" in node:
        for child in node["children"]:
            extract_chunks(child, flat_list)


def build_vectors():
    # Load your existing chunked data
    input_path = os.path.join("../data", "file_index_chunked.json")
    with open(input_path, "r", encoding='utf-8') as f:
        tree_data = json.load(f)

    # Flatten the tree into a list of chunks
    all_chunks = []
    extract_chunks(tree_data, all_chunks)

    print(f"Found {len(all_chunks)} total chunks. Starting embedding...")

    # Extract just the text for the model
    text_contents = [item["content"] for item in all_chunks]

    # 2. GENERATE EMBEDDINGS (The AI Step)
    # This turns text into a 384-dimensional vector
    embeddings = model.encode(text_contents, show_progress_bar=True)

    # 3. Save the results
    # We save the text and the vectors separately but linked by index
    # for better performance later.
    output_data_path = os.path.join("../data", "processed_chunks.json")
    output_vectors_path = os.path.join("../data", "vector_storage.npy")

    with open(output_data_path, "w", encoding='utf-8') as f:
        json.dump(all_chunks, f, indent=4)

    # Use Numpy to save the heavy numerical data efficiently
    np.save(output_vectors_path, embeddings)

    print(f"Success! Vectors saved to {output_vectors_path}")


if __name__ == "__main__":
    build_vectors()