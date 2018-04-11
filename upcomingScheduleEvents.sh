#!/bin/bash

## Code written by Mark Prager - 11th April 2018

# Get all the upcoming scheduled events
aws health describe-events --filter eventStatusCodes=upcoming  | grep -e "startTime" -e "endTime" -e arn | awk '{ printf "%s", $0; if (NR % 3 == 0) print ""; else printf " " }' | awk '{print $2, $4, $6}' | tr '",' ' ' > /tmp/output$$

## Get all the instances names and ids for all the regions in the account.
for region in `aws ec2 describe-regions --output text | cut -f3`
do
     aws ec2 describe-instances --region $region  --query 'Reservations[].Instances[].[Tags[?Key==`Name`] | [0].Value, InstanceId]' --output text >> /tmp/output-b$$
done

### Got over all the events, and parse out the region, the events and grab the instance name tag from the the output-b$$
while IFS=' ' read -r f1 f2 f3;
do
   instanceId=`aws health describe-affected-entities --filter eventArns="$f3" | grep entityValue | tr '":,' ' ' | awk '{print $2}'`
   event=`aws health describe-event-details --event-arns $f3 | grep eventTypeCode | tr '":,' ' ' |  awk '{print $2}'`
   region=`echo $f3 | tr ':' ' ' | awk '{print $4}'`
   instanceName=`grep $instanceId /tmp/output-b$$ | awk '{print $1}'`
   printf 'Starttime=%s Endtime=%s Event=%s region=%s instance=%s name=%s \n' "$f1" "$f2" "$event" "$region" "$instanceId" "$instanceName"
done < /tmp/output$$


## Cleanup
rm -f /tmp/output$$
rm -f /tmp/output-b$$

