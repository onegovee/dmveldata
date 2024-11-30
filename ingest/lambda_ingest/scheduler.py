import boto3
from datetime import datetime

eventbridge = boto3.client('events')
lambda_client = boto3.client('lambda')

RULE_NAME = "InvokeLambdaAtFutureTime"

def schedule_lambda_invocation(lambda_arn, future_timestamp):
    # Convert the UTC timestamp to a cron expression
    cron_expression = convert_to_cron(future_timestamp)

    # Check if the rule already exists
    rule_arn = create_or_update_event_rule(cron_expression, future_timestamp)

    # Update or add the Lambda function as the target
    eventbridge.put_targets(
        Rule=RULE_NAME,
        Targets=[
            {
                'Id': '1',
                'Arn': lambda_arn
            }
        ]
    )

    # Ensure EventBridge has permission to invoke the Lambda function
    ensure_permission(lambda_arn, rule_arn)

    print(f"Scheduled Lambda invocation for {future_timestamp} using rule '{RULE_NAME}'.")

def create_or_update_event_rule(cron_expression, future_timestamp):
    """
    Create or update the EventBridge rule with the new schedule expression.
    """
    try:
        # Attempt to update the existing rule
        response = eventbridge.put_rule(
            Name=RULE_NAME,
            ScheduleExpression=cron_expression,
            State='ENABLED',
            Description=f'Updated schedule for Lambda at {future_timestamp}'
        )
    except eventbridge.exceptions.ResourceNotFoundException:
        # If the rule does not exist, create it
        response = eventbridge.put_rule(
            Name=RULE_NAME,
            ScheduleExpression=cron_expression,
            State='ENABLED',
            Description=f'Schedule for Lambda at {future_timestamp}'
        )

    return response['RuleArn']

def ensure_permission(lambda_arn, rule_arn):
    """
    Add or update permission for EventBridge to invoke the Lambda function.
    """
    try:
        lambda_client.add_permission(
            FunctionName=lambda_arn,
            StatementId='EventBridgeInvokePermission',
            Action='lambda:InvokeFunction',
            Principal='events.amazonaws.com',
            SourceArn=rule_arn
        )
    except lambda_client.exceptions.ResourceConflictException:
        # Permission already exists, no need to update
        pass

def convert_to_cron(future_timestamp):
    """
    Convert a UTC timestamp to a cron expression.
    AWS cron format: cron(Minutes Hours Day Month Day-of-week Year)
    Example input: '2024-12-01T15:00:00Z'
    Example output: 'cron(0 15 1 12 ? 2024)'
    """
    dt = datetime.strptime(future_timestamp, "%Y-%m-%dT%H:%M:%SZ")
    return f"cron({dt.minute} {dt.hour} {dt.day} {dt.month} ? {dt.year})"
