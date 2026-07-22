import logging

log = logging.getLogger(__name__)

# We use a global model variable to load it only once on startup
_embedder = None
_categories = {}

def get_embedder():
    global _embedder, _categories
    if _embedder is None:
        try:
            import numpy as np
            from fastembed import TextEmbedding

            log.info("Loading fastembed model 'sentence-transformers/all-MiniLM-L6-v2'...")
            _embedder = TextEmbedding("sentence-transformers/all-MiniLM-L6-v2")

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
                _categories[cat] = np.array(list(_embedder.embed(phrases)))

            log.info("Semantic Intent Engine initialized successfully.")
        except ImportError:
            log.warning("fastembed not installed. Falling back to keyword heuristics.")
            _embedder = False
        except Exception as e:
            log.error(f"Error loading fastembed: {e}")
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

    import numpy as np

    # 1. Embed the incoming prompt
    prompt_emb = list(embedder.embed([text]))[0]
    prompt_emb_norm = prompt_emb / np.linalg.norm(prompt_emb)

    scores = {}
    # 2. Find the maximum cosine similarity across all phrases in each category
    for cat, embeddings in _categories.items():
        # Normalize the category embeddings
        norms = np.linalg.norm(embeddings, axis=1, keepdims=True)
        embeddings_norm = embeddings / np.where(norms == 0, 1e-10, norms)
        # Cosine similarity using dot product since both are normalized
        cos_scores = np.dot(embeddings_norm, prompt_emb_norm)
        scores[cat] = float(np.max(cos_scores))

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
