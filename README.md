# AI Semantic Search System

> *“A wealth of information leads to the poverty of attention.”* — Herbert A. Simon

This project is a desktop-native, **privacy-first semantic search engine** designed to help users synthesize massive local archives into actionable knowledge. By leveraging a hybrid local-cloud architecture, it ensures data sovereignty while providing high-level linguistic reasoning.

## 🌟 Key Features

- **Hybrid Reasoning Engine:** Seamlessly toggle between high-performance Cloud APIs and fully **Air-Gapped** local inference for sensitive data.
- **Semantic Retrieval:** Utilizes Vector Embeddings and Sentence Transformers to understand query intent, moving beyond traditional keyword matching.
- **Watchdog Pipeline:** An automated indexing service that monitors local directories and updates the knowledge base in real-time as files are modified.
- **Native OS Integration:** Built with `pywebview`, providing a lightweight UI that triggers native file explorer actions through a localized HTTP bridge.
- **Security Hardening:** Integrated sanitization layers designed to mitigate **Prompt Injection** and unauthorized data exfiltration.

## 🛠️ Tech Stack

- **Backend:** Python 3.9+
- **Frontend:** HTML5/CSS3/JS (via `pywebview`)
- **Vector Database:** SQLite / ChromaDB (Local storage)
- **LLM Support:** Llama 3 / Mistral (Local), GPT-4 / Claude (Cloud API)
- **Automation:** Python Watchdog API

## 🚀 Getting Started

### Prerequisites

- Python 3.9 or higher
- (Optional) CUDA-enabled GPU for optimized local inference performance

### Installation

1. **Clone the repository:**
  ```bash
   git clone https://github.com/Zafarbek05/BISP.git
  ```
2. **Install dependencies:**
  ```bash
   pip install -r requirements.txt
  ```
3. **Configure the API:**
  ```bash
   OPENAI_API_KEY=your_api
  ```
4. **Launch the Application:**
  ```bash
   streamlit run app.py
  ```

