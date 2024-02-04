from google.oauth2.credentials import Credentials
from google.auth.transport.requests import Request
from googleapiclient.discovery import build
from email.mime.text import MIMEText
import email
import base64
import quopri


SCOPES = ['https://www.googleapis.com/auth/gmail.compose', 'https://www.googleapis.com/auth/gmail.readonly']

def create_authenticated_service(access_token, refresh_token, client_id, client_secret):
    # Create credentials object from the access token
    credentials = Credentials(
        token=access_token,
        refresh_token=refresh_token,
        client_id=client_id,
        client_secret=client_secret,
        token_uri="https://oauth2.googleapis.com/token",
        scopes=SCOPES
    )

    # Check if the token is expired and refresh if needed
    try:
        credentials.refresh(Request())
    except Exception as e:
        return None # error with provided credentials
    
    # Create the Gmail service using the refreshed credentials
    service = build('gmail', 'v1', credentials=credentials)

    return service

def send_email(service, to: list, subject: str, body: str):
    # sender = service.users().getProfile(userId='me').execute()
    
    # Create an email message
    message = MIMEText(body)
    message['to'] = ", ".join(to)
    message['subject'] = subject
    create_message = {'raw': base64.urlsafe_b64encode(message.as_bytes()).decode()}

    # Send the encoded message using the Gmail API
    try:
        message = service.users().messages().send(userId='me', body=create_message).execute()
        print(f"Email sent!")
    except Exception as e:
        print(f"Failed to send email: {e}")


def draft_email(service, to: list, subject: str, body: str):
    # sender = service.users().getProfile(userId='me').execute()
    
    # Create an email message
    message = MIMEText(body)
    message['to'] = ", ".join(to)
    message['subject'] = subject
    create_message = {'message': {'raw': base64.urlsafe_b64encode(message.as_bytes()).decode()}}

    # Send the encoded message using the Gmail API
    try:
        message = service.users().drafts().create(userId='me', body=create_message).execute()
        print(f"Email drafted!")
    except Exception as e:
        print(f"Failed to draft email: {e}")


def read_email_from_sender(service, sender_email: str):
    response = service.users().messages().list(userId='me', q=f"from:{sender_email}").execute()
    messages = response.get('messages', [])

    if not messages:
        return f"No emails found from {sender_email}."
    else:
        # Get the first message from the list
        first_message = messages[0]

        # Assuming 'message_id' is obtained from the first message
        message_id = first_message['id']

        # Fetch the email details to get the 'payload'
        email_details = service.users().messages().get(userId='me', id=message_id).execute()

        # Access the 'payload' directly from the response
        payload = email_details['payload']

        # Extract subject
        subject = ""
        headers = payload.get('headers', [])
        for header in headers:
            if header['name'] == 'Subject':
                subject = header['value']
                break

        # Extract email body from different parts
        decoded_body = ""

        for part in payload.get('parts', []):
            if part['mimeType'] == 'text/plain':
                email_body_encoded = part['body']['data']
                decoded_body_bytes = base64.urlsafe_b64decode(email_body_encoded)
                decoded_body = quopri.decodestring(decoded_body_bytes).decode('utf-8')
                break  # Stop after finding the first text/plain part

        # If no body is found, set a default message
        if decoded_body == "":
            decoded_body = "No email body available."
    

        full_email =f"""
    Email Subject: {subject}

    {decoded_body}
    """

        return full_email
