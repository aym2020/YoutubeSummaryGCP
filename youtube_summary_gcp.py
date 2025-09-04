import os
import json
import smtplib
import logging
import requests
from email.mime.text import MIMEText
from openai import OpenAI
from googleapiclient.discovery import build
from youtube_transcript_api import YouTubeTranscriptApi, TranscriptsDisabled, NoTranscriptFound 
from email.utils import COMMASPACE
from google.cloud import secretmanager

# Configure logging
logging.basicConfig(level=logging.INFO)

# Secrets
project_id = os.getenv("PROJECT_ID")

def access_secret(secret_id, project_id="green-diagram-440416-c4"):
    client = secretmanager.SecretManagerServiceClient()
    name = f"projects/{project_id}/secrets/{secret_id}/versions/latest"
    try:
        response = client.access_secret_version(name=name)
        secret_value = response.payload.data.decode("UTF-8")
        logging.info(f"Successfully accessed secret {secret_id}")
        return secret_value
    except Exception as e:
        logging.error(f"Error accessing secret {secret_id}: {str(e)}")
        raise

# Assign secrets to variables
try:
    YOUTUBE_API_KEY = access_secret("YOUTUBE_API_KEY")
    OPENAI_API_KEY = access_secret("OPENAI_API_KEY")
    SENDER_PASSWORD = access_secret("SENDER_PWD")
    CHANNEL_ID = access_secret("CHANNEL_ID")
    USERNAME_PROXY = access_secret("USERNAME_PROXY")
    PASSWORD_PROXY = access_secret("PASSWORD_PROXY")
except Exception as e:
    logging.error(f"Failed to load secrets: {e}")
    raise

# Proxy
url = 'https://ip.smartproxy.com/json'
username = USERNAME_PROXY
password = PASSWORD_PROXY
proxy = f"http://{username}:{password}@fr.smartproxy.com:40000"
proxies = {
    'http': proxy,
    'https': proxy
}

def test_proxy():
    test_url = 'https://ip.smartproxy.com/json'
    try:
        response = requests.get(test_url, proxies=proxies, timeout=10)
        if response.status_code == 200:
            logging.info("Proxy authentication successful.")
            logging.info("Proxy response: %s", response.text)
            return True
        else:
            logging.warning(f"Proxy test returned status code: {response.status_code}")
            return False
    except requests.exceptions.RequestException as e:
        logging.error(f"Proxy authentication failed: {e}")
        return False

client = OpenAI(api_key=OPENAI_API_KEY)
SENDER_EMAIL = "xxx@gmail.com"
RECIPIENT_EMAILS = ["xxx@gmail.com", "xxx@gmail.com"]
SMTP_SERVER = 'smtp.gmail.com'
SMTP_PORT = 587

def check_new_video():
    youtube = build('youtube', 'v3', developerKey=YOUTUBE_API_KEY)
    try:
        request = youtube.search().list(
            part='snippet',
            channelId=CHANNEL_ID,
            maxResults=1,
            order='date'
        )
        response = request.execute()
        latest_video = response['items'][0]
        return latest_video['id']['videoId'], latest_video['snippet']['title']
    except Exception as e:
        logging.error(f"Error checking for new video: {e}")
        raise

def is_new_video(video_id):
    # Create the secret manager client within this function
    client = secretmanager.SecretManagerServiceClient()
    last_video_id_secret = "LAST_VIDEO_ID"  # Secret name in GCP
    parent = f"projects/{project_id}/secrets/{last_video_id_secret}"
    
    try:
        # Fetch the latest version of the last_video_id secret
        last_video_id = access_secret(last_video_id_secret, project_id)
        
        # If it's the same video, skip processing
        if last_video_id == video_id:
            return False
        
        # Update the secret if it's a new video
        client.add_secret_version(
            parent=parent,
            payload={'data': video_id.encode("UTF-8")}
        )
        logging.info(f"Updated last_video_id secret with new video ID: {video_id}")
        return True
    except Exception as e:
        logging.error(f"Error accessing or updating last_video_id in Secret Manager: {e}")
        raise

def get_transcript(video_id, video_title):
    try:
        ytt_api = YouTubeTranscriptApi(proxies=proxies) 
        fetched = ytt_api.fetch(video_id)
        transcript = fetched.to_raw_data()

        full_text = ' '.join([item['text'] for item in transcript])

        # Save the transcript to a text file
        with open('/tmp/transcript.txt', 'w') as file:
            file.write(full_text)

        logging.info(f"Transcript successfully retrieved for video: {video_title}")
        return full_text

    except TranscriptsDisabled:
        error_message = f"Transcripts are disabled for the video: {video_title} (ID: {video_id})"
        logging.error(error_message)
        send_error_email(error_message, video_title)
        return None

    except NoTranscriptFound:
        error_message = f"No transcript found for the video: {video_title} (ID: {video_id})"
        logging.error(error_message)
        send_error_email(error_message, video_title)
        return None

    except Exception as e:
        error_message = f"An error occurred while fetching the transcript for video: {video_title} (ID: {video_id}). Error: {str(e)}"
        logging.error(error_message)
        send_error_email(error_message, video_title)
        return None

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
    summary = chat_completion.choices[0].message.content
    return summary.replace("```html", "").replace("```", "").strip()

def send_email(subject, body):
    msg = MIMEText(body, 'html')
    msg['Subject'] = subject
    msg['From'] = SENDER_EMAIL
    msg['To'] = COMMASPACE.join(RECIPIENT_EMAILS)
    
    with smtplib.SMTP(SMTP_SERVER, SMTP_PORT) as server:
        server.starttls()
        server.login(SENDER_EMAIL, SENDER_PASSWORD)
        server.sendmail(SENDER_EMAIL, RECIPIENT_EMAILS, msg.as_string())

def send_error_email(error_message, video_title):
    subject = f"Error: Failed to get transcript for video - {video_title}"
    body = f"""
    <html>
    <body>
    <h2>Error in YouTube Summary Function</h2>
    <p>{error_message}</p>
    <p>Please check the function logs for more details.</p>
    </body>
    </html>
    """
    try:
        send_email(subject, body)
        logging.info("Error notification email sent successfully.")
    except Exception as e:
        logging.error(f"Failed to send error notification email: {str(e)}")

def main(event, context):
    # Test proxy before starting the main function logic
    if not test_proxy():
        logging.error("Proxy connection failed. Aborting function execution.")
        return

    try:
        video_id, video_title = check_new_video()
        
        if is_new_video(video_id):
            logging.info(f"New video detected: {video_title}")
            
            transcript = get_transcript(video_id, video_title)
            if transcript:
                summary = summarize_with_gpt('/tmp/transcript.txt')
                send_email(f"[GCP] Résumé de la dernière vidéo: {video_title}", summary)
                logging.info("Summary email sent successfully!")
            else:
                logging.warning("Skipping summary generation due to missing transcript.")
        else:
            logging.info("No new video detected.")
            send_email("[GCP] Pas de nouvelle vidéo", "Il n'y a pas de nouvelle vidéo pour aujourd'hui.")
            logging.info("No new video email sent.")
    except Exception as e:
        logging.error(f"An error occurred in the main function: {str(e)}")
        send_error_email(f"[GCP] An error occurred in the main function: {str(e)}", "Unknown Video")