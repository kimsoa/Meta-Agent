"""
Tool Registry — predefined tools + code generator for custom tools.

Each tool entry has:
  - id           : unique slug
  - name         : display name
  - description  : what it does
  - ecosystem    : None | "google" | "microsoft" | "custom"
  - requires_auth: bool — show "Connect" button in UI
  - connected    : runtime flag (session-level); persisted via /api/tools/connect
  - code         : Python function body used when scaffolding an agent
  - dependencies : pip packages the code needs
"""

from typing import Dict, List, Any
import textwrap

# ---------------------------------------------------------------------------
# Predefined tool catalogue
# ---------------------------------------------------------------------------

PREDEFINED_TOOLS: Dict[str, Dict[str, Any]] = {

    # ── Google ecosystem ────────────────────────────────────────────────────
    "gmail": {
        "name": "Gmail",
        "description": "Send and read emails via Gmail API",
        "ecosystem": "google",
        "requires_auth": True,
        "category": "communication",
        "dependencies": ["google-auth", "google-api-python-client"],
        "code": textwrap.dedent("""\
            def send_email(to: str, subject: str, body: str) -> dict:
                \"\"\"Send an email using Gmail API.\"\"\"
                from googleapiclient.discovery import build
                import base64, email.mime.text as mt
                service = build('gmail', 'v1')
                msg = mt.MIMEText(body)
                msg['to'], msg['subject'] = to, subject
                raw = base64.urlsafe_b64encode(msg.as_bytes()).decode()
                return service.users().messages().send(
                    userId='me', body={'raw': raw}).execute()
        """),
    },
    "google_calendar": {
        "name": "Google Calendar",
        "description": "Create, read, and update Google Calendar events",
        "ecosystem": "google",
        "requires_auth": True,
        "category": "productivity",
        "dependencies": ["google-auth", "google-api-python-client"],
        "code": textwrap.dedent("""\
            def create_event(summary: str, start: str, end: str, calendar_id: str = 'primary') -> dict:
                \"\"\"Create a Google Calendar event. Dates in ISO 8601 format.\"\"\"
                from googleapiclient.discovery import build
                service = build('calendar', 'v3')
                event = {
                    'summary': summary,
                    'start': {'dateTime': start, 'timeZone': 'UTC'},
                    'end': {'dateTime': end, 'timeZone': 'UTC'},
                }
                return service.events().insert(calendarId=calendar_id, body=event).execute()
        """),
    },
    "google_drive": {
        "name": "Google Drive",
        "description": "Read, upload, and manage files in Google Drive",
        "ecosystem": "google",
        "requires_auth": True,
        "category": "storage",
        "dependencies": ["google-auth", "google-api-python-client"],
        "code": textwrap.dedent("""\
            def list_files(query: str = '', max_results: int = 10) -> list:
                \"\"\"List files in Google Drive matching an optional query.\"\"\"
                from googleapiclient.discovery import build
                service = build('drive', 'v3')
                results = service.files().list(
                    q=query, pageSize=max_results, fields='files(id, name, mimeType)').execute()
                return results.get('files', [])
        """),
    },

    # ── Microsoft ecosystem ─────────────────────────────────────────────────
    "outlook_email": {
        "name": "Outlook / Microsoft 365 Mail",
        "description": "Send and read emails via Microsoft Graph API",
        "ecosystem": "microsoft",
        "requires_auth": True,
        "category": "communication",
        "dependencies": ["msal", "requests"],
        "code": textwrap.dedent("""\
            def send_email(to: str, subject: str, body: str, access_token: str) -> dict:
                \"\"\"Send an email via Microsoft Graph.\"\"\"
                import requests
                url = 'https://graph.microsoft.com/v1.0/me/sendMail'
                payload = {'message': {
                    'subject': subject,
                    'body': {'contentType': 'Text', 'content': body},
                    'toRecipients': [{'emailAddress': {'address': to}}]
                }}
                r = requests.post(url, json=payload, headers={'Authorization': f'Bearer {access_token}'})
                return {'status': r.status_code}
        """),
    },
    "teams": {
        "name": "Microsoft Teams",
        "description": "Post messages and notifications to Teams channels",
        "ecosystem": "microsoft",
        "requires_auth": True,
        "category": "communication",
        "dependencies": ["msal", "requests"],
        "code": textwrap.dedent("""\
            def post_message(channel_id: str, message: str, access_token: str) -> dict:
                \"\"\"Post a message to a Microsoft Teams channel.\"\"\"
                import requests
                url = f'https://graph.microsoft.com/v1.0/teams/{channel_id}/channels'
                # Simplified — requires full channel/team IDs
                r = requests.post(url, json={'body': {'content': message}},
                                  headers={'Authorization': f'Bearer {access_token}'})
                return {'status': r.status_code}
        """),
    },
    "sharepoint": {
        "name": "SharePoint",
        "description": "Read and write documents on SharePoint sites",
        "ecosystem": "microsoft",
        "requires_auth": True,
        "category": "storage",
        "dependencies": ["msal", "requests"],
        "code": textwrap.dedent("""\
            def get_document(site_id: str, item_id: str, access_token: str) -> bytes:
                \"\"\"Download a document from SharePoint.\"\"\"
                import requests
                url = f'https://graph.microsoft.com/v1.0/sites/{site_id}/drive/items/{item_id}/content'
                r = requests.get(url, headers={'Authorization': f'Bearer {access_token}'})
                return r.content
        """),
    },

    # ── Standalone / custom-integrated tools ────────────────────────────────
    "web_search": {
        "name": "Web Search",
        "description": "Search the web using DuckDuckGo (no API key required)",
        "ecosystem": None,
        "requires_auth": False,
        "category": "information",
        "dependencies": ["duckduckgo-search"],
        "code": textwrap.dedent("""\
            def web_search(query: str, max_results: int = 5) -> list:
                \"\"\"Search the web and return a list of result snippets.\"\"\"
                from duckduckgo_search import DDGS
                with DDGS() as ddgs:
                    return [r for r in ddgs.text(query, max_results=max_results)]
        """),
    },
    "database_query": {
        "name": "Database Query (SQLite)",
        "description": "Run read-only SQL queries against a local SQLite database",
        "ecosystem": None,
        "requires_auth": False,
        "category": "data",
        "dependencies": [],
        "code": textwrap.dedent("""\
            def query_db(db_path: str, sql: str, params: tuple = ()) -> list:
                \"\"\"Execute a read-only SQL query on a SQLite database.\"\"\"
                import sqlite3
                conn = sqlite3.connect(db_path)
                conn.row_factory = sqlite3.Row
                rows = conn.execute(sql, params).fetchall()
                conn.close()
                return [dict(r) for r in rows]
        """),
    },
    "http_request": {
        "name": "HTTP / REST API",
        "description": "Make authenticated HTTP requests to any REST API",
        "ecosystem": None,
        "requires_auth": False,
        "category": "integration",
        "dependencies": ["httpx"],
        "code": textwrap.dedent("""\
            def http_request(method: str, url: str, headers: dict = None,
                             json_body: dict = None) -> dict:
                \"\"\"Make an HTTP request and return the JSON response body.\"\"\"
                import httpx
                resp = httpx.request(method.upper(), url, headers=headers or {}, json=json_body)
                return {'status': resp.status_code, 'body': resp.json() if resp.content else {}}
        """),
    },
    "file_operations": {
        "name": "File Operations",
        "description": "Read, write, list, and delete local files",
        "ecosystem": None,
        "requires_auth": False,
        "category": "storage",
        "dependencies": [],
        "code": textwrap.dedent("""\
            def read_file(path: str) -> str:
                \"\"\"Read a text file and return its contents.\"\"\"
                from pathlib import Path
                return Path(path).read_text()

            def write_file(path: str, content: str) -> dict:
                \"\"\"Write content to a file, creating parent dirs as needed.\"\"\"
                from pathlib import Path
                p = Path(path)
                p.parent.mkdir(parents=True, exist_ok=True)
                p.write_text(content)
                return {'written': str(p), 'bytes': len(content)}
        """),
    },
    "escalate_to_human": {
        "name": "Human Escalation",
        "description": "Flag a conversation for human review / handoff",
        "ecosystem": None,
        "requires_auth": False,
        "category": "workflow",
        "dependencies": [],
        "code": textwrap.dedent("""\
            def escalate(reason: str, conversation_id: str = '') -> dict:
                \"\"\"Mark a conversation as needing human review.\"\"\"
                import json, pathlib, datetime
                record = {
                    'conversation_id': conversation_id,
                    'reason': reason,
                    'timestamp': datetime.datetime.utcnow().isoformat()
                }
                p = pathlib.Path('escalations.jsonl')
                with p.open('a') as f:
                    f.write(json.dumps(record) + '\\n')
                return record
        """),
    },
}


# ---------------------------------------------------------------------------
# Dynamically-generated tool templates (created fresh by the LLM analysis)
# ---------------------------------------------------------------------------

GENERATED_TOOL_TEMPLATES: Dict[str, Dict[str, Any]] = {
    "linter": {
        "name": "Code Linter",
        "description": "Run flake8/ruff to lint Python code and return violations",
        "ecosystem": None,
        "requires_auth": False,
        "category": "code_quality",
        "dependencies": ["ruff"],
        "code": textwrap.dedent("""\
            def lint_code(code: str, filename: str = 'snippet.py') -> dict:
                \"\"\"Lint Python code using ruff and return a list of violations.\"\"\"
                import subprocess, tempfile, pathlib
                with tempfile.NamedTemporaryFile(suffix='.py', delete=False,
                                                mode='w') as f:
                    f.write(code)
                    tmp = f.name
                result = subprocess.run(
                    ['ruff', 'check', '--output-format=json', tmp],
                    capture_output=True, text=True
                )
                import json
                violations = json.loads(result.stdout or '[]')
                pathlib.Path(tmp).unlink(missing_ok=True)
                return {'violations': violations, 'count': len(violations)}
        """),
    },
    "code_formatter": {
        "name": "Code Formatter",
        "description": "Auto-format Python code with ruff/black",
        "ecosystem": None,
        "requires_auth": False,
        "category": "code_quality",
        "dependencies": ["ruff"],
        "code": textwrap.dedent("""\
            def format_code(code: str) -> str:
                \"\"\"Format Python source code using ruff.\"\"\"
                import subprocess, tempfile, pathlib
                with tempfile.NamedTemporaryFile(suffix='.py', delete=False,
                                                mode='w') as f:
                    f.write(code)
                    tmp = f.name
                subprocess.run(['ruff', 'format', tmp], capture_output=True)
                formatted = pathlib.Path(tmp).read_text()
                pathlib.Path(tmp).unlink(missing_ok=True)
                return formatted
        """),
    },
    "test_runner": {
        "name": "Test Runner",
        "description": "Run pytest on a specified path and return results",
        "ecosystem": None,
        "requires_auth": False,
        "category": "code_quality",
        "dependencies": ["pytest"],
        "code": textwrap.dedent("""\
            def run_tests(path: str = '.', extra_args: list = None) -> dict:
                \"\"\"Run pytest and return a summary of results.\"\"\"
                import subprocess
                cmd = ['python', '-m', 'pytest', path, '--tb=short', '-q']
                if extra_args:
                    cmd.extend(extra_args)
                result = subprocess.run(cmd, capture_output=True, text=True)
                return {
                    'returncode': result.returncode,
                    'stdout': result.stdout,
                    'stderr': result.stderr,
                    'passed': result.returncode == 0
                }
        """),
    },
    "code_executor": {
        "name": "Safe Code Executor",
        "description": "Execute Python code in an isolated subprocess with a timeout",
        "ecosystem": None,
        "requires_auth": False,
        "category": "code_quality",
        "dependencies": [],
        "code": textwrap.dedent("""\
            def execute_code(code: str, timeout: int = 10) -> dict:
                \"\"\"Execute Python code safely in a subprocess with a timeout.\"\"\"
                import subprocess, sys
                result = subprocess.run(
                    [sys.executable, '-c', code],
                    capture_output=True, text=True, timeout=timeout
                )
                return {
                    'stdout': result.stdout,
                    'stderr': result.stderr,
                    'returncode': result.returncode
                }
        """),
    },
    "pdf_reader": {
        "name": "PDF Reader",
        "description": "Extract text from PDF files",
        "ecosystem": None,
        "requires_auth": False,
        "category": "documents",
        "dependencies": ["pypdf"],
        "code": textwrap.dedent("""\
            def read_pdf(path: str) -> str:
                \"\"\"Extract all text from a PDF file.\"\"\"
                from pypdf import PdfReader
                reader = PdfReader(path)
                return '\\n'.join(page.extract_text() or '' for page in reader.pages)
        """),
    },
    "sentiment_analyzer": {
        "name": "Sentiment Analyzer",
        "description": "Score text sentiment (positive/neutral/negative)",
        "ecosystem": None,
        "requires_auth": False,
        "category": "nlp",
        "dependencies": ["textblob"],
        "code": textwrap.dedent("""\
            def analyze_sentiment(text: str) -> dict:
                \"\"\"Return polarity (-1 to 1) and subjectivity (0 to 1) for text.\"\"\"
                from textblob import TextBlob
                blob = TextBlob(text)
                polarity = blob.sentiment.polarity
                label = 'positive' if polarity > 0.1 else ('negative' if polarity < -0.1 else 'neutral')
                return {
                    'label': label,
                    'polarity': round(polarity, 4),
                    'subjectivity': round(blob.sentiment.subjectivity, 4)
                }
        """),
    },
    "order_lookup": {
        "name": "Order Lookup",
        "description": "Look up e-commerce order status from an orders database",
        "ecosystem": None,
        "requires_auth": False,
        "category": "ecommerce",
        "dependencies": [],
        "code": textwrap.dedent("""\
            def get_order_status(order_id: str, db_path: str = 'orders.db') -> dict:
                \"\"\"Return status and details for a given order ID.\"\"\"
                import sqlite3, pathlib
                if not pathlib.Path(db_path).exists():
                    return {'error': f'Database not found: {db_path}'}
                conn = sqlite3.connect(db_path)
                conn.row_factory = sqlite3.Row
                row = conn.execute(
                    'SELECT * FROM orders WHERE id = ?', (order_id,)).fetchone()
                conn.close()
                return dict(row) if row else {'error': f'Order {order_id} not found'}
        """),
    },
    "ticket_creator": {
        "name": "Support Ticket Creator",
        "description": "Create support tickets in a local ticket store (JSON file)",
        "ecosystem": None,
        "requires_auth": False,
        "category": "support",
        "dependencies": [],
        "code": textwrap.dedent("""\
            def create_ticket(title: str, description: str, priority: str = 'medium') -> dict:
                \"\"\"Create a support ticket and return its ID.\"\"\"
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
                    f.write(json.dumps(ticket) + '\\n')
                return ticket
        """),
    },
}


# ---------------------------------------------------------------------------
# Domain → recommended tool IDs mapping (used as LLM fallback seed)
# ---------------------------------------------------------------------------

DOMAIN_TOOL_MAP: Dict[str, List[str]] = {
    "customer_service":    ["escalate_to_human", "ticket_creator", "order_lookup", "gmail", "outlook_email", "database_query"],
    "ecommerce":           ["order_lookup", "database_query", "gmail", "outlook_email", "web_search"],
    "coding_assistant":    ["linter", "code_formatter", "test_runner", "code_executor", "file_operations", "web_search"],
    "data_analysis":       ["database_query", "file_operations", "web_search", "http_request"],
    "content_creation":    ["web_search", "file_operations", "sentiment_analyzer"],
    "project_management":  ["google_calendar", "teams", "gmail", "outlook_email", "http_request"],
    "research":            ["web_search", "pdf_reader", "database_query", "file_operations"],
    "technical_support":   ["linter", "database_query", "web_search", "http_request", "escalate_to_human"],
    "education":           ["web_search", "pdf_reader", "file_operations", "database_query"],
    "finance":             ["database_query", "http_request", "gmail", "escalate_to_human"],
    "healthcare":          ["database_query", "escalate_to_human", "gmail", "file_operations"],
    "sales_marketing":     ["gmail", "outlook_email", "google_calendar", "web_search", "database_query"],
    "general":             ["web_search", "file_operations", "http_request"],
}


# ---------------------------------------------------------------------------
# Public helpers
# ---------------------------------------------------------------------------

def get_all_tools() -> Dict[str, Dict[str, Any]]:
    """Return all predefined + generated tool templates (code excluded)."""
    combined = {}
    for tid, t in {**PREDEFINED_TOOLS, **GENERATED_TOOL_TEMPLATES}.items():
        combined[tid] = {k: v for k, v in t.items() if k != "code"}
    return combined


def get_tool_code(tool_id: str) -> str | None:
    """Return the Python source code for a tool by ID."""
    all_tools = {**PREDEFINED_TOOLS, **GENERATED_TOOL_TEMPLATES}
    tool = all_tools.get(tool_id)
    return tool["code"] if tool else None


def get_tools_for_domain(domain: str) -> List[str]:
    """Return recommended tool IDs for a given domain slug."""
    return DOMAIN_TOOL_MAP.get(domain, DOMAIN_TOOL_MAP["general"])


def resolve_tool_ids(tool_ids: List[str]) -> List[Dict[str, Any]]:
    """Return full info (minus code) for a list of tool IDs."""
    all_tools = {**PREDEFINED_TOOLS, **GENERATED_TOOL_TEMPLATES}
    result = []
    for tid in tool_ids:
        if tid in all_tools:
            entry = {k: v for k, v in all_tools[tid].items() if k != "code"}
            result.append({"id": tid, **entry})
    return result


def get_ecosystem_groups() -> Dict[str, List[Dict]]:
    """Group tools by ecosystem for the UI tool marketplace."""
    groups: Dict[str, List[Dict]] = {"google": [], "microsoft": [], "standalone": [], "generated": []}

    for tid, t in PREDEFINED_TOOLS.items():
        eco = t.get("ecosystem") or "standalone"
        groups[eco].append({"id": tid, **{k: v for k, v in t.items() if k != "code"}})

    for tid, t in GENERATED_TOOL_TEMPLATES.items():
        groups["generated"].append({"id": tid, **{k: v for k, v in t.items() if k != "code"}})

    return groups
