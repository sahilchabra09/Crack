"""
Simple Playwright Scraper for JavaScript websites
Easy to understand - handles sites that need a real browser
"""

try:
    from playwright.async_api import async_playwright
    PLAYWRIGHT_AVAILABLE = True
except ImportError:
    PLAYWRIGHT_AVAILABLE = False
    print("⚠️ Playwright not installed. Install with: pip install playwright")

async def scrape_javascript_website(url, timeout=30):
    """
    Scrape a JavaScript website using Playwright
    Enhanced for Windows Store Python compatibility with robust error handling
    
    Args:
        url: Website URL to scrape
        timeout: How long to wait for page to load
    
    Returns:
        Dictionary with title, content, and success status
    """
    if not PLAYWRIGHT_AVAILABLE:
        return {
            'success': False,
            'title': '',
            'content': '',
            'method': 'Playwright',
            'url': url,
            'error': 'Playwright not installed'
        }
    
    # Debug info written to stderr to not interfere with JSON output
    import sys
    print(f"[Playwright] Scraping: {url}", file=sys.stderr)
    
    try:
        # Enhanced Windows Store Python compatibility approach
        async with async_playwright() as p:
            # Enhanced launch options for better site compatibility and stealth
            launch_options = {
                'headless': True,
                'args': [
                    '--no-sandbox',
                    '--disable-setuid-sandbox', 
                    '--disable-dev-shm-usage',
                    '--disable-web-security',
                    '--disable-features=VizDisplayCompositor',
                    '--disable-background-timer-throttling',
                    '--disable-backgrounding-occluded-windows',
                    '--disable-renderer-backgrounding',
                    '--disable-blink-features=AutomationControlled',
                    '--disable-extensions',
                    '--no-first-run',
                    '--disable-default-apps'
                ]
            }
            
            browser = await p.chromium.launch(**launch_options)
            page = await browser.new_page()
            
            # Set user agent to avoid detection
            await page.set_extra_http_headers({
                'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36'
            })
            
            # Block images and fonts to save bandwidth and speed up loading
            await page.route("**/*.{png,jpg,jpeg,gif,css,woff,woff2,svg,ico}", lambda route: route.abort())
            
            # Go to the page with more lenient settings
            await page.goto(url, wait_until='domcontentloaded', timeout=timeout * 1000)
            
            # Wait for JavaScript to execute and render content
            await page.wait_for_timeout(3000)
            
            # Get title
            title = await page.title()
            
            # Get content - remove unwanted elements first
            await page.evaluate("""
                // Remove unwanted elements
                const unwanted = document.querySelectorAll('script, style, nav, footer, header, .ad, .advertisement');
                unwanted.forEach(el => el.remove());
            """)
            
            # Try to get main content
            content = ""
            
            # Look for main content areas
            main_selectors = ['main', 'article', '[role="main"]', '.content', '.main-content', '#content']
            
            for selector in main_selectors:
                try:
                    element = await page.query_selector(selector)
                    if element:
                        content = await element.inner_text()
                        if len(content) > 100:  # Good enough content
                            break
                except:
                    continue
            
            # If no main content found, get all paragraphs
            if not content or len(content) < 100:
                paragraphs = await page.query_selector_all('p')
                paragraph_texts = []
                for p in paragraphs:
                    text = await p.inner_text()
                    if text.strip():
                        paragraph_texts.append(text.strip())
                content = '\n'.join(paragraph_texts)
            
            await browser.close()
            
            return {
                'success': True,
                'title': title,
                'content': content,
                'method': 'Playwright',
                'url': url
            }
    
    except NotImplementedError as e:
        print(f"⚠️ Playwright Windows Store Python limitation for {url}")
        print(f"   → This is a known Windows Store Python subprocess issue")
        print(f"   → Install regular Python (not Windows Store) to enable Playwright")
        return {
            'success': False,
            'title': '',
            'content': '',
            'method': 'Playwright',
            'url': url,
            'error': 'Windows Store Python subprocess limitation - use regular Python install for Playwright'
        }
    
    except Exception as e:
        print(f"❌ Playwright failed for {url}: {e}")
        return {
            'success': False,
            'title': '',
            'content': '',
            'method': 'Playwright',
            'url': url,
            'error': str(e)
        }

def should_use_playwright(url):
    """
    Simple check - should we use Playwright for this URL?
    
    Args:
        url: Website URL to check
    
    Returns:
        True if we should use Playwright, False for BeautifulSoup
    """
    if not PLAYWRIGHT_AVAILABLE:
        return False
    
    # Known sites that need JavaScript
    js_sites = [
        'twitter.com', 'x.com', 'facebook.com', 'instagram.com',
        'youtube.com', 'tiktok.com', 'linkedin.com',
        'reddit.com', 'medium.com', 'substack.com'
    ]
    
    url_lower = url.lower()
    return any(site in url_lower for site in js_sites)