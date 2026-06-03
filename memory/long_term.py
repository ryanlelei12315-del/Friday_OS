
import chromadb
client = chromadb.PersistentClient(
    path="./data/chroma"
)

collection = client.get_or_create_collection(
    name="friday_memory"
)


def save_memory(text: str):

    collection.add(
        documents=[text],
        ids=[str(hash(text))]
    )


def search_memory(query: str):

    results = collection.query(
        query_texts=[query],
        n_results=5
    )

    return results