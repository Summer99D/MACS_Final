import json
import boto3
from decimal import Decimal
import os
from datetime import datetime # Needed for timestamp validation
from botocore.exceptions import ClientError

s3_client = boto3.client('s3')
lambda_client = boto3.client('lambda') # To invoke cat_lambda

# Define the name of the categorization Lambda function
CAT_LAMBDA_FUNCTION_NAME = 'cat_lambda'

def lambda_handler(event, context):
    print(f"Received event: {json.dumps(event)}")
    
    processed_count = 0
    skipped_count = 0

    # This Lambda is triggered by an S3 PutObject event.
    for record in event['Records']:
        if 's3' in record:
            bucket_name = record['s3']['bucket']['name']
            object_key = record['s3']['object']['key']
            print(f"Processing S3 object: s3://{bucket_name}/{object_key}")

            try:
                # Get object content from S3
                response = s3_client.get_object(Bucket=bucket_name, Key=object_key)
                body = response['Body'].read().decode('utf-8')
                print(f"S3 object content (first 200 chars): {body[:200]}...")
                
                try:
                    # Expecting a list of questionnaire objects in the S3 file
                    questionnaires = json.loads(body)
                except json.JSONDecodeError as e:
                    print(f"JSON decode error for s3://{bucket_name}/{object_key}: {str(e)}. Skipping object.")
                    skipped_count += 1
                    continue # Skip to the next S3 record if JSON is invalid
                
                if not isinstance(questionnaires, list):
                    print(f"Error: Expected a list of questionnaires in s3://{bucket_name}/{object_key}, but got {type(questionnaires)}. Skipping object.")
                    skipped_count += 1
                    continue

                print(f"Parsed {len(questionnaires)} questionnaires from {object_key}.")
                
                # Process each questionnaire in the list
                for idx, questionnaire in enumerate(questionnaires):
                    try:
                        # --- Validation Logic ---
                        time_elapsed = questionnaire.get('time_elapsed', 0)
                        user_id = questionnaire.get('user_id', '').strip()
                        timestamp = questionnaire.get('timestamp', '').strip()

                        is_valid = True
                        validation_reason = []

                        if not isinstance(time_elapsed, (int, float)) or time_elapsed < 5.0: # Changed min_time_elapsed to 5s as per earlier discussion
                            is_valid = False
                            validation_reason.append(f"Invalid time_elapsed={time_elapsed} (must be >= 5).")
                        
                        if not user_id:
                            is_valid = False
                            validation_reason.append("Missing user_id.")
                        
                        if not timestamp:
                            is_valid = False
                            validation_reason.append("Missing timestamp.")
                        else:
                            try:
                                # Ensure timestamp is in correct format (MMDDYYHHMMSS)
                                datetime.strptime(timestamp, "%m%d%y%H%M%S") 
                            except ValueError:
                                is_valid = False
                                validation_reason.append(f"Invalid timestamp format={timestamp} (expected MMDDYYHHMMSS).")
                        
                        responses = {k.lower(): v for k, v in questionnaire.get("responses", {}).items()}
                        if not responses:
                            is_valid = False
                            validation_reason.append("Responses object is empty.")
                        elif not all(q in responses for q in ["q1", "q2", "q3", "q4", "q5", "q6"]):
                            is_valid = False
                            validation_reason.append("Missing one or more core questions (q1-q6).")
                        else:
                            q5_data = responses.get("q5", {})
                            if not q5_data.get("symptoms") and not q5_data.get("additional"):
                                is_valid = False
                                validation_reason.append("Q5 is empty: No symptoms or additional comments provided.")  


                        if not is_valid:
                            full_reason = " ".join(validation_reason)
                            print(f"Skipping questionnaire {idx + 1} for user {user_id}: Invalid entry. Reason: {full_reason}")
                            skipped_count += 1
                            continue # Skip to the next questionnaire in the list

                        # --- If Valid, Invoke cat_lambda ---
                        print(f"Questionnaire {idx + 1} for user {user_id} is valid. Invoking {CAT_LAMBDA_FUNCTION_NAME}.")
                        
                        # Prepare payload for cat_lambda (should match what cat_lambda expects)
                        cat_lambda_payload = {
                            'user_id': user_id,
                            'timestamp': timestamp,
                            'time_elapsed': time_elapsed,
                            'responses': responses  # Normalized lowercase keys
}

                        lambda_client.invoke(
                            FunctionName=CAT_LAMBDA_FUNCTION_NAME,
                            InvocationType='Event', # Asynchronous invocation
                            Payload=json.dumps(cat_lambda_payload)
                        )
                        processed_count += 1

                    except Exception as e:
                        print(f"Error processing questionnaire {idx + 1} from {object_key}: {str(e)}. Skipping.")
                        skipped_count += 1

            except ClientError as e:
                print(f"S3 ClientError for object s3://{bucket_name}/{object_key}: {str(e)}")
            except Exception as e:
                print(f"An unexpected error occurred for S3 object s3://{bucket_name}/{object_key}: {str(e)}")
        else:
            print(f"Record does not contain S3 event data: {json.dumps(record)}")

    return {
        'statusCode': 200,
        'body': json.dumps(f'S3 object processing complete. Processed: {processed_count}, Skipped: {skipped_count} questionnaires.')
    }