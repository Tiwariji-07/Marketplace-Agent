import os
import re
import json
import logging
import asyncio
from typing import Dict, List, Optional, Any, Tuple, Union
from urllib.parse import urlparse
from datetime import datetime

import aiohttp
import tiktoken
from github import Github, GithubException

from utils.config import settings

logger = logging.getLogger(__name__)

class GitHubAnalyzer:
    """
    A tool for analyzing GitHub repositories.
    Provides functionality to extract repository information, analyze code structure,
    and gather metadata about the project.
    """
    
    def __init__(self, github_token: str = None):
        """Initialize the GitHub analyzer with an optional GitHub token."""
        self.github_token = github_token or settings.GITHUB_TOKEN
        self.github = Github(self.github_token) if self.github_token else Github()
        self.session = aiohttp.ClientSession()
        self.rate_limit_remaining = 5000  # Default rate limit
        self.rate_limit_reset = 0
    
    async def close(self):
        """Close the aiohttp session."""
        if not self.session.closed:
            await self.session.close()
    
    def _extract_repo_info(self, url: str) -> Tuple[str, str]:
        """Extract owner and repo name from GitHub URL."""
        # Handle various GitHub URL formats
        patterns = [
            r'github\.com/([^/]+)/([^/]+?)(?:\.git|/|$)',
            r'github\.com/([^/]+)/([^/]+?)/?$',
        ]
        
        for pattern in patterns:
            match = re.search(pattern, url)
            if match:
                return match.group(1), match.group(2)
        
        # If no match, try to parse as a direct owner/repo string
        parts = url.split('/')
        if len(parts) >= 2:
            return parts[-2], parts[-1].replace('.git', '')
        
        raise ValueError(f"Could not extract owner and repo from URL: {url}")
    
    async def analyze_repository(
        self,
        url: str,
        analyze_code: bool = True,
        include_issues: bool = False,
        include_pull_requests: bool = False,
    ) -> Dict[str, Any]:
        """
        Analyze a GitHub repository and return structured information.
        
        Args:
            url: GitHub repository URL or owner/repo string
            analyze_code: Whether to analyze the codebase (can be slow for large repos)
            include_issues: Whether to include issue analysis
            include_pull_requests: Whether to include pull request analysis
            
        Returns:
            Dict containing repository analysis
        """
        try:
            # Extract owner and repo from URL
            owner, repo_name = self._extract_repo_info(url)
            full_name = f"{owner}/{repo_name}"
            
            # Get repository object
            try:
                repo = self.github.get_repo(full_name)
            except GithubException as e:
                logger.error(f"Error accessing repository {full_name}: {e}")
                return {"error": f"Could not access repository: {str(e)}"}
            
            # Basic repository information
            result = {
                "stars": repo.stargazers_count,
                "contributors": [],
                "description": repo.description or "",
                "appname": repo_name,
                "reponame": full_name,
                "features": "",
                "usecases": "",
                "languages": {},
                "license_info": None,
                "created_at": repo.created_at.isoformat() if repo.created_at else "",
                "updated_at": repo.updated_at.isoformat() if repo.updated_at else "",
                "pushed_at": repo.pushed_at.isoformat() if repo.pushed_at else "",
                "codebase_analysis": {
                    "main_technologies": [],
                    "architecture_pattern": "",
                    "key_modules": [],
                    "primary_functionality": ""
                }
            }
            
            # Get contributors
            try:
                contributors = repo.get_contributors()
                result["contributors"] = [c.login for c in list(contributors)[:10]]  # Top 10 contributors
            except GithubException as e:
                logger.warning(f"Could not fetch contributors: {e}")
            
            # Get languages
            try:
                result["languages"] = repo.get_languages()
                # Add main technologies to codebase analysis
                if result["languages"]:
                    result["codebase_analysis"]["main_technologies"] = list(result["languages"].keys())[:5]
            except GithubException as e:
                logger.warning(f"Could not fetch languages: {e}")
            
            # Get license info
            try:
                if repo.license:
                    result["license_info"] = {
                        "key": repo.license.key,
                        "name": repo.license.name,
                        "url": repo.license.url
                    }
            except GithubException as e:
                logger.warning(f"Could not fetch license info: {e}")
            
            # Get README content
            try:
                readme = repo.get_readme()
                result["readme"] = readme.decoded_content.decode("utf-8")
                
                # Extract features and use cases from README
                features, usecases = self._extract_features_from_readme(result["readme"])
                if features:
                    result["features"] = features
                if usecases:
                    result["usecases"] = usecases
                    
            except GithubException as e:
                logger.warning(f"Could not fetch README: {e}")
            
            # Analyze codebase if requested
            if analyze_code:
                try:
                    code_analysis = await self._analyze_codebase(repo)
                    if code_analysis:
                        result["codebase_analysis"].update(code_analysis)
                        
                        # If no features from README, try to infer from code analysis
                        if not result["features"] and "primary_functionality" in result["codebase_analysis"]:
                            result["features"] = result["codebase_analysis"]["primary_functionality"]
                            
                except Exception as e:
                    logger.error(f"Error during code analysis: {e}", exc_info=True)
            
            # Get recent issues if requested
            if include_issues:
                try:
                    issues = repo.get_issues(state="open", sort="created", direction="desc")[:5]  # Last 5 open issues
                    result["recent_issues"] = [{
                        "title": issue.title,
                        "number": issue.number,
                        "state": issue.state,
                        "created_at": issue.created_at.isoformat(),
                        "user": issue.user.login if issue.user else None,
                        "comments": issue.comments
                    } for issue in issues]
                except GithubException as e:
                    logger.warning(f"Could not fetch issues: {e}")
            
            # Get recent pull requests if requested
            if include_pull_requests:
                try:
                    pulls = repo.get_pulls(state="open", sort="created", direction="desc")[:5]  # Last 5 open PRs
                    result["recent_pull_requests"] = [{
                        "title": pr.title,
                        "number": pr.number,
                        "state": pr.state,
                        "created_at": pr.created_at.isoformat(),
                        "user": pr.user.login if pr.user else None,
                        "comments": pr.comments,
                        "commits": pr.commits,
                        "additions": pr.additions,
                        "deletions": pr.deletions
                    } for pr in pulls]
                except GithubException as e:
                    logger.warning(f"Could not fetch pull requests: {e}")
            
            return result
            
        except Exception as e:
            logger.error(f"Error analyzing repository: {e}", exc_info=True)
            return {"error": f"Failed to analyze repository: {str(e)}"}
    
    def _extract_features_from_readme(self, readme_content: str) -> Tuple[str, str]:
        """Extract features and use cases from README content."""
        features = []
        usecases = []
        
        # Simple pattern matching for features and use cases
        lines = readme_content.split('\n')
        in_features_section = False
        in_usecase_section = False
        
        for line in lines:
            line_lower = line.lower()
            
            # Detect sections
            if "feature" in line_lower and ("##" in line or "# " in line):
                in_features_section = True
                in_usecase_section = False
                continue
            elif "usecase" in line_lower or "use case" in line_lower or "examples" in line_lower:
                in_features_section = False
                in_usecase_section = True
                continue
            
            # Extract bullet points or numbered lists
            if (line.strip().startswith('- ') or line.strip().startswith('* ') or 
                (line.strip() and line.strip()[0].isdigit() and '. ' in line[:5])):
                if in_features_section:
                    features.append(line.strip(' -*').strip())
                elif in_usecase_section:
                    usecases.append(line.strip(' -*').strip())
        
        return ", ".join(features[:5]), ", ".join(usecases[:3])
    
    async def _analyze_codebase(self, repo) -> Dict[str, Any]:
        """
        Analyze the codebase structure and extract key information.
        This is a simplified version that doesn't clone the repository.
        """
        try:
            # Get repository contents (only top-level files and directories)
            contents = repo.get_contents("")
            
            # Look for key files to understand the project structure
            key_files = {
                'requirements.txt': 'python',
                'package.json': 'javascript',
                'pom.xml': 'java',
                'build.gradle': 'java',
                'Dockerfile': 'docker',
                'docker-compose.yml': 'docker',
                'Makefile': 'build',
                'CMakeLists.txt': 'c++',
                'setup.py': 'python',
                'pyproject.toml': 'python',
                'go.mod': 'go',
                'Cargo.toml': 'rust',
                'Gemfile': 'ruby',
                'composer.json': 'php',
            }
            
            # Check for framework-specific files
            framework_hints = {
                'django': ['manage.py', 'wsgi.py'],
                'flask': ['app.py', 'application.py', 'wsgi.py'],
                'react': ['src/App.js', 'src/index.js'],
                'angular': ['angular.json', 'src/app'],
                'vue': ['vue.config.js', 'src/main.js'],
                'next': ['next.config.js', 'pages/'],
                'nuxt': ['nuxt.config.js', 'pages/'],
                'laravel': ['artisan', 'app/Http/Controllers'],
                'rails': ['Gemfile.lock', 'app/controllers'],
                'spring': ['src/main/java', 'src/main/resources'],
            }
            
            # Analyze files and directories
            detected_frameworks = set()
            has_src = False
            has_tests = False
            has_docs = False
            
            for item in contents:
                if item.type == "dir":
                    if item.name.lower() == 'src':
                        has_src = True
                    elif item.name.lower() in ['test', 'tests']:
                        has_tests = True
                    elif item.name.lower() in ['doc', 'docs']:
                        has_docs = True
                else:
                    # Check for framework-specific files
                    for framework, files in framework_hints.items():
                        for f in files:
                            if f.lower() in item.path.lower():
                                detected_frameworks.add(framework)
            
            # Determine architecture pattern based on files and structure
            architecture = "Monolithic"  # Default
            if len(detected_frameworks) > 1:
                architecture = "Microservices"
            elif has_src and has_tests and has_docs:
                architecture = "Structured Monolithic"
            
            # Get primary language from repository
            primary_language = repo.language or "Unknown"
            
            return {
                "architecture_pattern": architecture,
                "detected_frameworks": list(detected_frameworks),
                "primary_language": primary_language,
                "has_tests": has_tests,
                "has_documentation": has_docs,
                "primary_functionality": self._infer_primary_functionality(repo, primary_language, detected_frameworks)
            }
            
        except Exception as e:
            logger.error(f"Error analyzing codebase: {e}", exc_info=True)
            return {"error": f"Code analysis failed: {str(e)}"}
    
    def _infer_primary_functionality(self, repo, primary_language: str, frameworks: set) -> str:
        """Infer the primary functionality of the repository."""
        # This is a simplified inference based on repository metadata
        description = (repo.description or "").lower()
        
        # Common patterns in repository descriptions
        if any(term in description for term in ["web app", "web application", "website"]):
            return "Web Application"
        elif any(term in description for term in ["api", "rest", "graphql"]):
            return "API Service"
        elif any(term in description for term in ["cli", "command line"]):
            return "Command Line Tool"
        elif any(term in description for term in ["library", "framework"]):
            return f"{primary_language} Library"
        
        # Infer based on frameworks
        if frameworks:
            if "django" in frameworks or "flask" in frameworks:
                return "Web Application"
            elif "react" in frameworks or "angular" in frameworks or "vue" in frameworks:
                return "Frontend Application"
            elif "spring" in frameworks:
                return "Enterprise Java Application"
        
        # Fallback based on primary language
        lang_to_functionality = {
            "python": "Python Application",
            "javascript": "JavaScript Application",
            "typescript": "TypeScript Application",
            "java": "Java Application",
            "go": "Go Application",
            "rust": "Rust Application",
            "ruby": "Ruby Application",
            "php": "PHP Application",
            "c#": "C# Application",
            "c++": "C++ Application",
        }
        
        return lang_to_functionality.get(primary_lower, "Software Application")
