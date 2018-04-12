#!/bin/bash

# Script written by Mark Prager - 12 Apr 2018

# Script to create a service endpoint-
# The script creates:
# a. one target group on the specified port
# b. a listener for that target group
# c. an nlb containing that target group.
# It then waits for the nlb to be provisioned.
# d. and then creates a service endpoint on that NLB

# Inputs are
# Param 1 - VpcId
# Param 2 - port to monitor
# Param 3 - Subnet name tag to look for, for list of subnets within nlb
# E.g. ./create_vpc_service_endpoints.sh vpc-1234567890abcde 80 "*Private*"

if [ "$#" -ne 3 ]; then
	    echo "Illegal number of parameters"
	    echo "Usage: ./create_vpc_service_endpoints.sh vpc-id port subnetNameTag"
	    echo "For example: ./create_vpc_service_endpoints.sh vpc-1234567890abcdef 80 \"*Private*\" "
	    exit
fi
vpcId1=$1
port=$2
subnetNameTag=$3


# grab list of subnets from vpcid1
subnets1=`aws ec2 describe-subnets --filters "Name=vpc-id,Values=$vpcId1" "Name=tag:Name,Values=$subnetNameTag" --query 'Subnets[].SubnetId'`

# Create NLB
nlb_arn=`aws elbv2 create-load-balancer --name nlb-vpc-proxy-$port --type network --subnets "$subnets1" --scheme internal | grep Arn | awk '{print $2}' | tr ',"' '  ' | awk '{print $1}'`
echo "NLB Created on VPC1: $vpcId1"
echo $nlb_arn

# Create Target Group
trg_arn=`aws elbv2 create-target-group --name nlb-vpc-proxy-trg-$port --protocol TCP --port $port  --vpc-id $vpcId1 | grep Arn | awk '{print $2}' | tr ',' ' '`
echo "Target Group created on NLB: $nlb_arn"
echo $trg_arn

### Create Listener
aws elbv2 create-listener --load-balancer-arn $nlb_arn --protocol TCP --port $port --default-actions Type=forward,TargetGroupArn=$trg_arn > /dev/null
echo "Listener created on on NLB:"

### Need to wait for the nlb to be provisioned.
lb_state=`aws elbv2  describe-load-balancers --load-balancer-arns  $nlb_arn --output table| grep Code | awk '{print $4}'`
echo -n "Waiting for NLB to be active .."
while [ $lb_state != "active" ]
do
  sleep 2
  echo -n ".."
 lb_state=`aws elbv2  describe-load-balancers --load-balancer-arns  $nlb_arn --output table| grep Code | awk '{print $4}'`
done
echo Done

## lb is now provisioned so you can create the eps.

# now create the endpoint service
ep_arn=`aws ec2 create-vpc-endpoint-service-configuration --network-load-balancer-arns $nlb_arn --no-acceptance-required |  grep ServiceName | awk '{print $2}' | tr ',"' '  '| awk '{print $1}'`
echo "Creating endpoint service on vpcId1: $vpcId1"
echo $ep_arn

echo "Waiting 30 seconds for endpoint service to complete setup ...."
sleep 30

## TBD To add cross load balancing, deletion protection.
