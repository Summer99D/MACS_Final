# cat_lambda.py (MODIFIED)
import json
import boto3
import os
from datetime import datetime
from botocore.exceptions import ClientError
from decimal import Decimal

# Initialize client for rec_lambda
lambda_client = boto3.client('lambda')

def lambda_handler(event, context):
    user_id = event.get("user_id")
    responses = event.get("responses")
    timestamp = event.get("timestamp")
    time_elapsed = event.get("time_elapsed", 0)

    # Parse and validate timestamp
    try:
        parsed_timestamp = datetime.strptime(timestamp, "%m%d%y%H%M%S")
    except Exception:
        print(f"Error: Invalid timestamp format for user {user_id}: {timestamp}")
        return {
            "user_id": user_id,
            "valid": False,
            "reason": "Invalid timestamp format"
        }

    # Categorize phase
    phase = classify_phase(responses)

    # Prepare data to send to rec_lambda
    rec_lambda_payload = {
        "user_id": user_id,
        "timestamp": timestamp,
        "responses": responses,
        "time_elapsed": time_elapsed,
        "phase": phase
    }

    # Invoke recommendation Lambda
    try:
        response = lambda_client.invoke(
            FunctionName='rec_lambda',  # Ensure this matches your rec_lambda function name
            InvocationType='Event',  # Asynchronous invocation
            Payload=json.dumps(rec_lambda_payload)
        )
        print(f"Invoked rec_lambda for user {user_id} with phase {phase}. Status code: {response['StatusCode']}")
    except ClientError as e:
        print(f"Error invoking rec_lambda for user {user_id}: {str(e)}")

    return {
        "statusCode": 200,
        "body": json.dumps({
            "user_id": user_id,
            "phase": phase,
            "status": "Processed and recommendation initiated."
        })
    }

def classify_phase(res):
    # (Phase classification logic - same as before)
    bleeding = res.get("q1")
    mucus = res.get("q2")
    libido = res.get("q3")
    mood = res.get("q4")
    symptoms = res.get("q5", [])
    energy = res.get("q6")

    menstruation_symptoms = ["Cramps", "Lower back pain", "Headache or migraine"]
    luteal_symptoms = ["Bloating", "Breast tenderness", "Breast fullness or swelling", "Digestive issues", "Acne or skin breakouts"]
    ovulation_symptoms = ["Feeling hot or flushed", "Egg-white consistency mucus", "High libido"]

    score = {"Menstruation": 0, "Luteal": 0, "Ovulation": 0, "Follicular": 0}

    if bleeding is not None:
        if bleeding >= 2:
            score["Menstruation"] += 3
        elif bleeding == 1:
            score["Luteal"] += 1

    if mucus is not None and libido is not None:
        if mucus == 4 or libido >= 4:
            score["Ovulation"] += 2
        elif mucus in [2, 3]:
            score["Follicular"] += 1

    if energy is not None:
        if energy in [1, 2]:
            score["Menstruation"] += 1
            score["Luteal"] += 1
        elif energy >= 4:
            score["Ovulation"] += 1
            score["Follicular"] += 1

    for symptom in symptoms:
        if symptom in menstruation_symptoms:
            score["Menstruation"] += 1
        elif symptom in luteal_symptoms:
            score["Luteal"] += 1
        elif symptom in ovulation_symptoms:
            score["Ovulation"] += 1

    assigned_phase = max(score, key=score.get)
    return assigned_phase