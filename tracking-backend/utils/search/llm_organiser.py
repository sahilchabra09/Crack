"""
Alice Content Organizer - Vector DB Integration Version
NO TRUNCATION - Works with pre-optimized content from Vector Database
Processes vector-optimized content using 70B model for comprehensive research synthesis.
"""

import json
import logging
import os
import re
from typing import Dict, List, Any, Optional
from groq import Groq
from dotenv import load_dotenv

load_dotenv()
logger = logging.getLogger(__name__)

# ==================== GLOBAL CONFIGURATION ====================

# LLM Configuration - Same model as llm_ranker for consistency
API_KEYS = [os.getenv('GROQ_API_KEY'),
            os.getenv('GROQ_API_KEY_ALT_1'), 
            os.getenv('GROQ_API_KEY_ALT_2'),
            os.getenv('GROQ_API_KEY_ALT_3'),
            os.getenv('GROQ_API_KEY_ALT_4')]

AVAILABLE_API_KEYS = [key for key in API_KEYS if key and key.strip()]
if not AVAILABLE_API_KEYS:
    raise ValueError("No valid GROQ API keys found in environment variables.")

ORGANIZER_API_ORDER = ['GROQ_API_KEY_ALT_2',
                       'GROQ_API_KEY_ALT_3',
                       'GROQ_API_KEY_ALT_4',
                       'GROQ_API_KEY',
                       'GROQ_API_KEY_ALT_1']
                   
LLM_MODEL = "llama-3.3-70b-versatile"
LLM_TEMPERATURE = 0.1
MAX_TOKENS = 8192

# Content Quality Validation Thresholds
MIN_UNIFIED_CONTENT_CHARS = 2500
TARGET_UNIFIED_CONTENT_CHARS = 4000
QUALITY_VALIDATION_ENABLED = True

# Vector DB Optimized Research Synthesis Prompt
VECTOR_OPTIMIZED_PROMPT = """You are Alice's Expert Information Synthesizer processing VECTOR-OPTIMIZED content. Create comprehensive, accurate research synthesis from pre-selected, high-relevance sources.
                             
                             🎯 **MISSION:** Create detailed, relevant synthesis for user query
                             Query: "{user_query}"
                             Vector-Optimized Sources: {source_data}
                             
                             🚨 **CRITICAL ADVANTAGES:** 
                             - Sources are PRE-FILTERED for relevance (85%+ semantic similarity)
                             - Content is SPAM-FREE (no navigation, ads, or boilerplate)
                             - All content is QUERY-RELEVANT (vector similarity selected)
                             - NO truncation applied - full optimized content available
                             
                             🚨 **CRITICAL LENGTH REQUIREMENT:** 
                             - unified_content MUST be 2500-4000 characters minimum
                             - Since content is pre-optimized, you have access to PERFECT information
                             - Expand with comprehensive details from the high-quality sources
                             - No need to filter spam - content is already clean
                             
                             📚 **CORE REQUIREMENTS:**
                             1. **LEVERAGE PRE-OPTIMIZATION** - Use the fact that content is already semantically relevant
                             2. **COMPREHENSIVE SYNTHESIS** - Combine all pre-selected high-quality information
                             3. **TECHNICAL DEPTH** - Include detailed specifications, numbers, and technical details
                             4. **PRACTICAL GUIDANCE** - Provide actionable recommendations from clean sources
                             5. **COMPLETE COVERAGE** - Address all aspects since sources are perfectly matched
                             
                             🧠 **SYNTHESIS STRATEGY:**
                             - **Technical Integration**: Combine specifications and data from multiple sources
                             - **Comprehensive Analysis**: Deep-dive into pre-selected relevant information  
                             - **Practical Applications**: Extract actionable insights from clean content
                             - **Comparative Analysis**: Compare information across optimized sources
                             - **Future Implications**: Discuss trends and predictions from authoritative content
                             
                             CRITICAL: You MUST respond with ONLY valid JSON. unified_content MUST be 2500-4000 characters.
                             
                             REQUIRED JSON FORMAT:
                             {{
                               "unified_content": "COMPREHENSIVE 2500-4000 character response leveraging vector-optimized, spam-free content to provide extensive technical details, practical guidance, comparative analysis, and actionable insights with complete coverage of the user's query from pre-selected high-relevance sources.",
                               "key_facts": ["Technical specification with exact numbers from optimized sources", "Practical implementation detail from clean content", "Comparative analysis from multiple pre-selected sources", "Performance metrics from authoritative data", "Cost/pricing information from verified sources"],
                               "main_findings": "Comprehensive summary of key insights from vector-optimized sources with technical specifications and practical recommendations",
                               "information_quality": "excellent",
                               "confidence": 0.95,
                               "content_depth": "comprehensive",
                               "word_count": 650,
                               "coverage_areas": ["technical_specifications", "implementation_guide", "comparative_analysis", "performance_metrics", "cost_analysis", "practical_recommendations"],
                               "source_usage": [{{"source_id": 1, "contributed_info": "Specific technical information and data points extracted from this vector-optimized source"}}],
                               "most_valuable_sources": [1, 2, 3],
                               "source_synthesis": "Explanation of how vector-optimized sources complement each other to provide complete technical and practical coverage"
                             }}
                             
                             🚨 CRITICAL: Since content is vector-optimized and spam-free, create comprehensive 2500-4000 character response with deep technical analysis.
                             
                             ONLY JSON. START WITH {{ END WITH }}"""
                             
# ==================== UTILITY FUNCTIONS ====================

def sanitize_json_content(raw_content: str) -> str:
    """Clean JSON content of invalid control characters"""
    import re
    
    start = raw_content.find('{')
    end = raw_content.rfind('}')
    
    if start == -1 or end == -1:
        return raw_content
    
    json_part = raw_content[start:end+1]
    json_part = json_part.strip().lstrip('\ufeff\u200b\u2060\ufffe\uffff')
    
    cleaned = ""
    for char in json_part:
        char_code = ord(char)
        if char_code < 32:
            if char in '\n\r\t':
                cleaned += ' '
        elif 127 <= char_code <= 159:
            continue
        else:
            cleaned += char
    
    cleaned = re.sub(r'\s+', ' ', cleaned)
    cleaned = re.sub(r'[\x00-\x08\x0b\x0c\x0e-\x1f\x7f-\x9f]', '', cleaned)
    
    return cleaned

def get_api_key_by_name(key_name: str) -> str:
    """Get API key by environment variable name"""
    key_map = {'GROQ_API_KEY': 0,
               'GROQ_API_KEY_ALT_1': 1,
               'GROQ_API_KEY_ALT_2': 2,
               'GROQ_API_KEY_ALT_3': 3,
               'GROQ_API_KEY_ALT_4': 4}
    
    index = key_map.get(key_name)
    if index is not None and index < len(API_KEYS):
        return API_KEYS[index]
    return None

def make_groq_request_with_fallback(messages, 
                                    model, 
                                    temperature=0.1, 
                                    max_tokens=8192, 
                                    api_key_priority_order=None):
    """Universal Groq request with automatic fallback between API keys"""
    
    if api_key_priority_order is None:
        api_key_priority_order = ORGANIZER_API_ORDER
    
    last_error = None
    
    for key_name in api_key_priority_order:
        api_key = get_api_key_by_name(key_name)
        
        if not api_key or not api_key.strip():
            logger.warning(f"API key {key_name} not found or empty")
            continue
            
        try:
            client = Groq(api_key=api_key)
            response = client.chat.completions.create(model=model,
                                                      messages=messages,
                                                      temperature=temperature,
                                                      max_tokens=max_tokens)
            
            logger.info(f"✅ Successfully used API key: {key_name}")
            return response
            
        except Exception as e:
            error_str = str(e).lower()
            logger.warning(f"❌ API key {key_name} failed: {e}")
            last_error = e
            
            if any(indicator in error_str for indicator in ['rate limit', 'too many requests', '429']):
                logger.warning(f"⏳ Rate limit hit on {key_name}, trying next key...")
                continue
            else:
                logger.error(f"🔥 Non-rate-limit error on {key_name}: {e}")
                continue
    
    raise Exception(f"All API keys failed. Last error: {last_error}")

def validate_synthesis_quality(result: Dict) -> Dict[str, Any]:
    """Validate the quality of synthesis output"""
    if not result:
        return {
            'quality_score': 0,
            'quality_checks': {},
            'content_length': 0,
            'passes_quality': False,
            'recommendations': ['Result is None']
        }
    
    content = result.get('unified_content', '')
    
    quality_checks = {'length_adequate': len(content) >= MIN_UNIFIED_CONTENT_CHARS,
                      'target_length_met': len(content) >= TARGET_UNIFIED_CONTENT_CHARS,
                      'technical_details': any(keyword in content.lower() for keyword in ['model', 'api', 'specification', 'performance', 'cost', 'implementation']),
                      'specific_numbers': bool(re.search(r'\d+', content)),
                      'multiple_sources': len(result.get('source_usage', [])) >= 2,
                      'comprehensive_coverage': len(result.get('coverage_areas', [])) >= 4,
                      'detailed_facts': len(result.get('key_facts', [])) >= 4}
    
    quality_score = sum(quality_checks.values()) / len(quality_checks)
    
    return {'quality_score': quality_score,
            'quality_checks': quality_checks,
            'content_length': len(content),
            'passes_quality': quality_score >= 0.8,  # Higher threshold for vector-optimized content
            'recommendations': [check for check, passed in quality_checks.items() if not passed]}

# ==================== MAIN CONTENT ORGANIZER CLASS ====================

class ContentOrganizer:
    """
    Vector DB Integrated Content Organizer
    NO TRUNCATION - Works with pre-optimized content from Vector Database
    """
    
    async def organize_scraped_content_optimized(self, 
                                                 optimized_results: List[Dict], 
                                                 user_query: str) -> Dict[str, Any]:
        """
        NEW METHOD: Process vector-optimized content WITHOUT any truncation
        
        Args:
            optimized_results: PRE-OPTIMIZED content from Vector Database (already relevant, spam-free)
            user_query: User's research query for context
            
        Returns:
            Dict containing comprehensive research synthesis from clean, relevant content
        """
        
        if not optimized_results or len(optimized_results) == 0:
            return self._create_fallback_response(user_query)
        
        logger.info(f"🎯 Processing {len(optimized_results)} vector-optimized sources (NO truncation needed)")
        
        # Calculate total content size (should be within optimal range)
        total_content_size = sum(len(r.get('content', '')) for r in optimized_results)
        logger.info(f"📊 Vector-optimized content: {total_content_size:,} chars (pre-filtered, spam-free)")
        
        # Create content summary directly from optimized results
        content_summary = []
        source_urls = []
        
        for i, result in enumerate(optimized_results):
            url = result.get('url', '')
            title = result.get('title', '')[:200]
            content = result.get('content', '')
            quality_score = result.get('quality_score', 85)  # Vector-optimized = higher quality
            relevance_score = result.get('relevance_score', 0.8)
            
            # Create content summary entry (FULL optimized content, NO truncation)
            content_summary.append({"source": i + 1,
                                    "title": title,
                                    "url": url,
                                    "content_preview": content,  # FULL OPTIMIZED CONTENT
                                    "quality_score": quality_score,
                                    "relevance_score": relevance_score,
                                    "word_count": len(content.split()),
                                    "char_count": len(content),
                                    "truncated": False,  # NEVER truncated - already optimized!
                                    "source_type": result.get('source_type', 'vector_optimized'),
                                    "optimization_applied": True})
                                
            # Track source URLs
            if url and title:
                source_urls.append({"source_id": i + 1,
                                    "title": title,
                                    "url": url,
                                    "domain": url.split('/')[2] if '/' in url else 'unknown',
                                    "quality_score": quality_score,
                                    "relevance_score": relevance_score,
                                    "content_length": len(content),
                                    "was_truncated": False,
                                    "source_type": result.get('source_type', 'vector_optimized')})
        
        logger.info(f"✅ Vector-optimized content prepared: {total_content_size:,} chars from {len(content_summary)} high-relevance sources")
        
        # Generate comprehensive synthesis from clean, relevant content
        try:
            synthesis_result = await self._generate_vector_optimized_synthesis(content_summary, 
                                                                               user_query, 
                                                                               source_urls, 
                                                                               optimized_results)
            
            # Enhanced post-processing for vector-optimized content
            if synthesis_result:
                synthesis_result = self._enhance_vector_synthesis(synthesis_result, 
                                                                  optimized_results)
                
                # Quality validation with higher standards
                if QUALITY_VALIDATION_ENABLED:
                    quality_report = validate_synthesis_quality(synthesis_result)
                    synthesis_result['quality_report'] = quality_report
                    
                    if not quality_report['passes_quality']:
                        logger.warning(f"⚠️ Vector-optimized content quality below threshold: {quality_report['quality_score']:.2%}")
                    else:
                        logger.info(f"✅ High-quality synthesis achieved: {quality_report['quality_score']:.2%}")
            
            content_length = len(synthesis_result.get('unified_content', '')) if synthesis_result else 0
            logger.info(f"✅ Vector-optimized synthesis complete: {content_length} chars from {len(content_summary)} sources")
            
            # Add vector optimization metadata
            if synthesis_result:
                synthesis_result.update({'vector_optimized': True,
                                         'truncation_applied': False,
                                         'optimization_method': 'semantic_vector_filtering',
                                         'source_relevance_avg': sum(r.get('relevance_score', 0) for r in optimized_results) / len(optimized_results),
                                         'original_vs_optimized': {'optimized_sources': len(optimized_results),
                                                                   'total_chars_processed': total_content_size,
                                                                   'content_quality': 'vector_filtered_high_relevance'}})
            return synthesis_result
            
        except Exception as e:
            logger.error(f"❌ Vector-optimized synthesis failed: {str(e)}")
            return self._create_vector_optimized_fallback(content_summary, user_query, optimized_results)
    
    async def _generate_vector_optimized_synthesis(self,
                                                   content_summary: List[Dict],
                                                   user_query: str,
                                                   source_urls: List[Dict],
                                                   optimized_results: List[Dict]) -> Dict[str, Any]:
        """Generate comprehensive synthesis from vector-optimized content"""
        
        logger.debug("🎯 Building vector-optimized synthesis prompt...")
        
        try:
            # Build enhanced prompt for vector-optimized content
            prompt = VECTOR_OPTIMIZED_PROMPT.format(user_query=user_query,
                                                    source_data=json.dumps(content_summary, indent=1))
            
            logger.debug(f"📊 Vector-optimized prompt: {len(prompt)} chars, {len(content_summary)} pre-filtered sources")
            
        except Exception as e:
            logger.error(f"❌ Vector-optimized prompt building failed: {e}")
            raise
        
        # Call LLM with vector-optimized content
        logger.debug("🧠 Processing vector-optimized content with LLM...")
        
        try:
            response = make_groq_request_with_fallback(messages=[{"role": "user", "content": prompt}],
                                                       model=LLM_MODEL,
                                                       temperature=LLM_TEMPERATURE,
                                                       max_tokens=MAX_TOKENS,
                                                       api_key_priority_order=ORGANIZER_API_ORDER)                                       
            
            logger.debug("✅ Vector-optimized LLM processing successful!")
            
        except Exception as e:
            logger.error(f"❌ Vector-optimized LLM call failed: {e}")
            raise
        
        # Parse response with enhanced error handling
        try:
            raw_content = response.choices[0].message.content
            
            if not raw_content or raw_content.strip() == "":
                raise Exception("Empty response from LLM")
            
            logger.debug(f"📊 LLM response: {len(raw_content)} chars")
            
            # Parse JSON with robust cleaning
            sanitized_json = sanitize_json_content(raw_content)
            result = json.loads(sanitized_json)
            
            logger.debug("✅ Vector-optimized JSON parsing successful!")
            
            # Validate result structure
            if not isinstance(result, dict) or 'unified_content' not in result:
                raise Exception("Invalid JSON structure from LLM")
            
            # Add comprehensive metadata
            result.update({'processing_method': 'vector_optimized_synthesis',
                           'source_count': len(content_summary),
                           'total_optimized_chars': sum(len(s['content_preview']) for s in content_summary),
                           'source_urls': source_urls,
                           'vector_optimization_applied': True})
            return result
            
        except json.JSONDecodeError as e:
            logger.error(f"❌ Vector-optimized JSON parsing failed: {e}")
            raise Exception(f"JSON parsing failed for vector-optimized content: {str(e)}")
        
        except Exception as e:
            logger.error(f"❌ Vector-optimized response processing failed: {e}")
            raise
    
    def _enhance_vector_synthesis(self, result: Dict, 
                                  optimized_sources: List[Dict]) -> Dict:
        """Enhance synthesis with vector-optimized content insights"""
        
        if not result or not isinstance(result, dict):
            return result
        
        # Extract additional insights from vector-optimized sources
        technical_insights = self._extract_technical_insights(optimized_sources)
        
        # Enhance result with vector-specific metadata
        result.update({'vector_insights': {'avg_relevance_score': sum(s.get('relevance_score', 0) for s in optimized_sources) / len(optimized_sources),
                                           'technical_depth': len(technical_insights.get('technical_terms', [])),
                                           'quantitative_data_points': len(technical_insights.get('numbers', [])),
                                           'source_diversity': len(set(s.get('url', '').split('/')[2] for s in optimized_sources if s.get('url')))}})
        return result
    
    def _extract_technical_insights(self, sources: List[Dict]) -> Dict:
        """Extract technical insights from vector-optimized sources"""
        
        technical_data = {'technical_terms': set(),
                          'numbers': [],
                          'specifications': []}
                      
        for source in sources:
            content = source.get('content', '').lower()
            
            # Extract technical terms
            tech_patterns = [r'\b\d+(?:\.\d+)?\s*(?:gb|mb|kb|ghz|mhz|cores?|tokens?|ms|seconds?)\b',
                             r'\b(?:api|sdk|model|algorithm|performance|latency|throughput)\b',
                             r'\$\d+(?:\.\d+)?(?:/month|/year|/request)?']              
            
            for pattern in tech_patterns:
                matches = re.findall(pattern, content)
                technical_data['technical_terms'].update(matches)
            
            # Extract numbers
            numbers = re.findall(r'\b\d+(?:\.\d+)?\b', content)
            technical_data['numbers'].extend(numbers[:10])  # Limit to avoid overflow
        
        return technical_data
    
    def _create_vector_optimized_fallback(self, 
                                          content_summary: List[Dict], 
                                          user_query: str, optimized_results: List[Dict]) -> Dict[str, Any]:
        """Create fallback response for vector-optimized content"""
        
        logger.info("🔄 Creating vector-optimized fallback response...")
        
        # Combine all optimized content
        combined_content = []
        for summary in content_summary:
            content = summary.get('content_preview', '')
            if content:
                combined_content.append(f"**{summary.get('title', 'Source')}**: {content[:800]}...")
        
        unified_content = "\n\n".join(combined_content)
        
        return {"unified_content": unified_content,
                "key_facts": [f"Vector-optimized analysis of {len(content_summary)} high-relevance sources",
                              f"Content pre-filtered for semantic relevance to: {user_query}",
                              f"Spam and navigation content removed through vector optimization",
                              f"Average relevance score: {sum(r.get('relevance_score', 0) for r in optimized_results) / len(optimized_results):.3f}",
                              f"Total optimized content: {len(unified_content):,} characters"],
                "main_findings": f"Comprehensive analysis from {len(content_summary)} vector-optimized sources providing high-relevance information about {user_query}",
                "information_quality": "excellent",
                "confidence": 0.85,
                "content_depth": "comprehensive",
                "word_count": len(unified_content.split()),
                "coverage_areas": ["vector_optimized_content", "high_relevance_sources", "spam_filtered"],
                "source_usage": [{"source_id": i+1, "contributed_info": f"Vector-optimized content from {summary.get('title', 'source')}"} 
                                   for i, summary in enumerate(content_summary)],
                "most_valuable_sources": list(range(1, len(content_summary) + 1)),
                "source_synthesis": "Vector database semantic filtering ensured all sources provide high-relevance content",
                "vector_optimized": True,
                "fallback_applied": True}
    
    def _create_fallback_response(self, user_query: str) -> Dict[str, Any]:
        """Create fallback when no optimized results available"""
        
        return {"unified_content": f"No vector-optimized content available for query: {user_query}. Please ensure the vector optimization process completed successfully.",
                "key_facts": ["No optimized sources available", "Vector optimization may have failed", "Try adjusting query or check vector database connection"],
                "main_findings": "Unable to process request due to lack of vector-optimized content",
                "information_quality": "poor",
                "confidence": 0.1,
                "content_depth": "minimal",
                "word_count": 0,
                "coverage_areas": [],
                "source_usage": [],
                "most_valuable_sources": [],
                "source_synthesis": "No vector-optimized sources available for synthesis",
                "vector_optimized": False,
                "error": "no_optimized_content_available"}

# ==================== GLOBAL INSTANCE MANAGEMENT ====================

_content_organizer = None

def get_content_organizer() -> ContentOrganizer:
    """Get global ContentOrganizer instance (Singleton pattern)"""
    global _content_organizer
    if _content_organizer is None:
        _content_organizer = ContentOrganizer()
    return _content_organizer

# ==================== CONVENIENCE FUNCTIONS ====================

async def organize_vector_optimized_content(optimized_results: List[Dict], user_query: str) -> Dict[str, Any]:
    """
    Process vector-optimized content - MAIN INTEGRATION FUNCTION
    
    Args:
        optimized_results: Pre-optimized content from Vector Database
        user_query: User's research query
        
    Returns:
        Dict containing comprehensive research synthesis
    """
    organizer = get_content_organizer()
    return await organizer.organize_scraped_content_optimized(optimized_results, user_query)
