"""
HTML parser utility for email body text extraction.

Per research.md lines 166-185, uses BeautifulSoup with lxml parser
and fallback to html.parser for robust handling of malformed HTML.
"""
from bs4 import BeautifulSoup

from src.utils.logger import get_logger

logger = get_logger(__name__)


def extract_plain_text(html_content: str) -> str:
    """
    Extract plain text from HTML email body.

    Args:
        html_content: HTML string from email body

    Returns:
        Clean plain text with whitespace stripped

    Raises:
        ValueError: If html_content is None or empty
    """
    if not html_content:
        raise ValueError("HTML content cannot be None or empty")

    # Try lxml parser first (fast), fallback to html.parser
    try:
        soup = BeautifulSoup(html_content, "lxml")
        logger.debug("Parsed HTML with lxml parser")
    except Exception as e:
        logger.debug(f"lxml parser failed ({e}), falling back to html.parser")
        try:
            soup = BeautifulSoup(html_content, "html.parser")
        except Exception as e2:
            logger.error(f"Both parsers failed: lxml={e}, html.parser={e2}")
            # Last resort: return raw text with HTML tags stripped manually
            return html_content.replace("<", " <").replace(">", "> ").strip()

    # Remove script and style elements
    for script_or_style in soup(['script', 'style']):
        script_or_style.decompose()

    # Get text with separator and strip whitespace
    text = soup.get_text(separator=" ", strip=True)

    # Collapse multiple spaces to single space
    import re
    return re.sub(r'\s+', ' ', text)

