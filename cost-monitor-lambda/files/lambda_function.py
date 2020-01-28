import json
import os
import traceback
import boto3
from datetime import datetime, timedelta
import time
from collections import OrderedDict
from urllib.request import Request, urlopen
from urllib.error import URLError, HTTPError

### Need to define 3 global variables:
## HookURL - your MS-teams webhook.
## AverageCost - what you think your average cost should be
## Threshold - the threshold difference when you start warning.

## NB - Only warns on price rise !

## Globals
HOOK_URL = os.environ['HookURL']
AVG_COST = os.environ['AverageCost']
THRESHOLD = os.environ['Threshold']
red="FF0000"


def lambda_handler(event, context):
    alias=boto3.client('iam').list_account_aliases()['AccountAliases'][0]
    #logger.info(message)
    title = "Message From " + alias

    # initialize cost explorer
    cd = boto3.client('ce', 'us-east-1')

    #get todays date
    today=datetime.strftime(datetime.now() - timedelta(0), '%Y-%m-%d')
    # print (today)

    #get yesterdays date
    yesterday=datetime.strftime(datetime.now() - timedelta(1), '%Y-%m-%d')
    #print (yesterday)

    # get the data of the daily cost for the past day
    data = cd.get_cost_and_usage(TimePeriod={'Start': yesterday, 'End': today}, Granularity='DAILY', Metrics=['UnblendedCost'])
    dailyCost=data['ResultsByTime'][0]['Total']['UnblendedCost']['Amount']
    #print (dailyCost)

    # Calculate actual percentage difference
    perc_diff=(float(dailyCost) - int(AVG_COST))/int(AVG_COST) *100

    # If the difference is larger than the threshold - then let someone know
    if float(perc_diff) > int(THRESHOLD):
           msgToSend = "Price has changed by more than " + THRESHOLD +"%: --> " + str(round(perc_diff,2)) + "% to a daily price of $" + str(round(float(dailyCost),2)) + '\nAverage Price is defined as: $' + AVG_COST
           my_message = {
                 "@context": "https://schema.org/extensions",
                 "@type": "MessageCard",
                 "themeColor": red,
                 "title": title,
                 "summary": "Just a summary",
                 "text" : msgToSend
           }
           messageToSend=json.dumps(my_message)
           req = Request(HOOK_URL, messageToSend.encode('utf-8'))
           try:
                response = urlopen(req)
                response.read()
                print("Message posted")
           except HTTPError as e:
                print("Request failed: %d %s", e.code, e.reason)
           except URLError as e:
                print("Server connection failed: %s", e.reason)

    return {
        'statusCode': 200,
        'body': json.dumps('Hello from Lambda!')
    }
