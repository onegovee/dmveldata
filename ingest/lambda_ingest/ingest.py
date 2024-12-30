import boto3
from botocore.exceptions import ClientError
import urllib3
import os
import json
from datetime import datetime, timedelta, timezone

s3 = boto3.client('s3')
events = boto3.client('events')
lambda_client = boto3.client('lambda')

# Get environment variables
account_id = os.environ['ACCOUNT_ID']
bucket_name = os.environ['BUCKET_NAME']
repo_url = os.environ['REPO_URL']
repo_params = os.environ['REPO_PARAMS']
repo_secret_arn = os.environ['REPO_SECRET_ARN']
scheduler_rule_name = os.environ['SCHEDULER_RULE_NAME']
after_filter = os.environ['AFTER_FILTER']
before_filter = os.environ['BEFORE_FILTER']

# Defined runtime environment variables
# https://docs.aws.amazon.com/lambda/latest/dg/configuration-envvars.html#configuration-envvars-runtime
aws_session_token = os.environ['AWS_SESSION_TOKEN']
aws_default_region = os.environ['AWS_DEFAULT_REGION']

rate_limit_threshold = 64
timeout_threshold = 30000
last_processed_commit_key = "last-processed-commit.json"
http = urllib3.PoolManager()

# get secret using lambda extension
# https://community.aws/content/2fiemtp5A1NuweZ3yD8wpj7oYqy
def get_secret(secret_arn):
  headers = {"X-Aws-Parameters-Secrets-Token": aws_session_token}
  url = "http://localhost:2773/secretsmanager/get?secretId=" + secret_arn
  resp = http.request("GET", url, headers=headers)
  data = json.loads(resp.data)
  secret = data['SecretString']
  return secret

def get_page_url(link_header, page):
  links = link_header.split(", ")
  for link in links:
    rel = f'rel="{page}"'
    if rel in link:
      parts = link.split("; ")
      url = parts[0].strip("<>")
      return url
  return None

def get_raw_url(sha, headers):
  url = f"{repo_url}/commits/{sha}"
  resp = http.request("GET", url, headers=headers)
  data = json.loads(resp.data.decode())
  for file in data.get('files', []):
    filename = file['filename']
    if filename == "data/pricing.json":
      raw_url = file['raw_url']
      return filename, raw_url

def upload_to_s3(filename, sha, date, url):
  try:
    resp = http.request("GET", url)
  except Exception as error:
    raise error
  content = resp.data.decode()
  get_date = datetime.strptime(date, "%Y-%m-%dT%H:%M:%SZ")
  date_prefix = get_date.strftime("%Y/%m")
  prefix = f"{filename}/{date_prefix}/{sha}.json"
  for object in prefix, filename:
    s3.put_object(
      Bucket=bucket_name, 
      Key=object,
      Body=content,
      ContentType='application/json'
    )

def update_last_processed_commit(commit):
  s3.put_object(
    Bucket=bucket_name,
    Key=last_processed_commit_key,
    Body=json.dumps(commit),
    ContentType='application/json'
  )

def get_last_processed_commit():
  try:
    resp = s3.get_object(
      Bucket=bucket_name, 
      Key=last_processed_commit_key
    )
    return json.loads(resp['Body'].read().decode('utf-8'))
  except s3.exceptions.NoSuchKey:
    return None

def invoke_lambda_scheduler(function_name, function_arn, timestamp, next_invoke_reason):
  # Convert the UTC timestamp to a cron expression
  # https://docs.aws.amazon.com/eventbridge/latest/userguide/eb-scheduled-rule-pattern.html#eb-cron-expressions
  ts = timestamp
  cron_expression = f"cron({ts.minute} {ts.hour} {ts.day} {ts.month} ? {ts.year})"
  
  try:
    put_rule_resp = events.put_rule(
      Name=scheduler_rule_name,
      ScheduleExpression=cron_expression,
      State='ENABLED',
      Description=next_invoke_reason
    )
    event_rule_arn = put_rule_resp["RuleArn"]
    events.put_targets(
      Rule=scheduler_rule_name,
      Targets=[{"Id": function_name, "Arn": function_arn}],
    )
    print("Next invocation scheduled for", timestamp)
    # Lambda permissions may already exist so print the next invocation time before trying to add it
    lambda_client.add_permission(
      FunctionName=function_name,
      StatementId=scheduler_rule_name,
      Action="lambda:InvokeFunction",
      Principal="events.amazonaws.com",
      SourceArn=event_rule_arn,
    )
  except lambda_client.exceptions.ResourceConflictException:
    print("Lambda permission already exists")
    pass
  except ClientError as error:
    print(error.response['Error']['Message'])
  except Exception as error:
    print(error)

def lambda_handler(event, context):
  print(event)
  
  # Use context to get info about execution environment
  # https://docs.aws.amazon.com/lambda/latest/dg/python-context.html
  function_name = context.function_name
  function_arn = f"arn:aws:lambda:{aws_default_region}:{account_id}:function:{function_name}"
  
  token = get_secret(repo_secret_arn)

  headers = {
    "Authorization": f"Bearer {token}",
    "Accept": "application/vnd.github.v3+json",
  }
  
  params = json.loads(repo_params)
  last_processed_commit = get_last_processed_commit()
  if last_processed_commit: params["since"] = last_processed_commit['commit']['committer']['date']
  if after_filter: params["since"] = after_filter
  if before_filter: params["until"] = before_filter
  print(params)

  url = f"{repo_url}/commits?{urllib3.request.urlencode(params)}"
  resp = http.request("GET", url, headers=headers)
  page_links = resp.headers.get('link')
  if page_links:
    # do the last page first
    url = get_page_url(page_links, "last")
  
  count = 0
  while url:
    resp = http.request("GET", url, headers=headers)
    print(resp.headers)
    data = json.loads(resp.data.decode())
    if data:
      data.reverse()
      for commit in data:
        sha = commit['sha']
        date = commit['commit']['committer']['date']
        filename, raw_url = get_raw_url(sha, headers)
        upload_to_s3(filename, sha, date, raw_url)
        update_last_processed_commit(commit)
        print(sha)
        count += 1
    else:
      print('No data to process')
      return

    # going backwards, the next page is the prev page
    # set 'url' to the prev page if there is one
    # if there is none then you're on the last/first page
    page_links = resp.headers.get('link')
    if page_links:
      if 'rel="prev"' in page_links:
        url = get_page_url(page_links, "prev")
      else:
        break
    else:
      break
    
    requests_remaining = int(resp.headers['X-RateLimit-Remaining'])
    if requests_remaining <= rate_limit_threshold:
      print(resp.headers)
      print("Only", requests_remaining, "requests remaining in the current rate limit window.")
      # Round up to the next minute so the next scheduled invoke happens after the reset time
      rate_limit_reset_time = datetime.fromtimestamp(int(resp.headers['X-RateLimit-Reset']) + 60)
      invoke_lambda_scheduler(function_name, function_arn, rate_limit_reset_time, "Rate limit reset time")
      break
    
    time_remaining = context.get_remaining_time_in_millis()
    if time_remaining <= timeout_threshold:
      print("Only", time_remaining/1000, " seconds remaining before lambda times out.")
      next_invoke_time = datetime.now(timezone.utc) + timedelta(seconds=120)
      invoke_lambda_scheduler(function_name, function_arn, next_invoke_time, "Lambda timeout retry")
      break

  print('Processed', count, "commit/s")
  print('Last commit', sha, date)