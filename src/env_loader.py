from dotenv import load_dotenv, find_dotenv

# Load environment variables from the nearest .env in the project tree.
load_dotenv(find_dotenv(), override=False)
