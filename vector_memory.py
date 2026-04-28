from pinecone import Pinecone
from config import PINECONE_API_KEY, PINECONE_INDEX_NAME

pc = Pinecone(api_key=PINECONE_API_KEY)

index = pc.Index(PINECONE_INDEX_NAME)


def store_vector(vector_id, embedding, metadata):

    index.upsert([
        {
            "id": vector_id,
            "values": embedding,
            "metadata": metadata
        }
    ])


def search_vectors(query_embedding, top_k=5):

    results = index.query(
        vector=query_embedding,
        top_k=top_k,
        include_metadata=True
    )

    matches = []

    for match in results["matches"]:
        matches.append(match["metadata"]["text"])

    return matches
