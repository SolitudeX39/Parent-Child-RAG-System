import json
import logging
from typing import List, Dict, Any, Optional
import requests
import os
from dotenv import load_dotenv

__ALL__ = ["OpenRouterRerank"]
OPENROUTER_API_KEY = os.getenv("OPENROUTER_API_KEY")
logger = logging.getLogger(__name__)

class OpenRouterRerank:
    def __init__(self, api_key= str, model ="nvidia/llama-nemotron-rerank-vl-1b-v2:free"):
        self.api_key = api_key
        self.model = model
        self.endpoint = "https://openrouter.ai/api/v1/rerank"
        self.headers = {
            "Authorization": f"Bearer {self.api_key}",
            "Content-Type": "application/json",}
        
    def rerank(self, query: str, documents: List[Dict[str, Any]], top_k: int=5) -> List[Dict[str]]:
        payload = {
            "model": self.model,
            "query": query,
            "documents": documents,
            "top_k": top_k
        }
        try:
            response = requests.post(self.endpoint, headers=self.headers, json= payload)
            response.raise_for_status()
            results = response.json().get("results", [])

            final_results = []
            for result in results:
                document = result.get("document")
                source = document.get("parent_chunk")
                result_index = result.get("index")
                score = result.get("relevace_score")
                final_results.append({
                    "index": result_index,
                    "score": score,
                    "source": source})
            return final_results
        except requests.exceptions.RequestException as e:
            logger.error(f"Reranking failed: {e}. Returning unranked fallback.")