#!/usr/bin/env python3
"""Simple web fetch tool for making HTTP requests."""

import os
import json
import requests
from typing import Dict, Any, Optional, Union
from urllib.parse import urlparse


class WebFetch:
    """Simple HTTP client for making web requests."""
    
    def __init__(self):
        self.session = requests.Session()
        self.session.headers.update({
            'User-Agent': 'EspressoBot/1.0 (Web Fetch Tool)'
        })
    
    def fetch_url(
        self, 
        url: str, 
        method: str = "GET",
        headers: Optional[Dict[str, str]] = None,
        data: Optional[Union[str, Dict[str, Any]]] = None,
        timeout: int = 30
    ) -> Dict[str, Any]:
        """
        Fetch content from a URL.
        
        Args:
            url: The URL to fetch
            method: HTTP method (GET, POST, PUT, DELETE, etc.)
            headers: Additional headers to send
            data: Request body (string or dict for JSON)
            timeout: Request timeout in seconds
            
        Returns:
            Dictionary with response data:
            {
                'status_code': int,
                'headers': dict,
                'content': str,
                'json': dict | None,
                'error': str | None
            }
        """
        try:
            # Validate URL
            parsed = urlparse(url)
            if not parsed.scheme or not parsed.netloc:
                return {
                    'status_code': 0,
                    'headers': {},
                    'content': '',
                    'json': None,
                    'error': f'Invalid URL: {url}'
                }
            
            # Prepare request
            request_headers = {}
            if headers:
                request_headers.update(headers)
            
            request_data = None
            if data:
                if isinstance(data, dict):
                    request_headers['Content-Type'] = 'application/json'
                    request_data = json.dumps(data)
                else:
                    request_data = data
            
            # Make request
            response = self.session.request(
                method=method.upper(),
                url=url,
                headers=request_headers,
                data=request_data,
                timeout=timeout
            )
            
            # Try to parse JSON
            json_data = None
            try:
                json_data = response.json()
            except:
                pass  # Not JSON content
            
            return {
                'status_code': response.status_code,
                'headers': dict(response.headers),
                'content': response.text,
                'json': json_data,
                'error': None
            }
            
        except requests.exceptions.Timeout:
            return {
                'status_code': 0,
                'headers': {},
                'content': '',
                'json': None,
                'error': f'Request timeout after {timeout} seconds'
            }
        except requests.exceptions.RequestException as e:
            return {
                'status_code': 0,
                'headers': {},
                'content': '',
                'json': None,
                'error': f'Request failed: {str(e)}'
            }
    
    def get(self, url: str, headers: Optional[Dict[str, str]] = None) -> Dict[str, Any]:
        """Make a GET request."""
        return self.fetch_url(url, method="GET", headers=headers)
    
    def post(self, url: str, data: Optional[Union[str, Dict[str, Any]]] = None, headers: Optional[Dict[str, str]] = None) -> Dict[str, Any]:
        """Make a POST request."""
        return self.fetch_url(url, method="POST", data=data, headers=headers)


# Global instance
_web_fetch = WebFetch()


def fetch_url(url: str, method: str = "GET", **kwargs) -> Dict[str, Any]:
    """Convenience function for fetching URLs."""
    return _web_fetch.fetch_url(url, method, **kwargs)


def get(url: str, **kwargs) -> Dict[str, Any]:
    """Convenience function for GET requests."""
    return _web_fetch.get(url, **kwargs)


def post(url: str, **kwargs) -> Dict[str, Any]:
    """Convenience function for POST requests."""
    return _web_fetch.post(url, **kwargs)


if __name__ == '__main__':
    # Test the tool
    print("Testing WebFetch tool...")
    
    # Test GET request
    result = get("https://httpbin.org/get")
    print("GET request result:")
    print(f"Status: {result['status_code']}")
    print(f"Content type: {result['headers'].get('content-type', 'unknown')}")
    print(f"JSON available: {result['json'] is not None}")
    
    # Test POST request
    result = post("https://httpbin.org/post", data={"test": "data"})
    print("\nPOST request result:")
    print(f"Status: {result['status_code']}")
    print(f"JSON available: {result['json'] is not None}")
