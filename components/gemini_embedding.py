from langchain_core.embeddings import Embeddings
from google import genai
from google.genai import types
import os
import tempfile

api_key = os.getenv("GOOGLE_API_KEY")

class GeminiEmbeddings(Embeddings):
    def __init__(self, api_key, model="gemini-embedding-2"):
        self.client = genai.Client(api_key=api_key)
        self.model = model

    def embed_documents(self, texts):

        embeddings = []
        batch_size = 50
        for i in range(0, len(texts), batch_size):
            batch = texts[i:i + batch_size]
            batch_contents = [
                    types.Content(
                        parts=[types.Part(text=text)],
                        role="user",
                    )
                    for text in batch
                    ]
                    
            resp = self.client.models.embed_content(
                model=self.model,
                contents=batch_contents
            )

            embeddings.extend(e.values for e in resp.embeddings)

        return embeddings

    def embed_query(self, text):
        resp = self.client.models.embed_content(
            model=self.model,
            contents=[text]
        )
        return resp.embeddings[0].values

gemini_embeddings = GeminiEmbeddings(api_key=api_key)
