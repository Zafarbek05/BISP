The current project scans the given directory and saves the file folder hierarchy in a tree data structure in file_index_chunked.json file. The contents of the .pdf and .docx files are also chunked for efficient data feeding. The build_vector_db.py vectorizes the contents and saves in a vector database. The "all-MiniLM-L6-v2" model is used to vectorize text

Next steps:
1) Migrate all json data to database (sqlite), wrap up in docker container
2) App-level auth
3) Find the most efficient model for local RAG
4) Input and output counters - throttle, restrict file uploads up to 100 MB
5) Make sure I allocate enough time for testing