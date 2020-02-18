#!/usr/bin/python

#### Script to turn and on demand instance into a spot - any attached volumes will be moved
#### Version 0.1 18/02/2020 Mark Prager
#### Tested on Python 2.7
#### Tested only on Linux (Centos) Servers
#### Limits - does not handle EIPs
####          Makes some assumptions about the instances - e.g. root volume on /dev/sda1

### Imports
import boto3
import json
import time
import sys,re
import logging
import base64
from datetime import datetime

#### Simple function to print out the usage.
def usage(text):
    if text:
        logging.critical(text)
    logging.critical("Usage: {0} instance-id".format(sys.argv[0]))

#### Simple function to pull out the instance name from the tags
def get_instance_name(tags):
    for tag in tags:
        if tag["Key"] == 'Name':
              instancename = tag["Value"]
    return instancename

#### Function to wait for a client image to be created.
def wait_for_image_to_be_available(client,image_id):
    try:
        available = 0
        while available == 0:
            image = client.describe_images(ImageIds=[image_id])
            if image['Images'][0]['State'] == 'available':
                available = 1
            else:
                logging.info( "Image not created yet.. Gonna sleep for 10 seconds")
                time.sleep(10)
        if available == 1:
            logging.info( "Image is now available for use.")
            return True
    except Exception, e:
        logging.info( e)

### Main

### Set up logging
logger = logging.getLogger()
logger.setLevel(logging.INFO)
logging.basicConfig(format='%(levelname)s %(asctime)s %(message)s')

### Read in the instance Id
iid=sys.argv[1]

### Print out Boto Version in case of support issues
logging.info( "Boto Version: " + boto3.__version__)
logging.info ("Attempting to migrate instance: " + iid )

### Get Current Date and Time.
now = datetime.now()
dt_string = now. strftime("%d%m%Y-%H%M%S")

ec2= boto3.client("ec2")
## Gather facts including instance name
try:
	response=ec2.describe_instances(InstanceIds=[iid])
except:
	usage("Instance Id not valid: " + iid)
        sys.exit()

VpcId=(response['Reservations'][0]['Instances'][0]['VpcId'])
SubnetId=(response['Reservations'][0]['Instances'][0]['SubnetId'])
Tags=(response['Reservations'][0]['Instances'][0]['Tags'])
KeyName=(response['Reservations'][0]['Instances'][0]['KeyName'])
BlockDeviceMappings=(response['Reservations'][0]['Instances'][0]['BlockDeviceMappings'])
InstanceType=(response['Reservations'][0]['Instances'][0]['InstanceType'])
SecurityGroups=(response['Reservations'][0]['Instances'][0]['NetworkInterfaces'][0]['Groups'])

InstanceName=get_instance_name(Tags)

#Discover which is the root disk, and which are any 'extra' mounted disks
extraDisks=[]
for i in BlockDeviceMappings:
 if i['DeviceName'] == '/dev/sda1' :
     # Save Root Device Information
     ## Get VolumeInformation
     rootVolume= i['Ebs']['VolumeId']
     volume=ec2.describe_volumes(VolumeIds=[rootVolume])
     rootIops=volume['Volumes'][0]['Iops']
     rootVolumeSize=volume['Volumes'][0]['Size']
     rootVolumeType=volume['Volumes'][0]['VolumeType']
 if i['DeviceName'] != '/dev/sda1' :
     extraDisks.append({'DeviceName': i['DeviceName'], 'VolumeId': i['Ebs']['VolumeId']})

logging.info( extraDisks)

## Prepare Root Block Device
## user for creating image - only do of root device - no need to copy all the volumes
## will be used later also.
rootBlockDevice=[]
vol={'DeviceName': '/dev/sda1', 'Ebs': {'VolumeSize': rootVolumeSize, 'VolumeType': rootVolumeType}}
## Don't create any extra devices - they will be moved
rootBlockDevice.append(dict(vol))
for disk in extraDisks:
    vol={'DeviceName': disk['DeviceName'], 'NoDevice': ''}
    rootBlockDevice.append(dict(vol))
logging.info(rootBlockDevice)

### Create an image copy of the instance ( for cloning )
response=ec2.create_image(BlockDeviceMappings=rootBlockDevice,InstanceId=iid, Name=InstanceName+"_clone-"+dt_string, NoReboot=True)
logging.info( response['ImageId'])
ImageId=response['ImageId']
wait_for_image_to_be_available(ec2,ImageId)

### If you arrived here, then image is created
### and now we begin creating the launch configurations
## Prepare security group
sg=[]
for i in SecurityGroups:
	sg.append(i['GroupId'])

## Prepare Network Interface
NetworkInterfaces=[]
iface={'DeviceIndex': 0, 'DeleteOnTermination': True, 'SubnetId': SubnetId , 'Groups': sg}
NetworkInterfaces.append(dict(iface))

### Here place the userdata to preserve the name of the instance, and change IPs etc....
hostnameCmd="#!/bin/bash " + "\n"
hostnameCmd= hostnameCmd + "sed -i '/^HOSTNAME=/ c \HOSTNAME=" + InstanceName +"' /etc/sysconfig/network\n"
hostnameCmd= hostnameCmd + "ip=`curl -sf http://169.254.169.254/latest/meta-data/local-ipv4`\n"
hostnameCmd= hostnameCmd + 'echo "${ip} ' + InstanceName +' localhost" > /etc/hosts\n'
hostnameCmd= hostnameCmd + "echo '127.0.0.1 localhost.localdomain localhost4 localhost4.localdomain4' >> /etc/hosts\n"
userdata=str(base64.b64encode(hostnameCmd))

## Prepare LaunchSpecification
LaunchSpecification={'BlockDeviceMappings': rootBlockDevice,  'ImageId': ImageId, 'KeyName': KeyName, 'InstanceType': InstanceType, 'NetworkInterfaces': NetworkInterfaces , 'UserData': userdata}
logging.info( LaunchSpecification)

## Request Spot !
spotRequest=ec2.request_spot_instances(Type='persistent', InstanceInterruptionBehavior='stop', LaunchSpecification=LaunchSpecification)
logging.info( spotRequest)

# Check Status of Spot request
sir=spotRequest['SpotInstanceRequests'][0]['SpotInstanceRequestId']
logging.info(sir)

### Give AWS some time ....
time.sleep(5)

# wait till fully launched and running
pending=0
while pending == 0:
    check=ec2.describe_spot_instance_requests(SpotInstanceRequestIds=[sir])
    status=check['SpotInstanceRequests'][0]['Status']['Code']
    if status == 'fulfilled' :
         newInstanceId=check['SpotInstanceRequests'][0]['InstanceId']
         pending=1
    else:
         time.sleep(1)
         logging.info ("Spot instance is still pending...")

logging.info( "New Instance Created: Stoppable Spot: " + newInstanceId)

## Tag Instance
response=ec2.create_tags(Resources=[newInstanceId], Tags=Tags)

## Wait for instance to fully come up:
InstanceState="notup"
while InstanceState != "running":
    response=ec2.describe_instances(InstanceIds=[newInstanceId])
    InstanceState=(response['Reservations'][0]['Instances'][0]['State']['Name'])
    time.sleep(5)
    logging.info ("Waiting for spot instance to be fully running....")

### Shutdown old Instance
response=ec2.stop_instances(InstanceIds=[iid])
InstanceState="running"
while InstanceState != "stopped":
    response=ec2.describe_instances(InstanceIds=[iid])
    InstanceState=(response['Reservations'][0]['Instances'][0]['State']['Name'])
    time.sleep(5)
    logging.info ("Waiting for old OD instance to be fully stopped....")

###  Detach old Volumes
for vol in extraDisks:
	response=ec2.detach_volume(InstanceId=iid, VolumeId=vol['VolumeId'] )
        logging.info("Detaching Volumes: "+ vol['VolumeId'])
        time.sleep(1)

### Attach old volumes to new instance
for vol in extraDisks:
	response=ec2.attach_volume(InstanceId=newInstanceId, Device=vol['DeviceName'] ,VolumeId=vol['VolumeId'] )
        logging.info("Attach Volumes: "+ vol['VolumeId'])
        time.sleep(1)

time.sleep(5)

### Reboot instance
response=ec2.stop_instances(InstanceIds=[newInstanceId])
InstanceState="running"
while InstanceState != "stopped":
    response=ec2.describe_instances(InstanceIds=[newInstanceId])
    InstanceState=(response['Reservations'][0]['Instances'][0]['State']['Name'])
    time.sleep(5)
    logging.info ("Waiting for new SPOT instance to be fully stopped....")

## Sleep 60 seconds - AWS needs time to adjust its spots status
time.sleep(60)

response=ec2.start_instances(InstanceIds=[newInstanceId])
InstanceState="stopped"
while InstanceState != "running":
    response=ec2.describe_instances(InstanceIds=[newInstanceId])
    InstanceState=(response['Reservations'][0]['Instances'][0]['State']['Name'])
    time.sleep(5)
    logging.info ("Waiting for new SPOT instance to be fully started....")

logging.info ("Done")
