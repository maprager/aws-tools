import json
import logging
import os
import boto3


from urllib.request import Request, urlopen
from urllib.error import URLError, HTTPError

## HOOK_URL is the webhook connector of a MS Teams Channel.
HOOK_URL = os.environ['HookURL']

#logger = logging.getLogger()
#logger.setLevel(logging.INFO)

def lambda_handler(event, context):
    
    #logger.info("Event: " + str(event))
    message = json.loads(event['Records'][0]['Sns']['Message'])

    green="04B431"
    red="FF0000"
    yellow="F7FE2E"
    msgType=message['detail-type']
    msgAccount=message['account']
    msgTime=message['time']
    msgRegion=message['region']
    tmpDetail=message['detail']
    msgInstanceId=tmpDetail['instance-id']
    
    alias=boto3.client('iam').list_account_aliases()['AccountAliases'][0]
    #logger.info(message)
    title = "Message From " + alias
    
    if msgType == "EC2 Spot Instance Request Fulfillment":
         msgEnding=" Spot request was fullfilled."
         msgColor=green
    if msgType == "EC2 Instance State-change Notification":
         msgEnding= " State has chaned to " + tmpDetail['state']
         if tmpDetail['state'] == "running":
             msgColor = green
         if tmpDetail['state'] == "pending":
             msgColor = yellow
         if tmpDetail['state'] == "terminated":
             msgColor = red
        
    if msgType == "EC2 Spot Instance Interruption Warning":
         msgEnding=" Spot has received a termination request - 2 minute warning !"
         msgColor=red
    msgToSend='Instance ' + msgInstanceId + ' in region: ' + msgRegion + ', at: ' + msgTime + msgEnding

    my_message = {
      "@context": "https://schema.org/extensions",
      "@type": "MessageCard",
      "themeColor": msgColor, 
      "title": title,
      "summary": "Just a summary",
      "text" : msgToSend
    }
    #"text" : json.dumps(message) 
    messageToSend=json.dumps(my_message)

    req = Request(HOOK_URL, messageToSend.encode('utf-8'))
    try:
        response = urlopen(req)
        response.read()
        logger.info("Message posted")
    except HTTPError as e:
        logger.error("Request failed: %d %s", e.code, e.reason)
    except URLError as e:
        logger.error("Server connection failed: %s", e.reason)

    return {
        'statusCode': 200,
        'body': json.dumps('Lambda Done')
    }
