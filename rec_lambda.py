# rec_lambda.py (COMPLETE UPDATED VERSION - SMS Sending)

import json
import boto3
import os
from datetime import datetime
from botocore.exceptions import ClientError
from decimal import Decimal

# Initialize clients
dynamodb = boto3.resource("dynamodb")
s3 = boto3.client("s3")
sns_client = boto3.client("sns", region_name="us-east-1") # <--- Initialize SNS client

# Get environment variables (or define constants if not using env vars)
S3_BUCKET = "final-summer99d"
DYNAMO_TABLE_NAME = "CyclicalBetaSurvey"

# --- SNS SMS Configuration (Optional for SMS, but useful for setting attributes) ---
# You can set default SMS type (transactional/promotional) and sender ID in account settings
# or per publish call. For project, usually default is fine.

# Helper function for DynamoDB Decimal conversion
def convert_floats(obj):
    if isinstance(obj, float):
        return Decimal(str(obj))
    elif isinstance(obj, dict):
        return {k: convert_floats(v) for k, v in obj.items()}
    elif isinstance(obj, list):
        return [convert_floats(elem) for elem in obj]
    else:
        return obj

# Recommendation Generation Function
def generate_recommendations(phase):
    recs = {
        "Menstruation": [
            "Get plenty of rest and iron-rich foods like spinach and lentils.",
            "Do gentle yoga or stretching instead of high-intensity workouts.",
            "Stay hydrated and use heat pads for cramps."
        ],
        "Follicular": [
            "Try new activities; your brain is in a great learning state.",
            "Add lean protein and colorful vegetables to your meals.",
            "Great time for strength training or cardio workouts."
        ],
        "Ovulation": [
            "Eat zinc-rich foods like pumpkin seeds for hormone support.",
            "Socialize and schedule big meetings—confidence peaks now.",
            "Engage in high-intensity or group workouts."
        ],
        "Luteal": [
            "Eat magnesium-rich foods (dark chocolate, leafy greens) to ease PMS.",
            "Practice mindfulness or journaling to regulate mood.",
            "Switch to moderate exercise like pilates or walking."
        ],
        "Unknown": [
            "Unable to identify your phase. Try submitting again tomorrow.",
            "Make sure your responses are complete and accurate."
        ]
    }
    return recs.get(phase, recs["Unknown"])

def lambda_handler(event, context):
    print(f"Received event: {json.dumps(event)}")

    # Extract data from the event payload (sent by cat_lambda)
    user_id = event.get("user_id")
    timestamp = event.get("timestamp")
    responses = event.get("responses")
    time_elapsed = event.get("time_elapsed", 0)
    phase = event.get("phase")

    # --- Recommendation Generation ---
    recommendations_list = generate_recommendations(phase)
    # Format recommendations for SMS (keep concise for character limits)
    # SMS typically has 160 char limit for single message, longer messages are split.
    # We'll truncate for a safer example.
    recommendations_sms_text = "\\n".join([f"- {rec}" for rec in recommendations_list])
    # A short greeting + recommendations
    full_sms_message = f"Hello {user_id}! Your daily recs for {phase} phase:\\n{recommendations_sms_text}"
    # Truncate to ensure it fits in a single message or is predictably split
    full_sms_message = (full_sms_message[:150] + '...') if len(full_sms_message) > 150 else full_sms_message


    # For SMS, you'll need the user's phone number.
    # IMPORTANT: In a real application, you'd fetch the user's phone number from a user profile
    # database (e.g., another DynamoDB table) using the user_id.
    # For this project, you must replace the placeholder with a real phone number in E.164 format.
    # E.g., user_phone_number = "+12065550100" (for US)
    user_phone_number = "+15551234567" # <--- IMPORTANT: REPLACE THIS with a real test phone number!


    if not user_phone_number or user_phone_number == "+15551234567":
        print(f"Skipping SMS for user {user_id}: No valid recipient phone number configured or found.")
        # Proceed with saving data even if SMS cannot be sent
        sms_status = "SMS skipped (no valid number)."
    else:
        # --- Send Recommendations via SNS SMS ---
        try:
            response = sns_client.publish(
                PhoneNumber=user_phone_number,
                Message=full_sms_message,
                # Optional: specify SMS type and sender ID
                # MessageAttributes={
                #     'AWS.SNS.SMS.SMSType': {'DataType': 'String', 'StringValue': 'Transactional'},
                #     'AWS.SNS.SMS.SenderID': {'DataType': 'String', 'StringValue': 'YourAppId'} # Max 11 alphanumeric, not all countries support
                # }
            )
            print(f"SMS sent successfully to {user_phone_number} for user {user_id}. MessageId: {response['MessageId']}")
            sms_status = f"SMS sent to {user_phone_number}."

        except ClientError as e:
            print(f"Error sending SMS to {user_phone_number} for user {user_id}: {str(e)}")
            sms_status = f"SMS failed: {str(e)}"
        except Exception as e:
            print(f"Unexpected error in SNS SMS sending for user {user_id}: {str(e)}")
            sms_status = f"SMS failed unexpectedly: {str(e)}"


    # Prepare the complete result, including the recommendations for storage
    # This 'result' dictionary contains all data from the pipeline stages
    result = {
        "user_id": user_id,
        "timestamp": timestamp, # Primary key for DynamoDB
        "responses": responses, # Original survey responses
        "time_elapsed": time_elapsed,
        "phase": phase, # Categorized phase
        "recommendations": recommendations_list, # Generated recommendations
        "valid": True, # Assuming valid if it reached rec_lambda
        "sms_sent_status": sms_status # Add SMS status to the stored record
    }

    # Save to DynamoDB
    try:
        table = dynamodb.Table(DYNAMO_TABLE_NAME)
        safe_result = convert_floats(result) # Ensure any floats in responses are converted to Decimal
        table.put_item(Item=safe_result)
        print(f"Successfully saved to DynamoDB for user {user_id}.")
    except ClientError as e:
        print(f"Error writing to DynamoDB for user {user_id}: {str(e)}")
    except Exception as e:
        print(f"Unexpected error saving to DynamoDB for user {user_id}: {str(e)}")


    # Save to S3
    try:
        # Save the complete result as a JSON file in S3 under 'recommendations/' prefix
        s3_key = f"recommendations/{user_id}_{timestamp}.json"
        class DecimalEncoder(json.JSONEncoder):
            def default(self, obj):
                if isinstance(obj, Decimal):
                    return float(obj)
                return super(DecimalEncoder, self).default(obj)
        s3.put_object(
            Bucket=S3_BUCKET,
            Key=s3_key,
            Body=json.dumps(safe_result, cls=DecimalEncoder, indent=2) # Use safe_result for S3 as well
        )
        print(f"Successfully saved to S3 for user {user_id}.")
    except ClientError as e:
        print(f"Error writing to S3 for user {user_id}: {str(e)}")
    except Exception as e:
        print(f"Unexpected error saving to S3 for user {user_id}: {str(e)}")

    return {
        "statusCode": 200,
        "body": json.dumps({
            "user_id": user_id,
            "phase": phase,
            "recommendations": recommendations_list,
            "status": f"Processed, recommendations generated, saved, and {sms_status}"
        })
    }