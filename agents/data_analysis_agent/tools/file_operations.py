"""Tool: file_operations"""

def read_file(path: str) -> str:
    """Read a text file and return its contents."""
    from pathlib import Path
    return Path(path).read_text()

def write_file(path: str, content: str) -> dict:
    """Write content to a file, creating parent dirs as needed."""
    from pathlib import Path
    p = Path(path)
    p.parent.mkdir(parents=True, exist_ok=True)
    p.write_text(content)
    return {'written': str(p), 'bytes': len(content)}

