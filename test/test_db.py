import warnings

from langchain_core.documents import Document
from langchain_huggingface import HuggingFaceEmbeddings
from langchain_postgres import PostgresVector

# Hide clean-up warnings from tokenizer models
warnings.filterwarnings("ignore", category=FutureWarning)

print("Loading local Hugging Face model... (This may take a moment on first run)")
# This downloads a tiny 90MB model to your machine once, then runs locally
embeddings = HuggingFaceEmbeddings(model_name="sentence-transformers/all-MiniLM-L6-v2")
print("Model loaded successfully!")

# Your PostgreSQL connection string
DB_URL = "postgresql+psycopg://friday:change_this_password@localhost:5432/friday_memory"

# Connect LangChain to your postgres vector table
# It will auto-create a table named 'jarvis_local_memories'
vector_store = PostgresVector(
    connection=DB_URL,
    embeddings=embeddings,
    table_name="jarvis_local_memories",
)

# --- TEST 1: SAVE A MEMORY ---
print("\nSaving a new memory to PostgreSQL...")
sample_memory = Document(
    page_content="The user mentioned their favorite programming language is Python.",
    metadata={"source": "user_chat", "importance": "high"},
)
vector_store.add_documents([sample_memory])
print("Memory saved successfully!")

# --- TEST 2: SMART SEARCH ---
print("\nTesting semantic search...")
# Notice we search for "coding style preference", not the exact words "programming language"
search_query = "What coding language does the user like?"
results = vector_store.similarity_search(search_query, k=1)

if results:
    print(f'Found Memory Match: "{results[0].page_content}"')
else:
    print("No matching memories found.")
