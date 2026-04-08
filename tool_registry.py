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

    # ── Weather & Environment ───────────────────────────────────────────────
    "weather": {
        "name": "Weather",
        "description": "Get current weather and forecasts for any city using Open-Meteo (no API key needed)",
        "ecosystem": None,
        "requires_auth": False,
        "category": "information",
        "dependencies": ["httpx"],
        "code": textwrap.dedent("""\
            def get_weather(city: str, country_code: str = '') -> dict:
                \"\"\"Return current temperature, wind speed and weather code for a city.\"\"\"
                import httpx
                # Step 1: geocode
                geo_url = 'https://geocoding-api.open-meteo.com/v1/search'
                q = f'{city},{country_code}' if country_code else city
                geo = httpx.get(geo_url, params={'name': q, 'count': 1}, timeout=10).json()
                if not geo.get('results'):
                    return {'error': f'City not found: {city}'}
                loc = geo['results'][0]
                # Step 2: fetch weather
                wx_url = 'https://api.open-meteo.com/v1/forecast'
                params = {
                    'latitude': loc['latitude'], 'longitude': loc['longitude'],
                    'current': 'temperature_2m,wind_speed_10m,weather_code',
                    'timezone': 'auto'
                }
                wx = httpx.get(wx_url, params=params, timeout=10).json()
                current = wx.get('current', {})
                return {
                    'city': loc['name'], 'country': loc.get('country', ''),
                    'temperature_c': current.get('temperature_2m'),
                    'wind_speed_kmh': current.get('wind_speed_10m'),
                    'weather_code': current.get('weather_code'),
                    'timezone': wx.get('timezone')
                }
        """),
    },

    # ── News ────────────────────────────────────────────────────────────────
    "news_search": {
        "name": "News Search",
        "description": "Fetch latest news headlines on any topic via GNews API or DuckDuckGo News",
        "ecosystem": None,
        "requires_auth": False,
        "category": "information",
        "dependencies": ["duckduckgo-search"],
        "code": textwrap.dedent("""\
            def get_news(topic: str, max_results: int = 5) -> list:
                \"\"\"Return recent news headlines and snippets for a topic.\"\"\"
                from duckduckgo_search import DDGS
                with DDGS() as ddgs:
                    results = list(ddgs.news(topic, max_results=max_results))
                return [{'title': r.get('title'), 'body': r.get('body'),
                         'url': r.get('url'), 'date': r.get('date')} for r in results]
        """),
    },

    # ── Calculator & Math ───────────────────────────────────────────────────
    "calculator": {
        "name": "Calculator",
        "description": "Evaluate mathematical expressions — arithmetic, algebra, statistics, finance (compound interest, loan EMI)",
        "ecosystem": None,
        "requires_auth": False,
        "category": "utilities",
        "dependencies": [],
        "code": textwrap.dedent("""\
            def calculate(expression: str) -> dict:
                \"\"\"Safely evaluate a math expression and return the result.\"\"\"
                import ast, math, statistics
                allowed_names = {k: v for k, v in vars(math).items() if not k.startswith('_')}
                allowed_names.update({'abs': abs, 'round': round, 'min': min, 'max': max,
                                      'sum': sum, 'len': len, 'pow': pow})
                try:
                    tree = ast.parse(expression, mode='eval')
                    # Whitelist only safe AST nodes
                    for node in ast.walk(tree):
                        if isinstance(node, ast.Call):
                            if not (isinstance(node.func, ast.Name) and node.func.id in allowed_names):
                                raise ValueError(f'Disallowed call: {ast.dump(node.func)}')
                    result = eval(compile(tree, '<expr>', 'eval'), {'__builtins__': {}}, allowed_names)
                    return {'expression': expression, 'result': result}
                except Exception as e:
                    return {'error': str(e)}

            def loan_emi(principal: float, annual_rate_pct: float, months: int) -> dict:
                \"\"\"Calculate monthly EMI for a loan.\"\"\"
                r = annual_rate_pct / 100 / 12
                if r == 0:
                    emi = principal / months
                else:
                    emi = principal * r * (1 + r)**months / ((1 + r)**months - 1)
                return {'emi': round(emi, 2), 'total': round(emi * months, 2),
                        'interest': round(emi * months - principal, 2)}

            def compound_interest(principal: float, annual_rate_pct: float,
                                   years: float, n: int = 12) -> dict:
                \"\"\"Calculate compound interest. n = compounds per year.\"\"\"
                amount = principal * (1 + annual_rate_pct / 100 / n) ** (n * years)
                return {'amount': round(amount, 2), 'interest': round(amount - principal, 2)}
        """),
    },

    # ── Unit Converter ──────────────────────────────────────────────────────
    "unit_converter": {
        "name": "Unit Converter",
        "description": "Convert between units: length, weight, temperature, speed, data size, pressure, energy",
        "ecosystem": None,
        "requires_auth": False,
        "category": "utilities",
        "dependencies": [],
        "code": textwrap.dedent("""\
            def convert_units(value: float, from_unit: str, to_unit: str) -> dict:
                \"\"\"Convert value from one unit to another. Example: convert_units(100, 'km', 'miles').\"\"\"
                from_unit, to_unit = from_unit.lower(), to_unit.lower()
                # Normalise to SI base, then convert out
                _TO_SI = {
                    # length (metre)
                    'mm': 0.001, 'cm': 0.01, 'm': 1, 'km': 1000,
                    'inch': 0.0254, 'inches': 0.0254, 'ft': 0.3048, 'feet': 0.3048,
                    'yard': 0.9144, 'mile': 1609.34, 'miles': 1609.34,
                    # weight (kg)
                    'g': 0.001, 'kg': 1, 'lb': 0.453592, 'lbs': 0.453592,
                    'oz': 0.0283495, 'tonne': 1000,
                    # speed (m/s)
                    'mph': 0.44704, 'kph': 0.277778, 'kmh': 0.277778,
                    'knots': 0.514444, 'm/s': 1,
                    # pressure (pascal)
                    'pa': 1, 'kpa': 1000, 'mpa': 1e6, 'bar': 1e5,
                    'psi': 6894.76, 'atm': 101325,
                    # data (bytes)
                    'b': 1, 'kb': 1024, 'mb': 1048576, 'gb': 1073741824,
                    'tb': 1099511627776,
                    # energy (joule)
                    'j': 1, 'kj': 1000, 'cal': 4.184, 'kcal': 4184, 'wh': 3600, 'kwh': 3600000,
                }
                # Temperature handled separately
                temp_units = {'c', 'f', 'k', 'celsius', 'fahrenheit', 'kelvin'}
                if from_unit in temp_units and to_unit in temp_units:
                    def to_kelvin(v, u):
                        if u in ('c', 'celsius'): return v + 273.15
                        if u in ('f', 'fahrenheit'): return (v - 32) * 5/9 + 273.15
                        return v
                    def from_kelvin(v, u):
                        if u in ('c', 'celsius'): return v - 273.15
                        if u in ('f', 'fahrenheit'): return (v - 273.15) * 9/5 + 32
                        return v
                    result = from_kelvin(to_kelvin(value, from_unit), to_unit)
                    return {'value': value, 'from': from_unit, 'to': to_unit, 'result': round(result, 6)}
                if from_unit not in _TO_SI or to_unit not in _TO_SI:
                    return {'error': f'Unknown unit: {from_unit!r} or {to_unit!r}'}
                si = value * _TO_SI[from_unit]
                result = si / _TO_SI[to_unit]
                return {'value': value, 'from': from_unit, 'to': to_unit, 'result': round(result, 8)}
        """),
    },

    # ── Currency Exchange ───────────────────────────────────────────────────
    "currency_exchange": {
        "name": "Currency Exchange",
        "description": "Convert between currencies using live exchange rates (open.er-api.com, no key needed)",
        "ecosystem": None,
        "requires_auth": False,
        "category": "finance",
        "dependencies": ["httpx"],
        "code": textwrap.dedent("""\
            def convert_currency(amount: float, from_currency: str, to_currency: str) -> dict:
                \"\"\"Convert amount between currencies using live rates.\"\"\"
                import httpx
                base = from_currency.upper()
                url = f'https://open.er-api.com/v6/latest/{base}'
                r = httpx.get(url, timeout=10).json()
                if r.get('result') != 'success':
                    return {'error': 'Exchange rate fetch failed', 'detail': r}
                target = to_currency.upper()
                rates = r.get('rates', {})
                if target not in rates:
                    return {'error': f'Unsupported currency: {target}'}
                rate = rates[target]
                return {
                    'amount': amount, 'from': base, 'to': target,
                    'rate': rate, 'converted': round(amount * rate, 4),
                    'updated': r.get('time_last_update_utc')
                }
        """),
    },

    # ── QR Code Generator ──────────────────────────────────────────────────
    "qr_code_generator": {
        "name": "QR Code Generator",
        "description": "Generate a QR code PNG file from any text or URL",
        "ecosystem": None,
        "requires_auth": False,
        "category": "utilities",
        "dependencies": ["qrcode[pil]"],
        "code": textwrap.dedent("""\
            def generate_qr(data: str, output_path: str = 'qrcode.png', box_size: int = 10) -> dict:
                \"\"\"Generate a QR code image file for the given data.\"\"\"
                import qrcode
                qr = qrcode.QRCode(box_size=box_size, border=4)
                qr.add_data(data)
                qr.make(fit=True)
                img = qr.make_image(fill_color='black', back_color='white')
                img.save(output_path)
                return {'output': output_path, 'data': data}
        """),
    },

    # ── JSON / Data Transformer ─────────────────────────────────────────────
    "json_transformer": {
        "name": "JSON / Data Transformer",
        "description": "Parse, validate, transform, flatten, or diff JSON payloads",
        "ecosystem": None,
        "requires_auth": False,
        "category": "data",
        "dependencies": [],
        "code": textwrap.dedent("""\
            def flatten_json(data: dict, sep: str = '.', prefix: str = '') -> dict:
                \"\"\"Flatten a nested dict to dot-separated keys.\"\"\"
                out = {}
                for k, v in data.items():
                    full_key = f'{prefix}{sep}{k}' if prefix else k
                    if isinstance(v, dict):
                        out.update(flatten_json(v, sep, full_key))
                    elif isinstance(v, list):
                        for i, item in enumerate(v):
                            idx_key = f'{full_key}[{i}]'
                            if isinstance(item, dict):
                                out.update(flatten_json(item, sep, idx_key))
                            else:
                                out[idx_key] = item
                    else:
                        out[full_key] = v
                return out

            def diff_json(a: dict, b: dict) -> dict:
                \"\"\"Return keys added, removed, or changed between two dicts.\"\"\"
                fa, fb = flatten_json(a), flatten_json(b)
                added = {k: fb[k] for k in fb if k not in fa}
                removed = {k: fa[k] for k in fa if k not in fb}
                changed = {k: {'old': fa[k], 'new': fb[k]} for k in fa if k in fb and fa[k] != fb[k]}
                return {'added': added, 'removed': removed, 'changed': changed}
        """),
    },

    # ── Cron / Schedule Parser ──────────────────────────────────────────────
    "cron_parser": {
        "name": "Cron Expression Parser",
        "description": "Parse cron expressions and return the next N scheduled run times",
        "ecosystem": None,
        "requires_auth": False,
        "category": "utilities",
        "dependencies": ["croniter"],
        "code": textwrap.dedent("""\
            def parse_cron(expression: str, next_n: int = 5) -> dict:
                \"\"\"Return the next N execution times for a cron expression.\"\"\"
                from croniter import croniter
                import datetime
                base = datetime.datetime.utcnow()
                cron = croniter(expression, base)
                times = [cron.get_next(datetime.datetime).isoformat() + 'Z' for _ in range(next_n)]
                return {'expression': expression, 'next_runs': times}
        """),
    },

    # ── Slack (no-auth webhook) ─────────────────────────────────────────────
    "slack_webhook": {
        "name": "Slack Webhook Notification",
        "description": "Send notifications to a Slack channel via an Incoming Webhook URL",
        "ecosystem": None,
        "requires_auth": True,
        "category": "communication",
        "dependencies": ["httpx"],
        "code": textwrap.dedent("""\
            def send_slack_message(webhook_url: str, text: str, username: str = 'Meta-Agent') -> dict:
                \"\"\"Post a message to Slack via an Incoming Webhook URL.\"\"\"
                import httpx
                r = httpx.post(webhook_url, json={'text': text, 'username': username}, timeout=10)
                return {'status': r.status_code, 'ok': r.text == 'ok'}
        """),
    },

    # ── SMS / Twilio ────────────────────────────────────────────────────────
    "sms_twilio": {
        "name": "SMS via Twilio",
        "description": "Send SMS messages via Twilio API",
        "ecosystem": None,
        "requires_auth": True,
        "category": "communication",
        "dependencies": ["twilio"],
        "code": textwrap.dedent("""\
            def send_sms(account_sid: str, auth_token: str, from_number: str,
                         to_number: str, body: str) -> dict:
                \"\"\"Send an SMS via Twilio.\"\"\"
                from twilio.rest import Client
                client = Client(account_sid, auth_token)
                msg = client.messages.create(body=body, from_=from_number, to=to_number)
                return {'sid': msg.sid, 'status': msg.status}
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

    # ── IT / DevOps / Infrastructure ────────────────────────────────────────
    "system_health_check": {
        "name": "System Health Check",
        "description": "Check CPU, memory, disk, and process health on the local host (for IT/ops monitoring)",
        "ecosystem": None,
        "requires_auth": False,
        "category": "infrastructure",
        "dependencies": ["psutil"],
        "code": textwrap.dedent("""\
            def system_health() -> dict:
                \"\"\"Return CPU, memory, disk, and top processes snapshot.\"\"\"
                import psutil, datetime
                cpu = psutil.cpu_percent(interval=1)
                mem = psutil.virtual_memory()
                disk = psutil.disk_usage('/')
                top_procs = sorted(
                    [{'pid': p.pid, 'name': p.info['name'], 'cpu': p.info['cpu_percent'],
                      'mem_mb': round(p.info['memory_info'].rss / 1e6, 1)}
                     for p in psutil.process_iter(['name', 'cpu_percent', 'memory_info'])
                     if p.info['memory_info']],
                    key=lambda x: x['mem_mb'], reverse=True
                )[:5]
                return {
                    'timestamp': datetime.datetime.utcnow().isoformat() + 'Z',
                    'cpu_percent': cpu,
                    'memory': {'total_gb': round(mem.total / 1e9, 2),
                               'used_gb': round(mem.used / 1e9, 2),
                               'percent': mem.percent},
                    'disk': {'total_gb': round(disk.total / 1e9, 2),
                             'used_gb': round(disk.used / 1e9, 2),
                             'percent': disk.percent},
                    'top_processes_by_memory': top_procs
                }
        """),
    },
    "port_scanner": {
        "name": "Network Port Scanner",
        "description": "Scan a host for open TCP ports — for network engineers and IT security auditing",
        "ecosystem": None,
        "requires_auth": False,
        "category": "networking",
        "dependencies": [],
        "code": textwrap.dedent("""\
            def scan_ports(host: str, ports: list = None, timeout: float = 0.5) -> dict:
                \"\"\"Scan TCP ports on a host. Default ports: common service ports.\"\"\"
                import socket
                if ports is None:
                    ports = [21, 22, 23, 25, 53, 80, 110, 143, 443, 445,
                             3306, 3389, 5432, 5900, 6379, 8080, 8443, 27017]
                open_ports, closed_ports = [], []
                for port in ports:
                    try:
                        with socket.create_connection((host, port), timeout=timeout):
                            open_ports.append(port)
                    except (socket.timeout, ConnectionRefusedError, OSError):
                        closed_ports.append(port)
                return {'host': host, 'open': open_ports, 'closed': closed_ports,
                        'total_scanned': len(ports)}
        """),
    },
    "dns_lookup": {
        "name": "DNS Lookup",
        "description": "Resolve DNS records (A, AAAA, MX, TXT, CNAME) for a domain — for network/IT engineers",
        "ecosystem": None,
        "requires_auth": False,
        "category": "networking",
        "dependencies": ["dnspython"],
        "code": textwrap.dedent("""\
            def dns_lookup(domain: str, record_type: str = 'A') -> dict:
                \"\"\"Resolve DNS records for a domain. record_type: A, AAAA, MX, TXT, CNAME, NS.\"\"\"
                import dns.resolver
                record_type = record_type.upper()
                try:
                    answers = dns.resolver.resolve(domain, record_type)
                    records = [r.to_text() for r in answers]
                    return {'domain': domain, 'type': record_type, 'records': records}
                except Exception as e:
                    return {'domain': domain, 'type': record_type, 'error': str(e)}
        """),
    },
    "ssl_certificate_checker": {
        "name": "SSL Certificate Checker",
        "description": "Inspect SSL/TLS certificate details (expiry, issuer, SANs) for any domain — security & ops teams",
        "ecosystem": None,
        "requires_auth": False,
        "category": "security",
        "dependencies": [],
        "code": textwrap.dedent("""\
            def check_ssl(hostname: str, port: int = 443) -> dict:
                \"\"\"Return SSL certificate details including expiry date and issuer.\"\"\"
                import ssl, socket, datetime
                ctx = ssl.create_default_context()
                with ctx.wrap_socket(socket.socket(), server_hostname=hostname) as s:
                    s.settimeout(10)
                    s.connect((hostname, port))
                    cert = s.getpeercert()
                not_after = datetime.datetime.strptime(cert['notAfter'], '%b %d %H:%M:%S %Y %Z')
                days_left = (not_after - datetime.datetime.utcnow()).days
                return {
                    'hostname': hostname,
                    'subject': dict(x[0] for x in cert.get('subject', [])),
                    'issuer': dict(x[0] for x in cert.get('issuer', [])),
                    'expires': cert['notAfter'],
                    'days_until_expiry': days_left,
                    'expired': days_left < 0,
                    'san': [v for _, v in cert.get('subjectAltName', [])]
                }
        """),
    },
    "log_analyzer": {
        "name": "Log File Analyzer",
        "description": "Parse log files — count error levels, find patterns, tail recent lines. For SREs, IT managers, DevOps",
        "ecosystem": None,
        "requires_auth": False,
        "category": "infrastructure",
        "dependencies": [],
        "code": textwrap.dedent("""\
            def analyze_log(path: str, tail_lines: int = 50, grep_pattern: str = '') -> dict:
                \"\"\"Parse a log file: count ERROR/WARN/INFO, tail lines, optional grep filter.\"\"\"
                import re, collections, pathlib
                text = pathlib.Path(path).read_text(errors='replace')
                lines = text.splitlines()
                counts = collections.Counter()
                for line in lines:
                    for level in ('ERROR', 'CRITICAL', 'WARNING', 'WARN', 'INFO', 'DEBUG'):
                        if level in line:
                            counts[level] += 1
                            break
                tail = lines[-tail_lines:]
                if grep_pattern:
                    try:
                        pat = re.compile(grep_pattern, re.IGNORECASE)
                        tail = [l for l in tail if pat.search(l)]
                    except re.error as e:
                        return {'error': f'Invalid regex: {e}'}
                return {
                    'total_lines': len(lines),
                    'level_counts': dict(counts),
                    'tail': tail
                }
        """),
    },
    "api_health_monitor": {
        "name": "API / Service Health Monitor",
        "description": "Ping HTTP endpoints and report status, latency, and response — for IT, banking, airline uptime monitoring",
        "ecosystem": None,
        "requires_auth": False,
        "category": "infrastructure",
        "dependencies": ["httpx"],
        "code": textwrap.dedent("""\
            def check_api_health(endpoints: list) -> list:
                \"\"\"
                Check health of multiple HTTP endpoints.
                endpoints: list of dicts with 'url' and optional 'expected_status' (default 200).
                \"\"\"
                import httpx, time
                results = []
                for ep in endpoints:
                    url = ep.get('url') if isinstance(ep, dict) else ep
                    expected = (ep.get('expected_status', 200) if isinstance(ep, dict) else 200)
                    t0 = time.monotonic()
                    try:
                        r = httpx.get(url, timeout=10, follow_redirects=True)
                        latency = round((time.monotonic() - t0) * 1000, 1)
                        results.append({
                            'url': url, 'status': r.status_code,
                            'ok': r.status_code == expected,
                            'latency_ms': latency
                        })
                    except Exception as e:
                        results.append({'url': url, 'error': str(e), 'ok': False})
                return results
        """),
    },
    "docker_manager": {
        "name": "Docker Container Manager",
        "description": "List, inspect, start, stop Docker containers — for DevOps/SRE/IT managers",
        "ecosystem": None,
        "requires_auth": False,
        "category": "infrastructure",
        "dependencies": ["docker"],
        "code": textwrap.dedent("""\
            def list_containers(all_containers: bool = False) -> list:
                \"\"\"List Docker containers. Set all_containers=True to include stopped ones.\"\"\"
                import docker
                client = docker.from_env()
                containers = client.containers.list(all=all_containers)
                return [{'id': c.short_id, 'name': c.name, 'status': c.status,
                         'image': c.image.tags[0] if c.image.tags else 'untagged'}
                        for c in containers]

            def restart_container(container_name: str) -> dict:
                \"\"\"Restart a Docker container by name.\"\"\"
                import docker
                client = docker.from_env()
                c = client.containers.get(container_name)
                c.restart()
                c.reload()
                return {'name': container_name, 'status': c.status}
        """),
    },
    "git_operations": {
        "name": "Git Repository Operations",
        "description": "Clone, pull, log, diff, and inspect Git repositories — for software engineers and IT",
        "ecosystem": None,
        "requires_auth": False,
        "category": "devops",
        "dependencies": ["gitpython"],
        "code": textwrap.dedent("""\
            def git_log(repo_path: str, max_entries: int = 10) -> list:
                \"\"\"Return the last N commits from a Git repo.\"\"\"
                import git
                repo = git.Repo(repo_path)
                return [{'sha': c.hexsha[:8], 'author': str(c.author),
                         'date': c.committed_datetime.isoformat(),
                         'message': c.message.strip().splitlines()[0]}
                        for c in repo.iter_commits(max_count=max_entries)]

            def git_status(repo_path: str) -> dict:
                \"\"\"Return the working tree status of a Git repository.\"\"\"
                import git
                repo = git.Repo(repo_path)
                return {
                    'branch': repo.active_branch.name,
                    'is_dirty': repo.is_dirty(),
                    'untracked': repo.untracked_files,
                    'modified': [d.a_path for d in repo.index.diff(None)],
                    'staged': [d.a_path for d in repo.index.diff('HEAD')]
                }
        """),
    },

    # ── Banking / Finance / Compliance ──────────────────────────────────────
    "iban_validator": {
        "name": "IBAN / Account Validator",
        "description": "Validate IBAN bank account numbers and extract bank country, check digit — for banking/fintech engineers",
        "ecosystem": None,
        "requires_auth": False,
        "category": "finance",
        "dependencies": ["schwifty"],
        "code": textwrap.dedent("""\
            def validate_iban(iban: str) -> dict:
                \"\"\"Validate an IBAN and extract bank metadata.\"\"\"
                from schwifty import IBAN
                try:
                    i = IBAN(iban)
                    return {
                        'iban': i.compact,
                        'formatted': i.formatted,
                        'valid': True,
                        'country': i.country_code,
                        'bank_code': i.bank_code,
                        'account_code': i.account_code,
                        'bic': str(i.bic) if i.bic else None
                    }
                except Exception as e:
                    return {'iban': iban, 'valid': False, 'error': str(e)}
        """),
    },
    "risk_calculator": {
        "name": "Financial Risk Calculator",
        "description": "Compute VaR, Sharpe ratio, and portfolio volatility — for banking/finance risk engineers",
        "ecosystem": None,
        "requires_auth": False,
        "category": "finance",
        "dependencies": [],
        "code": textwrap.dedent("""\
            def portfolio_var(returns: list, confidence: float = 0.95) -> dict:
                \"\"\"
                Calculate historical Value at Risk (VaR) at a given confidence level.
                returns: list of daily return values (e.g. [0.01, -0.02, 0.005, ...])
                \"\"\"
                import math
                sorted_r = sorted(returns)
                idx = int((1 - confidence) * len(sorted_r))
                var = abs(sorted_r[idx])
                mean = sum(returns) / len(returns)
                variance = sum((r - mean) ** 2 for r in returns) / len(returns)
                std = math.sqrt(variance)
                sharpe = (mean / std) * math.sqrt(252) if std > 0 else 0
                return {
                    'var': round(var, 6),
                    'confidence': confidence,
                    'sharpe_ratio_annualised': round(sharpe, 4),
                    'daily_std': round(std, 6),
                    'mean_return': round(mean, 6)
                }
        """),
    },

    # ── Healthcare / Medical ────────────────────────────────────────────────
    "hl7_parser": {
        "name": "HL7 Message Parser",
        "description": "Parse HL7 v2.x messages into structured segments — for healthcare IT engineers and EHR integrators",
        "ecosystem": None,
        "requires_auth": False,
        "category": "healthcare",
        "dependencies": ["hl7"],
        "code": textwrap.dedent("""\
            def parse_hl7(raw_message: str) -> dict:
                \"\"\"
                Parse an HL7 v2.x message string into segments.
                Returns a dict with segment names as keys.
                \"\"\"
                import hl7
                try:
                    msg = hl7.parse(raw_message.strip())
                    result = {}
                    for segment in msg:
                        name = str(segment[0])
                        result.setdefault(name, []).append(
                            [str(f) for f in segment]
                        )
                    return {'message_type': result.get('MSH', [[]])[0][8] if 'MSH' in result else 'unknown',
                            'segments': result}
                except Exception as e:
                    return {'error': str(e)}
        """),
    },
    "drug_interaction_checker": {
        "name": "Drug Interaction Checker",
        "description": "Check for drug interactions using the FDA openFDA API — for clinical/healthcare engineers",
        "ecosystem": None,
        "requires_auth": False,
        "category": "healthcare",
        "dependencies": ["httpx"],
        "code": textwrap.dedent("""\
            def check_drug_interactions(drug_name: str) -> dict:
                \"\"\"
                Look up FDA adverse event reports and label warnings for a drug.
                Uses the free openFDA API (no key needed).
                \"\"\"
                import httpx
                base = 'https://api.fda.gov/drug/label.json'
                r = httpx.get(base, params={'search': f'openfda.brand_name:"{drug_name}"', 'limit': 1}, timeout=10)
                if r.status_code != 200:
                    return {'error': f'FDA API error {r.status_code}'}
                results = r.json().get('results', [])
                if not results:
                    return {'drug': drug_name, 'found': False}
                label = results[0]
                return {
                    'drug': drug_name,
                    'found': True,
                    'warnings': label.get('warnings', []),
                    'drug_interactions': label.get('drug_interactions', []),
                    'contraindications': label.get('contraindications', [])
                }
        """),
    },
    "icd_code_lookup": {
        "name": "ICD-10 Code Lookup",
        "description": "Look up ICD-10 diagnosis codes and descriptions — for healthcare/medical record engineers",
        "ecosystem": None,
        "requires_auth": False,
        "category": "healthcare",
        "dependencies": ["httpx"],
        "code": textwrap.dedent("""\
            def lookup_icd10(code_or_term: str) -> dict:
                \"\"\"Search ICD-10 codes using the WHO/CMS public API.\"\"\"
                import httpx
                # Use the free clinicaltables.nlm.nih.gov API
                url = 'https://clinicaltables.nlm.nih.gov/api/icd10cm/v3/search'
                r = httpx.get(url, params={'sf': 'code,name', 'terms': code_or_term, 'maxList': 5}, timeout=10)
                data = r.json()
                # Response: [total, codes_list, extra, display_strs]
                if not data or len(data) < 4:
                    return {'error': 'No results'}
                codes = data[1] or []
                names = [d[1] if d else '' for d in (data[3] or [])]
                return {
                    'query': code_or_term,
                    'total': data[0],
                    'results': [{'code': c, 'description': n} for c, n in zip(codes, names)]
                }
        """),
    },

    # ── Airline / Transportation ────────────────────────────────────────────
    "flight_status": {
        "name": "Flight Status",
        "description": "Get live flight status and schedule information via AviationStack API (free tier available)",
        "ecosystem": None,
        "requires_auth": True,
        "category": "transportation",
        "dependencies": ["httpx"],
        "code": textwrap.dedent("""\
            def get_flight_status(flight_iata: str, api_key: str) -> dict:
                \"\"\"
                Get live status for a flight by IATA code (e.g. 'BA123').
                Requires an AviationStack API key (free tier at aviationstack.com).
                \"\"\"
                import httpx
                url = 'http://api.aviationstack.com/v1/flights'
                r = httpx.get(url, params={'access_key': api_key, 'flight_iata': flight_iata}, timeout=15)
                if r.status_code != 200:
                    return {'error': f'API error {r.status_code}'}
                data = r.json().get('data', [])
                if not data:
                    return {'flight': flight_iata, 'found': False}
                f = data[0]
                return {
                    'flight': f.get('flight', {}).get('iata'),
                    'status': f.get('flight_status'),
                    'departure': f.get('departure', {}),
                    'arrival': f.get('arrival', {}),
                    'airline': f.get('airline', {}).get('name')
                }
        """),
    },
    "geolocation": {
        "name": "IP Geolocation",
        "description": "Geolocate an IP address (country, city, ISP, lat/lon) using ip-api.com — for network/security engineers",
        "ecosystem": None,
        "requires_auth": False,
        "category": "networking",
        "dependencies": ["httpx"],
        "code": textwrap.dedent("""\
            def geolocate_ip(ip: str) -> dict:
                \"\"\"Return geolocation info for an IP address using the free ip-api.com service.\"\"\"
                import httpx
                r = httpx.get(f'http://ip-api.com/json/{ip}', timeout=10)
                data = r.json()
                if data.get('status') != 'success':
                    return {'ip': ip, 'error': data.get('message', 'lookup failed')}
                return {
                    'ip': ip, 'country': data.get('country'),
                    'region': data.get('regionName'), 'city': data.get('city'),
                    'isp': data.get('isp'), 'org': data.get('org'),
                    'lat': data.get('lat'), 'lon': data.get('lon'),
                    'timezone': data.get('timezone')
                }
        """),
    },

    # ── Data Quality / Validation ────────────────────────────────────────────
    "data_validator": {
        "name": "Data Validator",
        "description": "Validate emails, phone numbers, URLs, dates, and postcodes — for data engineers and system integrators",
        "ecosystem": None,
        "requires_auth": False,
        "category": "data",
        "dependencies": [],
        "code": textwrap.dedent("""\
            def validate_email(email: str) -> dict:
                \"\"\"Basic RFC-5321 email validation.\"\"\"
                import re
                pattern = r'^[\\w.+\\-]+@[\\w\\-]+\\.[a-z]{2,}$'
                valid = bool(re.match(pattern, email, re.IGNORECASE))
                return {'email': email, 'valid': valid}

            def validate_url(url: str) -> dict:
                \"\"\"Check if a URL has a valid scheme and netloc.\"\"\"
                from urllib.parse import urlparse
                parsed = urlparse(url)
                valid = parsed.scheme in ('http', 'https') and bool(parsed.netloc)
                return {'url': url, 'valid': valid, 'scheme': parsed.scheme, 'host': parsed.netloc}

            def validate_date(date_str: str, fmt: str = '%Y-%m-%d') -> dict:
                \"\"\"Validate a date string against a format (default ISO 8601).\"\"\"
                import datetime
                try:
                    dt = datetime.datetime.strptime(date_str, fmt)
                    return {'date': date_str, 'valid': True, 'parsed': dt.isoformat()}
                except ValueError as e:
                    return {'date': date_str, 'valid': False, 'error': str(e)}
        """),
    },

    # ── Cryptography / Security ─────────────────────────────────────────────
    "hash_generator": {
        "name": "Hash & Checksum Generator",
        "description": "Generate MD5, SHA-1, SHA-256, SHA-512 hashes for text or files — for security and DevOps engineers",
        "ecosystem": None,
        "requires_auth": False,
        "category": "security",
        "dependencies": [],
        "code": textwrap.dedent("""\
            def hash_text(text: str, algorithm: str = 'sha256') -> dict:
                \"\"\"Hash a string with the specified algorithm (md5, sha1, sha256, sha512).\"\"\"
                import hashlib
                try:
                    h = hashlib.new(algorithm, text.encode('utf-8'))
                    return {'algorithm': algorithm, 'input': text[:80], 'hash': h.hexdigest()}
                except (ValueError, Exception) as e:
                    return {'algorithm': algorithm, 'error': str(e)}

            def hash_file(path: str, algorithm: str = 'sha256') -> dict:
                \"\"\"Compute the hash of a file (streaming, handles large files).\"\"\"
                import hashlib, pathlib
                h = hashlib.new(algorithm)
                data = pathlib.Path(path).read_bytes()
                h.update(data)
                return {'algorithm': algorithm, 'file': path,
                        'hash': h.hexdigest(), 'size_bytes': len(data)}
        """),
    },

    # ── Reporting / Scheduling ───────────────────────────────────────────────
    "csv_processor": {
        "name": "CSV Processor",
        "description": "Read, filter, sort, summarise and export CSV files — for data analysts and reporting engineers",
        "ecosystem": None,
        "requires_auth": False,
        "category": "data",
        "dependencies": [],
        "code": textwrap.dedent("""\
            def read_csv(path: str, max_rows: int = 100) -> dict:
                \"\"\"Read a CSV file and return headers plus the first max_rows rows.\"\"\"
                import csv, pathlib
                with pathlib.Path(path).open(newline='', encoding='utf-8-sig') as f:
                    reader = csv.DictReader(f)
                    rows = [row for row, _ in zip(reader, range(max_rows))]
                return {'headers': list(rows[0].keys()) if rows else [], 'rows': rows,
                        'count': len(rows)}

            def filter_csv(path: str, column: str, value: str) -> list:
                \"\"\"Return rows from a CSV where column equals value.\"\"\"
                import csv, pathlib
                with pathlib.Path(path).open(newline='', encoding='utf-8-sig') as f:
                    return [row for row in csv.DictReader(f) if row.get(column) == value]

            def summarise_csv(path: str, numeric_column: str) -> dict:
                \"\"\"Return min, max, mean, and count for a numeric column in a CSV.\"\"\"
                import csv, pathlib
                values = []
                with pathlib.Path(path).open(newline='', encoding='utf-8-sig') as f:
                    for row in csv.DictReader(f):
                        try:
                            values.append(float(row[numeric_column]))
                        except (ValueError, KeyError):
                            pass
                if not values:
                    return {'error': f'No numeric values in column: {numeric_column}'}
                return {'column': numeric_column, 'count': len(values),
                        'min': min(values), 'max': max(values),
                        'mean': round(sum(values) / len(values), 4)}
        """),
    },

    # ── Airline/Transportation Ops ───────────────────────────────────────────
    "maintenance_scheduler": {
        "name": "Maintenance Schedule Manager",
        "description": "Create, list, and update maintenance windows for systems/aircraft/equipment — for ops and engineering managers",
        "ecosystem": None,
        "requires_auth": False,
        "category": "operations",
        "dependencies": [],
        "code": textwrap.dedent("""\
            def create_maintenance_window(asset_id: str, start_iso: str, end_iso: str,
                                           description: str, engineer: str = '') -> dict:
                \"\"\"Schedule a maintenance window for an asset (system, aircraft, equipment).\"\"\"
                import json, pathlib, datetime, uuid
                record = {
                    'id': str(uuid.uuid4())[:8],
                    'asset_id': asset_id,
                    'start': start_iso,
                    'end': end_iso,
                    'description': description,
                    'engineer': engineer,
                    'status': 'scheduled',
                    'created_at': datetime.datetime.utcnow().isoformat()
                }
                p = pathlib.Path('maintenance_windows.jsonl')
                with p.open('a') as f:
                    f.write(json.dumps(record) + '\\n')
                return record

            def list_maintenance_windows(asset_id: str = '') -> list:
                \"\"\"List all maintenance windows, optionally filtered by asset_id.\"\"\"
                import json, pathlib
                p = pathlib.Path('maintenance_windows.jsonl')
                if not p.exists():
                    return []
                windows = [json.loads(l) for l in p.read_text().splitlines() if l.strip()]
                return [w for w in windows if not asset_id or w['asset_id'] == asset_id]
        """),
    },

    # ── Compliance / Audit ───────────────────────────────────────────────────
    "audit_logger": {
        "name": "Compliance Audit Logger",
        "description": "Append immutable audit trail entries — for banking, healthcare, airline compliance and regulatory engineering",
        "ecosystem": None,
        "requires_auth": False,
        "category": "compliance",
        "dependencies": [],
        "code": textwrap.dedent("""\
            def log_audit_event(actor: str, action: str, resource: str,
                                 outcome: str = 'success', metadata: dict = None) -> dict:
                \"\"\"
                Append an audit log entry. Immutable append-only.
                outcome: 'success' | 'failure' | 'denied'
                \"\"\"
                import json, pathlib, datetime, hashlib
                entry = {
                    'timestamp': datetime.datetime.utcnow().isoformat() + 'Z',
                    'actor': actor,
                    'action': action,
                    'resource': resource,
                    'outcome': outcome,
                    'metadata': metadata or {}
                }
                # Integrity hash for tamper detection
                entry['integrity'] = hashlib.sha256(json.dumps(entry, sort_keys=True).encode()).hexdigest()
                p = pathlib.Path('audit.jsonl')
                with p.open('a') as f:
                    f.write(json.dumps(entry) + '\\n')
                return entry

            def query_audit_log(actor: str = '', action: str = '', limit: int = 50) -> list:
                \"\"\"Query the audit log by actor or action.\"\"\"
                import json, pathlib
                p = pathlib.Path('audit.jsonl')
                if not p.exists():
                    return []
                entries = [json.loads(l) for l in p.read_text().splitlines() if l.strip()]
                if actor:
                    entries = [e for e in entries if e.get('actor') == actor]
                if action:
                    entries = [e for e in entries if e.get('action') == action]
                return entries[-limit:]
        """),
    },

    # ── Docker / Ceagent agent builders ─────────────────────────────────────

    "create_single_docker_agent": {
        "name": "Create Single Docker Agent",
        "description": (
            "Scaffold a complete single-agent project using the Ceagent v2 YAML format with "
            "Dockerfile and Docker Compose. Ideal for standalone specialized agents that run "
            "inside Docker. Supports Docker Model Runner (DMR) for free local inference as well "
            "as OpenAI, Anthropic, and Groq hosted models."
        ),
        "ecosystem": "docker",
        "category": "deployment",
        "requires_auth": False,
        "dependencies": ["httpx"],
        "code": textwrap.dedent("""\
            def create_single_docker_agent(
                agent_id: str,
                model: str = "dmr/ai/gemma3",
                instruction: str = "You are a helpful AI assistant.",
                toolsets: list = None,
                port: int = 8301,
            ) -> dict:
                \"\"\"
                Create a complete single-agent Docker project using Ceagent v2 format.
                The generated project contains ceagent.yaml, Dockerfile, docker-compose.yml,
                .env.example, README.md, and agent.json.

                Args:
                    agent_id:    Short slug for the agent (used as folder and image name).
                    model:       Ceagent model string, e.g. "dmr/ai/gemma3" for Docker Model
                                 Runner local inference or "openai/gpt-4o" for OpenAI.
                    instruction: System prompt / instruction for the agent.
                    toolsets:    List of toolset dicts, e.g.
                                 [{"type":"builtin","name":"thinking"},
                                  {"type":"builtin","name":"shell"}].
                                 Defaults to [{"type":"builtin","name":"thinking"}].
                    port:        Host port to expose the agent on. Defaults to 8301.

                Returns:
                    dict with keys: agent_id, path, files_created, ceagent_yaml,
                    port, scaffold_type, runtime.
                \"\"\"
                import httpx
                payload = {
                    "agent_id": agent_id,
                    "model": model,
                    "instruction": instruction,
                    "toolsets": toolsets or [{"type": "builtin", "name": "thinking"}],
                    "port": port,
                }
                resp = httpx.post(
                    "http://localhost:8002/api/docker/single",
                    json=payload,
                    timeout=30,
                )
                resp.raise_for_status()
                return resp.json()
        """),
    },

    "create_multi_docker_agent": {
        "name": "Create Multi-Agent Docker Stack",
        "description": (
            "Scaffold a multi-agent Docker orchestration stack using the Ceagent v2 runtime. "
            "Creates a root orchestrator agent that delegates tasks to one or more specialized "
            "sub-agents via tool calls — all defined in a single ceagent.yaml. Use for complex "
            "workflows requiring role separation (e.g. research + writing + review agents). "
            "Supports Docker Model Runner for free local inference and cloud-hosted models."
        ),
        "ecosystem": "docker",
        "category": "deployment",
        "requires_auth": False,
        "dependencies": ["httpx"],
        "code": textwrap.dedent("""\
            def create_multi_docker_agent(
                agent_id: str,
                root_agent: dict,
                sub_agents: list,
                port: int = 8401,
            ) -> dict:
                \"\"\"
                Create a multi-agent Docker stack using Ceagent v2 orchestration.

                Args:
                    agent_id:   Short slug for the stack (folder and image name).
                    root_agent: Dict with keys: model, instruction, toolsets.
                                Example: {
                                    "model": "openai/gpt-4o",
                                    "instruction": "You orchestrate specialized agents.",
                                    "toolsets": [{"type":"builtin","name":"thinking"}]
                                }
                    sub_agents: List of sub-agent dicts, each with keys:
                                agent_id, model, description, instruction, toolsets.
                                Example: [
                                    {
                                        "agent_id": "research_agent",
                                        "model": "dmr/ai/gemma3",
                                        "description": "Researches topics in depth.",
                                        "instruction": "Research and summarise the topic.",
                                        "toolsets": [{"type":"builtin","name":"thinking"}]
                                    }
                                ]
                    port:       Host port for the stack. Defaults to 8401.

                Returns:
                    dict with keys: agent_id, path, files_created, ceagent_yaml,
                    port, scaffold_type, runtime, sub_agents.
                \"\"\"
                import httpx
                payload = {
                    "agent_id": agent_id,
                    "root_agent": root_agent,
                    "sub_agents": sub_agents,
                    "port": port,
                }
                resp = httpx.post(
                    "http://localhost:8002/api/docker/multi",
                    json=payload,
                    timeout=30,
                )
                resp.raise_for_status()
                return resp.json()
        """),
    },
}


# ---------------------------------------------------------------------------
# Domain → recommended tool IDs mapping (used as LLM fallback seed)
# ---------------------------------------------------------------------------

DOMAIN_TOOL_MAP: Dict[str, List[str]] = {
    # ── Customer-facing & commerce ──────────────────────────────────────────
    "customer_service":    ["escalate_to_human", "ticket_creator", "order_lookup", "gmail",
                            "outlook_email", "database_query", "sentiment_analyzer", "calculator"],
    "ecommerce":           ["order_lookup", "database_query", "gmail", "outlook_email",
                            "web_search", "calculator", "currency_exchange"],

    # ── Software engineering ────────────────────────────────────────────────
    "coding_assistant":    ["linter", "code_formatter", "test_runner", "code_executor",
                            "file_operations", "web_search", "git_operations", "hash_generator"],
    "software_engineering": ["linter", "code_formatter", "test_runner", "code_executor",
                             "file_operations", "web_search", "git_operations",
                             "ssl_certificate_checker", "dns_lookup", "hash_generator",
                             "json_transformer", "audit_logger"],

    # ── IT / DevOps / SRE ──────────────────────────────────────────────────
    "devops":              ["docker_manager", "git_operations", "system_health_check",
                            "api_health_monitor", "log_analyzer", "ssl_certificate_checker",
                            "dns_lookup", "port_scanner", "cron_parser", "hash_generator",
                            "audit_logger"],
    "it_management":       ["system_health_check", "api_health_monitor", "log_analyzer",
                            "port_scanner", "dns_lookup", "ssl_certificate_checker",
                            "docker_manager", "ticket_creator", "escalate_to_human",
                            "geolocation", "audit_logger"],
    "technical_support":   ["linter", "database_query", "web_search", "http_request",
                            "escalate_to_human", "system_health_check", "log_analyzer",
                            "api_health_monitor", "ticket_creator"],
    "networking":          ["port_scanner", "dns_lookup", "ssl_certificate_checker",
                            "geolocation", "api_health_monitor", "http_request"],
    "cybersecurity":       ["port_scanner", "ssl_certificate_checker", "hash_generator",
                            "dns_lookup", "geolocation", "audit_logger", "log_analyzer"],

    # ── Banking / Finance ───────────────────────────────────────────────────
    "finance":             ["calculator", "currency_exchange", "iban_validator",
                            "risk_calculator", "database_query", "http_request",
                            "gmail", "escalate_to_human", "audit_logger", "csv_processor"],
    "banking":             ["iban_validator", "risk_calculator", "calculator",
                            "currency_exchange", "database_query", "audit_logger",
                            "escalate_to_human", "ssl_certificate_checker", "hash_generator"],

    # ── Healthcare / Medical ────────────────────────────────────────────────
    "healthcare":          ["hl7_parser", "icd_code_lookup", "drug_interaction_checker",
                            "database_query", "escalate_to_human", "gmail",
                            "file_operations", "audit_logger", "data_validator"],
    "medical":             ["hl7_parser", "icd_code_lookup", "drug_interaction_checker",
                            "calculator", "database_query", "audit_logger"],

    # ── Airline / Transportation ────────────────────────────────────────────
    "airline":             ["flight_status", "maintenance_scheduler", "weather",
                            "geolocation", "api_health_monitor", "audit_logger",
                            "database_query", "calculator", "escalate_to_human"],
    "transportation":      ["flight_status", "weather", "geolocation",
                            "maintenance_scheduler", "calculator", "database_query"],

    # ── Operations & Compliance ─────────────────────────────────────────────
    "operations":          ["maintenance_scheduler", "audit_logger", "system_health_check",
                            "api_health_monitor", "calculator", "csv_processor",
                            "ticket_creator", "escalate_to_human"],
    "compliance":          ["audit_logger", "hash_generator", "data_validator",
                            "iban_validator", "database_query", "pdf_reader", "csv_processor"],

    # ── Data & Analytics ────────────────────────────────────────────────────
    "data_analysis":       ["database_query", "csv_processor", "file_operations",
                            "web_search", "http_request", "json_transformer",
                            "calculator", "data_validator"],
    "data_engineering":    ["csv_processor", "json_transformer", "database_query",
                            "data_validator", "file_operations", "hash_generator"],

    # ── Content & Research ──────────────────────────────────────────────────
    "content_creation":    ["web_search", "news_search", "file_operations",
                            "sentiment_analyzer", "pdf_reader"],
    "research":            ["web_search", "news_search", "pdf_reader", "database_query",
                            "file_operations", "calculator", "icd_code_lookup"],

    # ── Project Management / Comms ──────────────────────────────────────────
    "project_management":  ["google_calendar", "teams", "gmail", "outlook_email",
                            "http_request", "slack_webhook", "calculator", "ticket_creator"],
    "sales_marketing":     ["gmail", "outlook_email", "google_calendar", "web_search",
                            "news_search", "database_query", "sentiment_analyzer",
                            "currency_exchange", "slack_webhook"],

    # ── Education ───────────────────────────────────────────────────────────
    "education":           ["web_search", "news_search", "pdf_reader", "file_operations",
                            "database_query", "calculator", "unit_converter"],

    # ── General fallback ────────────────────────────────────────────────────
    "general":             ["web_search", "news_search", "weather", "calculator",
                            "unit_converter", "file_operations", "http_request"],
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
