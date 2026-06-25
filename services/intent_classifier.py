import logging
from typing import Dict, Any

log = logging.getLogger(__name__)

# We use a global model variable to load it only once on startup
_embedder = None
_categories = {}

def get_embedder():
    global _embedder, _categories
    if _embedder is None:
        try:
            from sentence_transformers import SentenceTransformer
            import torch
            
            log.info("Loading sentence-transformers model 'all-MiniLM-L6-v2'...")
            _embedder = SentenceTransformer('all-MiniLM-L6-v2')
            
            # Pre-compute the embeddings for our cluster centers
            clusters = {
                "casual_chat": [
                    "hello there", "what's your name?", "how are you doing", "tell me a joke",
                    "good morning", "thanks for the help", "who won the game yesterday"
                ],
                "code_generation": [
                    "write a python script to", "debug this react component", "fix the sql injection in this code",
                    "implement a binary search tree", "how do I center a div", "import pandas as pd", "create a fastapi route"
                ],
                "complex_reasoning": [
                    "analyze this legal contract", "deduce the mathematical proof for", "evaluate the system architecture",
                    "extract unstructured financial data into json", "step by step explanation", "edge cases for"
                ]
            }
            
            for cat, phrases in clusters.items():
                _categories[cat] = torch.tensor(_embedder.encode(phrases))
                
            log.info("Semantic Intent Engine initialized successfully.")
        except ImportError:
            log.warning("sentence-transformers not installed. Falling back to keyword heuristics.")
            _embedder = False
        except Exception as e:
            log.error(f"Error loading sentence-transformers: {e}")
            _embedder = False
            
    return _embedder

def classify_intent(text: str) -> str:
    """Classifies prompt intent using semantic embeddings. Returns 'high' or 'low' complexity."""
    if not text:
        return "low"
        
    embedder = get_embedder()
    if embedder is False:
        # Fallback to simple length if ML is missing
        return "high" if len(text) > 2000 else "low"
        
    import torch
    import torch.nn.functional as F
    
    # 1. Embed the incoming prompt
    prompt_emb = embedder.encode(text, convert_to_tensor=True)
    
    scores = {}
    # 2. Find the maximum cosine similarity across all phrases in each category
    for cat, embeddings in _categories.items():
        embeddings = embeddings.to(prompt_emb.device)
        cos_scores = F.cosine_similarity(prompt_emb.unsqueeze(0), embeddings)
        scores[cat] = cos_scores.max().item()
        
    # 3. Find the winning category
    best_cat = max(scores, key=scores.get)
    best_score = scores[best_cat]
    log.info(f"ML Semantic Router classified intent as '{best_cat}' (Confidence: {best_score:.2f})")
    
    # If confidence is below threshold, default to cheap model (fail-safe)
    if best_score < 0.30:
        log.info(f"ML Semantic Router: Low confidence ({best_score:.2f}), defaulting to 'low' complexity.")
        return "low"
    
    # Casual chat routes to 'low' (lite models), Code/Reasoning routes to 'high' (pro models)
    if best_cat == "casual_chat":
        return "low"
    return "high"
