#!/bin/bash

# Mark Prager - 12 April 2018

# Script to detect network blackholes within a region - can be run from a crontab
# vpcsToIgnore - are tagged with the tag VPCname - change as necessary.

vpcsToIgnore="VPCMAIN vpcdefault"
vpcs=`aws ec2 describe-vpcs | grep VpcId | awk '{print $2}' | tr "\"," " " | awk '{print $1}'`
rm -f /tmp/blackholes.txt
for i in $vpcs
do
   vpcname=`aws ec2 describe-vpcs --vpc-ids $i | grep Value | tr '":,' ' '  | awk '{print $2}'| head -1 `
   if  [[ $vpcsToIgnore != *"$vpcname"* ]]; then
          echo "VPCName:" $vpcname ":" >> /tmp/blackholes.txt
          aws ec2 describe-route-tables --filters "Name=vpc-id,Values=$i" --output text | grep -e "blackhole" -e "Name"  | awk '{print $2"\t" $3"\t" $5"\t"$7}'  | tac >> /tmp/b
lackholes.txt
          echo "--------------------------------------------------------------------" >> /tmp/blackholes.txt
   fi
done

# check to see if there are any blackholes, and if there are - publish them
numOfBlackholes=`grep blackhole /tmp/blackholes.txt | wc -l`
if [ $numOfBlackholes -gt 0 ]; then
    aws sns publish --topic-arn "PLACE SNS TOPIC HERE" --subject "Network blackholes found on REGION" --message file:///tmp/blackholes.txt
fi
