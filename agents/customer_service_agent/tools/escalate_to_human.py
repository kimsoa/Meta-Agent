"""Tool: escalate_to_human"""

def escalate(reason: str, conversation_id: str = '') -> dict:
    """Mark a conversation as needing human review."""
    import json, pathlib, datetime
    record = {
        'conversation_id': conversation_id,
        'reason': reason,
        'timestamp': datetime.datetime.utcnow().isoformat()
    }
    p = pathlib.Path('escalations.jsonl')
    with p.open('a') as f:
        f.write(json.dumps(record) + '\n')
    return record

