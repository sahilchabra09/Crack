"""
Crawl4AI Scraper - WITH PRE-INITIALIZATION
Smart middle tier with instant startup
"""

try:
    from crawl4ai import AsyncWebCrawler
    from crawl4ai.async_crawler_strategy import AsyncHTTPCrawlerStrategy
    from crawl4ai import HTTPCrawlerConfig
    CRAWL4AI_AVAILABLE = True
except ImportError:
    CRAWL4AI_AVAILABLE = False
    print("⚠️ Crawl4AI not installed. Install with: pip install crawl4ai")

import asyncio
import time
import re
from bs4 import BeautifulSoup

# OPTIMIZATION: Global pre-initialized crawler
_global_crawler = None
_crawler_lock = asyncio.Lock()

# Domains that benefit from Crawl4AI's advanced extraction
CRAWL4AI_DOMAINS = {
    # News sites
    'cnn.com', 'bbc.com', 'reuters.com', 'ap.org', 'npr.org',
    'theguardian.com', 'nytimes.com', 'wsj.com', 'bloomberg.com',
    # Academic sites
    'arxiv.org', 'scholar.google.com', 'researchgate.net',
    'ieee.org', 'acm.org', 'springer.com', 'sciencedirect.com',
    # E-commerce
    'amazon.com', 'ebay.com', 'etsy.com', 'shopify.com',
    'aliexpress.com', 'walmart.com',
    # Tech blogs/complex sites
    'medium.com', 'dev.to', 'stackoverflow.com', 'reddit.com',
    'hackernews.ycombinator.com', 'github.com'
}

async def warmup_crawl4ai():
    """
    🔥 PRE-INITIALIZE Crawl4AI for instant access
    This eliminates startup delays during scraping!
    """
    global _global_crawler
    
    if not CRAWL4AI_AVAILABLE:
        print("⚠️ Crawl4AI not available for warmup")
        return False
    
    async with _crawler_lock:
        if _global_crawler is not None:
            print("🔥 Crawl4AI already pre-warmed")
            return True
        
        try:
            print("🔥 Pre-warming Crawl4AI...")
            
            # Create HTTP-only crawler strategy
            http_config = HTTPCrawlerConfig(
                headers={
                    'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36',
                    'Accept': 'text/html,application/xhtml+xml,application/xml;q=0.9,image/webp,*/*;q=0.8',
                    'Accept-Language': 'en-US,en;q=0.9',
                    'Accept-Encoding': 'gzip, deflate, br'
                },
                follow_redirects=True,
                verify_ssl=False
            )
            
            http_strategy = AsyncHTTPCrawlerStrategy(browser_config=http_config)
            
            # Initialize global crawler
            _global_crawler = AsyncWebCrawler(
                crawler_strategy=http_strategy,
                verbose=False
            )
            
            print("✅ Crawl4AI pre-warmed and ready for INSTANT use!")
            return True
            
        except Exception as e:
            print(f"⚠️ Crawl4AI warmup failed: {e}")
            _global_crawler = None
            return False

async def shutdown_crawl4ai():
    """
    🧹 Properly shutdown pre-initialized crawler
    """
    global _global_crawler
    
    async with _crawler_lock:
        if _global_crawler is not None:
            try:
                # Crawl4AI doesn't need explicit shutdown for HTTP-only mode
                _global_crawler = None
                print("🧹 Crawl4AI shut down cleanly")
            except Exception as e:
                print(f"⚠️ Crawl4AI shutdown warning: {e}")

def should_use_crawl4ai(url, content_length=0, content_sample=""):
    """
    Smart criteria to determine if Crawl4AI should be used
    """
    if not CRAWL4AI_AVAILABLE:
        return False

    # Criterion 1: BeautifulSoup got < 50 words
    if content_length > 0:
        word_count = len(content_sample.split()) if content_sample else 0
        if word_count < 50:
            return True

    # Criterion 2: Content looks messy/mixed
    if content_sample:
        messy_indicators = [
            'javascript', 'advertisement', 'cookie', 'subscribe',
            'login', 'register', 'popup', 'modal', 'sidebar'
        ]
        messy_count = sum(1 for indicator in messy_indicators
                         if indicator in content_sample.lower())
        if messy_count >= 3:
            return True

    # Criterion 3: Beneficial domains
    from urllib.parse import urlparse
    domain = urlparse(url).netloc.lower()
    for crawl4ai_domain in CRAWL4AI_DOMAINS:
        if crawl4ai_domain in domain:
            return True

    return False

async def scrape_with_crawl4ai(url, timeout=30, max_retries=2):
    """
    ⚡ INSTANT Crawl4AI scraping using pre-warmed crawler
    NO startup delays!
    """
    global _global_crawler
    
    if not CRAWL4AI_AVAILABLE:
        return {
            'success': False,
            'title': '',
            'content': '',
            'method': 'Crawl4AI',
            'error': 'Crawl4AI not available'
        }

    print(f"🕷️ INSTANT Crawl4AI scraping: {url}")
    
    # Ensure crawler is warmed up
    if _global_crawler is None:
        await warmup_crawl4ai()
    
    if _global_crawler is None:
        return {
            'success': False,
            'title': '',
            'content': '',
            'method': 'Crawl4AI',
            'error': 'Crawl4AI warmup failed'
        }

    # Retry logic for handling connection timeouts
    for attempt in range(max_retries + 1):
        try:
            # Use PRE-WARMED crawler for INSTANT access
            result = await _global_crawler.arun(
                url=url,
                word_count_threshold=10,
                bypass_cache=True,
                page_timeout=45000, # Page timeout in milliseconds (45 seconds)
                # HTTP-only specific options
                process_iframes=False,
                remove_overlay_elements=True
            )

            if result.success:
                # Extract raw content
                raw_content = result.extracted_content or result.cleaned_html or result.markdown or ""
                title = ""
                
                # Try to extract title from metadata
                if hasattr(result, 'metadata') and result.metadata:
                    title = result.metadata.get('title', '')

                # Clean HTML properly using BeautifulSoup
                clean_content = extract_clean_text_from_html(raw_content)
                
                # Apply additional cleaning
                clean_content = clean_crawl4ai_content(clean_content)

                if len(clean_content.split()) > 10: # Meaningful content threshold
                    print(f"✅ INSTANT Crawl4AI success: {len(clean_content)} chars, {len(clean_content.split())} words")
                    return {
                        'success': True,
                        'title': title,
                        'content': clean_content,
                        'method': 'Crawl4AI-Instant',
                        'word_count': len(clean_content.split()),
                        'quality_score': min(len(clean_content.split()) * 2, 100)
                    }
                else:
                    print(f"⚠️ Crawl4AI minimal content: {len(clean_content)} chars")
            else:
                print(f"⚠️ Crawl4AI request failed")

        except Exception as e:
            if attempt < max_retries:
                print(f"🔄 Crawl4AI attempt {attempt + 1} failed, retrying... ({str(e)})")
                await asyncio.sleep(2 * (attempt + 1)) # Exponential backoff
                continue
            else:
                print(f"❌ Crawl4AI error after {max_retries + 1} attempts: {str(e)}")

    return {
        'success': False,
        'title': '',
        'content': '',
        'method': 'Crawl4AI-Instant',
        'error': 'HTTP request failed or insufficient content after all retries'
    }

def extract_clean_text_from_html(html_content):
    """Extract clean text from HTML using BeautifulSoup"""
    if not html_content:
        return ""
    
    try:
        soup = BeautifulSoup(html_content, 'html.parser')
        for element in soup(['script', 'style', 'nav', 'header', 'footer', 'aside', 'form', 'button', 'input']):
            element.decompose()
        
        text = soup.get_text()
        lines = (line.strip() for line in text.splitlines())
        chunks = (phrase.strip() for line in lines for phrase in line.split(" "))
        text = ' '.join(chunk for chunk in chunks if chunk)
        
        return text
    except Exception as e:
        print(f"⚠️ HTML parsing error: {e}")
        text = re.sub('<[^<]+?>', '', html_content)
        return re.sub(r'\s+', ' ', text).strip()

def clean_crawl4ai_content(content):
    """Clean and optimize Crawl4AI extracted content"""
    if not content:
        return ""

    content = re.sub(r'\s+', ' ', content).strip()

    boilerplate_patterns = [
        r'accept cookies?', r'privacy policy', r'terms of service',
        r'subscribe to newsletter', r'follow us on', r'share this article',
        r'sign in', r'register', r'advertisement', r'ad feedback', r'close'
    ]

    for pattern in boilerplate_patterns:
        content = re.sub(pattern, '', content, flags=re.IGNORECASE)

    words = content.split()
    meaningful_words = [word for word in words if len(word.strip()) > 2]
    
    return ' '.join(meaningful_words)

# Test function
async def test_crawl4ai():
    """Test Crawl4AI functionality"""
    await warmup_crawl4ai()
    test_url = "https://example.com"
    result = await scrape_with_crawl4ai(test_url)
    print(f"Crawl4AI Test Result: {result}")
    await shutdown_crawl4ai()
    return result

if __name__ == "__main__":
    asyncio.run(test_crawl4ai())
