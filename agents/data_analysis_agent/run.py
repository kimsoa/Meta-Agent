"""
Auto-generated agent server for: data_analysis_agent
Domain: data_analysis | Type: conversational

Run:  uvicorn run:app --port 8100
"""
import importlib, json, os
from pathlib import Path
from typing import List
import httpx
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel

SYSTEM_PROMPT = Path(__file__).parent.joinpath('system_prompt.txt').read_text()
OLLAMA_URL    = os.getenv('OLLAMA_URL', 'http://localhost:11434')
MODEL         = os.getenv('MODEL', 'gemma3:latest')
AGENT_ID      = 'data_analysis_agent'

app = FastAPI(title=f'Agent: data_analysis_agent')
app.add_middleware(CORSMiddleware, allow_origins=['*'],
                   allow_methods=['*'], allow_headers=['*'])

class Message(BaseModel):
    role: str
    content: str

class ChatRequest(BaseModel):
    messages: List[Message]
    model: str = MODEL

@app.get('/health')
def health():
    return {'agent_id': AGENT_ID, 'status': 'ok'}

@app.post('/chat')
async def chat(req: ChatRequest):
    payload = {
        'model': req.model,
        'stream': False,
        'messages': [{'role': 'system', 'content': SYSTEM_PROMPT}]
                    + [{'role': m.role, 'content': m.content} for m in req.messages],
    }
    async with httpx.AsyncClient(timeout=None) as client:
        r = await client.post(f'{OLLAMA_URL}/api/chat', json=payload)
        r.raise_for_status()
        return r.json()
