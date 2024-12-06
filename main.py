import os
import json
import datetime
from dotenv import load_dotenv
import assemblyai as aai
from google.oauth2.credentials import Credentials
from google_auth_oauthlib.flow import InstalledAppFlow
from google.auth.transport.requests import Request  # Ensure this import exists
from googleapiclient.discovery import build
import pytz  # For timezone handling

# Load environment variables from .env file
load_dotenv()

# AssemblyAI Setup
ASSEMBLYAI_API_KEY = os.getenv("ASSEMBLYAI_API_KEY")
if not ASSEMBLYAI_API_KEY:
    raise ValueError("AssemblyAI API key not set. Please check your .env file.")

aai.settings.api_key = ASSEMBLYAI_API_KEY
transcriber = aai.Transcriber()

# Google Calendar API Setup
SCOPES = ['https://www.googleapis.com/auth/calendar']
GOOGLE_CLIENT_SECRET_FILE = os.getenv("GOOGLE_CLIENT_SECRET_FILE")
if not GOOGLE_CLIENT_SECRET_FILE:
    raise ValueError("Google client secret file path not set. Please check your .env file.")

def authenticate_google_calendar():
    """Authenticate and return the Google Calendar service."""
    creds = None
    # Token file stores the user's access and refresh tokens
    if os.path.exists('token.json'):
        creds = Credentials.from_authorized_user_file('token.json', SCOPES)
    # If no valid credentials, let the user log in
    if not creds or not creds.valid:
        if creds and creds.expired and creds.refresh_token:
            creds.refresh(Request())  # Ensure 'Request' is imported
        else:
            flow = InstalledAppFlow.from_client_secrets_file(
                GOOGLE_CLIENT_SECRET_FILE, SCOPES
            )
            creds = flow.run_local_server(port=8080)  # Use fixed port
        # Save the credentials for next time
        with open('token.json', 'w') as token:
            token.write(creds.to_json())

    service = build('calendar', 'v3', credentials=creds)
    return service

def transcribe_audio(audio_file_path):
    """
    Transcribes an audio file from a local path using AssemblyAI.
    """
    try:
        print("Transcribing audio...")
        transcript = transcriber.transcribe(audio_file_path)
        transcript = transcript.wait_for_completion()
        if transcript.status == aai.TranscriptStatus.error:
            print(f"Transcription failed: {transcript.error}")
            return None
        return transcript
    except Exception as e:
        print(f"Transcription error: {e}")
        return None

def extract_task_details_llm(transcript_text):
    """
    Extracts structured task details (task, with_whom, time) from transcript using an LLM.
    """
    prompt = (
        "Understand the following text and extract structured information about a task. "
        "Return only a JSON object with the following fields: 'task', 'with_whom', and 'time'. "
        "Do not include any additional text or explanations.\n\n"
        f"Text: {transcript_text}\n\n"
        "Response:"
    )

    try:
        print("Enhancing understanding with LLM...")
        # Placeholder for LLM processing
        # Replace this with actual LLM integration as per your setup
        # For demonstration, using a mock response
        # Example: Using OpenAI's GPT-3.5 API
        # Here, we simulate the response
        mock_response = {
            "task": "Meeting with John",
            "with_whom": "John",
            "time": "2024-12-07T15:00:00-05:00"  # ISO format with timezone
        }
        return mock_response
    except Exception as e:
        print("LLM processing failed:", e)
        return None

def parse_time(time_str):
    """
    Parses time string into a timezone-aware datetime object.
    """
    try:
        # Parse the ISO format time string with timezone information
        return datetime.datetime.fromisoformat(time_str)
    except ValueError as ve:
        print(f"Time parsing error: {ve}")
        raise

def add_event_to_calendar(service, task_details):
    """
    Adds an event to Google Calendar without checking for conflicts.
    """
    try:
        task = task_details.get("task", "No task specified")
        with_whom = task_details.get("with_whom", "Not specified")
        time_str = task_details.get("time", None)

        if not time_str:
            print("No time provided for the event.")
            return

        start_time = parse_time(time_str)
        # Assuming a default duration of 1 hour if not specified
        end_time = start_time + datetime.timedelta(hours=1)

        # Define the event with timezone-aware datetime objects
        event = {
            'summary': task,
            'description': f"With: {with_whom}",
            'start': {
                'dateTime': start_time.isoformat(),
                'timeZone': str(start_time.tzinfo) if start_time.tzinfo else 'UTC',
            },
            'end': {
                'dateTime': end_time.isoformat(),
                'timeZone': str(end_time.tzinfo) if end_time.tzinfo else 'UTC',
            },
        }

        created_event = service.events().insert(calendarId='primary', body=event).execute()
        print(f"Event created: {created_event.get('htmlLink')}")
    except Exception as e:
        print(f"Error adding event to calendar: {e}")

def display_upcoming_events(service, max_results=10):
    """
    Displays upcoming events from Google Calendar.
    """
    try:
        print("\nYour Upcoming Events:")
        now = datetime.datetime.now(datetime.timezone.utc).isoformat()
        events_result = service.events().list(
            calendarId='primary',
            timeMin=now,
            maxResults=max_results,
            singleEvents=True,
            orderBy='startTime'
        ).execute()
        events = events_result.get('items', [])

        if not events:
            print("No upcoming events found.")
            return

        for event in events:
            start = event['start'].get('dateTime', event['start'].get('date'))
            print(f"- {event['summary']} at {start}")
    except Exception as e:
        print(f"Error fetching upcoming events: {e}")

def main(audio_file_path):
    # Step 1: Transcribe audio
    transcript_obj = transcribe_audio(audio_file_path)
    if not transcript_obj:
        print("Failed to transcribe audio.")
        return

    transcript_text = transcript_obj.text
    print(f"\nTranscript:\n{transcript_text}")

    # Step 2: Extract task details using LLM
    task_details = extract_task_details_llm(transcript_text)
    if not task_details:
        print("Failed to extract task details.")
        return

    print("\nExtracted Task Details:")
    print(json.dumps(task_details, indent=2))

    # Step 3: Authenticate with Google Calendar
    service = authenticate_google_calendar()

    # Step 4: Add event to calendar without conflict checking
    add_event_to_calendar(service, task_details)

    # Step 5: Display updated schedule
    display_upcoming_events(service)

if __name__ == "__main__":
    # Example Usage
    # Replace 'your_audio_file.wav' with the actual path to your local audio file
    audio_file_path = "audio.wav"
    main(audio_file_path)
