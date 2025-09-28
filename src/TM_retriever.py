"""
TM Repository Cataloging System for MonlamAI

This script creates a comprehensive catalog of all Tibetan-English text repositories 
within the MonlamAI GitHub organization whose names start with 'TM'.

Features:
- Automatic discovery of TM* repositories
- Identification of Tibetan (bo) and English (en) .txt files
- Line counting and title extraction
- CSV catalog generation with metadata
- Comprehensive error handling and logging

Author: Dharmadutta Dhakar
Date: 2025-09-23
"""

import os
import csv
import json
import logging
import time
import requests
from datetime import datetime, timedelta
from typing import Dict, List, Optional, Tuple, Any, Set
from dataclasses import dataclass, asdict
from pathlib import Path
from types import SimpleNamespace

import pandas as pd
from github import Github, GithubException
from github.Repository import Repository
from github.ContentFile import ContentFile
from dotenv import load_dotenv

# Import fast repository discovery and title extractors
from fast_repo_discovery import FastRepositoryDiscovery
from tmx_title_extractor import create_tmx_extractor, TMXTitleExtractor

# Import Gemini title extractor
try:
    from gemini_title_extractor import create_gemini_extractor, GeminiTitleExtractor
    GEMINI_AVAILABLE = True
except ImportError:
    GEMINI_AVAILABLE = False


# Configure logging with logs directory
logs_dir = Path("logs")
logs_dir.mkdir(exist_ok=True)

# Clear any existing handlers
for handler in logging.root.handlers[:]:
    logging.root.removeHandler(handler)

logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(levelname)s - %(message)s',
    handlers=[
        logging.FileHandler(logs_dir / 'tm_retriever.log', encoding='utf-8', mode='a'),
        logging.StreamHandler()
    ],
    force=True
)
logger = logging.getLogger(__name__)


@dataclass
class RepoMetadata:
    """Data class to store repository metadata"""
    repo_name: str
    repo_url: str
    bo_file_path: str = ""
    bo_lines: int = 0
    bo_title: str = ""
    en_file_path: str = ""
    en_lines: int = 0
    en_title: str = ""
    notes: str = ""


class TMRepositoryCatalogger:
    """Main class for cataloging TM repositories in MonlamAI organization"""
    
    def __init__(self, github_token: str, org_name: str = "MonlamAI", 
                 checkpoint_dir: str = "checkpoints", batch_size: int = 10,
                 output_csv: str = "tm_repos_catalog.csv"):
        """
        Initialize the catalogger with GitHub authentication and checkpoint system
        
        Args:
            github_token: GitHub Personal Access Token
            org_name: GitHub organization name (default: MonlamAI)
            checkpoint_dir: Directory for storing checkpoint files
            batch_size: Number of repos to process before writing to CSV
            output_csv: Output CSV filename
        """
        self.github_token = github_token
        self.github = Github(github_token)
        self.org_name = org_name
        self.org = None
        self.catalog_data: List[RepoMetadata] = []
        
        # Checkpoint and progress tracking
        self.checkpoint_dir = Path(checkpoint_dir)
        self.batch_size = batch_size
        self.output_csv = output_csv
        self.progress_file = logs_dir / "progress.json"
        self.processed_repos: Set[str] = set()
        self.failed_repos: Dict[str, str] = {}
        
        # caching system: src/cache
        script_dir = Path(__file__).parent
        self.cache_dir = script_dir / "cache"
        self.cache_dir.mkdir(exist_ok=True)
        self.repo_cache_file = self.cache_dir / "repository_cache.json"
        
        # Tibetan title markers to search for
        self.tibetan_markers = [
            "བོད་སྐད་དུ",      # Primary marker
            "མདོ།",        # Sutra marker
            "སྔགས།",       # Mantra marker  
            "གཟུངས།",      # Dharani marker
            "རྒྱ་གར་སྐད་དུ"     # Tantra marker
        ]
        
        self.checkpoint_dir.mkdir(exist_ok=True)
        logger.info(f"📁 Checkpoint directory: {self.checkpoint_dir.absolute()}")
        
        self._authenticate()
        self._load_progress()
        self._load_existing_processed_repos()
        
        # Initialize TMX title extractor with automatic cache building
        self.tmx_extractor = self._initialize_tmx_extractor(github_token)
        
        # Initialize Gemini title extractor (optional)
        self.gemini_extractor = self._initialize_gemini_extractor()
    
    def _authenticate(self) -> None:
        """Authenticate with GitHub and get organization"""
        try:
            # Test authentication
            user = self.github.get_user()
            logger.info(f"Authenticated as: {user.login}")
            
            # Get organization
            self.org = self.github.get_organization(self.org_name)
            logger.info(f"Successfully connected to organization: {self.org_name}")
            
        except GithubException as e:
            logger.error(f"GitHub authentication failed: {e}")
            raise
        except Exception as e:
            logger.error(f"Unexpected error during authentication: {e}")
            raise
    
    def _initialize_tmx_extractor(self, github_token: str):
        """
        Initialize TMX title extractor with automatic cache building
        
        Args:
            github_token: GitHub Personal Access Token
            
        Returns:
            TMXTitleExtractor instance
        """
        # Use the same cache directory as defined in __init__
        cache_dir = self.cache_dir
        cache_file = cache_dir / "tmx_title_cache.json"
        
        # Check if TMX cache exists
        if cache_file.exists():
            logger.info(f"📋 TMX cache found at {cache_file}")
            # Create extractor with existing cache
            return create_tmx_extractor(github_token, str(cache_dir))
        else:
            logger.info("📋 No TMX cache found. Building TMX cache automatically...")
            
            # Create cache directory
            cache_dir.mkdir(exist_ok=True)
            logger.info(f"📁 Created cache directory: {cache_dir.absolute()}")
            
            # Create TMX extractor and build cache
            extractor = TMXTitleExtractor(github_token=github_token, cache_dir=str(cache_dir))
            
            try:
                extractor.build_tmx_mapping(force_refresh=True)
                logger.info(f"✅ TMX cache built successfully with {len(extractor.tmx_mapping)} mappings")
                logger.info(f"💾 Cache saved to: {cache_file}")
                
            except Exception as e:
                logger.warning(f"⚠️  TMX cache building failed: {e}")
                logger.info("💡 Continuing without TMX cache - will use fallback title extraction")
        
        return extractor
    
    def _initialize_gemini_extractor(self) -> Optional[GeminiTitleExtractor]:
        """
        Initialize Gemini title extractor (optional)
        
        Returns:
            GeminiTitleExtractor instance or None if not available/configured
        """
        if not GEMINI_AVAILABLE:
            logger.info("🤖 Gemini AI not available - install google-generativeai for AI-powered title extraction")
            return None
        
        try:
            # Try to create Gemini extractor
            extractor = create_gemini_extractor()
            
            if extractor:
                logger.info("🤖 Gemini AI title extractor initialized successfully")
                stats = extractor.get_cache_stats()
                logger.info(f"📋 Gemini cache: {stats['total_cached']} cached responses")
                return extractor
            else:
                logger.warning("⚠️  Gemini extractor creation failed - check API key")
                return None
                
        except Exception as e:
            logger.warning(f"⚠️  Gemini initialization failed: {e}")
            logger.info("💡 Continuing without Gemini AI - will use TMX and fallback methods")
            return None
    
    def _load_progress(self) -> None:
        """Load existing progress from previous runs"""
        if Path(self.progress_file).exists():
            try:
                with open(self.progress_file, 'r', encoding='utf-8') as f:
                    progress = json.load(f)
                    self.processed_repos = set(progress.get('processed_repos', []))
                    self.failed_repos = progress.get('failed_repos', {})
                    logger.info(f"Resumed session: {len(self.processed_repos)} repos already processed, "
                              f"{len(self.failed_repos)} failed repos found")
            except Exception as e:
                logger.warning(f"Could not load progress file: {e}. Starting fresh.")
                self.processed_repos = set()
                self.failed_repos = {}
        else:
            logger.info("No previous progress found. Starting fresh cataloging session.")
    
    def _save_progress(self) -> None:
        """Save current progress to file"""
        try:
            progress = {
                'session_id': datetime.now().strftime("%Y-%m-%d_%H-%M-%S"),
                'total_discovered': len(self.processed_repos) + len(self.failed_repos),
                'processed_repos': list(self.processed_repos),
                'failed_repos': self.failed_repos,
                'last_processed_time': datetime.now().isoformat(),
                'batch_size': self.batch_size,
                'output_csv': self.output_csv
            }
            
            with open(self.progress_file, 'w', encoding='utf-8') as f:
                json.dump(progress, f, indent=2, ensure_ascii=False)
                
        except Exception as e:
            logger.error(f"Failed to save progress: {e}")
    
    def _load_existing_processed_repos(self) -> None:
        """Load list of already processed repositories from existing CSV file"""
        existing_csv_path = Path("../existing_data") / "existing_file_name.csv"
        
        if existing_csv_path.exists():
            try:
                import pandas as pd
                df = pd.read_csv(existing_csv_path)
                
                # Get the list of already processed repo names
                existing_repos = set(df['file_name'].astype(str).tolist())
                
                # Add to processed repos to exclude them
                self.processed_repos.update(existing_repos)
                
                logger.info(f"📋 Loaded {len(existing_repos)} already processed repositories from existing data")
                logger.info(f"🚫 These repositories will be skipped during discovery")
                
            except Exception as e:
                logger.warning(f"Could not load existing processed repos: {e}")
                logger.info("Will proceed without exclusion list")
        else:
            logger.info(f"No existing data file found at {existing_csv_path}")
            logger.info("Will process all discovered TM repositories")
    
    def _load_repository_cache(self) -> List[Dict]:
        """Load repository list from cache if exists"""
        if not self.repo_cache_file.exists():
            logger.info("No repository cache found. Will fetch from GitHub API.")
            return []
        
        try:
            with open(self.repo_cache_file, 'r', encoding='utf-8') as f:
                cache_data = json.load(f)
            
            tm_repos = cache_data['tm_repos']
            logger.info(f"📋 Loaded {len(tm_repos)} TM repositories from cache")
            return tm_repos
            
        except Exception as e:
            logger.warning(f"Failed to load repository cache: {e}. Will fetch from API.")
            return []
    
    def _save_repository_cache(self, tm_repos: List[Repository]) -> None:
        """Save TM repository list to cache"""
        try:
            # Extract essential data from TM repositories
            tm_repos_data = []
            for repo in tm_repos:
                repo_data = {
                    'name': repo.name,
                    'html_url': repo.html_url,
                    'full_name': repo.full_name,
                    'id': repo.id
                }
                tm_repos_data.append(repo_data)
            
            cache_data = {
                'tm_repos': tm_repos_data,
                'total_count': len(tm_repos_data),
                'cached_at': datetime.now().isoformat(),
                'organization': self.org_name
            }
            
            with open(self.repo_cache_file, 'w', encoding='utf-8') as f:
                json.dump(cache_data, f, indent=2, ensure_ascii=False)
            
            logger.info(f"💾 Cached {len(tm_repos_data)} TM repositories to {self.repo_cache_file}")
            
        except Exception as e:
            logger.error(f"Failed to save repository cache: {e}")
    
    
    def _write_batch_to_csv(self, batch_data: List[RepoMetadata], append: bool = True) -> None:
        """
        Write batch data to CSV incrementally
        
        Args:
            batch_data: List of RepoMetadata to write
            append: Whether to append to existing file or create new
        """
        if not batch_data:
            return
            
        try:
            # Determine write mode
            file_exists = Path(self.output_csv).exists()
            mode = 'a' if append and file_exists else 'w'
            write_header = mode == 'w'
            
            # Convert to DataFrame
            catalog_dicts = [asdict(metadata) for metadata in batch_data]
            df = pd.DataFrame(catalog_dicts)
            
            # Ensure output directory exists
            output_dir = Path(self.output_csv).parent
            output_dir.mkdir(parents=True, exist_ok=True)
            
            # Write to CSV
            df.to_csv(self.output_csv, mode=mode, header=write_header, 
                     index=False, encoding='utf-8')
            
            logger.info(f"{'Appended' if append and file_exists else 'Created'} CSV with "
                       f"{len(batch_data)} repositories. Total processed: {len(self.processed_repos)}")
            
        except Exception as e:
            logger.error(f"Failed to write batch to CSV: {e}")
            raise
    
    def _write_checkpoint_csv(self, batch_data: List[RepoMetadata], checkpoint_num: int) -> None:
        """
        Write checkpoint CSV file for each batch
        
        Args:
            batch_data: List of RepoMetadata to write
            checkpoint_num: Current checkpoint number
        """
        if not batch_data:
            return
            
        try:
            # Create checkpoint filename
            checkpoint_file = self.checkpoint_dir / f"checkpoint_{checkpoint_num:04d}.csv"
            
            # Convert to DataFrame
            catalog_dicts = [asdict(metadata) for metadata in batch_data]
            df = pd.DataFrame(catalog_dicts)
            
            # Write checkpoint CSV
            df.to_csv(checkpoint_file, index=False, encoding='utf-8')
            
            logger.info(f"💾 Checkpoint CSV saved: {checkpoint_file}")
            
        except Exception as e:
            logger.error(f"Failed to write checkpoint CSV: {e}")
            raise
    
    def discover_tm_repositories(self, limit: Optional[int] = None) -> List[Dict]:
        """
        Discover all TM* repositories using cached data or fast discovery
        
        Args:
            limit: Optional limit on number of repositories to return
            
        Returns:
            List of repository dictionaries with keys: name, html_url, full_name, id
        """
        logger.info("🔍 Discovering TM* repositories...")
        if limit:
            logger.info(f"🧪 TESTING MODE: Will process only first {limit} TM repositories found")
        
        # Try to load from cache first
        cached_repos = self._load_repository_cache()
        if cached_repos:
            # Use cached data directly (no conversion needed)
            all_tm_repos = cached_repos
            logger.info(f"✅ Using cached repository data ({len(all_tm_repos)} repos)")
        else:
            # Use fast repository discovery
            logger.info("🚀 Using fast repository discovery for TM* repositories...")
            
            try:
                # Create fast discovery instance
                fast_discovery = FastRepositoryDiscovery(
                    github_token=os.getenv('GITHUB_TOKEN'),
                    org_name=self.org_name
                )
                
                # returns Repository objects - convert to dictionaries immediately
                repo_objects = fast_discovery.discover_tm_repositories_fast()
                
                # Convert Repository objects to dictionaries for consistent handling
                all_tm_repos = []
                for repo in repo_objects:
                    repo_dict = {
                        'name': repo.name,
                        'html_url': repo.html_url,
                        'full_name': repo.full_name,
                        'id': repo.id
                    }
                    all_tm_repos.append(repo_dict)
                
                logger.info(f"✅ Fast discovery completed: {len(all_tm_repos)} TM repositories found")
                
                # Save to our cache format
                self._save_repository_cache(repo_objects)
                
            except Exception as e:
                logger.error(f"❌ Fast repository discovery failed: {e}")
                logger.error("💡 Please check your GitHub token and network connection")
                logger.error("🔄 You can try running the fast_repo_discovery.py script separately first")
                raise SystemExit(1)
        
        # Apply limit if specified
        if limit and len(all_tm_repos) > limit:
            all_tm_repos = all_tm_repos[:limit]
            logger.info(f"🧪 Limited to first {limit} repositories for testing")
        
        # Count exclusions for statistics
        excluded_count = 0
        for repo in all_tm_repos:
            repo_name = repo['name']
            
            if repo_name in self.processed_repos:
                excluded_count += 1
                logger.debug(f"⏭️  Skipping already processed: {repo_name}")
            else:
                logger.info(f"✅ Found new TM repository: {repo_name}")
        
        # Statistics
        total_found = len(all_tm_repos)
        new_repos = total_found - excluded_count
        
        logger.info("=" * 50)
        logger.info("📊 REPOSITORY DISCOVERY SUMMARY")
        logger.info("=" * 50)
        logger.info(f"🔍 Total TM repositories found: {total_found}")
        logger.info(f"🚫 Already processed (excluded): {excluded_count}")
        logger.info(f"🆕 New repositories to process: {new_repos}")
        if total_found > 0:
            logger.info(f"📈 Processing efficiency: {((excluded_count/total_found)*100):.1f}% work already done!")
        logger.info("=" * 50)
        
        return all_tm_repos

    
    def _count_lines(self, content: str) -> int:
        """
        Count total lines in content
        
        Args:
            content: File content as string
            
        Returns:
            Total number of lines
        """
        # Remove trailing newline to avoid counting extra empty line
        content = content.rstrip('\n\r')
        
        # Handle empty content case
        if not content.strip():
            return 0
        
        lines = content.split('\n')
        total_lines = len(lines)
        
        return total_lines
    
    def _extract_parallel_titles(self, bo_content: str, en_content: str) -> Tuple[str, str]:
        """
        Extract titles from both Tibetan and English content using parallel line matching
        
        Args:
            bo_content: Tibetan file content
            en_content: English file content
            
        Returns:
            Tuple of (bo_title, en_title)
        """
        # Split content into lines
        bo_lines = [line.strip() for line in bo_content.split('\n')]
        en_lines = [line.strip() for line in en_content.split('\n')]
        
        # Find the first non-empty line in English file
        en_title = ""
        title_line_number = -1
        
        for i, line in enumerate(en_lines):
            if line.strip():  # First non-empty line
                en_title = line
                title_line_number = i
                break
        
        # Get the corresponding line from Tibetan file
        bo_title = ""
        if title_line_number >= 0 and title_line_number < len(bo_lines):
            bo_title = bo_lines[title_line_number].strip()
        
        # Enhanced fallback: if no corresponding Tibetan line or too short, find meaningful line
        if not bo_title or len(bo_title) < 15:
            bo_title = self._find_meaningful_tibetan_line(bo_lines)
        
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
    
    def _extract_titles_with_tmx(self, repo_name: str, bo_content: str, en_content: str) -> Tuple[Optional[str], Optional[str]]:
        """
        Extract titles using TMX mapping method
        
        Args:
            repo_name: Repository name
            bo_content: Tibetan file content
            en_content: English file content
            
        Returns:
            Tuple of (bo_title, en_title) or (None, None) if TMX method fails
        """
        try:
            return self.tmx_extractor.extract_titles_with_tmx_mapping(repo_name, bo_content, en_content)
        except Exception as e:
            logger.warning(f"TMX extraction failed for {repo_name}: {e}")
            return None, None
    
    def _extract_titles_with_gemini(self, repo_name: str, bo_content: str, en_content: str) -> Tuple[Optional[str], Optional[str]]:
        """
        Extract titles using Gemini AI
        
        Args:
            repo_name: Repository name
            bo_content: Tibetan file content
            en_content: English file content
            
        Returns:
            Tuple of (bo_title, en_title) or (None, None) if Gemini method fails
        """
        if not self.gemini_extractor:
            return None, None
        
        try:
            return self.gemini_extractor.extract_titles_with_gemini(bo_content, en_content, repo_name)
        except Exception as e:
            logger.warning(f"Gemini extraction failed for {repo_name}: {e}")
            return None, None
    
    def _extract_title(self, content: str, language: str) -> str:
        """
        Extract title from file content based on language-specific rules
        
        Args:
            content: File content as string
            language: 'bo' for Tibetan or 'en' for English
            
        Returns:
            Extracted title string
        """
        lines = [line.strip() for line in content.split('\n') if line.strip()]
        
        if not lines:
            return ""
        
        if language == 'en':
            # For English, take the first non-empty line
            return lines[0]
        
        elif language == 'bo':
            # For Tibetan, search for marker in first ~10 lines
            search_lines = lines[:min(10, len(lines))]
            
            for line in search_lines:
                for marker in self.tibetan_markers:
                    if marker in line:
                        return line
            
            # Fallback: find first substantial line (more than 20 characters)
            # This skips ornamental symbols like ༄༅། །
            for line in lines:
                if len(line) > 20:  # Skip very short lines that are likely ornaments
                    return line
            
            # Final fallback to first non-empty line if no substantial line found
            return lines[0] if lines else ""
        
        return ""
    
    def _download_and_analyze_file(self, file: ContentFile, language: str) -> Dict[str, Any]:
        """
        Download and analyze a single file
        
        Args:
            file: ContentFile object
            language: 'bo' or 'en'
            
        Returns:
            Dictionary with analysis results
        """
        result = {
            'path': file.path,
            'lines': 0,
            'title': '',
            'error': None
        }
        
        try:
            # Try different encodings
            encodings = ['utf-8', 'utf-16', 'latin-1']
            content = None
            
            for encoding in encodings:
                try:
                    content = file.decoded_content.decode(encoding)
                    break
                except UnicodeDecodeError:
                    continue
            
            if content is None:
                result['error'] = "Failed to decode file with any encoding"
                return result
            
            # Count lines
            result['lines'] = self._count_lines(content)
            
            # Extract title
            result['title'] = self._extract_title(content, language)
            
        except GithubException as e:
            result['error'] = f"GitHub API error: {e}"
        except Exception as e:
            result['error'] = f"Unexpected error: {e}"
        
        return result
    
    def _get_repo_contents_via_api(self, repo_full_name: str) -> List[Dict]:
        """
        Get repository root contents using direct GitHub API calls
        
        Args:
            repo_full_name: Full repository name (e.g., "MonlamAI/TMtoh267_84000")
            
        Returns:
            List of file/directory dictionaries from GitHub API
        """
        api_url = f"https://api.github.com/repos/{repo_full_name}/contents"
        
        headers = {
            'Authorization': f'token {self.github_token}',
            'Accept': 'application/vnd.github.v3+json'
        }
        
        try:
            response = requests.get(api_url, headers=headers, timeout=30)
            
            if response.status_code == 200:
                return response.json()
            elif response.status_code == 404:
                logger.warning(f"Repository {repo_full_name} not found or not accessible")
                return []
            else:
                logger.error(f"GitHub API error for {repo_full_name}: {response.status_code} - {response.text}")
                return []
                
        except requests.RequestException as e:
            logger.error(f"Request failed for {repo_full_name}: {e}")
            return []
    
    def _download_file_content_via_api(self, download_url: str) -> Optional[str]:
        """
        Download file content using direct HTTP request
        
        Args:
            download_url: Direct download URL from GitHub API
            
        Returns:
            File content as string or None if failed
        """
        try:
            response = requests.get(download_url, timeout=30)
            
            if response.status_code == 200:
                # Try different encodings
                encodings = ['utf-8', 'utf-16', 'latin-1']
                
                for encoding in encodings:
                    try:
                        return response.content.decode(encoding)
                    except UnicodeDecodeError:
                        continue
                
                logger.warning(f"Failed to decode file content with any encoding")
                return None
            else:
                logger.error(f"Failed to download file: {response.status_code}")
                return None
                
        except requests.RequestException as e:
            logger.error(f"Request failed for file download: {e}")
            return None
    
    def _download_and_analyze_file_via_api(self, file_dict: Dict, language: str) -> Dict[str, Any]:
        """
        Download and analyze a single file using direct API calls
        
        Args:
            file_dict: File dictionary from GitHub API response
            language: 'bo' or 'en'
            
        Returns:
            Dictionary with analysis results
        """
        result = {
            'path': file_dict.get('path', ''),
            'lines': 0,
            'title': '',
            'error': None
        }
        
        try:
            # Get download URL from the file dict
            download_url = file_dict.get('download_url')
            
            if not download_url:
                result['error'] = "No download URL found in file data"
                return result
            
            # Download file content
            content = self._download_file_content_via_api(download_url)
            
            if content is None:
                result['error'] = "Failed to download file content"
                return result
            
            # Count lines (non-empty lines)
            result['lines'] = self._count_nonempty_lines(content)
            
            # Extract title
            result['title'] = self._extract_title(content, language)
            
        except Exception as e:
            result['error'] = f"Unexpected error: {e}"
        
        return result
    
    def _count_nonempty_lines(self, content: str) -> int:
        """Count non-empty lines in content"""
        lines = content.split('\n')
        return len([line for line in lines if line.strip()])
    
    def analyze_repository(self, repo_dict: Dict) -> RepoMetadata:
        """
        Analyze a single repository using direct API calls with cache data
        
        Args:
            repo_dict: Repository dictionary from cache
            
        Returns:
            RepoMetadata object with analysis results
        """
        repo_name = repo_dict['name']
        repo_url = repo_dict['html_url']
        repo_full_name = repo_dict['full_name']
            
        logger.info(f"Analyzing repository: {repo_name}")
        
        metadata = RepoMetadata(
            repo_name=repo_name,
            repo_url=repo_url
        )
        
        try:
            # Get all files from root directory using direct API calls
            bo_file = None
            en_file = None
            
            # Get repository contents via direct API
            root_contents = self._get_repo_contents_via_api(repo_full_name)
            
            if root_contents:
                # Filter for .txt files only
                txt_files = [f for f in root_contents if f.get('type') == 'file' and f.get('name', '').endswith('.txt')]
                
                # Find Tibetan file (contains 'bo' in filename)
                bo_candidates = [f for f in txt_files if 'bo' in f.get('name', '').lower()]
                if bo_candidates:
                    # Sort by filename length (shorter first) as tie-breaker
                    bo_candidates.sort(key=lambda f: len(f.get('name', '')))
                    bo_file = bo_candidates[0]
                
                # Find English file (contains 'en' in filename)
                en_candidates = [f for f in txt_files if 'en' in f.get('name', '').lower()]
                if en_candidates:
                    # Sort by filename length (shorter first) as tie-breaker
                    en_candidates.sort(key=lambda f: len(f.get('name', '')))
                    en_file = en_candidates[0]
            else:
                logger.warning(f"Could not access root directory contents for {repo_name}")
                # Continue with bo_file and en_file as None
            
            notes = []
            
            # If both files exist, use parallel title extraction
            if bo_file and en_file:
                # Analyze both files for line counts using direct API
                bo_analysis = self._download_and_analyze_file_via_api(bo_file, 'bo')
                en_analysis = self._download_and_analyze_file_via_api(en_file, 'en')
                
                # Set basic metadata
                metadata.bo_file_path = bo_analysis['path']
                metadata.bo_lines = bo_analysis['lines']
                metadata.en_file_path = en_analysis['path']
                metadata.en_lines = en_analysis['lines']
                
                # Check for errors
                if bo_analysis['error']:
                    notes.append(f"Tibetan file error: {bo_analysis['error']}")
                if en_analysis['error']:
                    notes.append(f"English file error: {en_analysis['error']}")
                
                # Use TMX-based title extraction if no errors
                if not bo_analysis['error'] and not en_analysis['error']:
                    try:
                        # Download file contents for TMX processing
                        bo_content = self._download_file_content_via_api(bo_file.get('download_url'))
                        en_content = self._download_file_content_via_api(en_file.get('download_url'))
                        
                        if bo_content and en_content:
                            # Try TMX extraction first
                            tmx_bo_title, tmx_en_title = self._extract_titles_with_tmx(repo_name, bo_content, en_content)
                            
                            if tmx_bo_title and tmx_en_title:
                                # TMX extraction successful
                                metadata.bo_title = tmx_bo_title
                                metadata.en_title = tmx_en_title
                                notes.append("Used TMX mapping for title extraction")
                            else:
                                # Try Gemini AI extraction as second option
                                gemini_bo_title, gemini_en_title = self._extract_titles_with_gemini(repo_name, bo_content, en_content)
                                
                                if gemini_bo_title and gemini_en_title:
                                    # Gemini extraction successful
                                    metadata.bo_title = gemini_bo_title
                                    metadata.en_title = gemini_en_title
                                    notes.append("Used Gemini AI for title extraction")
                                else:
                                    # Final fallback to parallel line matching
                                    bo_title, en_title = self._extract_parallel_titles(bo_content, en_content)
                                    metadata.bo_title = bo_title
                                    metadata.en_title = en_title
                                    notes.append("Used parallel line matching for title extraction (TMX+Gemini fallback)")
                        else:
                            # Use individual analysis results if content download failed
                            metadata.bo_title = bo_analysis['title']
                            metadata.en_title = en_analysis['title']
                            notes.append("Content download failed, used individual analysis")
                        
                    except Exception as e:
                        # Final fallback to individual title extraction
                        metadata.bo_title = bo_analysis['title']
                        metadata.en_title = en_analysis['title']
                        notes.append(f"Title extraction failed, used individual analysis: {e}")
                else:
                    # Use individual analysis results if there were errors
                    metadata.bo_title = bo_analysis['title']
                    metadata.en_title = en_analysis['title']
                
            
            else:
                # Handle cases where only one file exists or neither exists
                if bo_file:
                    bo_analysis = self._download_and_analyze_file_via_api(bo_file, 'bo')
                    metadata.bo_file_path = bo_analysis['path']
                    metadata.bo_lines = bo_analysis['lines']
                    metadata.bo_title = bo_analysis['title']
                    
                    if bo_analysis['error']:
                        notes.append(f"Tibetan file error: {bo_analysis['error']}")
                else:
                    # Leave bo fields empty (they're already initialized as empty in RepoMetadata)
                    notes.append("No .txt file with 'bo' in filename found")
                
                if en_file:
                    en_analysis = self._download_and_analyze_file_via_api(en_file, 'en')
                    metadata.en_file_path = en_analysis['path']
                    metadata.en_lines = en_analysis['lines']
                    metadata.en_title = en_analysis['title']
                    
                    if en_analysis['error']:
                        notes.append(f"English file error: {en_analysis['error']}")
                else:
                    # Leave en fields empty (they're already initialized as empty in RepoMetadata)
                    notes.append("No .txt file with 'en' in filename found")
            
            metadata.notes = "; ".join(notes)
        
        except GithubException as e:
            error_msg = f"status={getattr(e, 'status', 'unknown')} data={getattr(e, 'data', {})}"
            metadata.notes = f"Repository analysis failed: {error_msg}"
            logger.error(f"Repo {repo_name} failed with GithubException: {error_msg}")
            
        except Exception as e:
            metadata.notes = f"Repository analysis failed: {type(e).__name__}: {e}"
            logger.error(f"Repo {repo_name} failed: {type(e).__name__}: {e}")
        
        return metadata
    
    def catalog_all_repositories(self, limit: Optional[int] = None, retry_failed: bool = False) -> None:
        """
        Enhanced cataloging with resume capability and checkpoint system
        
        Args:
            limit: Optional limit on number of TM repositories to process (for testing)
            retry_failed: If True, retry only previously failed repositories
        """
        logger.info("Starting comprehensive cataloging with resume capability...")
        
        # Discover repositories
        tm_repos = self.discover_tm_repositories(limit=limit)
        
        if not tm_repos:
            logger.warning("No TM repositories found!")
            return
        
        # Determine which repos to process
        if retry_failed:
            # Only retry failed repositories
            pending_repos = [repo for repo in tm_repos if repo['name'] in self.failed_repos]
            logger.info(f"Retry mode: Processing {len(pending_repos)} previously failed repositories")
            # Clear failed repos for retry
            for repo in pending_repos:
                self.failed_repos.pop(repo['name'], None)
        else:
            # Filter out already processed repos
            pending_repos = [repo for repo in tm_repos if repo['name'] not in self.processed_repos]
        
        logger.info(f"Found {len(tm_repos)} total TM repositories")
        logger.info(f"Already processed: {len(self.processed_repos)}")
        logger.info(f"Previously failed: {len(self.failed_repos)}")
        logger.info(f"Pending to process: {len(pending_repos)}")
        
        if not pending_repos:
            logger.info("All repositories already processed! Use retry_failed=True to retry failed ones.")
            self._generate_final_report()
            return
        
        # Process repositories in batches
        batch_data = []
        
        for i, repo in enumerate(pending_repos, 1):
            repo_name = repo['name']
            logger.info(f"Processing {i}/{len(pending_repos)}: {repo_name}")
            
            try:
                metadata = self.analyze_repository(repo)
                
                # Check if analysis actually succeeded (not just returned error metadata)
                if "Repository analysis failed" in metadata.notes or "Processing failed" in metadata.notes:
                    # This is actually a failed analysis, treat as exception
                    raise Exception(metadata.notes)
                
                batch_data.append(metadata)
                self.processed_repos.add(repo_name)
                
                # Remove from failed repos if it was there
                self.failed_repos.pop(repo_name, None)
                
                logger.info(f"✅ Successfully processed {repo_name}")
                
                # Write batch to CSV when batch is full
                if len(batch_data) >= self.batch_size:
                    self._write_batch_to_csv(batch_data)
                    self._write_checkpoint_csv(batch_data, len(self.processed_repos))
                    self._save_progress()
                    batch_data = []  # Reset batch
                    logger.info(f"📊 Checkpoint saved. Progress: {len(self.processed_repos)}/{len(tm_repos)}")
                
                # Rate limiting
                time.sleep(1)
                
            except Exception as e:
                logger.error(f"❌ Failed to process {repo_name}: {e}")
                self.failed_repos[repo_name] = str(e)
                
                # Save progress even on failure
                self._save_progress()
                
                # Add error entry to current batch for CSV
                error_metadata = RepoMetadata(
                    repo_name=repo_name,
                    repo_url=repo['html_url'],
                    notes=f"Processing failed: {e}"
                )
                batch_data.append(error_metadata)
                
                # Continue processing other repositories
                continue
        
        # Write remaining batch
        if batch_data:
            self._write_batch_to_csv(batch_data)
            logger.info("📝 Final batch written to CSV")
        
        # Save final progress
        self._save_progress()
        
        # Generate comprehensive report
        self._generate_final_report()
        
        logger.info("🎉 Cataloging session completed!")
    
    def generate_csv_catalog(self, output_path: str = "tm_repos_catalog.csv") -> None:
        """
        Generate CSV catalog from collected data
        
        Args:
            output_path: Path for output CSV file
        """
        if not self.catalog_data:
            logger.warning("No catalog data to export!")
            return
        
        logger.info(f"Generating CSV catalog: {output_path}")
        
        # Convert to list of dictionaries
        catalog_dicts = [asdict(metadata) for metadata in self.catalog_data]
        
        # Create DataFrame and save to CSV
        df = pd.DataFrame(catalog_dicts)
        
        # Ensure output directory exists
        output_dir = Path(output_path).parent
        output_dir.mkdir(parents=True, exist_ok=True)
        
        df.to_csv(output_path, index=False, encoding='utf-8')
        logger.info(f"CSV catalog saved to: {output_path}")
        
        # Generate summary statistics
        self._analyze_csv_content(df)
    
    def _generate_final_report(self) -> None:
        """Generate comprehensive final report with statistics"""
        logger.info("=" * 50)
        logger.info("🎯 FINAL CATALOGING REPORT")
        logger.info("=" * 50)
        
        # Overall statistics
        total_processed = len(self.processed_repos)
        total_failed = len(self.failed_repos)
        total_attempted = total_processed + total_failed
        
        logger.info(f"📊 PROCESSING SUMMARY:")
        logger.info(f"   ✅ Successfully processed: {total_processed}")
        logger.info(f"   ❌ Failed repositories: {total_failed}")
        logger.info(f"   📈 Total attempted: {total_attempted}")
        
        if total_attempted > 0:
            success_rate = (total_processed / total_attempted) * 100
            logger.info(f"   🎯 Success rate: {success_rate:.1f}%")
        
        # Failed repositories details
        if self.failed_repos:
            logger.info(f"\n❌ FAILED REPOSITORIES ({len(self.failed_repos)}):")
            for repo_name, error in self.failed_repos.items():
                logger.info(f"   - {repo_name}: {error}")
        
        # CSV file analysis (if exists)
        if Path(self.output_csv).exists():
            try:
                df = pd.read_csv(self.output_csv)
                self._analyze_csv_content(df)
            except Exception as e:
                logger.warning(f"Could not analyze CSV content: {e}")
        
        # Session information
        logger.info(f"\n📁 OUTPUT FILES:")
        logger.info(f"   📄 CSV catalog: {self.output_csv}")
        logger.info(f"   💾 Progress file: {self.progress_file}")
        logger.info(f"   📂 Checkpoint dir: {self.checkpoint_dir}")
        
        logger.info("=" * 50)
    
    def _analyze_csv_content(self, df: pd.DataFrame) -> None:
        """Analyze and report CSV content statistics"""
        total_repos = len(df)
        has_both = len(df[(df['bo_file_path'] != '') & (df['en_file_path'] != '')])
        has_only_bo = len(df[(df['bo_file_path'] != '') & (df['en_file_path'] == '')])
        has_only_en = len(df[(df['bo_file_path'] == '') & (df['en_file_path'] != '')])
        has_none = len(df[(df['bo_file_path'] == '') & (df['en_file_path'] == '')])
        
        logger.info(f"\n📋 CSV CONTENT ANALYSIS:")
        logger.info(f"   📚 Total repositories in CSV: {total_repos}")
        logger.info(f"   🔄 Both bo and en files: {has_both}")
        logger.info(f"   🇹🇧 Only Tibetan files: {has_only_bo}")
        logger.info(f"   🇬🇧 Only English files: {has_only_en}")
        logger.info(f"   📭 No text files found: {has_none}")
        
        if has_both > 0:
            try:
                avg_bo_lines = df[df['bo_lines'] > 0]['bo_lines'].mean()
                avg_en_lines = df[df['en_lines'] > 0]['en_lines'].mean()
                logger.info(f"   📊 Average Tibetan lines: {avg_bo_lines:.1f}")
                logger.info(f"   📊 Average English lines: {avg_en_lines:.1f}")
            except Exception:
                logger.info("   ⚠️  Could not calculate line averages")


def main():
    """Main function to run the TM repository cataloging with checkpoint system"""
    load_dotenv()
    
    github_token = os.getenv('GITHUB_TOKEN')
    if not github_token:
        logger.error("GITHUB_TOKEN not found in environment variables!")
        logger.error("Please create a .env file with your GitHub Personal Access Token")
        return
    
    try:
        # Initialize catalogger with checkpoint system
        output_path = Path("..") / "output_csv" / "tm_repos_catalog.csv"
        checkpoints_dir = Path("checkpoints")
        checkpoints_dir.mkdir(exist_ok=True)
        
        catalogger = TMRepositoryCatalogger(
            github_token=github_token,
            checkpoint_dir=str(checkpoints_dir),
            batch_size=20,  # Write CSV every 20 repositories
            output_csv=str(output_path)
        )
        
        logger.info("🚀 Starting TM repository cataloging with checkpoint system...")
        logger.info(f"📊 Batch size: {catalogger.batch_size} repositories")
        logger.info(f"📄 Output CSV: {catalogger.output_csv}")
        logger.info(f"💾 Progress file: {catalogger.progress_file}")
        
        # Remove limit for production, or set limit=50 for testing
        catalogger.catalog_all_repositories()
        
        logger.info("🎉 TM repository cataloging completed successfully!")
        
    except KeyboardInterrupt:
        logger.info("⏹️  Cataloging interrupted by user. Progress has been saved.")
        logger.info("💡 Run the script again to resume from where you left off.")
    except Exception as e:
        logger.error(f"❌ Cataloging process failed: {e}")
        logger.info("💾 Progress has been saved. You can resume by running the script again.")
        raise


if __name__ == "__main__":
    main()