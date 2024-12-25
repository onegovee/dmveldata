import os
import urllib3
import json
import hmac
import hashlib
import boto3
from botocore.exceptions import ClientError

# Get environment variables
hook_secret_arn = os.environ['HOOK_SECRET_ARN']
ingest_lambda_arn = os.environ['INGEST_LAMBDA_ARN']

# Defined runtime environment variables
# https://docs.aws.amazon.com/lambda/latest/dg/configuration-envvars.html#configuration-envvars-runtime
aws_session_token = os.environ['AWS_SESSION_TOKEN']
aws_default_region = os.environ['AWS_DEFAULT_REGION']

lambda_client = boto3.client('lambda')

# get secret using lambda extension
# https://community.aws/content/2fiemtp5A1NuweZ3yD8wpj7oYqy
def get_secret(secret_arn):
  http = urllib3.PoolManager()
  headers = {"X-Aws-Parameters-Secrets-Token": aws_session_token}
  url = "http://localhost:2773/secretsmanager/get?secretId=" + secret_arn
  resp = http.request("GET", url, headers=headers)
  data = json.loads(resp.data)
  secret = data['SecretString']
  return secret

def verify_signature(secret, payload, signature):
  encoded_secret = hmac.new(
    key=secret.encode(),
    msg=payload,
    digestmod=hashlib.sha256
  ).hexdigest()
  return hmac.compare_digest(f"sha256={encoded_secret}", signature)

def lambda_handler(event, context):
  print(event)

  # Get header from event and very signature if available
  payload = event["body"].encode("utf-8")
  headers = event.get("headers")
  signature = headers.get("X-Hub-Signature-256")

  # Create an event using payload data
  json_body = json.loads(event["body"])
  invoke_event = {}
  invoke_event['ref'] = json_body['ref']
  invoke_event['before'] = json_body['before']
  invoke_event['after'] = json_body['after']

  secret = get_secret(hook_secret_arn)
  
  if verify_signature(secret, payload, signature):
    if "pricing_updates" in json_body['ref']:
      try:
        invoke_lambda_response = lambda_client.invoke(
          FunctionName=ingest_lambda_arn,
          InvocationType='Event',
          Payload=json.dumps(invoke_event)
        )
      except ClientError as error:
        print(error)
        msg = error.response['Error']['Message']
        return {'statusCode': 500,'body': json.dumps(msg)}
      
      print(invoke_lambda_response)
      return {'statusCode': 200,'body': json.dumps('Success')}
    else:
      return {'statusCode': 202,'body': json.dumps('These are not the drones you\'re looking for')}
  else:
    return {'statusCode': 401,'body': json.dumps('Unauthorized')}