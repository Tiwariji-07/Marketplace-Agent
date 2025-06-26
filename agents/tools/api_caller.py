import json
import logging
import re
import aiohttp
from typing import Dict, Any, Optional, Union, List, Tuple
from urllib.parse import urlparse, urlencode, parse_qs, urlunparse, parse_qsl
from enum import Enum
import ssl

from utils.config import settings

logger = logging.getLogger(__name__)

class HTTPMethod(str, Enum):
    """Supported HTTP methods for API calls."""
    GET = "GET"
    POST = "POST"
    PUT = "PUT"
    DELETE = "DELETE"
    PATCH = "PATCH"
    HEAD = "HEAD"
    OPTIONS = "OPTIONS"

class APICaller:
    """
    A tool for making HTTP API calls with support for various authentication methods,
    request types, and response handling.
    """
    
    def __init__(self, session: Optional[aiohttp.ClientSession] = None):
        """Initialize the API caller with an optional aiohttp session."""
        self.session = session or aiohttp.ClientSession()
        self.default_headers = {
            "User-Agent": f"MultiAgent-APICaller/1.0",
            "Accept": "application/json",
            "Content-Type": "application/json"
        }
        self.ssl_context = ssl.create_default_context()
        self.ssl_context.check_hostname = False
        self.ssl_context.verify_mode = ssl.CERT_NONE
    
    async def close(self):
        """Close the aiohttp session."""
        if not self.session.closed:
            await self.session.close()
    
    async def call(
        self,
        url: str,
        method: Union[str, HTTPMethod] = HTTPMethod.GET,
        headers: Optional[Dict[str, str]] = None,
        params: Optional[Dict[str, Any]] = None,
        data: Optional[Union[Dict[str, Any], str, bytes]] = None,
        json_data: Optional[Any] = None,
        auth: Optional[Dict[str, str]] = None,
        timeout: int = 30,
        allow_redirects: bool = True,
        verify_ssl: bool = True,
    ) -> Dict[str, Any]:
        """
        Make an HTTP request to the specified URL.
        
        Args:
            url: The URL to make the request to
            method: HTTP method (GET, POST, PUT, DELETE, etc.)
            headers: Request headers
            params: Query parameters
            data: Form data or raw request body
            json_data: JSON-serializable data (alternative to data)
            auth: Authentication credentials (supports 'basic', 'bearer', 'api_key')
            timeout: Request timeout in seconds
            allow_redirects: Whether to follow redirects
            verify_ssl: Whether to verify SSL certificates
            
        Returns:
            Dict containing the response data and metadata
        """
        try:
            # Normalize method
            method = HTTPMethod(method.upper()) if isinstance(method, str) else method
            
            # Prepare headers
            request_headers = self.default_headers.copy()
            if headers:
                request_headers.update(headers)
            
            # Handle authentication
            if auth:
                request_headers.update(self._prepare_auth_headers(auth))
            
            # Prepare SSL context
            ssl_context = None if verify_ssl else self.ssl_context
            
            # Make the request
            request_kwargs = {
                "headers": request_headers,
                "params": params,
                "timeout": aiohttp.ClientTimeout(total=timeout),
                "allow_redirects": allow_redirects,
                "ssl": ssl_context,
            }
            
            # Add request body based on content type
            if data is not None:
                if isinstance(data, (dict, list)) and 'application/json' in request_headers.get('Content-Type', ''):
                    request_kwargs["json"] = data
                else:
                    request_kwargs["data"] = data
            elif json_data is not None:
                request_kwargs["json"] = json_data
            
            # Log the request
            logger.info(f"Making {method} request to {url}")
            
            # Make the actual request
            async with self.session.request(method.value, url, **request_kwargs) as response:
                # Read response content
                content_type = response.headers.get('Content-Type', '').lower()
                is_json = 'application/json' in content_type
                
                response_data = {
                    "status": response.status,
                    "headers": dict(response.headers),
                    "url": str(response.url),
                    "content_type": content_type,
                    "is_success": 200 <= response.status < 300,
                }
                
                # Handle different content types
                if is_json:
                    try:
                        response_data["data"] = await response.json()
                    except Exception as e:
                        logger.warning(f"Failed to parse JSON response: {e}")
                        response_data["data"] = await response.text()
                else:
                    response_data["data"] = await response.text()
                
                return response_data
                
        except aiohttp.ClientError as e:
            logger.error(f"API request failed: {str(e)}", exc_info=True)
            return {
                "error": f"API request failed: {str(e)}",
                "status": 0,
                "is_success": False
            }
        except Exception as e:
            logger.error(f"Unexpected error during API request: {str(e)}", exc_info=True)
            return {
                "error": f"Unexpected error: {str(e)}",
                "status": 0,
                "is_success": False
            }
    
    def _prepare_auth_headers(self, auth_config: Dict[str, Any]) -> Dict[str, str]:
        """
        Prepare authentication headers based on the provided configuration.
        
        Args:
            auth_config: Authentication configuration
                - For 'basic': {'type': 'basic', 'username': 'user', 'password': 'pass'}
                - For 'bearer': {'type': 'bearer', 'token': 'token'}
                - For 'api_key': {'type': 'api_key', 'key': 'X-API-Key', 'value': 'key'}
                - For 'oauth2': {'type': 'oauth2', 'token': 'token'}
                
        Returns:
            Dictionary of headers to include in the request
        """
        auth_type = auth_config.get('type', '').lower()
        headers = {}
        
        if auth_type == 'basic' and 'username' in auth_config and 'password' in auth_config:
            import base64
            credentials = f"{auth_config['username']}:{auth_config['password']}"
            encoded_credentials = base64.b64encode(credentials.encode('utf-8')).decode('utf-8')
            headers['Authorization'] = f"Basic {encoded_credentials}"
            
        elif auth_type == 'bearer' and 'token' in auth_config:
            headers['Authorization'] = f"Bearer {auth_config['token']}"
            
        elif auth_type == 'api_key' and 'key' in auth_config and 'value' in auth_config:
            headers[auth_config['key']] = auth_config['value']
            
        elif auth_type == 'oauth2' and 'token' in auth_config:
            headers['Authorization'] = f"Bearer {auth_config['token']}"
        
        return headers
    
    async def call_from_natural_language(
        self,
        request: str,
        context: Optional[Dict[str, Any]] = None
    ) -> Dict[str, Any]:
        """
        Make an API call based on a natural language request.
        
        Example requests:
        - "GET https://api.example.com/users"
        - "POST to https://api.example.com/users with name=John&age=30"
        - "Call the API at example.com with my API key 12345"
        
        Args:
            request: Natural language API request
            context: Optional context from previous interactions
            
        Returns:
            Dict containing the response data and metadata
        """
        try:
            # Parse the natural language request
            parsed = self._parse_natural_language_request(request, context or {})
            
            # Make the API call
            return await self.call(
                url=parsed['url'],
                method=parsed.get('method', 'GET'),
                headers=parsed.get('headers'),
                params=parsed.get('params'),
                data=parsed.get('data'),
                json_data=parsed.get('json'),
                auth=parsed.get('auth'),
                timeout=parsed.get('timeout', 30),
                verify_ssl=parsed.get('verify_ssl', True)
            )
            
        except Exception as e:
            logger.error(f"Failed to process natural language request: {str(e)}", exc_info=True)
            return {
                "error": f"Failed to process request: {str(e)}",
                "is_success": False
            }
    
    def _parse_natural_language_request(
        self,
        request: str,
        context: Dict[str, Any]
    ) -> Dict[str, Any]:
        """
        Parse a natural language API request into its components.
        
        This is a simplified implementation that can be enhanced with NLP.
        
        Args:
            request: Natural language API request
            context: Context from previous interactions
            
        Returns:
            Dictionary containing the parsed request components
        """
        # Default values
        result = {
            'method': 'GET',
            'url': '',
            'headers': {},
            'params': {},
            'data': None,
            'auth': None,
            'timeout': 30,
            'verify_ssl': True
        }
        
        # Extract HTTP method
        method_match = re.search(r'^(GET|POST|PUT|DELETE|PATCH|HEAD|OPTIONS)\s+', request, re.IGNORECASE)
        if method_match:
            result['method'] = method_match.group(1).upper()
            request = request[method_match.end():].strip()
        
        # Extract URL
        url_match = re.search(r'(https?://[^\s\?&#]+|www\.[^\s\?&#]+)', request, re.IGNORECASE)
        if not url_match:
            raise ValueError("Could not find a valid URL in the request")
        
        result['url'] = url_match.group(1)
        if not result['url'].startswith(('http://', 'https://')):
            result['url'] = 'https://' + result['url']
        
        # Extract query parameters
        if '?' in result['url']:
            url_parts = result['url'].split('?', 1)
            result['url'] = url_parts[0]
            query_string = url_parts[1].split('#', 1)[0]  # Remove fragment
            result['params'] = dict(parse_qsl(query_string))
        
        # Extract headers, auth, and body from the remaining text
        remaining_text = request[url_match.end():].strip()
        
        # Look for API key in the text
        api_key_match = re.search(r'(?:api[_-]?key|token)[\s:]+([\w-]+)', remaining_text, re.IGNORECASE)
        if api_key_match:
            result['auth'] = {
                'type': 'api_key',
                'key': 'Authorization',
                'value': f"Bearer {api_key_match.group(1)}"
            }
        
        # Look for basic auth
        auth_match = re.search(r'user(?:name)?[\s:]+([^\s,;]+)[\s,;]+pass(?:word)?[\s:]+([^\s,;]+)', remaining_text, re.IGNORECASE)
        if auth_match:
            result['auth'] = {
                'type': 'basic',
                'username': auth_match.group(1),
                'password': auth_match.group(2)
            }
        
        # Look for JSON body
        json_match = re.search(r'\{.*\}', remaining_text, re.DOTALL)
        if json_match:
            try:
                result['json'] = json.loads(json_match.group(0))
            except json.JSONDecodeError:
                pass
        
        # Look for form data
        form_match = re.findall(r'(\w+)=([^\s,;]+)', remaining_text)
        if form_match and 'json' not in result:
            result['data'] = {k: v for k, v in form_match}
        
        return result

    def __del__(self):
        """Ensure the session is closed when the object is destroyed."""
        if hasattr(self, 'session') and self.session and not self.session.closed:
            asyncio.create_task(self.close())

# Example usage
async def example():
    async with aiohttp.ClientSession() as session:
        caller = APICaller(session)
        
        # Example 1: Simple GET request
        response = await caller.call(
            "https://api.github.com/repos/octocat/hello-world",
            method="GET"
        )
        print(json.dumps(response, indent=2))
        
        # Example 2: Using natural language
        response = await caller.call_from_natural_language(
            "GET https://api.github.com/repos/octocat/hello-world"
        )
        print(json.dumps(response, indent=2))

if __name__ == "__main__":
    import asyncio
    asyncio.run(example())
