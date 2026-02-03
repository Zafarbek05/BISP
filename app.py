import os

import streamlit as st

from src.rag_final_answer import ask_gemini  # Importing your RAG backend

# --- CONFIG & PATHS ---
st.set_page_config(page_title="WIUT Academic Assistant", page_icon="🎓", layout="wide")

# Define paths (Anchor-based)
BASE_DIR = os.path.dirname(os.path.abspath(__file__))
RAW_DATA_DIR = os.path.join(BASE_DIR, "data", "raw")
PROCESSED_PATH = os.path.join(BASE_DIR, "data", "processed", "vector_storage.npy")

# Ensure raw directory exists
if not os.path.exists(RAW_DATA_DIR):
    os.makedirs(RAW_DATA_DIR)

# --- CUSTOM CSS ---
st.markdown("""
    <style>
    .main { background-color: #f5f7f9; }
    .stChatMessage { border-radius: 15px; }
    div.stButton > button { width: 100%; border-radius: 5px; }
    </style>
    """, unsafe_allow_html=True)

# --- SIDEBAR ---
with st.sidebar:
    st.title("⚙️ System Control")

    # --- FEATURE: FILE UPLOAD ---
    st.subheader("📤 Add Knowledge")
    uploaded_files = st.file_uploader(
        "Upload PDF, DOCX, or TXT",
        type=["pdf", "docx", "txt"],
        accept_multiple_files=True
    )

    if uploaded_files:
        with st.spinner("Ingesting files..."):
            for uploaded_file in uploaded_files:
                # 1. Define save path
                save_path = os.path.join(RAW_DATA_DIR, uploaded_file.name)

                # 2. Save the file to data/raw
                with open(save_path, "wb") as f:
                    f.write(uploaded_file.getbuffer())

            st.success(f"✅ Saved {len(uploaded_files)} file(s)!")
            st.caption("The background pipeline will now index these files automatically.")

    st.divider()

    # --- SYSTEM STATUS ---
    st.subheader("Database Status")
    if os.path.exists(PROCESSED_PATH):
        st.success("🟢 Vector DB: Online")
    else:
        st.error("🔴 Vector DB: Offline")

    st.info("💡 Tip: Drop files above, and the AI will learn them in ~5 seconds.")

# --- MAIN CHAT INTERFACE ---
st.title("Smart Search Assistant")
st.markdown("### Ask questions about your uploaded documents")

# Initialize chat history
if "messages" not in st.session_state:
    st.session_state.messages = []

# Display chat history
for message in st.session_state.messages:
    with st.chat_message(message["role"]):
        st.markdown(message["content"])
        if "sources" in message:
            st.caption(f"📚 Sources: {', '.join(message['sources'])}")

# Chat Input
if prompt := st.chat_input("Ex: When is the CW2 deadline?"):
    # Show User Message
    st.chat_message("user").markdown(prompt)
    st.session_state.messages.append({"role": "user", "content": prompt})

    # Generate AI Response
    with st.chat_message("assistant"):
        with st.spinner("Analyzing documents..."):
            try:
                answer, sources = ask_gemini(prompt)

                st.markdown(answer)

                if sources:
                    st.caption(f"📚 Sources: {', '.join(sources)}")
                else:
                    st.caption("⚠️ No specific documents referenced.")

                # Save to history
                st.session_state.messages.append({
                    "role": "assistant",
                    "content": answer,
                    "sources": sources
                })
            except Exception as e:
                st.error(f"An error occurred: {e}")