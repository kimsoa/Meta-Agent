"""Tool: web_search"""

def web_search(query: str, max_results: int = 5) -> list:
    """Search the web and return a list of result snippets."""
    from duckduckgo_search import DDGS
    with DDGS() as ddgs:
        return [r for r in ddgs.text(query, max_results=max_results)]

