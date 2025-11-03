"""
Alice LLM URL Ranker & Enhanced Query Generator - OPTIMIZED VERSION
Smart URL ranking with scraping method selection AND enhanced query generation in single LLM call.
Provides relevance scoring, optimal scraping method determination, AND enhanced vector search queries.
"""

import json
import os
import time
import logging
import asyncio
from typing import Dict, List, Any, Tuple
from dotenv import load_dotenv

logger = logging.getLogger(__name__)
load_dotenv()

# ==================== GLOBAL CONFIGURATION ====================

# Load API keys once at module level
API_KEYS = [
    os.getenv('GROQ_API_KEY'),
    os.getenv('GROQ_API_KEY_ALT_1'), 
    os.getenv('GROQ_API_KEY_ALT_2'),
    os.getenv('GROQ_API_KEY_ALT_3'),
    os.getenv('GROQ_API_KEY_ALT_4')
]

AVAILABLE_API_KEYS = [key for key in API_KEYS if key and key.strip()]

LLM_RANKER_API_ORDER = [
    'GROQ_API_KEY_ALT_2',
    'GROQ_API_KEY_ALT_3',
    'GROQ_API_KEY_ALT_4',
    'GROQ_API_KEY',         
    'GROQ_API_KEY_ALT_1'
]

LLM_MODEL = "llama-3.3-70b-versatile"
LLM_TEMPERATURE = 0.3
MAX_RANKING_URLS = 100
MAX_TOKENS = 3000

# Scraping Method Categories
JAVASCRIPT_HEAVY_SITES = [
    'twitter.com', 'x.com', 'facebook.com', 'instagram.com',
    'youtube.com', 'tiktok.com', 'linkedin.com', 'discord.com'
]

COMPLEX_DYNAMIC_SITES = [
    'amazon.com', 'ebay.com', 'cnn.com', 'bbc.com',
    'medium.com', 'reddit.com', 'github.com', 'stackoverflow.com'
]

# COMBINED Ranking + Query Enhancement Prompt Template
COMBINED_RANKING_ENHANCEMENT_PROMPT = """DUAL TASK: URL Ranking + Enhanced Query Generation
                                         
                                         Original Query: "{user_query}"
                                         
                                         TASK 1 - URL RANKING: Rank ALL these web search results by relevance to the query.
                                         For EACH URL, determine the BEST scraping method:
                                         **beautifulsoup**: Simple static HTML sites, blogs, news articles, documentation
                                         **crawl4ai**: Complex sites with dynamic content but no heavy JavaScript (e-commerce, modern news sites)
                                         **playwright**: JavaScript-heavy sites, SPAs, social media, interactive applications
                                         
                                         TASK 2 - ENHANCED QUERY GENERATION: Create an optimized search query for vector similarity matching.
                                         Transform the original query to include:
                                         - Synonyms and related terms that would appear in relevant content
                                         - Domain-specific keywords and professional terminology
                                         - Technical terms and context that content creators would use
                                         - Geographic, temporal, or categorical context when relevant
                                         
                                         Examples of query enhancement:
                                         - "weather today" → "weather forecast today current temperature conditions humidity precipitation climate meteorology"
                                         - "best laptops" → "best laptops 2025 reviews specifications performance benchmarks comparison top rated gaming business ultrabook"
                                         - "python tutorial" → "python programming tutorial guide learn basics syntax examples code functions variables loops"
                                         
                                         Return JSON with TWO sections:
                                         {{
                                             "enhanced_query": "comprehensive enhanced version with domain-specific terms, synonyms, technical vocabulary, and contextual keywords that would appear in high-quality content about this topic",
                                             "url_rankings": [
                                                 {{"id": 0, "relevance_score": 95, "method": "beautifulsoup", "reason": "Static site with simple HTML structure"}},
                                                 {{"id": 1, "relevance_score": 85, "method": "crawl4ai", "reason": "Dynamic content site with complex structure"}},
                                                 {{"id": 2, "relevance_score": 75, "method": "playwright", "reason": "JavaScript-heavy application requiring browser rendering"}},
                                                 ... (continue for ALL {total_count} URLs)
                                             ]
                                         }}
                                         
                                         CRITICAL: 
                                         1. Enhanced query should be 3-5x longer than original with professional vocabulary
                                         2. Include ALL {total_count} URLs in rankings
                                         3. Ensure enhanced query includes terms that would appear in authoritative content
                                         
                                         Search Results:
                                         {url_data}
                                         
                                         Return ONLY valid JSON starting with {{ and ending with }}"""
                                         
# System Prompt
LLM_SYSTEM_PROMPT = """You are an expert at ranking web search results AND generating enhanced search queries for vector similarity matching. You understand when sites need specific scraping methods and how to optimize queries for semantic search."""

# ==================== DEPENDENCY MANAGEMENT ====================

try:
    from groq import Groq
    GROQ_AVAILABLE = True
except ImportError:
    GROQ_AVAILABLE = False
    print("⚠️ Groq not installed. Install with: pip install groq")

# ==================== UTILITY FUNCTIONS ====================

def check_groq_availability() -> bool:
    """Check if Groq is available and at least one API key is configured"""
    if not GROQ_AVAILABLE:
        return False
    return len(AVAILABLE_API_KEYS) > 0

def get_api_key_by_name(key_name: str) -> str:
    """Get API key by environment variable name"""
    key_map = {
        'GROQ_API_KEY': 0,
        'GROQ_API_KEY_ALT_1': 1,
        'GROQ_API_KEY_ALT_2': 2,
        'GROQ_API_KEY_ALT_3': 3,
        'GROQ_API_KEY_ALT_4': 4
    }
    
    index = key_map.get(key_name)
    if index is not None and index < len(API_KEYS):
        return API_KEYS[index]
    return None

def make_groq_request_with_fallback(messages, model,
                                    temperature=0.7, 
                                    max_tokens=1500, 
                                    api_key_priority_order=None):
    """Make Groq request with automatic fallback between API keys"""
    
    if api_key_priority_order is None:
        api_key_priority_order = LLM_RANKER_API_ORDER
    
    last_error = None
    
    for key_name in api_key_priority_order:
        api_key = get_api_key_by_name(key_name)
        
        if not api_key or not api_key.strip():
            logger.warning(f"API key {key_name} not found or empty")
            continue
            
        try:
            client = Groq(api_key=api_key)
            response = client.chat.completions.create(
                model=model,
                messages=messages,
                temperature=temperature,
                max_tokens=max_tokens
            )
            
            logger.info(f"✅ Successfully used API key: {key_name}")
            return response
            
        except Exception as e:
            error_str = str(e).lower()
            logger.warning(f"❌ API key {key_name} failed: {e}")
            last_error = e
            
            rate_limit_indicators = [
                'rate limit', 'too many requests', 'quota exceeded', 
                'tokens exhausted', '429', 'rate_limit_exceeded',
                'insufficient_quota', 'billing'
            ]
            
            if any(indicator in error_str for indicator in rate_limit_indicators):
                logger.warning(f"⏳ Rate limit hit on {key_name}, trying next key...")
                continue
            else:
                logger.error(f"🔥 Non-rate-limit error on {key_name}: {e}")
                continue
    
    raise Exception(f"All API keys failed. Last error: {last_error}")

def prepare_url_data_for_ranking(search_results: List[Dict]) -> List[Dict]:
    """Prepare search results for LLM ranking analysis"""
    url_data = []
    for i, result in enumerate(search_results):
        url_data.append({
            'id': i,
            'title': result.get('title', ''),
            'url': result.get('url', ''),
            'snippet': result.get('snippet', '')
        })
    return url_data

def determine_simple_method(url: str) -> str:
    """Determine scraping method based on simple URL pattern matching"""
    url_lower = url.lower()
    
    if any(site in url_lower for site in JAVASCRIPT_HEAVY_SITES):
        return 'playwright'
    
    if any(site in url_lower for site in COMPLEX_DYNAMIC_SITES):
        return 'crawl4ai'
    
    return 'beautifulsoup'

def calculate_simple_relevance_score(result: Dict, 
                                     query_words: List[str]) -> int:
    """Calculate relevance score using simple keyword matching"""
    score = 0
    title = result.get('title', '').lower()
    snippet = result.get('snippet', '').lower()
    
    for word in query_words:
        if word in title:
            score += 10
        if word in snippet:
            score += 5
    
    return score

def _simple_query_enhancement(user_query: str) -> str:
    """Simple fallback query enhancement using domain templates"""
    
    query_lower = user_query.lower()
    
    if any(term in query_lower for term in ['weather', 'temperature', 'rain', 'forecast', 'climate']):
        return f"{user_query} weather forecast temperature conditions humidity wind precipitation climate meteorology today current"
    
    elif any(term in query_lower for term in ['laptop', 'computer', 'tech', 'review', 'specifications']):
        return f"{user_query} specifications performance reviews comparison features price 2025 technology hardware"
    
    elif any(term in query_lower for term in ['python', 'programming', 'code', 'tutorial', 'learn']):
        return f"{user_query} programming tutorial guide code examples syntax documentation functions variables"
    
    elif any(term in query_lower for term in ['recipe', 'cooking', 'food', 'ingredients']):
        return f"{user_query} recipe ingredients cooking instructions preparation method cuisine food"
    
    elif any(term in query_lower for term in ['news', 'latest', 'today', 'current']):
        return f"{user_query} news latest updates current events today breaking recent"
    
    else:
        return f"{user_query} information details guide overview analysis explanation"

def log_method_distribution(results: List[Dict]) -> None:
    """Log distribution of scraping methods for monitoring"""
    method_count = {}
    for result in results:
        method = result.get('suggested_method', 'unknown')
        method_count[method] = method_count.get(method, 0) + 1
    
    print(f"🎯 Method Distribution: {method_count}")

# ==================== MAIN COMBINED RANKING + ENHANCEMENT FUNCTION ====================

async def rank_urls_with_enhanced_query(search_results: List[Dict], 
                                        user_query: str, 
                                        required_count: int = 5) -> Tuple[List[Dict], str]:
    """
    MAIN FUNCTION: Get URL rankings AND enhanced query in single LLM call
    
    Args:
        search_results: List of search result dictionaries
        user_query: User's search query for relevance analysis
        required_count: Number of top results needed
        
    Returns:
        Tuple[List[Dict], str]: (ranked_urls, enhanced_query)
    """
    
    if not search_results:
        logger.warning("No search results provided")
        return [], user_query
    
    if not check_groq_availability():
        print("⚠️ LLM ranking not available, using simple ranking + enhancement")
        ranked_urls = simple_rank_urls_with_methods(search_results, user_query, len(search_results))
        enhanced_query = _simple_query_enhancement(user_query)
        return ranked_urls, enhanced_query
    
    print(f"🧠 COMBINED LLM: Ranking {len(search_results)} URLs + Enhanced Query Generation")
    print(f"🎯 Query: '{user_query}'")
    print(f"🔑 Available API keys: {len(AVAILABLE_API_KEYS)}")
    
    urls_to_rank = search_results[:MAX_RANKING_URLS]
    
    try:
        ranked_results, enhanced_query = await _generate_combined_ranking_and_query(urls_to_rank, user_query)
        
        print(f"✅ COMBINED LLM completed: {len(ranked_results)} URLs ranked + query enhanced")
        print(f"🎯 Enhanced Query: '{enhanced_query}'")
        log_method_distribution(ranked_results)
        
        return ranked_results, enhanced_query
        
    except Exception as e:
        print(f"❌ Combined LLM ranking failed: {e}")
        print("🔄 Falling back to simple ranking + enhancement")
        ranked_urls = simple_rank_urls_with_methods(search_results, user_query, len(search_results))
        enhanced_query = _simple_query_enhancement(user_query)
        return ranked_urls, enhanced_query

async def _generate_combined_ranking_and_query(search_results: List[Dict], 
                                               user_query: str) -> Tuple[List[Dict], str]:
    """Generate URL rankings and enhanced query in single LLM call"""
    
    try:
        url_data = prepare_url_data_for_ranking(search_results)
        combined_prompt = _build_combined_ranking_prompt(user_query, url_data)
        
        print("🤖 Asking LLM for URL rankings + enhanced query...")
        
        response = make_groq_request_with_fallback(
            messages=[
                {"role": "system", "content": LLM_SYSTEM_PROMPT},
                {"role": "user", "content": combined_prompt}
            ],
            model=LLM_MODEL,
            temperature=LLM_TEMPERATURE,
            max_tokens=MAX_TOKENS,
            api_key_priority_order=LLM_RANKER_API_ORDER
        )
        
        llm_output = response.choices[0].message.content.strip()
        ranked_results, enhanced_query = _parse_combined_response(llm_output, 
                                                                  search_results, 
                                                                  user_query)
        
        return ranked_results, enhanced_query
        
    except Exception as e:
        logger.error(f"Combined ranking and query enhancement failed: {e}")
        raise e

def _build_combined_ranking_prompt(user_query: str, 
                                   url_data: List[Dict]) -> str:
    """Build combined prompt for URL ranking + query enhancement"""
    
    url_data_formatted = ""
    for item in url_data:
        url_data_formatted += f"""
        ID: {item['id']}
        Title: {item['title']}
        URL: {item['url']}
        Snippet: {item['snippet']}
        ---
        """
    
    return COMBINED_RANKING_ENHANCEMENT_PROMPT.format(
        user_query=user_query,
        total_count=len(url_data),
        url_data=url_data_formatted
    )

def _parse_combined_response(llm_output: str, 
                             original_results: List[Dict], 
                             user_query: str) -> Tuple[List[Dict], str]:
    """Parse combined LLM response for both rankings and enhanced query"""
    
    try:
        print("🔍 Parsing combined LLM output...")
        
        # Extract JSON from response
        json_start = llm_output.find('{')
        json_end = llm_output.rfind('}') + 1
        
        if json_start >= 0 and json_end > json_start:
            json_str = llm_output[json_start:json_end]
            combined_data = json.loads(json_str)
            
            enhanced_query = combined_data.get('enhanced_query', user_query)
            url_rankings = combined_data.get('url_rankings', [])
            
            if not enhanced_query or len(enhanced_query.strip()) < 10:
                logger.warning("⚠️ Enhanced query too short, using fallback")
                enhanced_query = _simple_query_enhancement(user_query)
            
            # Build ranked results
            ranked_results = _build_ranked_results_from_combined(url_rankings, original_results)
            
            # Ensure all URLs are included
            ranked_results = _finalize_combined_ranking(ranked_results, original_results)
            
            return ranked_results, enhanced_query
        else:
            raise ValueError("No valid JSON found in response")
            
    except Exception as e:
        print(f"❌ Error parsing combined response: {e}")
        ranked_results = simple_rank_urls_with_methods(original_results, user_query, len(original_results))
        enhanced_query = _simple_query_enhancement(user_query)
        return ranked_results, enhanced_query

def _build_ranked_results_from_combined(ranking_data: List[Dict], 
                                        original_results: List[Dict]) -> List[Dict]:
    """Build ranked results from combined LLM analysis data"""
    
    ranked_results = []
    used_ids = set()
    
    for item in ranking_data:
        result_id = item.get('id')
        relevance_score = item.get('relevance_score', 0)
        suggested_method = item.get('method', 'beautifulsoup')
        reason = item.get('reason', '')
        
        if 0 <= result_id < len(original_results) and result_id not in used_ids:
            result = original_results[result_id].copy()
            result['relevance_score'] = relevance_score
            result['suggested_method'] = suggested_method
            result['method_reason'] = reason
            ranked_results.append(result)
            used_ids.add(result_id)
    
    return ranked_results, used_ids

def _finalize_combined_ranking(ranked_results: List[Dict], 
                               original_results: List[Dict]) -> List[Dict]:
    """Finalize ranking by adding missing URLs and sorting"""
    
    if isinstance(ranked_results, tuple):
        ranked_results, used_ids = ranked_results
    else:
        used_ids = set()
    
    # Add missing URLs with default method
    for i, original_result in enumerate(original_results):
        if i not in used_ids:
            result = original_result.copy()
            result['relevance_score'] = 10
            result['suggested_method'] = 'beautifulsoup'
            result['method_reason'] = "Fallback - LLM didn't suggest method"
            ranked_results.append(result)
    
    # Sort by relevance score
    ranked_results.sort(key=lambda x: x.get('relevance_score', 0), reverse=True)
    
    return ranked_results

def simple_rank_urls_with_methods(search_results: List[Dict], 
                                  user_query: str, 
                                  total_count: int) -> List[Dict]:
    """Simple fallback ranking system with basic method selection"""
    
    print(f"📊 Simple ranking with method selection for {len(search_results)} URLs")
    
    query_words = user_query.lower().split() if user_query else []
    
    for result in search_results:
        score = calculate_simple_relevance_score(result, query_words)
        suggested_method = determine_simple_method(result.get('url', ''))
        
        result['relevance_score'] = score
        result['suggested_method'] = suggested_method
        result['method_reason'] = f"Simple pattern matching for {suggested_method}"
    
    ranked_results = sorted(search_results, key=lambda x: x.get('relevance_score', 0), reverse=True)
    
    print(f"📊 Simple ranking completed for {len(ranked_results)} URLs")
    log_method_distribution(ranked_results)
    
    return ranked_results

# ==================== CONVENIENCE FUNCTIONS ====================

# Backward compatibility - old function name
async def rank_urls_with_method_selection(search_results: List[Dict], 
                                         user_query: str, 
                                         required_count: int = 5) -> List[Dict]:
    """Backward compatibility function - returns only URLs"""
    ranked_urls, enhanced_query = await rank_urls_with_enhanced_query(search_results, user_query, required_count)
    return ranked_urls

# Enhanced Query Generation (standalone function for backward compatibility)
async def enhance_query_for_vector_search(user_query: str, scraped_data_context: List[Dict] = None) -> str:
    """Generate enhanced search query for vector database retrieval"""
    
    if not check_groq_availability():
        logger.warning("⚠️ LLM not available for query enhancement, using simple enhancement")
        return _simple_query_enhancement(user_query)
    
    # If we have context, we can create a minimal search result for combined processing
    if scraped_data_context:
        mock_search_results = [
            {
                'title': result.get('title', ''),
                'url': result.get('url', ''), 
                'snippet': result.get('content', '')[:200] if result.get('content') else ''
            }
            for result in scraped_data_context[:5]
        ]
        
        try:
            _, enhanced_query = await rank_urls_with_enhanced_query(mock_search_results, user_query, 5)
            return enhanced_query
        except Exception as e:
            logger.error(f"❌ Enhanced query generation failed: {e}")
            return _simple_query_enhancement(user_query)
    else:
        # Fallback to simple enhancement
        return _simple_query_enhancement(user_query)

def get_method_statistics(ranked_results: List[Dict]) -> Dict[str, int]:
    """Get statistics about method distribution in ranked results"""
    method_count = {}
    for result in ranked_results:
        method = result.get('suggested_method', 'unknown')
        method_count[method] = method_count.get(method, 0) + 1
    
    return method_count
