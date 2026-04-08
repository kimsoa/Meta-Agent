"""Tool: gmail"""

def send_email(to: str, subject: str, body: str) -> dict:
    """Send an email using Gmail API."""
    from googleapiclient.discovery import build
    import base64, email.mime.text as mt
    service = build('gmail', 'v1')
    msg = mt.MIMEText(body)
    msg['to'], msg['subject'] = to, subject
    raw = base64.urlsafe_b64encode(msg.as_bytes()).decode()
    return service.users().messages().send(
        userId='me', body={'raw': raw}).execute()

