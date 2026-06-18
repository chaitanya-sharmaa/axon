import re
import logging

log = logging.getLogger(__name__)

# A conservative list of English stop words that are often structurally redundant for LLMs.
STOP_WORDS = {
    "a", "an", "the", "is", "are", "am", "was", "were", "be", "been", "being",
    "it", "this", "that", "these", "those", "of", "to", "in", "for", "on", "with",
    "as", "by", "at", "from", "about", "into", "through", "during", "before",
    "after", "over", "between", "out", "against", "under", "again", "further", "then",
    "once", "here", "there", "when", "where", "why", "how", "all", "any", "both", "each",
    "few", "more", "most", "other", "some", "such", "no", "nor", "not", "only", "own",
    "same", "so", "than", "too", "very", "can", "will", "just", "should", "now"
}

def prune_text(text: str) -> str:
    """
    LLMLingua-style text condenser.
    - Strips multiple spaces, tabs, and excessive newlines.
    - Removes common English stop words.
    - Preserves basic punctuation.
    """
    try:
        # 1. Condense whitespace
        # Replace multiple newlines with a single newline
        text = re.sub(r'\n+', '\n', text)
        # Replace multiple spaces/tabs with a single space
        text = re.sub(r'[ \t]+', ' ', text)

        # 2. Stop-word removal
        # We split by word boundaries, filter, and rejoin.
        # This keeps punctuation intact because \b separates words from punctuation.
        def _filter_word(match):
            word = match.group(0)
            if word.lower() in STOP_WORDS:
                return ""
            return word

        # Only target alphabetical sequences
        text = re.sub(r'\b[a-zA-Z]+\b', _filter_word, text)
        
        # 3. Final cleanup of orphaned spaces from word removal
        text = re.sub(r'[ \t]+', ' ', text)
        text = re.sub(r' \.', '.', text)
        text = re.sub(r' ,', ',', text)
        
        return text.strip()
    except Exception as e:
        log.warning(f"Text pruner failed: {e}")
        return text
