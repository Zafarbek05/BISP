import os
import json
import numpy as np
from google import genai
from google.genai import types
from sentence_transformers import SentenceTransformer
from sklearn.metrics.pairwise import cosine_similarity
from dotenv import load_dotenv

# --- SMART PATHING ---
# Gets the 'src' folder, then goes up to the Project Root
BASE_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
PROCESSED_DATA_DIR = os.path.join(BASE_DIR, "data", "processed")
ENV_PATH = os.path.join(BASE_DIR, ".env")

# Load environment variables from the root .env
load_dotenv(ENV_PATH)
api_key = os.getenv("GEMINI_API_KEY")

# --- INITIALIZATION ---
if not api_key:
    raise ValueError("API Key not found. Please check your .env file in the root directory.")

client = genai.Client(api_key=api_key)
CURRENT_MODEL = "gemini-2.5-flash-lite"

# 1. Setup Embedding Model
print("Initializing Embedding Model...")
model_embed = SentenceTransformer('all-MiniLM-L6-v2')

# 2. Load Processed Data
chunks_path = os.path.join(PROCESSED_DATA_DIR, "processed_chunks.json")
vectors_path = os.path.join(PROCESSED_DATA_DIR, "vector_storage.npy")

if not os.path.exists(chunks_path) or not os.path.exists(vectors_path):
    raise FileNotFoundError(f"Processed data not found in {PROCESSED_DATA_DIR}. Please run the pipeline first.")

with open(chunks_path, "r", encoding='utf-8') as f:
    all_chunks = json.load(f)
vectors = np.load(vectors_path)


def get_relevant_context(query, top_k=3):
    """Finds the most semantically similar chunks from the vector database."""
    query_vector = model_embed.encode([query])

    # Calculate cosine similarity between query and all stored vectors
    similarities = cosine_similarity(query_vector, vectors).flatten()

    # Get indices of the top_k results
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