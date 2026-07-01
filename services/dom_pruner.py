import logging
import trafilatura

log = logging.getLogger(__name__)

def compress_html_to_markdown(html_content: str) -> str:
    """
    Compresses a raw HTML dump into dense Markdown.
    Strips scripts, styles, hidden elements, and empty tags.
    Useful for compressing payloads from browser-automation agents.
    """
    try:
        # Extract main content and convert to markdown without links/images to save tokens
        compressed_md = trafilatura.extract(
            html_content, 
            output_format="markdown",
            include_links=False, 
            include_images=False,
            include_comments=False
        )
        
        if compressed_md:
            return compressed_md
        else:
            # Trafilatura might return None if it couldn't find the "main article".
            # For purely structural DOM dumps without a main article, fallback to simple HTML-to-text.
            return trafilatura.html2txt(html_content) or html_content
            
    except Exception as e:
        log.warning(f"Failed to compress HTML to Markdown with Trafilatura: {e}")
        # Fallback to returning original if parsing fails
        return html_content
