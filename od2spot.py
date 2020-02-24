#!/usr/bin/python
#### Script to turn and on demand instance into a spot - any attached volumes will be moved
#### Version 0.1 18/02/2020 Mark Prager - Initial version
#### Version 0.2 20/20/2020 Mark Prager - tested on Python 3.6, and added tenacity.
####
#### Details:
#### Tested on Python 2.7
#### Tested on Python 3.6
#### Converted only Linux (Centos) Servers
####
#### Limits:
#### - does not handle EIPs
#### - 5 minutes waiting period of AWS operations
####
#### Usage: od2spot.py -i <instance-id>
####
#### Credits:
####     Mike Miller for Guidance
####     Corey Quinn for Guidance
############################################################################################

### Imports
import boto3
#!/usr/bin/python
#### Script to turn and on demand instance into a spot - any attached volumes will be moved
#### Version 0.1 18/02/2020 Mark Prager - Initial version
#### Version 0.2 20/02/2020 Mark Prager - tested on Python 3.6, and added tenacity.
#### Version 0.3 24/02/2020 Mark Prager - Added additional parameter -o to override the name
####
#### Details:
#### Tested on Python 2.7
#### Tested on Python 3.6
#### Converted only Linux (Centos) Servers
####
#### Limits:
#### - does not handle EIPs
#### - 5 minutes waiting period of AWS operations
####
#### Usage: od2spot.py -i <instance-id>
####
#### Credits:
####     Mike Miller for Guidance
############################################################################################

### Imports
import boto3
import json
import time
import sys,re
import logging
import base64
import argparse
from datetime import datetime
from tenacity import retry, wait_random_exponential, stop_after_delay
from platform import python_version

#### Simple function to print out the usage.
def usage(text):
    if text:
        logging.critical(text)
    logging.critical("Usage: {0} -i instance-id [-o override_instance_name]".format(sys.argv[0]))

#### Simple function to pull out the instance name from the tags
def get_instance_name(tags):
    for tag in tags:
        if tag["Key"] == 'Name':
              instancename = tag["Value"]
    return instancename

#### Function to wait for a client image to be created.
@retry(wait=wait_random_exponential(multiplier=1, max=10), stop=stop_after_delay(300))
def wait_for_image_to_be_available(client,image_id):
    image = client.describe_images(ImageIds=[image_id])
    imageState = image['Images'][0]['State']
    logging.info ( "waiting for image to be ready ....[%s]" % image_id)
    assert imageState == "available"

#### Function to wait for a spot instance to be created
@retry(wait=wait_random_exponential(multiplier=1, max=10), stop=stop_after_delay(300))
def wait_for_spot_request_state(client,state,sir):
    check=client.describe_spot_instance_requests(SpotInstanceRequestIds=[sir])
    logging.info ( "waiting for spot to reach state: %s"  % state )
    assert check['SpotInstanceRequests'][0]['Status']['Code'] == state
    return check['SpotInstanceRequests'][0]['InstanceId']

#### Function to wait for an instance to get into a particular state.
@retry(wait=wait_random_exponential(multiplier=1, max=10), stop=stop_after_delay(300))
def wait_for_instance_state(client,instanceid, state):
    response=ec2.describe_instances(InstanceIds=[instanceid])
    instanceState=(response['Reservations'][0]['Instances'][0]['State']['Name'])
    logging.info ( "waiting for instance %s to reach state: %s" % (instanceid,state ))
    assert instanceState == state

### Main

### Read Command Line arguments
parser = argparse.ArgumentParser(description='Script to convert AWS OnDemand Instances to Persistant Stoppable Spots')
parser.add_argument('-i', '--instance-id', required=True, help='The instance Id to convert')
parser.add_argument('-o', '--override', required=False, help='An overriding name for the instance')
args = vars(parser.parse_args())
iid = args["instance_id"]
try:
   overrideInstanceName=args["override"]
except:
   pass

### Set up logging
logger = logging.getLogger()
logger.setLevel(logging.INFO)
logging.basicConfig(format='%(levelname)s %(asctime)s %(message)s')

pythonVersion = python_version()

### Print out Boto Version in case of support issues
logging.info( "Boto Version: %s" % boto3.__version__)
logging.info( "Running Python Version: %s" % pythonVersion )
logging.info ("Attempting to migrate instance: %s" % iid )


### Get Current Date and Time.
now = datetime.now()
dt_string = now.strftime("%d%m%Y-%H%M%S")

ec2= boto3.client("ec2")
## Gather facts including instance name
try:
        response=ec2.describe_instances(InstanceIds=[iid])
except:
        usage("Instance Id not valid: " + iid)
        sys.exit(1)

VpcId=(response['Reservations'][0]['Instances'][0]['VpcId'])
SubnetId=(response['Reservations'][0]['Instances'][0]['SubnetId'])
Tags=(response['Reservations'][0]['Instances'][0]['Tags'])
RootDeviceName=(response['Reservations'][0]['Instances'][0]['RootDeviceName'])
KeyName=(response['Reservations'][0]['Instances'][0]['KeyName'])
BlockDeviceMappings=(response['Reservations'][0]['Instances'][0]['BlockDeviceMappings'])
InstanceType=(response['Reservations'][0]['Instances'][0]['InstanceType'])
SecurityGroups=(response['Reservations'][0]['Instances'][0]['NetworkInterfaces'][0]['Groups'])

InstanceName=get_instance_name(Tags)

#Discover which is the root disk, and which are any 'extra' mounted disks
extraDisks=[]
for i in BlockDeviceMappings:
 if i['DeviceName'] == RootDeviceName :
     # Save Root Device Information
     rootVolume= i['Ebs']['VolumeId']
     volume=ec2.describe_volumes(VolumeIds=[rootVolume])
     rootIops=volume['Volumes'][0]['Iops']
     rootVolumeSize=volume['Volumes'][0]['Size']
     rootVolumeType=volume['Volumes'][0]['VolumeType']
 if i['DeviceName'] != RootDeviceName:
     extraDisks.append({'DeviceName': i['DeviceName'], 'VolumeId': i['Ebs']['VolumeId']})

# logging.info( extraDisks)

## Prepare Root Block Device
## user for creating image - only do the root device - no need to copy all the volumes
## will be used later also.
rootBlockDevice=[]
vol={'DeviceName': RootDeviceName, 'Ebs': {'VolumeSize': rootVolumeSize, 'VolumeType': rootVolumeType}}
## Don't create any extra devices - they will be moved
rootBlockDevice.append(dict(vol))
for disk in extraDisks:
    vol={'DeviceName': disk['DeviceName'], 'NoDevice': ''}
    rootBlockDevice.append(dict(vol))
# logging.info(rootBlockDevice)

### Create an image copy of the instance ( for cloning )
response=ec2.create_image(BlockDeviceMappings=rootBlockDevice,InstanceId=iid, Name=InstanceName+"_clone-"+dt_string, NoReboot=True)
logging.info( "Image to be created: %s [%s]" % (response['ImageId'],InstanceName+"_clone-"+dt_string))
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
### If you have specifics for your server - you could place them here.
### Alternatively, take this out, and readin the user data from the command line....
### Maybe in a later version ... :)
if overrideInstanceName=="None":
   overrideInstanceName=InstanceName
hostnameCmd="#!/bin/bash " + "\n"
hostnameCmd= hostnameCmd + "sed -i '/^HOSTNAME=/ c \HOSTNAME=" + overrideInstanceName +"' /etc/sysconfig/network\n"
hostnameCmd= hostnameCmd + "ip=`curl -sf http://169.254.169.254/latest/meta-data/local-ipv4`\n"
hostnameCmd= hostnameCmd + 'echo "${ip} ' + overrideInstanceName +' localhost" > /etc/hosts\n'
hostnameCmd= hostnameCmd + "echo '127.0.0.1 localhost.localdomain localhost4 localhost4.localdomain4' >> /etc/hosts\n"
### Different commands in python 2 and 3
if  sys.version_info < (3, 6 ) :
	userdata=str(base64.b64encode(hostnameCmd))
else:
	userdata=base64.b64encode(hostnameCmd.encode()).decode("ascii")

## Prepare LaunchSpecification
LaunchSpecification={'BlockDeviceMappings': rootBlockDevice,  'ImageId': ImageId, 'KeyName': KeyName, 'InstanceType': InstanceType, 'NetworkInterfaces': NetworkInterfaces , 'UserData': userdata}
#logging.info( LaunchSpecification)

## Request Spot !
spotRequest=ec2.request_spot_instances(Type='persistent', InstanceInterruptionBehavior='stop', LaunchSpecification=LaunchSpecification)
# Check Status of Spot request
sir=spotRequest['SpotInstanceRequests'][0]['SpotInstanceRequestId']
# logging.info(sir)
newInstanceId=wait_for_spot_request_state(ec2,"fulfilled",sir)
logging.info( "New Instance Created: Stoppable Spot: %s" % newInstanceId)

## Tag Instance
response=ec2.create_tags(Resources=[newInstanceId], Tags=Tags)

## Wait for instance to fully come up:
wait_for_instance_state(ec2,newInstanceId,"running")

### Shutdown old Instance
ec2.stop_instances(InstanceIds=[iid])
wait_for_instance_state(ec2, iid, "stopped")

###  Detach old Volumes
for vol in extraDisks:
        response=ec2.detach_volume(InstanceId=iid, VolumeId=vol['VolumeId'] )
        logging.info("Detaching Volumes: %s " % vol['VolumeId'])
        time.sleep(1)

### Attach old volumes to new instance
for vol in extraDisks:
        response=ec2.attach_volume(InstanceId=newInstanceId, Device=vol['DeviceName'] ,VolumeId=vol['VolumeId'] )
        logging.info("Attach Volumes: %s " %  vol['VolumeId'])
        time.sleep(1)

### Let AWS Rest ...
time.sleep(5)

### Reboot instance
ec2.stop_instances(InstanceIds=[newInstanceId])
wait_for_instance_state(ec2,newInstanceId,"stopped")
## Sleep 90 seconds - AWS needs time to adjust its spots status - not sure how to check this
time.sleep(90)
ec2.start_instances(InstanceIds=[newInstanceId])
wait_for_instance_state(ec2,newInstanceId,"running")

logging.info ("Conversion Done")
