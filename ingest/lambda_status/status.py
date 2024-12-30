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

bucket_name = os.environ['BUCKET_NAME']
status_url = os.environ['STATUS_URL']
status_key = os.environ['STATUS_KEY']
status_topic_arn = os.environ['STATUS_TOPIC_ARN']

s3 = boto3.client('s3')
sns = boto3.client('sns')

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
      sns_publish_resp = sns.publish(
        TopicArn=status_topic_arn,
        Message=msg
      )
      print(sns_publish_resp)
  
  except Exception as error:
    print(error)