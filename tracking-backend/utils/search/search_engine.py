"""
Enhanced Search Engine - DuckDuckGo Only
FIXED: Simplified to use only DuckDuckGo for better reliability
Removes SearXNG dependency and complexity
"""

from ddgs import DDGS
import time
import re
from .search_config import DEFAULT_URL_MULTIPLIER

async def search_web_enhanced(query, required_results=5, url_multiplier=None):
    """
    Enhanced search using only DuckDuckGo (more reliable)
    FIXED: Simplified architecture - DuckDuckGo only
    
    Args:
        query: What to search for
        required_results: How many final results user wants  
        url_multiplier: Multiplier (5 or 10), uses default if None
    
    Returns:
        List of search results (multiplied count for LLM ranking)
    """
    # Step 1: Calculate how many URLs to get (multiplier system)
    if url_multiplier is None:
        url_multiplier = DEFAULT_URL_MULTIPLIER
        
    total_urls_needed = required_results * url_multiplier
    
    print(f"🔍 DuckDuckGo search for: '{query}'")  
    print(f"📊 Required: {required_results}, Multiplier: {url_multiplier}x, Total URLs: {total_urls_needed}")
    
    # Step 2: Get URLs from DuckDuckGo
    print("🦆 Searching DuckDuckGo...")
    all_results = await search_duckduckgo(query, total_urls_needed)
    
    # Remove duplicates
    unique_results = remove_duplicate_urls(all_results)
    
    print(f"✅ Total unique URLs found: {len(unique_results)}")
    return unique_results[:total_urls_needed]

async def search_duckduckgo(query, max_results):
    """
    Search using DuckDuckGo
    FIXED: Enhanced with better error handling and retry logic
    """
    print(f"🦆 Searching DuckDuckGo for: '{query}' (max: {max_results} results)")
    
    try:
        results = []
        
        # FIXED: Retry logic for better reliability
        max_retries = 3
        for attempt in range(max_retries):
            try:
                # Use DuckDuckGo search with enhanced parameters
                with DDGS() as ddgs:
                    search_results = ddgs.text(
                        query,
                        max_results=max_results,
                        region='us-en',
                        safesearch='moderate',
                        timelimit=None,  # No time limit
                        backend='api'    # Use API backend for better reliability
                    )
                    
                    for result in search_results:
                        clean_result = {
                            'title': clean_text(result.get('title', '')),
                            'url': result.get('href', ''),
                            'snippet': clean_text(result.get('body', '')),
                            'source': 'duckduckgo'
                        }
                        
                        if clean_result['url'] and is_valid_url(clean_result['url']):
                            results.append(clean_result)
                
                # If we got results, break out of retry loop
                if results:
                    break
                    
            except Exception as e:
                print(f"🔄 DuckDuckGo attempt {attempt + 1} failed: {e}")
                if attempt < max_retries - 1:
                    time.sleep(1)  # Wait before retry
                else:
                    raise
        
        print(f"🦆 DuckDuckGo found {len(results)} results")
        return results
        
    except Exception as e:
        print(f"❌ DuckDuckGo search failed after retries: {e}")
        return []

# Keep backward compatibility functions
async def search_web(query, max_results=5):
    """
    Simple search (backward compatibility)
    """
    return await search_duckduckgo(query, max_results)

def search_web_sync(query, max_results=5):
    """
    Synchronous version of search_web
    """
    import asyncio
    return asyncio.run(search_web(query, max_results))

def clean_text(text):
    """
    Clean up text from search results
    Remove weird characters and extra spaces
    """
    if not text:
        return ""
    
    # Remove extra whitespace
    text = re.sub(r'\s+', ' ', text)
    # Remove weird characters but keep basic punctuation
    text = re.sub(r'[^\w\s\.\,\!\?\-\(\)\[\]\/\:]', '', text)
    return text.strip()

def is_valid_url(url):
    """
    Simple check - is this a valid URL we can scrape?
    FIXED: Enhanced filtering
    """
    if not url:
        return False
    
    # Must start with http or https
    if not (url.startswith('http://') or url.startswith('https://')):
        return False
    
    # Skip certain file types we can't scrape
    skip_extensions = ['.pdf', '.doc', '.docx', '.xls', '.xlsx', '.ppt', '.pptx',
                       '.zip', '.rar', '.exe', '.dmg', '.mp4', '.avi', '.mov', 
                       '.jpg', '.jpeg', '.png', '.gif', '.svg', '.ico']
    url_lower = url.lower()
    if any(url_lower.endswith(ext) for ext in skip_extensions):
        return False
    
    # Skip certain sites that are hard to scrape
    skip_sites = ['youtube.com/watch', 'twitter.com/status', 'instagram.com/p/',
                  'facebook.com/photo', 'pinterest.com/pin', 'tiktok.com']
    if any(site in url_lower for site in skip_sites):
        return False
    
    return True

def remove_duplicate_urls(results):
    """
    Remove duplicate URLs from search results
    Keep the first occurrence of each URL
    """
    seen_urls = set()
    unique_results = []
    
    for result in results:
        url = result.get('url', '')
        if url and url not in seen_urls:
            seen_urls.add(url)
            unique_results.append(result)
    
    return unique_results

def improve_search_query(query):
    """
    Simple query improvement
    """
    # Add quotes around exact phrases for better matching
    if ' ' in query and '"' not in query:
        if len(query.split()) <= 3:  # Short phrases get quotes
            query = f'"{query}"'
    
    return query

async def search_multiple_queries(queries, max_results_per_query=3):
    """
    Search multiple queries and combine results
    """
    print(f"🔍 Searching {len(queries)} different queries")
    all_results = []
    
    for query in queries:
        print(f"  Searching: '{query}'")
        results = await search_duckduckgo(query, max_results_per_query)
        all_results.extend(results)
        time.sleep(0.5)  # Rate limiting
    
    # Remove duplicates
    unique_results = remove_duplicate_urls(all_results)
    print(f"✅ Combined {len(unique_results)} unique results from all queries")
    
    return unique_results
