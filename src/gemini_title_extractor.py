"""
Gemini LLM Title Extractor for Tibetan-English Parallel Texts

This module uses Google's Gemini AI to extract titles from Tibetan-English parallel texts
by analyzing the first few lines of both files.

Author: Dharmadutta Dhakar
Date: 2025-09-26
"""

import os
import json
import logging
from typing import Tuple, Optional, Dict, Any
from pathlib import Path

try:
    import google.generativeai as genai
    GEMINI_AVAILABLE = True
except ImportError:
    GEMINI_AVAILABLE = False
    logging.warning("Google Generative AI library not available. Install with: pip install google-generativeai")

logger = logging.getLogger(__name__)

class GeminiTitleExtractor:
    """Extract titles from Tibetan-English parallel texts using Gemini AI"""
    
    def __init__(self, api_key: Optional[str] = None, model_name: str = "gemini-2.5-flash-lite"):
        """
        Initialize Gemini Title Extractor
        
        Args:
            api_key: Gemini API key (if None, will try to get from environment)
            model_name: Gemini model to use
        """
        if not GEMINI_AVAILABLE:
            raise ImportError("Google Generative AI library not installed")
        
        # Get API key
        self.api_key = api_key or os.getenv('GEMINI_API_KEY')
        if not self.api_key:
            raise ValueError("Gemini API key not provided. Set GEMINI_API_KEY environment variable or pass api_key parameter")
        
        # Configure Gemini
        genai.configure(api_key=self.api_key)
        self.model = genai.GenerativeModel(model_name)
        self.model_name = model_name
        
        # Cache for API responses to avoid repeated calls
        self.cache_dir = Path("cache")
        self.cache_dir.mkdir(exist_ok=True)
        self.cache_file = self.cache_dir / "gemini_title_cache.json"
        self.cache = self._load_cache()
        
        logger.info(f"🤖 Gemini Title Extractor initialized with model: {model_name}")
    
    def _load_cache(self) -> Dict[str, Dict[str, str]]:
        """Load cached Gemini responses"""
        if self.cache_file.exists():
            try:
                with open(self.cache_file, 'r', encoding='utf-8') as f:
                    cache = json.load(f)
                    logger.info(f"📋 Loaded {len(cache)} cached Gemini responses")
                    return cache
            except Exception as e:
                logger.warning(f"Failed to load Gemini cache: {e}")
        return {}
    
    def _save_cache(self):
        """Save cache to file"""
        try:
            with open(self.cache_file, 'w', encoding='utf-8') as f:
                json.dump(self.cache, f, indent=2, ensure_ascii=False)
            logger.debug(f"💾 Saved Gemini cache with {len(self.cache)} entries")
        except Exception as e:
            logger.error(f"Failed to save Gemini cache: {e}")
    
    def _create_cache_key(self, bo_lines: str, en_lines: str) -> str:
        """Create a unique cache key for the input"""
        import hashlib
        content = f"{bo_lines}|||{en_lines}"
        return hashlib.md5(content.encode('utf-8')).hexdigest()
    
    def _get_first_n_lines(self, content: str, n: int = 5) -> str:
        """Get first n non-empty lines from content"""
        lines = [line.strip() for line in content.split('\n') if line.strip()]
        return '\n'.join(lines[:n])
    
    def _create_prompt(self, bo_lines: str, en_lines: str) -> str:
        """Create the prompt for Gemini"""
        return f"""You are a Tibetan-English parallel text analyzer. You will receive the first 5 lines of a Tibetan file and the first 5 lines of its English translation. Both files are translations of the same Buddhist text.

Your task:
- Identify and return the *main title* of the text, as it appears in both files.
- Ignore decorative lines (such as lines with only symbols, or publisher/copyright notices).
- If possible, return both titles (Tibetan and English) that refer to the same work, as a JSON object: 
    {{
      "tibetan_title": "<title>",
      "english_title": "<title>"
    }}
- If you can't find a good match, leave the field as an empty string.
- Return ONLY the JSON object, no additional text or explanation.

Tibetan lines:
{bo_lines}

English lines:
{en_lines}"""
    
    def _parse_gemini_response(self, response_text: str) -> Tuple[Optional[str], Optional[str]]:
        """Parse Gemini's JSON response"""
        try:
            # Clean the response (remove markdown code blocks if present)
            cleaned_response = response_text.strip()
            if cleaned_response.startswith('```json'):
                cleaned_response = cleaned_response[7:]
            if cleaned_response.endswith('```'):
                cleaned_response = cleaned_response[:-3]
            cleaned_response = cleaned_response.strip()
            
            # Parse JSON
            result = json.loads(cleaned_response)
            
            bo_title = result.get('tibetan_title', '').strip()
            en_title = result.get('english_title', '').strip()
            
            # Return None for empty strings
            bo_title = bo_title if bo_title else None
            en_title = en_title if en_title else None
            
            return bo_title, en_title
            
        except json.JSONDecodeError as e:
            logger.warning(f"Failed to parse Gemini JSON response: {e}")
            logger.debug(f"Raw response: {response_text}")
            return None, None
        except Exception as e:
            logger.error(f"Error parsing Gemini response: {e}")
            return None, None
    
    def extract_titles_with_gemini(self, bo_content: str, en_content: str, repo_name: str = "") -> Tuple[Optional[str], Optional[str]]:
        """
        Extract titles using Gemini AI
        
        Args:
            bo_content: Tibetan file content
            en_content: English file content
            repo_name: Repository name (for logging)
            
        Returns:
            Tuple of (bo_title, en_title) or (None, None) if extraction fails
        """
        try:
            # Get first 5 lines from each file
            bo_lines = self._get_first_n_lines(bo_content, 5)
            en_lines = self._get_first_n_lines(en_content, 5)
            
            if not bo_lines or not en_lines:
                logger.warning(f"Insufficient content for Gemini analysis: {repo_name}")
                return None, None
            
            # Check cache first
            cache_key = self._create_cache_key(bo_lines, en_lines)
            if cache_key in self.cache:
                logger.debug(f"🎯 Using cached Gemini response for {repo_name}")
                cached_result = self.cache[cache_key]
                return cached_result.get('bo_title'), cached_result.get('en_title')
            
            # Create prompt
            prompt = self._create_prompt(bo_lines, en_lines)
            
            logger.info(f"🤖 Calling Gemini AI for title extraction: {repo_name}")
            
            # Call Gemini API
            response = self.model.generate_content(prompt)
            
            if not response.text:
                logger.warning(f"Empty response from Gemini for {repo_name}")
                return None, None
            
            # Parse response
            bo_title, en_title = self._parse_gemini_response(response.text)
            
            # Cache the result
            self.cache[cache_key] = {
                'bo_title': bo_title,
                'en_title': en_title,
                'repo_name': repo_name,
                'model': self.model_name
            }
            self._save_cache()
            
            if bo_title and en_title:
                logger.info(f"✅ Gemini extracted titles for {repo_name}")
                logger.debug(f"Tibetan: {bo_title}")
                logger.debug(f"English: {en_title}")
            else:
                logger.warning(f"⚠️ Gemini could not extract titles for {repo_name}")
            
            return bo_title, en_title
            
        except Exception as e:
            logger.error(f"❌ Gemini title extraction failed for {repo_name}: {e}")
            return None, None
    
    def get_cache_stats(self) -> Dict[str, Any]:
        """Get cache statistics"""
        return {
            'total_cached': len(self.cache),
            'cache_file': str(self.cache_file),
            'model_used': self.model_name
        }

def create_gemini_extractor(api_key: Optional[str] = None) -> Optional[GeminiTitleExtractor]:
    """
    Factory function to create Gemini extractor with error handling
    
    Args:
        api_key: Optional Gemini API key
        
    Returns:
        GeminiTitleExtractor instance or None if creation fails
    """
    try:
        return GeminiTitleExtractor(api_key=api_key)
    except Exception as e:
        logger.error(f"Failed to create Gemini extractor: {e}")
        return None

# Example usage
if __name__ == "__main__":
    # Test the extractor
    extractor = create_gemini_extractor()
    
    if extractor:
        # Example Tibetan and English content
        bo_test = """འཕགས་པ་ཤེས་རབ་ཀྱི་ཕ་རོལ་ཏུ་ཕྱིན་པ་བརྒྱད་སྟོང་པ།
        
        རྒྱ་གར་སྐད་དུ། ཨཱརྱ་ཨཥྚ་སཱ་ཧསྲི་ཀཱ་པྲཛྙཱ་པཱ་ར་མི་ཏཱ།
        བོད་སྐད་དུ། འཕགས་པ་ཤེས་རབ་ཀྱི་ཕ་རོལ་ཏུ་ཕྱིན་པ་བརྒྱད་སྟོང་པ།
        སངས་རྒྱས་དང་བྱང་ཆུབ་སེམས་དཔའ་ཐམས་ཅད་ལ་ཕྱག་འཚལ་ལོ།
        འདི་སྐད་བདག་གིས་ཐོས་པ་དུས་གཅིག་ན།"""
        
        en_test = """The Perfection of Wisdom in Eight Thousand Lines
        
        Homage to all buddhas and bodhisattvas!
        Thus did I hear at one time:
        The Blessed One was dwelling in Rājagṛha
        on Vulture Peak Mountain"""
        
        bo_title, en_title = extractor.extract_titles_with_gemini(bo_test, en_test, "test_repo")
        print(f"Tibetan Title: {bo_title}")
        print(f"English Title: {en_title}")
        
        # Print cache stats
        stats = extractor.get_cache_stats()
        print(f"Cache stats: {stats}")
