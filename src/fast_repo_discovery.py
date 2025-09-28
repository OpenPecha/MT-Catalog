"""
Fast Repository Discovery Script

Uses multiple targeted search queries to efficiently find TM repositories
without processing all 27,000+ repositories in the organization.

Features:
- Smart pattern-based searches (75 patterns)
- Automatic deduplication
- Comprehensive coverage (numeric, alphabetic, special chars)
- Fast execution.

Author: Dharmadutta Dhakar
Date: 2025-09-25
"""

import os
import json
import logging
from datetime import datetime
from pathlib import Path
from typing import Dict, List, Set

from github import Github, GithubException
from dotenv import load_dotenv

# Configure logging
logs_dir = Path("logs")
logs_dir.mkdir(exist_ok=True)

logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(levelname)s - %(message)s',
    handlers=[
        logging.FileHandler(logs_dir / 'fast_repo_discovery.log'),
        logging.StreamHandler()
    ]
)

logger = logging.getLogger(__name__)


class FastRepositoryDiscovery:
    """Fast discovery using multiple targeted search queries"""
    
    def __init__(self, github_token: str, org_name: str = "MonlamAI"):
        self.github = Github(github_token)
        self.org_name = org_name
        
        # Repository caching system
        self.cache_dir = Path("cache")
        self.cache_dir.mkdir(exist_ok=True)
        self.repo_cache_file = self.cache_dir / "repository_cache.json"
        
        self._authenticate()
    
    def _authenticate(self) -> None:
        """Authenticate with GitHub"""
        try:
            user = self.github.get_user()
            logger.info(f"✅ Authenticated as: {user.login}")
        except GithubException as e:
            logger.error(f"❌ Authentication failed: {e}")
            raise
    
    def _save_repository_cache(self, tm_repos: List) -> None:
        """Save TM repository list to cache"""
        try:
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
            
            logger.info(f"💾 Successfully cached {len(tm_repos_data)} TM repositories")
            
        except Exception as e:
            logger.error(f"Failed to save repository cache: {e}")
    
    def discover_tm_repositories_fast(self) -> List:
        """
        Fast discovery using multiple targeted search queries
        """
        logger.info("🚀 Starting FAST TM repository discovery...")
        logger.info("💡 Using multiple targeted search queries instead of processing all repos")
        
        all_tm_repos = []
        seen_repo_ids = set()  # Avoid duplicates
        
        # Get all search patterns
        search_patterns = self._get_search_patterns()
        
        # Execute all searches
        self._execute_searches(search_patterns, all_tm_repos, seen_repo_ids)
        
        # Execute final broad search
        self._execute_final_search(all_tm_repos, seen_repo_ids)
        
        # Log completion summary
        self._log_completion_summary(all_tm_repos)
        
        # Save to cache
        self._save_repository_cache(all_tm_repos)
        
        return all_tm_repos
    
    def _get_search_patterns(self) -> List[str]:
        """
        Get all search patterns for TM repositories
        
        Returns:
            List of search patterns to use
        """
        # Primary specific patterns
        specific_patterns = [
            "TMtoh",      # TMtoh1, TMtoh2, etc.
            "TMICD",      # TMICD6_LH, TMICD1, etc.
            "TMKGY",      # TMKGY patterns
            "TMKAN",      # TMKAN patterns  
            "TMGYU",      # TMGYU patterns
            "TMDEN",      # TMDEN patterns
            "TMTSA",      # TMTSA patterns
            "TMNAR",      # TMNAR patterns
            "TMDUD",      # TMDUD patterns
            "TMSHAD",     # TMSHAD patterns
        ]
        
        # Numeric patterns
        numeric_patterns = [f"TM{i}" for i in range(10)]  # TM0-TM9
        
        # Special character patterns
        special_patterns = ["TM_", "TM-"]
        
        # Alphabetic patterns (lowercase + uppercase)
        alpha_patterns = []
        for char in "abcdefghijklmnopqrstuvwxyz":
            alpha_patterns.append(f"TM{char}")
            alpha_patterns.append(f"TM{char.upper()}")
        
        # Combine all patterns
        all_patterns = specific_patterns + numeric_patterns + special_patterns + alpha_patterns
        
        logger.info(f"📋 Generated {len(all_patterns)} search patterns")
        return all_patterns
    
    def _execute_searches(self, patterns: List[str], all_repos: List, seen_ids: set) -> None:
        """
        Execute searches for all patterns
        
        Args:
            patterns: List of search patterns
            all_repos: List to append found repositories
            seen_ids: Set of already seen repository IDs
        """
        import time
        
        for i, pattern in enumerate(patterns, 1):
            try:
                logger.info(f"🔍 Search {i}/{len(patterns)}: Looking for '{pattern}*' repositories...")
                
                # Skip TMt to avoid duplicating TMtoh results
                if pattern == "TMt":
                    continue
                
                search_query = f"org:{self.org_name} {pattern} in:name"
                search_results = self.github.search_repositories(query=search_query)
                
                pattern_count = 0
                for repo in search_results:
                    if repo.name.startswith("TM") and repo.id not in seen_ids:
                        all_repos.append(repo)
                        seen_ids.add(repo.id)
                        pattern_count += 1
                
                if pattern_count > 0:
                    logger.info(f"✅ Found {pattern_count} new TM repos with pattern '{pattern}*' (Total: {len(all_repos)})")
                
                # Rate limiting
                time.sleep(0.3)
                
            except GithubException as e:
                logger.warning(f"Search for pattern '{pattern}' failed: {e}")
                continue
    
    def _execute_final_search(self, all_repos: List, seen_ids: set) -> None:
        """
        Execute final broad search for any remaining repositories
        
        Args:
            all_repos: List to append found repositories
            seen_ids: Set of already seen repository IDs
        """
        try:
            logger.info("🔍 Final broad search for any remaining TM repositories...")
            search_query = f"org:{self.org_name} TM in:name"
            search_results = self.github.search_repositories(query=search_query)
            
            additional_count = 0
            for repo in search_results:
                if repo.name.startswith("TM") and repo.id not in seen_ids:
                    all_repos.append(repo)
                    seen_ids.add(repo.id)
                    additional_count += 1
            
            if additional_count > 0:
                logger.info(f"✅ Found {additional_count} additional TM repos in final broad search")
            
        except GithubException as e:
            logger.warning(f"Final broad search failed: {e}")
    
    def _log_completion_summary(self, all_repos: List) -> None:
        """
        Log completion summary with statistics
        
        Args:
            all_repos: List of discovered repositories
        """
        logger.info("=" * 60)
        logger.info("📊 FAST REPOSITORY DISCOVERY COMPLETE")
        logger.info("=" * 60)
        logger.info(f"🔍 Total TM repositories discovered: {len(all_repos)}")
        logger.info(f"⚡ Discovery method: Multiple targeted searches")
        logger.info(f"📅 Discovery completed at: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
        logger.info("=" * 60)


def main():
    """Main function"""
    load_dotenv()
    
    github_token = os.getenv('GITHUB_TOKEN')
    if not github_token:
        logger.error("❌ GITHUB_TOKEN not found in environment variables!")
        return
    
    try:
        discovery = FastRepositoryDiscovery(github_token=github_token)
        tm_repos = discovery.discover_tm_repositories_fast()
        
        logger.info("🎉 Fast repository discovery completed successfully!")
        logger.info(f"💡 Found {len(tm_repos)} TM repositories")
        logger.info("💡 You can now run the main TM_retriever.py for processing")
        
    except KeyboardInterrupt:
        logger.info("⏹️  Discovery interrupted by user.")
    except Exception as e:
        logger.error(f"❌ Discovery process failed: {e}")
        raise


if __name__ == "__main__":
    main()
