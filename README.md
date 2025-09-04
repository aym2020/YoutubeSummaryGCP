# YouTube Summary Project on GCP

## Overview
This project automates the process of summarizing the content of the latest YouTube videos from a specific channel and sending the summary via email. The project is implemented using Google Cloud Platform (GCP) services, including Cloud Functions and Secret Manager, along with Python and various libraries for integration.

## Key Components
- **Google Cloud Functions**: Serverless compute service used to execute the main script.
- **Google Secret Manager**: Securely stores and manages secrets such as API keys and credentials.
- **YouTube Data API**: Fetches the latest video information from a specific YouTube channel.
- **YouTube Transcript API**: Extracts the transcript of the video.
- **OpenAI API**: Summarizes the extracted transcript.
- **GCP Scheduler**: Schedules the function to run at specified intervals.
- **SMTP (Gmail)**: Sends the summarized content via email.

## Requirements
- Python 3.x
- Required Python libraries as specified in `requirements.txt`.

### Required Libraries
```plaintext
boto3==1.35.52
google-auth==2.35.0
httplib2==0.22.0
openai==1.54.4
requests==2.32.3
youtube-transcript-api>=1.2.2
