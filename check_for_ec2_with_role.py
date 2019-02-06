#!/usr/bin/python
import boto3
from prettytable import PrettyTable
import sys


if len(sys.argv) == 1:
  print "Error: Please enter a list of iam profile names"
  print "For example: check_for_ec2_with_role.py role1 role2 role3"
  exit()

filterValue=[]
accountId=boto3.client('sts').get_caller_identity().get('Account')

for i in range(1, len(sys.argv)):
    string='arn:aws:iam::'+accountId+':instance-profile/'+sys.argv[i]
    filterValue.append(string)

client = boto3.client('ec2')
regions = client.describe_regions()['Regions']
for region in regions:
  print "%%%" , region['RegionName']
  t = PrettyTable(['Name', 'State', 'Public IP', 'Private IP'])
  ec2 = boto3.resource('ec2',region_name=region['RegionName'])
  # Get information for all running instances
  running_instances = ec2.instances.filter(Filters=[{'Name': 'iam-instance-profile.arn', 'Values': filterValue }])
  rowExists=False
  for instance in running_instances:
        rowExists=True
        for tag in instance.tags:
          if 'Name'in tag['Key']:
            name = tag['Value']
            break
          else:
            name = "unknown"
        t.add_row([name, instance.state['Name'] ,instance.public_ip_address, instance.private_ip_address])
  if rowExists == True:
    print t
