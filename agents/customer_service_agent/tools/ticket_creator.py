"""Tool: ticket_creator"""

def create_ticket(title: str, description: str, priority: str = 'medium') -> dict:
    """Create a support ticket and return its ID."""
    import json, pathlib, datetime, uuid
    ticket = {
        'id': str(uuid.uuid4())[:8],
        'title': title,
        'description': description,
        'priority': priority,
        'status': 'open',
        'created_at': datetime.datetime.utcnow().isoformat()
    }
    p = pathlib.Path('tickets.jsonl')
    with p.open('a') as f:
        f.write(json.dumps(ticket) + '\n')
    return ticket

