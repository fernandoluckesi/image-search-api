import os
import numpy as np
import faiss
from app.model import get_embedding

IMAGE_FOLDER = "images"

image_paths = []
embeddings = []

print("Indexando imagens...")

for file in os.listdir(IMAGE_FOLDER):
    path = os.path.join(IMAGE_FOLDER, file)
    
    try:
        emb = get_embedding(path)
        embeddings.append(emb)
        image_paths.append(path)
    except:
        print(f"Erro na imagem: {file}")

embeddings = np.array(embeddings).astype("float32")

# normalizar (importante!)
faiss.normalize_L2(embeddings)

index = faiss.IndexFlatIP(embeddings.shape[1])  # cosine similarity
index.add(embeddings)

print(f"{len(image_paths)} imagens indexadas.")