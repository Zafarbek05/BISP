The pipeline scans data/raw, chunks supported documents, and stores processed metadata and chunks in a SQLite database at data/processed/processed_data.db. It also vectorizes the chunks and saves embeddings in data/processed/vector_storage.npy using the "all-MiniLM-L6-v2" model.

Next steps:
1) Wrap up in a Docker container
2) App-level auth
3) Find the most efficient model for local RAG
4) Input and output counters - throttle, restrict file uploads up to 100 MB
5) Make sure I allocate enough time for testing
