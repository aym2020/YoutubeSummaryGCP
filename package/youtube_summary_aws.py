import os
import json
import smtplib
from email.mime.text import MIMEText
from openai import OpenAI
from googleapiclient.discovery import build
from youtube_transcript_api import YouTubeTranscriptApi
from email.utils import COMMASPACE
import boto3

# Initialize the AWS Secrets Manager client
def get_secrets():
    secret_name = "YouTubeSummaryAPIs"  # Change to your secret's name
    region_name = "eu-central-1"  # Change to your AWS region

    # Create a Secrets Manager client
    client = boto3.client('secretsmanager', region_name=region_name)

    # Fetch the secret
    response = client.get_secret_value(SecretId=secret_name)
    secrets = json.loads(response['SecretString'])
    return secrets

# Load secrets
secrets = get_secrets()

# Assign secrets to variables
YOUTUBE_API_KEY = secrets["YOUTUBE_API_KEY"]
OPENAI_API_KEY  = secrets["OPENAI_API_KEY"]
SENDER_PASSWORD = secrets["SENDER_PWD"]
CHANNEL_ID      = secrets["CHANNEL_ID"]

client = OpenAI(api_key=OPENAI_API_KEY)
SENDER_EMAIL = "ay.mislah@gmail.com"
RECIPIENT_EMAILS = ["ay.mislah@gmail.com", "bastien.burgard@gmail.com"]
SMTP_SERVER = 'smtp.gmail.com'
SMTP_PORT = 587

def check_new_video():
    youtube = build('youtube', 'v3', developerKey=YOUTUBE_API_KEY)
    
    # Get the latest video from the creator
    request = youtube.search().list(
        part='snippet',
        channelId=CHANNEL_ID,
        maxResults=1,
        order='date'
    )
    
    response = request.execute()
    latest_video = response['items'][0]
    video_id = latest_video['id']['videoId']
    video_title = latest_video['snippet']['title']

    return video_id, video_title

def is_new_video(video_id):
    video_id_file = '/home/rhodes/Desktop/YoutubeSummary/last_video_id.json'
    
    # Check if the file exists and has valid content
    if os.path.exists(video_id_file):
        try:
            with open(video_id_file, 'r') as file:
                last_video = json.load(file)
                # If the last video ID matches, return False (no new video)
                if last_video.get('video_id') == video_id:
                    return False
        except (json.JSONDecodeError, ValueError):
            print("Error reading JSON. The file might be corrupted or empty.")
    else:
        print(f"No previous video ID found, creating new file: {video_id_file}")

    # If no valid last video ID is found, save the current video ID and return True
    with open(video_id_file, 'w') as file:
        json.dump({'video_id': video_id}, file)
    
    return True

def get_transcript(video_id):
    transcript = YouTubeTranscriptApi.get_transcript(video_id)
    full_text = ' '.join([item['text'] for item in transcript])
    
    # Save the transcript to a text file
    with open('transcript.txt', 'w') as file:
        file.write(full_text)
    
    return full_text

def summarize_with_gpt(file_path):
    # Read the transcript from the file
    with open(file_path, 'r') as file:
        transcript = file.read()

# Use GPT to summarize the transcript with the new OpenAI client
def summarize_with_gpt(file_path):
    with open(file_path, 'r') as file:
        transcript = file.read()

    chat_completion = client.chat.completions.create(
        messages=[
            {
                "role": "user",
                "content": (
                    f"Please summarize the following YouTube video transcript with a focus on securities portfolio management. "
                    f"Highlight the key numbers, trends, and critical information relevant to investment decisions. Speak about every company mentioned in the transcript"
                    f"Format the response as an HTML email with:\n"
                    f"- A title in <h2> format\n"
                    f"- Key points structured as a bullet-point list with a title for each key point using <ul> and <li> tags\n"
                    f"- Important numbers, percentages, and trends in <strong> bold </strong> using <strong> tags\n"
                    f"- A detailed analysis for each key point, ensuring it's not too short, so it helps someone make informed decisions\n"
                    f"- A final section with recommendations, structured as bullet points, each recommendation starting with a title in bold, followed by a clear explanation\n"
                    f"Ensure no markdown or special characters are used. The output must be directly in HTML format, and only in French.\n\n"
                    f"Transcript:\n{transcript}"
                ),
            }
        ],
        model="gpt-4o",
    )
    # Remove Markdown code block delimiters if present
    summary = chat_completion.choices[0].message.content
    summary = summary.replace("```html", "").replace("```", "").strip()

    return summary

# Function to send the email with proper HTML formatting
def send_email(subject, body):
    # Create the HTML email content
    msg = MIMEText(body, 'html')
    msg['Subject'] = subject
    msg['From'] = SENDER_EMAIL
    msg['To'] = COMMASPACE.join(RECIPIENT_EMAILS)  # Join multiple recipients with a comma

    # Send the email
    with smtplib.SMTP(SMTP_SERVER, SMTP_PORT) as server:
        server.starttls()
        server.login(SENDER_EMAIL, SENDER_PASSWORD)
        server.sendmail(SENDER_EMAIL, RECIPIENT_EMAILS, msg.as_string())

if __name__ == "__main__":
    video_id, video_title = check_new_video()
    
    # Check if the video is new
    if is_new_video(video_id):
        print(f"New video detected: {video_title}")
        
        transcript = get_transcript(video_id)
        
        # Summarize the transcript with HTML formatting and in French, without markdown
        summary = summarize_with_gpt('transcript.txt')   
        
        # Send the formatted summary as an HTML email
        send_email(f"Résumé de la dernière vidéo: {video_title}", summary)
        
        print("Email sent successfully!")
    else:
        print("No new video detected.")
        # Send email notifying no new video
        send_email("Pas de nouvelle vidéo", "Il n'y a pas de nouvelle vidéo pour aujourd'hui.")
        print("No new video email sent.")

