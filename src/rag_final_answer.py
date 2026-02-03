import os
import json
import numpy as np
from google import genai
from google.genai import types
from sentence_transformers import SentenceTransformer
from sklearn.metrics.pairwise import cosine_similarity
from dotenv import load_dotenv

load_dotenv()
api_key = os.getenv("GEMINI_API_KEY")

# --- INITIALIZATION ---
client = genai.Client(api_key=api_key)
CURRENT_MODEL = "gemini-2.5-flash-lite"

# 2. Setup Embedding Model
model_embed = SentenceTransformer('all-MiniLM-L6-v2')

# 3. Load Data
with open(os.path.join("../data", "processed_chunks.json"), "r", encoding='utf-8') as f:
    all_chunks = json.load(f)
vectors = np.load(os.path.join("../data", "vector_storage.npy"))


def get_relevant_context(query, top_k=3):
    query_vector = model_embed.encode([query])
    similarities = cosine_similarity(query_vector, vectors).flatten()
    top_indices = similarities.argsort()[-top_k:][::-1]

    context_text = ""
    sources = []
    for idx in top_indices:
        context_text += f"\n--- SOURCE: {all_chunks[idx]['source']} ---\n"
        context_text += all_chunks[idx]['content'] + "\n"
        sources.append(all_chunks[idx]['source'])
    return context_text, list(set(sources))


def ask_gemini(query):
    context, source_list = get_relevant_context(query)

    # Define the system instructions and the user prompt
    prompt = f"""
    Use the following pieces of retrieved context to answer the question.
    If the answer is not in the context, say you don't know.

    CONTEXT:
    {context}

    QUESTION: {query}
    """

    # Generate response using the new SDK method
    response = client.models.generate_content(
        model=CURRENT_MODEL,
        contents=prompt,
        config=types.GenerateContentConfig(
            system_instruction="You are a professional assistant at WIUT. Answer using ONLY provided context."
        )
    )

    return response.text, source_list


# --- TEST LOOP ---
if __name__ == "__main__":
    print(f"--- RAG System Online (Powered by {CURRENT_MODEL}) ---")
    while True:
        user_input = input("\nAsk a question (or 'q'): ")
        if user_input.lower() == 'q': break

        try:
            answer, sources = ask_gemini(user_input)
            print("\n" + "=" * 50)
            print("AI ANSWER:", answer)
            print("SOURCES:", ", ".join(sources))
            print("=" * 50)
        except Exception as e:
            print(f"Error occurred: {e}")