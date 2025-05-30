# send_email_lambda.py (NEW Lambda Function)
import json
import boto3
import os
from botocore.exceptions import ClientError
from decimal import Decimal # Needed if processing data that might contain decimals

# Initialize clients
s3_client = boto3.client("s3")
ses_client = boto3.client("ses", region_name="us-east-1") # Ensure region matches your SES verification

# Configuration for the S3 bucket where user_emails.json is stored
# This should be your main bucket, e.g., "final-summer99d"
S3_CONFIG_BUCKET = "final-summer99d"
S3_USER_EMAILS_KEY = "config/user_email.json" # The key where user_email.json is stored

# --- SES Configuration ---
# This is the email address you verified in SES.
# IMPORTANT: Replace with YOUR verified sender email address in SES.
SENDER_EMAIL_ADDRESS = "samarneg@uchicago.edu" # Placeholder, user must replace this.


# Helper function to find user email from the loaded JSON list
def get_user_email_from_config(user_id, email_config_list):
    for entry in email_config_list:
        if entry.get("user_id") == user_id:
            return entry.get("email")
    return None

def lambda_handler(event, context):
    print(f"Received event for send_email_lambda: {json.dumps(event)}")

    # Extract data from the event payload (sent by rec_lambda)
    user_id = event.get("user_id")
    phase = event.get("phase")
    recommendations_list = event.get("recommendations_list") # Renamed from 'recommendations' to avoid confusion

    if not user_id or not phase or not recommendations_list:
        print("Error: Missing required data in event payload (user_id, phase, or recommendations_list).")
        return {
            'statusCode': 400,
            'body': json.dumps('Missing required data.')
        }

    # --- Step 1: Read user_emails.json from S3 ---
    user_emails_config = []
    try:
        response = s3_client.get_object(Bucket=S3_CONFIG_BUCKET, Key=S3_USER_EMAILS_KEY)
        user_emails_config_body = response['Body'].read().decode('utf-8')
        user_emails_config = json.loads(user_emails_config_body)
        print(f"Successfully loaded user emails config from s3://{S3_CONFIG_BUCKET}/{S3_USER_EMAILS_KEY}")
    except ClientError as e:
        print(f"Error loading user emails config from S3: {str(e)}. Cannot send emails.")
        # Return success for the Lambda, but indicate email skipped due to config issue
        return {
            "statusCode": 200,
            "body": json.dumps({"user_id": user_id, "status": "Email skipped (config load error)."})
        }
    except json.JSONDecodeError as e:
        print(f"Error decoding user emails config JSON: {str(e)}. Cannot send emails.")
        return {
            "statusCode": 200,
            "body": json.dumps({"user_id": user_id, "status": "Email skipped (config JSON error)."})
        }
    except Exception as e:
        print(f"Unexpected error loading user emails config: {str(e)}. Cannot send emails.")
        return {
            "statusCode": 200,
            "body": json.dumps({"user_id": user_id, "status": "Email skipped (unexpected config error)."})
        }

    # --- Step 2: Find the user's email address ---
    user_email = get_user_email_from_config(user_id, user_emails_config)

    if not user_email:
        print(f"Skipping email for user {user_id}: Email address not found in config file for this user_id.")
        # Return success for the Lambda, but indicate email skipped
        return {
            "statusCode": 200,
            "body": json.dumps({"user_id": user_id, "status": "Email skipped (address not found)."})
        }

    # --- Step 3: Send Recommendations via SES Email ---
    recommendations_html = "<ul>" + "".join([f"<li>{rec}</li>" for rec in recommendations_list]) + "</ul>"
    recommendations_text = "\\n".join([f"- {rec}" for rec in recommendations_list])

    subject = f"Your Daily Cycle Recommendations for Your {phase} Phase!"
    body_text = f"""
Dear {user_id},

Here are your personalized daily recommendations for your {phase} phase:

{recommendations_text}

Stay empowered!
Your Fem-Tech App Team
"""
    body_html = f"""
<html>
<head></head>
<body>
  <h1>Hello {user_id},</h1>
  <p>Here are your personalized daily recommendations for your <b>{phase}</b> phase:</p>
  {recommendations_html}
  <p>Stay empowered!</p>
  <p>Your Fem-Tech App Team</p>
</body>
</html>
"""

    try:
        response = ses_client.send_email(
            Source=SENDER_EMAIL_ADDRESS,
            Destination={'ToAddresses': [user_email]},
            Message={
                'Subject': {'Data': subject},
                'Body': {
                    'Text': {'Data': body_text},
                    'Html': {'Data': body_html}
                }
            }
        )
        print(f"Email sent successfully to {user_email} for user {user_id}. MessageId: {response['MessageId']}")
        email_status = f"Email sent to {user_email}."

    except ClientError as e:
        print(f"Error sending email to {user_email} for user {user_id}: {str(e)}")
        email_status = f"Email failed: {str(e)}"
    except Exception as e:
        print(f"Unexpected error in SES email sending for user {user_id}: {str(e)}")
        email_status = f"Email failed unexpectedly: {str(e)}"

    return {
        "statusCode": 200,
        "body": json.dumps({
            "user_id": user_id,
            "phase": phase,
            "recommendations": recommendations_list,
            "status": f"Recommendations sent, {email_status}"
        })
    }