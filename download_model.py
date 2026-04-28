from sentence_transformers import SentenceTransformer

print("Downloading model (one time only)...")

model = SentenceTransformer("sentence-transformers/all-MiniLM-L6-v2")

print("Model downloaded successfully.")
