import uuid
import logging
from typing import Dict, List, Any
from services.intent_classifier import get_embedder
import torch
import torch.nn.functional as F

log = logging.getLogger(__name__)

class VectorStore:
    def __init__(self):
        # file_id -> {"chunks": [str], "embeddings": tensor(N, 384)}
        self.files: Dict[str, Dict[str, Any]] = {}
        
    def chunk_text(self, text: str, chunk_size: int = 1000) -> List[str]:
        """Simple character-based chunking."""
        words = text.split()
        chunks = []
        current_chunk = []
        current_length = 0
        
        for word in words:
            current_chunk.append(word)
            current_length += len(word) + 1
            if current_length >= chunk_size:
                chunks.append(" ".join(current_chunk))
                current_chunk = []
                current_length = 0
                
        if current_chunk:
            chunks.append(" ".join(current_chunk))
            
        return chunks

    def add_file(self, file_id: str, text: str) -> None:
        """Chunks the text, embeds it, and stores it in memory."""
        embedder = get_embedder()
        if not embedder:
            log.warning("Embedder not available. Storing chunks without vectors.")
            self.files[file_id] = {"chunks": self.chunk_text(text), "embeddings": None}
            return
            
        chunks = self.chunk_text(text)
        if not chunks:
            self.files[file_id] = {"chunks": [], "embeddings": None}
            return
            
        log.info(f"Embedding {len(chunks)} chunks for file {file_id}...")
        embeddings = torch.tensor(embedder.encode(chunks))
        self.files[file_id] = {"chunks": chunks, "embeddings": embeddings}
        log.info(f"Successfully vectorized file {file_id}.")
        
    def search(self, file_ids: List[str], query: str, top_k: int = 3) -> List[str]:
        """Search across specific files for the most relevant chunks using Cosine Similarity."""
        embedder = get_embedder()
        if not embedder or not query.strip():
            return []
            
        query_emb = torch.tensor(embedder.encode(query))
        
        all_chunks = []
        all_embeddings = []
        
        for fid in file_ids:
            if fid in self.files and self.files[fid]["embeddings"] is not None:
                all_chunks.extend(self.files[fid]["chunks"])
                all_embeddings.append(self.files[fid]["embeddings"])
                
        if not all_chunks:
            return []
            
        # Concatenate all embeddings from the attached files
        corpus_embeddings = torch.cat(all_embeddings, dim=0)
        
        # Calculate cosine similarity between query and all chunks
        # Ensure query is (1, 384)
        query_emb = query_emb.unsqueeze(0).to(corpus_embeddings.device)
        corpus_embeddings = corpus_embeddings.to(corpus_embeddings.device)
        
        cos_scores = F.cosine_similarity(query_emb, corpus_embeddings)
        
        # Get the top K indices
        top_k = min(top_k, len(all_chunks))
        top_results = torch.topk(cos_scores, k=top_k)
        
        results = []
        for score, idx in zip(top_results[0], top_results[1]):
            # Only include chunks with a reasonable similarity score
            if score.item() > 0.2:
                results.append(all_chunks[idx.item()])
                
        return results

# Singleton instance
vector_store = VectorStore()
