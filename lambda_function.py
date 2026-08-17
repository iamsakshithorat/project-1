"""
EC2-CPU-AutoRemediation
------------------------
AWS Lambda function that automatically remediates high CPU utilization
on an EC2 instance by rebooting it, in response to a CloudWatch Alarm.

Trigger : CloudWatch Alarm (CPUUtilization > 70%)
Action  : Reboots the target EC2 instance if it is in a "running" state
Logging : All actions are written to CloudWatch Logs for auditing
"""

import boto3
import json
import logging

# Logger setup - automatically shows up in CloudWatch Logs
logger = logging.getLogger()
logger.setLevel(logging.INFO)

ec2_client = boto3.client('ec2')


def lambda_handler(event, context):
    logger.info("Event received: " + json.dumps(event))

    # Extract instance ID from the CloudWatch Alarm event (via SNS)
    try:
        alarm_data = event['Records'][0]['Sns']['Message']
        alarm_data = json.loads(alarm_data)
        instance_id = alarm_data['Trigger']['Dimensions'][0]['value']
        alarm_name = alarm_data['AlarmName']
    except (KeyError, IndexError):
        # Fallback for manual/direct testing (no SNS wrapper present)
        instance_id = "i-005f57b2c94dc02a2"  # <-- replace with your EC2 instance ID
        alarm_name = "Manual Test Trigger"

    logger.info(f"Alarm Triggered: {alarm_name}")
    logger.info(f"Target Instance: {instance_id}")

    try:
        # Check current instance state before taking action
        response = ec2_client.describe_instances(InstanceIds=[instance_id])
        state = response['Reservations'][0]['Instances'][0]['State']['Name']
        logger.info(f"Current instance state: {state}")

        if state == "running":
            # Core remediation action - reboot the instance
            ec2_client.reboot_instances(InstanceIds=[instance_id])
            logger.info(
                f"SUCCESS: Instance {instance_id} restart command sent "
                f"successfully due to high CPU alarm."
            )
            return {
                'statusCode': 200,
                'body': json.dumps(f'Instance {instance_id} restarted successfully.')
            }
        else:
            logger.info(f"Instance {instance_id} is not in running state. No action taken.")
            return {
                'statusCode': 200,
                'body': json.dumps(f'Instance {instance_id} not running, no action taken.')
            }

    except Exception as e:
        logger.error(f"ERROR: Failed to restart instance {instance_id}. Reason: {str(e)}")
        return {
            'statusCode': 500,
            'body': json.dumps(f'Error: {str(e)}')
        }