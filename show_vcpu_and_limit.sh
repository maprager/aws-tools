#!/bin/bash

region=$1

vcpuLimit=$(aws service-quotas get-service-quota --region $region --service-code ec2 --quota-code L-1216C47A --query 'Quota.Value')
vcpuInUse=$(aws ec2 describe-instances --region $region --filters "Name=instance-state-name,Values=running" --query 'Reservations[*].Instances[*].{"InstanceType": InstanceType,"CpuOptions": CpuOptions}' | grep -e "CoreCount" -e "ThreadsPerCore" | awk '{print $2}' | tr ',' ' ' | paste - - -d\* | perl -ne 'print eval $_,"\n"' |  perl -nle '$sum += $_ } END { print $sum' )

echo "You have $vcpuInUse vCPUSs in use out of the Limit: $vcpuLimit in region $region"
