"""
TMX Title Extractor Module

This module handles extracting English titles from the data-translation-memory repository
and matching them with MonlamAI repositories for accurate title extraction.

Author: Dharmadutta Dhakar
Date: 2025-09-25
"""

import json
import logging
import re
import urllib.parse
from pathlib import Path
from typing import Dict, List, Optional, Tuple

from github import Github, GithubException
from github.ContentFile import ContentFile

logger = logging.getLogger(__name__)


class TMXTitleExtractor:
    """
    Handles TMX-based title extraction from data-translation-memory repository
    """
    
    def __init__(self, github_token: str, cache_dir: str = "logs"):
        """
        Initialize TMX title extractor
        
        Args:
            github_token: GitHub Personal Access Token
            cache_dir: Directory to store cache files
        """
        self.github = Github(github_token)
        self.cache_dir = Path(cache_dir)
        self.cache_file = self.cache_dir / "tmx_title_cache.json"
        self.tmx_repo_owner = "OpenPecha-Data"
        self.tmx_repo_name = "data-translation-memory"
        
        # TMX title mapping cache
        self.tmx_mapping: Dict[str, str] = {}
        
        # Load cached data
        self._load_cache()
    
    def _load_cache(self) -> None:
        """Load TMX mapping from cache file if it exists"""
        if self.cache_file.exists():
            try:
                with open(self.cache_file, 'r', encoding='utf-8') as f:
                    cache_data = json.load(f)
                    self.tmx_mapping = cache_data.get('tmx_mapping', {})
                    logger.info(f"📋 Loaded {len(self.tmx_mapping)} TMX mappings from cache")
            except Exception as e:
                logger.warning(f"Could not load TMX cache: {e}")
                self.tmx_mapping = {}
        else:
            logger.info("No TMX cache found. Will fetch from GitHub.")
    
    def _save_cache(self) -> None:
        """Save TMX mapping to cache file"""
        try:
            cache_data = {
                'tmx_mapping': self.tmx_mapping,
                'last_updated': '2025-09-25',
                'total_mappings': len(self.tmx_mapping)
            }
            
            with open(self.cache_file, 'w', encoding='utf-8') as f:
                json.dump(cache_data, f, indent=2, ensure_ascii=False)
                
            logger.info(f"💾 Saved {len(self.tmx_mapping)} TMX mappings to cache")
        except Exception as e:
            logger.error(f"Failed to save TMX cache: {e}")
    
    def _fetch_tmx_files(self) -> List[ContentFile]:
        """
        Fetch all TMX files from data-translation-memory repository
        
        Returns:
            List of TMX ContentFile objects
        """
        try:
            repo = self.github.get_repo(f"{self.tmx_repo_owner}/{self.tmx_repo_name}")
            contents = repo.get_contents("")
            
            tmx_files = []
            for content in contents:
                if content.name.endswith('.tmx'):
                    tmx_files.append(content)
            
            logger.info(f"🔍 Found {len(tmx_files)} TMX files in {self.tmx_repo_owner}/{self.tmx_repo_name}")
            return tmx_files
            
        except GithubException as e:
            logger.error(f"Failed to fetch TMX files: {e}")
            return []
    
    def _decode_tmx_filename(self, filename: str) -> str:
        """
        Decode URL-encoded TMX filename
        
        Args:
            filename: Raw filename with potential URL encoding
            
        Returns:
            Decoded filename
        """
        try:
            decoded = urllib.parse.unquote(filename)
            logger.debug(f"Decoded filename: {filename} → {decoded}")
            return decoded
        except Exception as e:
            logger.warning(f"Could not decode filename {filename}: {e}")
            return filename
    
    def _extract_title_from_tmx_filename(self, filename: str) -> Tuple[Optional[str], Optional[str]]:
        """
        Extract Toh identifier and English title from TMX filename
        
        Args:
            filename: TMX filename (e.g., "Toh_1-1-The_Chapter_on_Going_Forth-v1.tmx")
            
        Returns:
            Tuple of (toh_identifier, english_title) or (None, None) if no match
        """
        # Decode URL encoding first
        decoded_filename = self._decode_tmx_filename(filename)
        
        # Pattern: Toh_NUMBER(-PART)?-TITLE-vVERSION.tmx
        # Also handle .bo.en.tmx extensions
        pattern = r'Toh_(\d+(?:-\d+)?)-(.+?)-v\d+(?:\.bo\.en)?\.tmx'
        
        match = re.match(pattern, decoded_filename)
        if match:
            toh_number = match.group(1)  # e.g., "1-1" or "100"
            title_part = match.group(2)  # e.g., "The_Chapter_on_Going_Forth"
            
            # Convert identifier for matching: Toh_1-1 → toh1-1
            toh_identifier = f"toh{toh_number}".replace("_", "")
            
            # Convert title: The_Chapter_on_Going_Forth → The Chapter on Going Forth
            english_title = title_part.replace("_", " ")
            
            logger.debug(f"Extracted from {filename}: {toh_identifier} → '{english_title}'")
            return toh_identifier, english_title
        
        logger.debug(f"No match found for filename: {filename}")
        return None, None
    
    def build_tmx_mapping(self, force_refresh: bool = False) -> None:
        """
        Build mapping from Toh identifiers to English titles
        
        Args:
            force_refresh: If True, fetch fresh data from GitHub even if cache exists
        """
        if self.tmx_mapping and not force_refresh:
            logger.info("TMX mapping already loaded from cache")
            return
        
        logger.info("🔄 Building TMX title mapping from GitHub...")
        
        tmx_files = self._fetch_tmx_files()
        if not tmx_files:
            logger.warning("No TMX files found!")
            return
        
        mapping_count = 0
        for tmx_file in tmx_files:
            toh_id, english_title = self._extract_title_from_tmx_filename(tmx_file.name)
            if toh_id and english_title:
                self.tmx_mapping[toh_id] = english_title
                mapping_count += 1
        
        logger.info(f"✅ Built TMX mapping with {mapping_count} entries")
        
        # Save to cache
        self._save_cache()
    
    def get_english_title_for_repo(self, repo_name: str) -> Optional[str]:
        """
        Get English title for a MonlamAI repository from TMX mapping
        
        Args:
            repo_name: MonlamAI repository name (e.g., "TMtoh1-1_84000")
            
        Returns:
            English title if found, None otherwise
        """
        # Ensure mapping is built
        if not self.tmx_mapping:
            self.build_tmx_mapping()
        
        # Extract potential Toh identifier from repo name
        # TMtoh1-1_84000 → toh1-1
        # TMtoh100_84000 → toh100
        repo_lower = repo_name.lower()
        
        for toh_id in self.tmx_mapping.keys():
            if toh_id in repo_lower:
                english_title = self.tmx_mapping[toh_id]
                logger.debug(f"Found TMX match: {repo_name} → {toh_id} → '{english_title}'")
                return english_title
        
        logger.debug(f"No TMX match found for repository: {repo_name}")
        return None
    
    def find_title_in_content_lines(self, content: str, target_title: str, max_lines: int = 5) -> Optional[int]:
        """
        Find the line number where the target title appears in content
        
        Args:
            content: File content to search in
            target_title: Title to search for
            max_lines: Maximum number of lines to search (default: 5)
            
        Returns:
            Line number (0-indexed) if found, None otherwise
        """
        lines = content.split('\n')
        search_lines = lines[:max_lines]
        
        for i, line in enumerate(search_lines):
            line_clean = line.strip()
            if not line_clean:
                continue
                
            # Check for partial match (case-insensitive)
            if target_title.lower() in line_clean.lower():
                logger.debug(f"Found title match on line {i}: '{line_clean}' contains '{target_title}'")
                return i
        
        logger.debug(f"Title '{target_title}' not found in first {max_lines} lines")
        return None
    
    def extract_titles_with_tmx_mapping(self, repo_name: str, bo_content: str, en_content: str) -> Tuple[Optional[str], Optional[str]]:
        """
        Extract titles using TMX mapping and line matching
        
        Args:
            repo_name: MonlamAI repository name
            bo_content: Tibetan file content
            en_content: English file content
            
        Returns:
            Tuple of (bo_title, en_title) or (None, None) if TMX method fails
        """
        # Step 1: Get English title from TMX mapping
        tmx_english_title = self.get_english_title_for_repo(repo_name)
        if not tmx_english_title:
            logger.debug(f"No TMX mapping found for {repo_name}")
            return None, None
        
        # Step 2: Find the title in English content (first 5 lines)
        title_line_number = self.find_title_in_content_lines(en_content, tmx_english_title, max_lines=5)
        if title_line_number is None:
            logger.debug(f"TMX title '{tmx_english_title}' not found in English content for {repo_name}")
            return None, None
        
        # Step 3: Extract titles from the matching line
        bo_lines = bo_content.split('\n')
        en_lines = en_content.split('\n')
        
        if title_line_number >= len(bo_lines):
            logger.warning(f"Line {title_line_number} not available in Tibetan content for {repo_name}")
            return None, None
        
        bo_title = bo_lines[title_line_number].strip()
        en_title = en_lines[title_line_number].strip()
        
        # Enhanced fallback: if Tibetan title is empty or too short, find meaningful line
        if not bo_title or len(bo_title) < 15:
            logger.debug(f"Tibetan title on line {title_line_number} is empty or too short: '{bo_title}'")
            bo_title = self._find_meaningful_tibetan_line(bo_lines)
            logger.debug(f"Using meaningful Tibetan line as fallback: '{bo_title}'")
        
        logger.info(f"✅ TMX extraction successful for {repo_name}: Line {title_line_number}")
        logger.debug(f"   Tibetan: '{bo_title}'")
        logger.debug(f"   English: '{en_title}'")
        
        return bo_title, en_title
    
    def _find_meaningful_tibetan_line(self, bo_lines: List[str]) -> str:
        """
        Find the first meaningful Tibetan line (>15 characters, not ceremonial symbols)
        
        Args:
            bo_lines: List of Tibetan content lines
            
        Returns:
            First meaningful Tibetan line or empty string if none found
        """
        ceremonial_symbols = ['༄༅།', '༄༅', '༄', '༅', '།།', '༔', '༎', '༏', '༐', '༑']
        
        for line in bo_lines:
            line_clean = line.strip()
            
            # Skip empty lines
            if not line_clean:
                continue
            
            # Skip lines that are only ceremonial symbols
            if line_clean in ceremonial_symbols:
                continue
                
            # Skip lines that start with only ceremonial symbols
            line_without_ceremonial = line_clean
            for symbol in ceremonial_symbols:
                line_without_ceremonial = line_without_ceremonial.replace(symbol, '').strip()
            
            # Check if remaining content is meaningful (>15 characters)
            if len(line_without_ceremonial) >= 15:
                logger.debug(f"Found meaningful Tibetan line: '{line_clean}' (content length: {len(line_without_ceremonial)})")
                return line_clean
        
        # Fallback: return first non-empty line if no meaningful line found
        for line in bo_lines:
            if line.strip():
                logger.debug(f"No meaningful line found, using first non-empty: '{line.strip()}'")
                return line.strip()
        
        logger.warning("No meaningful Tibetan content found")
        return ""


def create_tmx_extractor(github_token: str, cache_dir: str = "logs") -> TMXTitleExtractor:
    """
    Factory function to create TMX title extractor
    
    Args:
        github_token: GitHub Personal Access Token
        cache_dir: Directory for cache files
        
    Returns:
        TMXTitleExtractor instance
    """
    return TMXTitleExtractor(github_token, cache_dir)


def main():
    """
    Main function to build TMX cache as standalone script
    """
    import os
    from dotenv import load_dotenv
    
    # Configure logging
    logging.basicConfig(
        level=logging.INFO,
        format='%(asctime)s - %(levelname)s - %(message)s'
    )
    
    # Load environment variables
    load_dotenv()
    
    github_token = os.getenv('GITHUB_TOKEN')
    if not github_token:
        logger.error("❌ GITHUB_TOKEN not found in environment variables!")
        logger.error("Please create a .env file with your GitHub Personal Access Token")
        return
    
    try:
        logger.info("🚀 Starting TMX cache building process...")
        
        # Create cache directory if it doesn't exist
        cache_dir = Path("cache")
        cache_dir.mkdir(exist_ok=True)
        logger.info(f"📁 Cache directory: {cache_dir.absolute()}")
        
        # Create TMX extractor
        extractor = TMXTitleExtractor(github_token=github_token, cache_dir="cache")
        
        # Build TMX mapping (force refresh to get latest data)
        extractor.build_tmx_mapping(force_refresh=True)
        
        # Display statistics
        logger.info("=" * 60)
        logger.info("📊 TMX CACHE BUILD COMPLETE")
        logger.info("=" * 60)
        logger.info(f"📋 Total TMX mappings: {len(extractor.tmx_mapping)}")
        logger.info(f"💾 Cache file: {extractor.cache_file}")
        logger.info(f"🔍 Repository: {extractor.tmx_repo_owner}/{extractor.tmx_repo_name}")
        
        # Show some sample mappings
        if extractor.tmx_mapping:
            logger.info("\n📋 Sample TMX mappings:")
            sample_count = min(5, len(extractor.tmx_mapping))
            for i, (toh_id, title) in enumerate(list(extractor.tmx_mapping.items())[:sample_count]):
                logger.info(f"   {toh_id} → '{title}'")
            
            if len(extractor.tmx_mapping) > sample_count:
                logger.info(f"   ... and {len(extractor.tmx_mapping) - sample_count} more mappings")
        
        logger.info("=" * 60)
        logger.info("🎉 TMX cache building completed successfully!")
        logger.info("💡 You can now run TM_retriever.py to use the cached TMX data")
        
    except Exception as e:
        logger.error(f"❌ TMX cache building failed: {e}")
        raise


if __name__ == "__main__":
    main()
