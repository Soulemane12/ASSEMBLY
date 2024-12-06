import datetime
import assemblyai as aai
from dotenv import load_dotenv
import os
import re
import json

# Load environment variables from .env file
load_dotenv()

# Get the API key from the environment
api_key = os.getenv("ASSEMBLYAI_API_KEY")

if not api_key:
    raise ValueError("API key is not set. Please check your .env file.")

aai.settings.api_key = api_key
transcriber = aai.Transcriber()

# Function to transcribe speech
def transcribe_audio(audio_url):
    """
    Transcribes an audio file from a URL using AssemblyAI.
    """
    try:
        print("Transcribing audio...")
        transcript = transcriber.transcribe(audio_url)
        if transcript.status == aai.TranscriptStatus.error:
            print(f"Transcription failed: {transcript.error}")
            return None
        return transcript
    except Exception as e:
        print(f"Transcription error: {e}")
        return None

# Function to extract task details using LLM
def extract_task_details_llm(transcript_obj):
    """
    Extracts structured task details (task, with_whom, time, location, agenda, duration, participants) from transcript using an LLM.
    Attempts to infer or fill in missing details where possible.
    """
    prompt = (
        "Understand the following text and extract structured information about a task. "
        "Return only a JSON object with the following fields: "
        "'task', 'with_whom', 'time', 'location', 'agenda', 'duration', 'participants'. "
        "If any field is not mentioned in the text, set it to 'N/A'. "
        "Do not include any additional text or explanations.\n\n"
        f"Text: {transcript_obj.text}\n\n"
        "Response:"
    )

    try:
        print("Enhancing understanding with LLM...")
        result = transcript_obj.lemur.task(
            prompt, final_model=aai.LemurModel.claude3_5_sonnet
        )
        
        # Log raw response
        print("Raw LLM Response:", result.response)

        # Ensure response is JSON formatted
        try:
            structured_response = json.loads(result.response)
            # Replace any None values with 'N/A'
            for key, value in structured_response.items():
                if value is None:
                    structured_response[key] = "N/A"
            return structured_response
        except json.JSONDecodeError:
            print("Response is not in JSON format. Parsing manually.")
            structured_response = parse_text_response(result.response)
            # Replace any None values with 'N/A'
            for key, value in structured_response.items():
                if value is None:
                    structured_response[key] = "N/A"
            return structured_response
    except Exception as e:
        print("LLM processing failed:", e)
        return None

# Define the parse_text_response function
def parse_text_response(response_text):
    """
    Parses a response text to extract structured data when JSON decoding fails.
    This is a simple implementation and may need to be tailored based on your LLM's output.
    """
    try:
        # Find the start of the JSON object
        json_start = response_text.find('{')
        if json_start == -1:
            print("No JSON object found in the response.")
            return {}

        json_str = response_text[json_start:]
        # Remove any trailing characters after the JSON object
        json_end = json_str.rfind('}') + 1
        json_str = json_str[:json_end]

        data = json.loads(json_str)
        # Replace any None values with 'N/A'
        for key, value in data.items():
            if value is None:
                data[key] = "N/A"
        return data
    except Exception as e:
        print(f"Error parsing text response: {e}")
        return {}

# Function to validate and format time input
def validate_time(time_str):
    """
    Validates and formats the time string.
    """
    if not time_str:
        print("No time provided. Setting to 'N/A'.")
        return "N/A"
    
    if isinstance(time_str, str) and time_str.strip().upper() == "N/A":
        # Recognize 'N/A' as a valid default and skip validation
        return "N/A"
    
    time_pattern = re.compile(r'^(1[0-2]|0?[1-9]):([0-5][0-9])\s?(AM|PM|am|pm)$')
    match = time_pattern.match(time_str)
    if match:
        # Convert to uppercase for consistency
        hour = int(match.group(1))
        minute = match.group(2)
        period = match.group(3).upper()
        return f"{hour}:{minute} {period}"
    else:
        print("Invalid time format detected in the LLM response. Setting to 'N/A'.")
        return "N/A"

def get_field_value(field_value, field_name):
    """
    Returns the field value if present; otherwise, returns 'N/A'.
    """
    if not field_value:
        print(f"No {field_name} provided. Setting to 'N/A'.")
        return "N/A"
    return field_value

def prompt_for_missing_fields(task_details):
    """
    Prompts the user to input missing fields that are set to 'N/A'.
    """
    fields_to_prompt = ['time', 'location', 'agenda', 'duration', 'participants']
    for field in fields_to_prompt:
        if task_details.get(field) == "N/A":
            user_input = input(f"Please provide the {field} for the task '{task_details.get('task', 'N/A')}' (or type 'skip' to leave as 'N/A'): ").strip()
            if user_input.lower() != 'skip' and user_input:
                # Optionally, enhance the user input using LLM
                enhanced_input = enhance_input_with_llm(field, user_input)
                task_details[field] = enhanced_input
            else:
                print(f"Leaving {field} as 'N/A'.")
    return task_details

def enhance_input_with_llm(field, user_input):
    """
    Enhances the user's input using the LLM to ensure consistency and quality.
    """
    prompt = (
        f"Improve the following {field} information for a calendar event:\n\n"
        f"Original {field}: {user_input}\n\n"
        "Enhanced:"
    )
    
    try:
        print(f"Enhancing the {field} with LLM...")
        # Adjust the method based on AssemblyAI's API for LLM interaction
        # This is a placeholder and may need to be modified
        response = aai.LemurModel.claude3_5_sonnet.complete(prompt)
        enhanced_response = response.text.strip()
        print(f"Enhanced {field}: {enhanced_response}")
        return enhanced_response
    except Exception as e:
        print(f"Failed to enhance {field} with LLM: {e}")
        return user_input  # Fallback to original input if enhancement fails

# Function to add task to a calendar
def add_task_to_calendar(task_details):
    """
    Creates a formatted calendar event representation of the extracted task details.
    """
    # Validate and format the time field if possible
    task_details['time'] = validate_time(task_details.get('time', 'N/A'))
    
    # Handle other fields
    task_details['with_whom'] = get_field_value(task_details.get('with_whom'), 'with_whom')
    task_details['location'] = get_field_value(task_details.get('location'), 'location')
    task_details['agenda'] = get_field_value(task_details.get('agenda'), 'agenda')
    task_details['duration'] = get_field_value(task_details.get('duration'), 'duration')
    
    # Ensure participants is a list and not empty
    participants = task_details.get('participants', [])
    if isinstance(participants, str):
        participants = [participant.strip() for participant in participants.split(',') if participant.strip()]
    if not participants:
        participants = ["N/A"]
    task_details['participants'] = participants
    
    print("\n=== Calendar Event ===")
    print(f"Task: {task_details.get('task', 'N/A')}")
    print(f"With Whom: {task_details.get('with_whom', 'N/A')}")
    print(f"Time: {task_details.get('time', 'N/A')}")
    print(f"Location: {task_details.get('location', 'N/A')}")
    print(f"Agenda: {task_details.get('agenda', 'N/A')}")
    print(f"Duration: {task_details.get('duration', 'N/A')}")
    print(f"Participants: {', '.join(task_details.get('participants', ['N/A']))}")
    print("======================")

# Main Function
def main(audio_url):
    # Step 1: Transcribe audio
    transcript_obj = transcribe_audio(audio_url)
    if not transcript_obj:
        print("Failed to transcribe audio.")
        return

    print(f"\nTranscript:\n{transcript_obj.text}")

    # Step 2: Extract task details using LLM
    task_details = extract_task_details_llm(transcript_obj)
    if not task_details:
        print("Failed to extract task details.")
        return

    print("\nExtracted Task Details:")
    print(json.dumps(task_details, indent=2))

    # Step 3: Prompt user for missing fields
    task_details = prompt_for_missing_fields(task_details)

    print("\nUpdated Task Details:")
    print(json.dumps(task_details, indent=2))

    # Step 4: Add to calendar or create a representation
    add_task_to_calendar(task_details)

# Example Usage
if __name__ == "__main__":
    # List of audio files to process
    audio_files = ["audio2.wav"]
    
    for audio_file in audio_files:
        print(f"\nProcessing file: {audio_file}\n{'='*30}")
        # Assuming audio_url is a valid URL or file path accessible by AssemblyAI
        main(audio_file)
