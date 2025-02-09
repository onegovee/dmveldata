# https://expresslanes.com/learn-the-lanes#approximate-schedule
# When the 95 and 395 Express Lanes are open
# Weekdays:
#   Closed for reversal – 1am to 2:30am (except on Monday)
#   Open northbound – 2:30am to 11am
#   Closed for reversal – 11am to 1pm
#   Open southbound – 1pm to 1am
# Saturday:
#   Open southbound – 12am to 2pm
#   Closed for reversal – 2pm to 4pm
#   Open northbound – 4pm to 12am
# Sunday:
#   Open northbound – 12am Sunday to 12am Monday

import os
import urllib3
import json
import boto3
from twilio.rest import Client as TwilioClient
from twilio.base.exceptions import TwilioRestException
import re

s3 = boto3.client('s3')

# Get environment variables
bucket_name = os.environ['BUCKET_NAME']
status_url = os.environ['STATUS_URL']
status_key = os.environ['STATUS_KEY']
status_msg_from = os.environ['STATUS_MSG_FROM']
status_msg_to = os.environ['STATUS_MSG_TO']
msg_secret_arn = os.environ['MSG_SECRET_ARN']

# Defined runtime environment variables
aws_session_token = os.environ['AWS_SESSION_TOKEN']

def get_secret(secret_arn):
  http = urllib3.PoolManager()
  headers = {"X-Aws-Parameters-Secrets-Token": aws_session_token}
  url = "http://localhost:2773/secretsmanager/get?secretId=" + secret_arn
  resp = http.request("GET", url, headers=headers)
  data = json.loads(resp.data)
  secret = data['SecretString']
  return secret

def lambda_handler(event, context):
  print(event)

  s3_status_prefix = "lane-status.json"

  try:
    # get old lane status
    s3_get_resp = s3.get_object(
        Bucket=bucket_name, 
        Key=s3_status_prefix
      )
    s3_json = json.loads(s3_get_resp['Body'].read().decode('utf-8'))
    status = s3_json.get(status_key)
    print("Status:", status)

    # get updated lane status
    http = urllib3.PoolManager()
    resp = http.request("GET", status_url)
    status_body = resp.data.decode()
    status_json = json.loads(status_body)
    update = status_json.get(status_key, "Not available")
    print("Update:", update)

    if status and update != "Not available" and update != status:
      msg=f"Status updated from '{status}' to '{update}'"
      print(msg)
      s3_put_resp = s3.put_object(
        Bucket=bucket_name,
        Key=s3_status_prefix,
        Body=status_body,
        ContentType='application/json'
      )
      print(s3_put_resp)

      msg_secret = json.loads(get_secret(msg_secret_arn))
      msg_api_key = msg_secret['api_key']
      msg_api_secret = msg_secret['api_secret']
      msg_account_sid = msg_secret['account_sid']
      msg_client = TwilioClient(msg_api_key, msg_api_secret, msg_account_sid)

      recipient_format = r'^\+?[1-9]\d{1,14}$'
      recipient_list = status_msg_to.split(',')
      for recipient in recipient_list:
        if re.match(recipient_format, recipient):
          try:
            message = msg_client.messages.create(
              from_=status_msg_from,
              body=msg,
              to=recipient
            )
            print(message)
          except TwilioRestException as e:
            print("Twilio API error:", e)
          except Exception as e:
            print("Other exception:", e)
        else:
          print(recipient, "is not a valid recipient")
  
  except Exception as error:
    raise error