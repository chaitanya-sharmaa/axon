"""Semantic NLP Compressor using LLMLingua.

This module provides an optional pass for compressing long natural language blocks
(like RAG contexts) to reduce token counts while preserving semantic meaning.
It relies on the `llmlingua` package, which must be installed separately.
"""

import logging
import os

log = logging.getLogger(__name__)

class LLMLinguaCompressor:
    def __init__(self):
        self._compressor = None
        self._loaded = False
        self._enabled_but_failed = False

    def _lazy_load(self):
        if self._loaded or self._enabled_but_failed:
            return
        
        try:
            from llmlingua import PromptCompressor
            
            # Allow configuring device via environment, default to 'cpu' for safety in proxies
            device = os.getenv("AXON_LLMLINGUA_DEVICE", "cpu")
            model_name = os.getenv("AXON_LLMLINGUA_MODEL", "microsoft/llmlingua-2-bert-base-multilingual-cased-meetingbank")
            use_v2 = "llmlingua-2" in model_name.lower()
            
            log.info(f"Loading LLMLingua model ({model_name}) on {device}...")
            self._compressor = PromptCompressor(
                model_name=model_name,
                use_llmlingua2=use_v2,
                device_map=device,
            )
            self._loaded = True
            log.info("LLMLingua model loaded successfully.")
        except ImportError:
            log.warning("llmlingua package not found. Please run `pip install axon-bridge[lingua]` to enable semantic NLP compression.")
            self._enabled_but_failed = True
        except Exception as e:
            log.error(f"Failed to load LLMLingua model: {e}")
            self._enabled_but_failed = True

    def compress_text(self, text: str, target_token=None, rate=0.33) -> str:
        """Compresses a large block of text.

        If target_token is not provided, uses `rate` (e.g. 0.33 = 1/3 of original size).
        """
        self._lazy_load()
        if not self._compressor:
            return text

        try:
            results = self._compressor.compress_prompt(
                context=[text],
                target_token=target_token,
                rate=rate,
                force_tokens=['\n', '?', '.', '!', ',']
            )
            return results.get("compressed_prompt", text)
        except Exception as e:
            log.error(f"LLMLingua compression failed: {e}")
            return text

llmlingua_compressor = LLMLinguaCompressor()
