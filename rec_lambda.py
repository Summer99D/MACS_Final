# rec_lambda.py (MODIFIED to invoke send_email_lambda)

import json
import boto3
import os
from datetime import datetime
from botocore.exceptions import ClientError
from decimal import Decimal

# Initialize clients
dynamodb = boto3.resource("dynamodb")
s3 = boto3.client("s3")
lambda_client = boto3.client("lambda") # <--- Add Lambda client to invoke send_email_lambda

# Get environment variables (or define constants if not using env vars)
S3_BUCKET = "final-summer99d"
DYNAMO_TABLE_NAME = "CyclicalBetaSurvey"

# Define the name of the new email sending Lambda function
SEND_EMAIL_LAMBDA_FUNCTION_NAME = "send_email_lambda"

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
    print(f"Received event for rec_lambda: {json.dumps(event)}")

    # Extract data from the event payload (sent by cat_lambda)
    user_id = event.get("user_id")
    timestamp = event.get("timestamp")
    responses = event.get("responses")
    time_elapsed = event.get("time_elapsed", 0)
    phase = event.get("phase")

    # --- Recommendation Generation ---
    recommendations_list = generate_recommendations(phase)

    # Prepare the complete result, including the recommendations for storage
    result = {
        "user_id": user_id,
        "timestamp": timestamp, # Primary key for DynamoDB
        "responses": responses, # Original survey responses
        "time_elapsed": time_elapsed,
        "phase": phase, # Categorized phase
        "recommendations": recommendations_list, # Generated recommendations
        "valid": True # Assuming valid if it reached rec_lambda
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

    # --- Invoke send_email_lambda ---
    # Pass the necessary data to the email sending Lambda
    email_payload = {
        "user_id": user_id,
        "phase": phase,
        "recommendations_list": recommendations_list # Use the generated list
    }
    try:
        response = lambda_client.invoke(
            FunctionName=SEND_EMAIL_LAMBDA_FUNCTION_NAME,
            InvocationType='Event', # Asynchronous invocation
            Payload=json.dumps(email_payload)
        )
        print(f"Invoked {SEND_EMAIL_LAMBDA_FUNCTION_NAME} for user {user_id}. Status code: {response['StatusCode']}")
    except ClientError as e:
        print(f"Error invoking {SEND_EMAIL_LAMBDA_FUNCTION_NAME} for user {user_id}: {str(e)}")
    except Exception as e:
        print(f"Unexpected error invoking {SEND_EMAIL_LAMBDA_FUNCTION_NAME} for user {user_id}: {str(e)}")


    return {
        "statusCode": 200,
        "body": json.dumps({
            "user_id": user_id,
            "phase": phase,
            "recommendations": recommendations_list,
            "status": "Processed, recommendations generated, saved, and email sending initiated."
        })
    }