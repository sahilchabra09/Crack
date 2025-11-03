"""
Search Configuration - DuckDuckGo Only
FIXED: Removed SearXNG dependency for better reliability
"""

import os
from dotenv import load_dotenv

# Load environment variables (only need GROQ_API_KEY now)
env_path = os.path.join(os.path.dirname(__file__), '..', '..', '..', 'alice_ai_agent', '.env')
load_dotenv(env_path)

# REMOVED: LOCAL_SEARXNG_URL - no longer needed
# Only Groq API for LLM ranking
GROQ_API_KEY = os.getenv('GROQ_API_KEY', '')

# URL Multiplier settings  
URL_MULTIPLIER_OPTIONS = [5, 10]  # Either 5x or 10x more URLs than requested
DEFAULT_URL_MULTIPLIER = 4       # FIXED: Default to 10x for better fallback

# FIXED: Search engine - DuckDuckGo only
SEARCH_ENGINES = ['duckduckgo']   # Simplified

# Scraping settings
MAX_PARALLEL_SCRAPING = 10         # Optimized for better performance
MIN_PARALLEL_SCRAPING = 1         
SCRAPING_TIMEOUT = 20            

# Hardware monitoring thresholds
CPU_USAGE_THRESHOLD = 90         
MEMORY_USAGE_THRESHOLD = 90      
MIN_AVAILABLE_MEMORY_GB = 1.0    

# LLM Settings for URL ranking
LLM_MODEL = "llama-3.3-70b-versatile"  # Groq Cloud Ollama 3.3 70B model
LLM_TEMPERATURE = 0.3                   # Lower temperature for consistent ranking  
MAX_RANKING_URLS = 100                  # Maximum URLs to send to LLM for ranking

# User agents for scraping
USER_AGENTS = [
    'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/91.0.4472.124 Safari/537.36',
    'Mozilla/5.0 (Windows NT 10.0; Win64; x64; rv:89.0) Gecko/20100101 Firefox/89.0', 
    'Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/91.0.4472.124 Safari/537.36'
]

def get_config():
    """
    Get all configuration as a dictionary
    FIXED: Removed SearXNG references
    """
    return {
        'groq_api_key': GROQ_API_KEY,
        'url_multiplier_options': URL_MULTIPLIER_OPTIONS,
        'default_url_multiplier': DEFAULT_URL_MULTIPLIER,
        'search_engines': SEARCH_ENGINES,
        'max_parallel_scraping': MAX_PARALLEL_SCRAPING,
        'scraping_timeout': SCRAPING_TIMEOUT,
        'llm_model': LLM_MODEL,
        'user_agents': USER_AGENTS
    }

def print_config_status():
    """
    Print current configuration status
    FIXED: Removed SearXNG references
    """
    print("\n🔧 Search Configuration (FIXED - DuckDuckGo Only):")
    print(f"   Search Engine: DuckDuckGo Only")
    print(f"   Groq API Key: {'✅ Loaded' if GROQ_API_KEY else '❌ Missing'}")
    print(f"   URL Multiplier: {DEFAULT_URL_MULTIPLIER}x") 
    print(f"   Max Parallel: {MAX_PARALLEL_SCRAPING}")
    print(f"   LLM Model: {LLM_MODEL}")
    print()
