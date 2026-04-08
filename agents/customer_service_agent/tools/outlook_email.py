"""Tool: outlook_email"""

def send_email(to: str, subject: str, body: str, access_token: str) -> dict:
    """Send an email via Microsoft Graph."""
    import requests
    url = 'https://graph.microsoft.com/v1.0/me/sendMail'
    payload = {'message': {
        'subject': subject,
        'body': {'contentType': 'Text', 'content': body},
        'toRecipients': [{'emailAddress': {'address': to}}]
    }}
    r = requests.post(url, json=payload, headers={'Authorization': f'Bearer {access_token}'})
    return {'status': r.status_code}

