"""Tool: http_request"""

def http_request(method: str, url: str, headers: dict = None,
                 json_body: dict = None) -> dict:
    """Make an HTTP request and return the JSON response body."""
    import httpx
    resp = httpx.request(method.upper(), url, headers=headers or {}, json=json_body)
    return {'status': resp.status_code, 'body': resp.json() if resp.content else {}}

