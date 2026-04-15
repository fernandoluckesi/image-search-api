from fastapi import FastAPI, UploadFile, File
import shutil
import numpy as np
import faiss

from app.model import get_embedding
from app.index import index, image_paths

app = FastAPI()

@app.post("/search")
async def search(file: UploadFile = File(...)):
    temp_path = "temp.jpg"

    with open(temp_path, "wb") as buffer:
        shutil.copyfileobj(file.file, buffer)

    query = get_embedding(temp_path)
    query = np.array([query]).astype("float32")

    faiss.normalize_L2(query)

    D, I = index.search(query, k=5)

    results = []
    for i, score in zip(I[0], D[0]):
        results.append({
            "image": image_paths[i],
            "score": float(score)
        })

    return {"results": results}