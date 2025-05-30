# send_email_lambda.py (NEW Lambda Function - Using SNS for Email Sending)
import json
import boto3
import os
from botocore.exceptions import ClientError
from decimal import Decimal # Needed if processing data that might contain decimals

# Initialize clients
s3_client = boto3.client("s3")
sns_client = boto3.client("sns", region_name="us-east-1") # <--- Initialize SNS client

# Configuration for the S3 bucket where user_emails.json is stored
S3_CONFIG_BUCKET = "final-summer99d"
# IMPORTANT: Check your S3 key: is it user_email.json or user_emails.json?
# Based on previous context, it was 'user_emails.json'. Correcting here.
S3_USER_EMAILS_KEY = "config/user_email.json" 

# --- SNS Email Topic Configuration ---
# IMPORTANT: You MUST create this SNS Topic in the AWS Console (e.g., 'your-recommendation-email-topic')
# and subscribe the recipient email addresses to it.
# Replace with the actual ARN of your SNS topic.
# Example ARN: "arn:aws:sns:us-east-1:YOUR_ACCOUNT_ID:your-recommendation-email-topic"
SNS_EMAIL_TOPIC_ARN = "arn:aws:sns:us-east-1:544835564974:daily_recs" 


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
    recommendations_list = event.get("recommendations_list")

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
    # For SNS email, you subscribe the email address to the topic.
    # The publish is then done to the topic.
    # So, we just need to ensure the user_email is valid to proceed,
    # but the actual "To" address is handled by SNS subscriptions.
    # We'll still retrieve it for logging/confirmation.
    user_email_for_logging = get_user_email_from_config(user_id, user_emails_config)

    if not user_email_for_logging:
        print(f"Skipping email for user {user_id}: Email address not found in config file for this user_id.")
        return {
            "statusCode": 200,
            "body": json.dumps({"user_id": user_id, "status": "Email skipped (address not found)."})
        }

    # --- Step 3: Send Recommendations via SNS Publish to Topic ---
    recommendations_html = "<ul>" + "".join([f"<li>{rec}</li>" for rec in recommendations_list]) + "</ul>"
    recommendations_text = "\\n".join([f"- {rec}" for rec in recommendations_list])

    subject = f"Your Daily Cycle Recommendations for Your {phase} Phase!"
    
    # Message structure for SNS Email subscriptions
    sns_message = {
        "default": f"Dear {user_id}, Here are your personalized daily recommendations for your {phase} phase: {recommendations_text} Stay empowered! Your Fem-Tech App Team",
        "email": f"""
  Hello {user_id},
  Here are your personalized daily recommendations for your {phase} phase:
  {recommendations_html}
  Stay empowered!
  Cyclical
"""
    }

    try:
        response = sns_client.publish(
            TopicArn=SNS_EMAIL_TOPIC_ARN,
            Message=json.dumps(sns_message), # SNS expects a string here
            Subject=subject,
            MessageStructure='json' # This tells SNS the Message is a JSON string with different platform messages
        )
        print(f"Email sent successfully via SNS to topic {SNS_EMAIL_TOPIC_ARN} for user {user_id} (email: {user_email_for_logging}). MessageId: {response['MessageId']}")
        email_status = f"Email sent via SNS to topic {SNS_EMAIL_TOPIC_ARN}."

    except ClientError as e:
        print(f"Error sending email via SNS for user {user_id} (email: {user_email_for_logging}): {str(e)}")
        email_status = f"Email failed via SNS: {str(e)}"
    except Exception as e:
        print(f"Unexpected error in SNS email sending for user {user_id} (email: {user_email_for_logging}): {str(e)}")
        email_status = f"Email failed via SNS unexpectedly: {str(e)}"

    return {
        "statusCode": 200,
        "body": json.dumps({
            "user_id": user_id,
            "phase": phase,
            "recommendations": recommendations_list,
            "status": f"Recommendations sent, {email_status}"
        })
    }