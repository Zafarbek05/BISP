import os
import argparse
import numpy as np
try:
    from . import env_loader  # noqa: F401
except ImportError:
    import env_loader  # noqa: F401
try:
    from . import processed_storage as storage
except ImportError:
    import processed_storage as storage

# --- SMART PATHING ---
# Gets the 'src' folder, then goes up to the Project Root
BASE_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
PROCESSED_DATA_DIR = os.path.join(BASE_DIR, "data", "processed")
api_key = os.getenv("GEMINI_API_KEY")

# --- INITIALIZATION ---
CURRENT_MODEL = "gemini-2.5-flash"

# 1. Setup Embedding Model
model_embed = None
genai_client = None

# 2. Load Processed Data
db_path = storage.get_db_path()
vectors_path = os.path.join(PROCESSED_DATA_DIR, "vector_storage.npy")

data_cache = {
    "chunks": None,
    "vectors": None,
    "db_mtime": None,
    "vectors_mtime": None,
    "db_size": None,
    "vectors_size": None,
}


def get_embedder():
    global model_embed
    if model_embed is None:
        # Lazy import to keep Streamlit startup fast.
        from sentence_transformers import SentenceTransformer
        print("Initializing Embedding Model...")
        model_embed = SentenceTransformer("all-MiniLM-L6-v2")
    return model_embed


def get_genai_client():
    global genai_client
    if genai_client is None:
        if not api_key:
            raise ValueError("API Key not found. Please check your .env file in the root directory.")
        # Lazy import to reduce import-time overhead.
        from google import genai
        genai_client = genai.Client(api_key=api_key)
    return genai_client


def load_processed_data():
    if not os.path.exists(db_path) or not os.path.exists(vectors_path):
        raise FileNotFoundError(f"Processed data not found in {PROCESSED_DATA_DIR}. Please run the pipeline first.")

    db_mtime = os.path.getmtime(db_path)
    vectors_mtime = os.path.getmtime(vectors_path)
    db_size = os.path.getsize(db_path)
    vectors_size = os.path.getsize(vectors_path)

    if (data_cache["chunks"] is not None
            and data_cache["db_mtime"] == db_mtime
            and data_cache["vectors_mtime"] == vectors_mtime
            and data_cache["db_size"] == db_size
            and data_cache["vectors_size"] == vectors_size):
        return data_cache["chunks"], data_cache["vectors"]

    all_chunks = storage.get_all_chunks()
    vectors = np.load(vectors_path)

    data_cache["chunks"] = all_chunks
    data_cache["vectors"] = vectors
    data_cache["db_mtime"] = db_mtime
    data_cache["vectors_mtime"] = vectors_mtime
    data_cache["db_size"] = db_size
    data_cache["vectors_size"] = vectors_size
    return all_chunks, vectors


def get_relevant_context(query, top_k=5):
    """Finds the most semantically similar chunks from the vector database."""
    model = get_embedder()
    all_chunks, vectors = load_processed_data()
    if len(all_chunks) == 0:
        return "", []
    query_vector = model.encode([query])
    query_vector = np.asarray(query_vector)
    if query_vector.ndim == 2 and query_vector.shape[0] == 1:
        query_vector = query_vector[0]

    # Calculate cosine similarity without sklearn to avoid heavy import cost.
    vnorms = np.linalg.norm(vectors, axis=1)
    qnorm = np.linalg.norm(query_vector)
    denom = (vnorms * qnorm) + 1e-12
    similarities = (vectors @ query_vector) / denom

    # Get indices of the top_k results
    top_k = min(top_k, len(all_chunks))
    top_indices = similarities.argsort()[-top_k:][::-1]

    context_text = ""
    sources = []
    for idx in top_indices:
        context_text += f"\n--- SOURCE FILE: {all_chunks[idx]['source']} ---\n"
        context_text += f"CONTENT: {all_chunks[idx]['content']}\n"
        sources.append(all_chunks[idx]['source'])

    return context_text, list(set(sources))


def ask_gemini(query):
    """Retrieves context and generates an answer using Gemini."""
    context, source_list = get_relevant_context(query)

    # System instruction to keep the AI grounded (prevent hallucinations)
    system_instr = (
        "You are a professional academic assistant at WIUT. "
        "Answer the question using ONLY the provided context. "
        "If the answer is not in the context, say: 'I'm sorry, but that information is not in your documents.' "
        "Always cite which document you found the information in."
    )

    prompt = f"""
    CONTEXT FROM DOCUMENTS:
    {context}

    USER QUESTION: 
    {query}
    """

    # Generate response using the 2026 google-genai SDK
    client = get_genai_client()
    # Lazy import here to avoid overhead at module import time.
    from google.genai import types

    response = client.models.generate_content(
        model=CURRENT_MODEL,
        contents=prompt,
        config=types.GenerateContentConfig(
            system_instruction=system_instr,
            temperature=0.1  # Low temperature for more factual, less creative answers
        )
    )

    return response.text, source_list


# --- TEST LOOP ---
if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="RAG question answering CLI")
    parser.add_argument(
        "--no-interactive",
        action="store_true",
        help="Load models and data, then exit without starting the prompt loop.",
    )
    args = parser.parse_args()

    if args.no_interactive:
        print(f"RAG initialized (Powered by {CURRENT_MODEL}).")
        raise SystemExit(0)

    print(f"\n--- RAG System Online (Powered by {CURRENT_MODEL}) ---")
    print("Type your question and press Enter. Type 'q' to quit.")

    while True:
        user_input = input("\nYour Question: ")
        if user_input.lower() == 'q':
            print("Shutting down...")
            break

        try:
            answer, sources = ask_gemini(user_input)
            print("\n" + "=" * 60)
            print("AI RESPONSE:")
            print(answer)
            print("\nSOURCES USED:", ", ".join(sources))
            print("=" * 60)
        except Exception as e:
            print(f"Error occurred: {e}")
