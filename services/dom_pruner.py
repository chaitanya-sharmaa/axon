import logging
from bs4 import BeautifulSoup
import markdownify

log = logging.getLogger(__name__)

def compress_html_to_markdown(html_content: str) -> str:
    """
    Compresses a raw HTML dump into dense Markdown.
    Strips scripts, styles, hidden elements, and empty tags.
    Useful for compressing payloads from browser-automation agents.
    """
    try:
        soup = BeautifulSoup(html_content, "html.parser")
        
        # 1. Remove non-content tags
        for tag in soup(["script", "style", "meta", "noscript", "svg", "path", "head", "iframe"]):
            tag.decompose()
            
        # 2. Remove hidden elements
        for tag in soup.find_all(style=True):
            style_str = tag["style"].lower()
            if "display: none" in style_str or "visibility: hidden" in style_str or "display:none" in style_str:
                tag.decompose()
                
        # 3. Convert remaining structure to Markdown
        # Strip hrefs and images to save pure text structural tokens
        cleaned_html = str(soup)
        md = markdownify.markdownify(cleaned_html, heading_style="ATX", strip=["a", "img"])
        
        # 4. Condense whitespace
        lines = [line.strip() for line in md.splitlines() if line.strip()]
        compressed_md = "\n".join(lines)
        
        return compressed_md
    except Exception as e:
        log.warning(f"Failed to compress HTML to Markdown: {e}")
        # Fallback to returning original if parsing fails
        return html_content
