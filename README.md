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
- **Frontend:** Streamlit (via `pywebview`)
- **Vector Database:** SQLite
- **LLM Support:** Ollama 3 (Local), Gemini (Cloud API)
- **Automation:** Python Watchdog API

## 🚀 Getting Started

### Prerequisites

- Python 3.9 or higher
- Ollama for local reasoning
- Gemini Cloud API keys for cloud reasoning

### Installation

1. **Clone the repository:**
  ```bash
   git clone https://github.com/Zafarbek05/BISP.git
  ```
2. **Install dependencies:**
  ```bash
   pip install -r requirements.txt
  ```
### Configuration (Environment Variables)

- `GEMINI_API_KEY`: Required for Gemini Cloud API access.
- `DB_KEY`: Key for SQLCipher database encryption.
- `ADMIN_LOGIN` / `ADMIN_PASSWORD`: Credentials for the Admin Dashboard.

#### Gemini Quota Monitoring
The Gemini API usage is automatically tracked in the **Admin Dashboard**. It captures:
- **RPM (Requests Per Minute)**: Automatically parsed from 429 errors or inferred from usage.
- **Token Usage**: Captured from `usageMetadata` in successful responses.
- **Historical Data**: View and export the last 30 days of usage as CSV or JSON.

*Note: Real-time quota visibility depends on the Gemini API version and tier. If headers are missing, the dashboard will show "Usage data unavailable" for those specific metrics.*
4. **Launch the Application:**
  ```bash
   streamlit run app.py
  ```

