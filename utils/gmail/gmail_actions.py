from google.oauth2.credentials import Credentials
from google.auth.transport.requests import Request
from googleapiclient.discovery import build
from email.mime.text import MIMEText
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
    # Search for emails from the specific sender
    response = service.users().messages().list(userId='me', q=f"from:{sender_email}").execute()
    messages = response.get('messages', [])

    if not messages:
        print(f"No emails found from {sender_email}.")
    else:
        message_id = messages[0]['id']  # Get the first email ID from the sender

        # Retrieve the email details using the message ID
        email = service.users().messages().get(userId='me', id=message_id).execute()

        print(email)
        
        # fetch subject
        headers = email['payload']['headers']
        subject = next((header['value'] for header in headers if header['name'] == 'subject'), None)

        # fetch body
        email_body_encoded = email['payload']['body']['data']

        # Decode the Base64 encoded body and convert to readable text
        decoded_body_bytes = base64.urlsafe_b64decode(email_body_encoded)
        decoded_body = quopri.decodestring(decoded_body_bytes).decode('utf-8')

        full_email =f"""
                    Email Subject: {subject}

                    {decoded_body}
                    """

        return full_email


# def read_email_from_sender(service, sender_email: str):
#     try:
#         # Search for emails from the specific sender
#         response = service.users().messages().list(userId='me', q=f"from:{sender_email}").execute()
#         messages = response.get('messages', [])

#         if not messages:
#             print(f"No emails found from {sender_email}.")
#         else:
#             message_id = messages[0]['id']  # Get the first email ID from the sender

#             # Retrieve the email details using the message ID
#             email = service.users().messages().get(userId='me', id=message_id).execute()

#             # fetch subject
#             headers = email['payload']['headers']
#             subject = next((header['value'] for header in headers if header['name'] == 'subject'), None)

#             # fetch body
#             email_body_encoded = email['payload']['body']['data']

#             # Decode the Base64 encoded body and convert to readable text
#             decoded_body_bytes = base64.urlsafe_b64decode(email_body_encoded)
#             decoded_body = quopri.decodestring(decoded_body_bytes).decode('utf-8')

#             full_email =f"""
#                         Email Subject: {subject}

#                         {decoded_body}
#                         """

#             return full_email
#     except Exception as e:
#         print(f"Failed to read email: {e}")
