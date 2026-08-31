import logging
import asyncio
import re
from typing import Dict, Any

try:
    import requests
    from bs4 import BeautifulSoup
    HAS_SCRAPING_LIBS = True
except ImportError:
    HAS_SCRAPING_LIBS = False

logger = logging.getLogger("DeepScraperAgent")

def extract_urls(text: str) -> list:
    """Helper function to find URLs hidden inside text."""
    url_pattern = re.compile(r'(https?://[^\s]+)')
    return url_pattern.findall(text)

async def execute(query: str, context: Dict[str, Any] = None) -> str:
    """
    The Deep Scraper Agent: Takes a query containing a URL (or looks into the context for URLs),
    visits the webpage, and extracts the full text of the article.
    """
    context = context or {}
    logger.info(f"[DeepScraperAgent] Received scraping task: '{query}'")
    
    if not HAS_SCRAPING_LIBS:
        error_msg = "⚠️ ERROR: Deep Scraper requires 'requests' and 'beautifulsoup4'. Please run: pip install requests beautifulsoup4"
        logger.error(error_msg)
        return error_msg

    # 1. Look for a URL in the direct query
    target_urls = extract_urls(query)
    
    # 2. If no URL in the query, look through the context (e.g., output from the research_module)
    if not target_urls:
        for task_id, task_result in context.items():
            if task_id != "memory" and isinstance(task_result, str):
                target_urls.extend(extract_urls(task_result))
                
    if not target_urls:
        logger.warning("[DeepScraperAgent] No URLs found to scrape.")
        return "⚠️ ERROR: No valid URLs found in the query or context to scrape."

    # We will just scrape the first valid URL we find to prevent massive context bloat
    target_url = target_urls[0]
    # Clean up trailing quotes or brackets that regex might have caught
    target_url = target_url.strip("']\"),.") 
    
    logger.info(f"[DeepScraperAgent] Targeting URL for deep extraction: {target_url}")

    headers = {
        "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36",
        "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,image/avif,image/webp,*/*;q=0.8",
        "Accept-Language": "en-US,en;q=0.5"
    }

    try:
        # We use asyncio.to_thread so the synchronous requests library doesn't block the Orchestrator
        response = await asyncio.to_thread(
            requests.get, 
            target_url, 
            headers=headers, 
            timeout=10
        )
        response.raise_for_status()

        logger.info("[DeepScraperAgent] Page retrieved successfully. Parsing HTML...")
        soup = BeautifulSoup(response.text, 'html.parser')

        # Kill all script and style elements
        for script in soup(["script", "style", "nav", "footer", "header", "aside"]):
            script.extract()

        # Get text from paragraphs and headers (usually where the meat of the article is)
        content_elements = soup.find_all(['p', 'h1', 'h2', 'h3', 'li'])
        
        extracted_text = []
        for el in content_elements:
            text = el.get_text(separator=' ', strip=True)
            if text and len(text) > 20: # Ignore tiny fragments and button text
                extracted_text.append(text)

        full_article = "\n\n".join(extracted_text)

        # We truncate to ~15,000 characters to prevent blowing up the LLM's context window
        # when this data gets passed to the Clarity or Writer modules.
        max_chars = 15000
        if len(full_article) > max_chars:
            logger.info(f"[DeepScraperAgent] Article too long ({len(full_article)} chars). Truncating.")
            full_article = full_article[:max_chars] + "\n\n... [CONTENT TRUNCATED FOR CONTEXT LIMITS]"

        if not full_article.strip():
             return f"⚠️ [DeepScraperAgent] Successfully connected to {target_url}, but couldn't extract readable article text (might be a dynamic JS app)."

        logger.info("[DeepScraperAgent] Deep scraping successful.")
        return f"--- DEEP SCRAPE RESULTS FOR {target_url} ---\n{full_article}\n------------------------------------------"

    except requests.exceptions.RequestException as e:
        logger.error(f"[DeepScraperAgent] Failed to fetch URL: {e}")
        return f"⚠️ ERROR: Deep Scraper failed to fetch {target_url}. Reason: {e}"
    except Exception as e:
        logger.error(f"[DeepScraperAgent] Unexpected error during scraping: {e}")
        return f"⚠️ ERROR: Deep Scraper encountered an unexpected issue: {e}"