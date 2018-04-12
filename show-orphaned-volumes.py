#!/usr/bin/env   python 

## This is a lambda function, using Python 2.7
## The function looks for orphaned volumes (unused volumes) in each region
## It is adapted from various code snippets found on the internet.

## Uses us-east-1 as the parent region (or control region) for the SNSArn target.
## Uses a target SNSArn - to seend email to a specific email address 


import boto3
from datetime import *
from os import environ


def publish_sns(sns_message, sns_arn):
    """
    Publish message to the master SNS topic
    """
  
    sns_client = boto3.client('sns', region_name='us-east-1')

    print "Publishing message to SNS topic..."
    print sns_message
    sns_client.publish(TargetArn=sns_arn, Message=sns_message, Subject='Orphaned Volume Report: ' + str(today))
    return


def lambda_handler(event, context):
   #set the date to today for the snapshot

   client = boto3.client('ec2') 
   regions = client.describe_regions()['Regions'] 

   missingReport = "Unattached Volumes Report - Date:" + str(today) + "\n"

   x=0
   # Connect to EC2 
   for region in regions: 
      region_name=region['RegionName'] 
      missingReport  +=  "\nBelow are the volumes that exist but are not attached in " + region_name + ":\n"
      ec2 = boto3.resource('ec2',region_name=region['RegionName']) 

      volumes = ec2.volumes.all()
      for v in volumes:
          if v.state != "in-use":
               missingReport +=  str(v.id) + " - Size: " + str(v.size) + " - Created: " + str(v.create_time) + " State: " + str (v.state) + "\n"
               x += 1

   if x > 0:
      ## There are unattached volumes
      publish_sns(missingReport, environ['SNSArn'])

   return 'lambda success'
