import boto3
import urllib3
import os
import json
from datetime import datetime
from zoneinfo import ZoneInfo

s3 = boto3.client('s3')
events = boto3.client('events')

# Get environment variables
account_id = os.environ['ACCOUNT_ID']
bucket_name = os.environ['BUCKET_NAME']
repo_url = os.environ['REPO_URL']
repo_params = os.environ['REPO_PARAMS']
zone_info = os.environ['ZONE_INFO']
secret_arn = os.environ['SECRET_ARN']
after_filter = os.environ['AFTER_FILTER']
before_filter = os.environ['BEFORE_FILTER']

# Defined runtime environment variables
# https://docs.aws.amazon.com/lambda/latest/dg/configuration-envvars.html#configuration-envvars-runtime
aws_session_token = os.environ['AWS_SESSION_TOKEN']
aws_default_region = os.environ['AWS_DEFAULT_REGION']

rate_limit_threshold = 32
timeout_threshold = 30000
last_processed_commit_key = "last_processed_commit.json"
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
  s3.put_object(
    Bucket=bucket_name, 
    Key=prefix,
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

def schedule_lambda_invocation(lambda_arn, timestamp):
  # Convert the UTC timestamp to a cron expression
  dt = datetime.strptime(timestamp, "%Y-%m-%dT%H:%M:%SZ")
  cron_expression = f"cron({dt.minute} {dt.hour} {dt.day} {dt.month} ? {dt.year})"

  resp = events.put_rule(
    Name="invoke-ingest-lambda-scheduled-rule",
    ScheduleExpression=cron_expression,
    State='ENABLED',
    Description=f'Scheduled event rule to invoke ingest lambda at {timestamp}'
  )

def lambda_handler(event, context):
  function_name = context.function_name()
  function_arn = f"arn:aws:lambda:{aws_default_region}:{account_id}:function:{function_name}"
  # event_type = event.get('detail-type')
  
  token = get_secret(secret_arn)

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
      local_time = datetime.fromtimestamp(int(resp.headers['X-RateLimit-Reset']), tz=ZoneInfo(zone_info))
      print("Try again after", local_time, "local time")
      break
    
    time_remaining = context.get_remaining_time_in_millis()
    if time_remaining <= timeout_threshold:
      print("Only", time_remaining/1000, " seconds remaining. Re-invoke lambda to continue.")
      break

  print('Processed', count, "commit/s")
  print('Last commit', sha, date)
  

  

  

  

  
  

  
  

  
  
  
