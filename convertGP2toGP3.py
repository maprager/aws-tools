#!/usr/bin/python3

#######################################################################
# Script:  convertGP2toGP3.py                                         #
# Author:  Mark Prager                                                #
# Description: Script to convert all gp2 volumes to gp3               #
#              Can ignore volumes with the 'skip_tag_key'             #
# Date:   03/12/2020                                                  #
#######################################################################
import boto3
from botocore.exceptions import ClientError
import logging
from datetime import *
from os import environ
import getopt
import sys


#setup simple logging for INFO
logger = logging.getLogger()
logger.setLevel(logging.INFO)
today = datetime.now().date()


def printUsage():
    logging.info ("     Usage:")
    logging.info ("     convertGP2toGP3.py [ -s <skip-tag> ]  [ -r <region-name> ] [ -v <vpc-id> ] [-dry] ")
    logging.info ("      -s <skip-tag>     : Volumes with tags to skip")
    logging.info ("      -r  <region-name> : region-name to check - If not specified do all regions" )
    logging.info ("      -v  <vpc-id>      : Check only if it belongs to this vpc - if not specified do all vpcs" )
    logging.info ("      -d                : For dry run only")
    logging.info ("     For example:")
    logging.info ("     convertGP2toGP3.py -s 'DontConvert_from_gp2' -r us-east-1 -v vpc-123432556647 -dry")
    logging.info ("     or")
    logging.info ("     convertGP2toGP3.py --skiptag='DontConvert_from_gp2' --region=us-east-1 -vpcid=vpc-123432556647 --dry")

def main(argv):

   dryrun=False
   skip_tag_key=None
   specific_region="ALL"
   specific_vpcid="ALL"
   count=0
   skip_count=0

   ## First check input arguments
   if (argv == []):
         printUsage()
         sys.exit(2)

   # Enter replica set name and size:
   try:
         short_options =   "hs:r:v:d"
         long_options  = [ "help","skiptag=","region=","vpcid=","dry" ]
         arguments, values = getopt.getopt(argv, short_options,long_options)
   except  getopt.GetoptError:
         printUsage()
         sys.exit(2)

   for current_argument, current_value in arguments:
      if current_argument in ("-d", "--dry"):
        dryrun=True
      elif current_argument in ("-h", "--help"):
        printUsage()
        sys.exit()
      elif current_argument in ("-s", "--skiptag"):
        skip_tag_key=current_value
      elif current_argument in ("-r", "--region"):
        specific_region=current_value
      elif current_argument in ("-v", "--vpcid"):
        specific_vpcid=current_value

   logging.info('skip_tag_key %s',skip_tag_key)
   logging.info('specific_region %s',specific_region)
   logging.info('specific_vpc %s',specific_vpcid)
   logging.info('dryrun %s',dryrun)

   logging.basicConfig(level=logging.INFO)
   logging.info('Started')
   client = boto3.client('ec2') 
   regions = client.describe_regions()['Regions'] 


   for region in regions: 
      region_name=region['RegionName'] 
      if (specific_region == region_name or specific_region == "ALL") :
          vol_client=boto3.client('ec2',region_name=region_name)
          logging.info ("Region: %s",region_name)
          vol = boto3.resource('ec2',region_name=region['RegionName']) 
          for v in vol.volumes.all():
             if v.volume_type != 'gp2' :
                skip_count += 1
                logging.warning ("  Skip NonGP2: %s %s %s %s", v.volume_id,v.volume_type,v.size,v.iops)
             else:
                ## Get volume attachment
                if v.state == 'in-use' :
                      volume_not_in_use = False
                      response=vol_client.describe_instances(Filters=[{'Name':'block-device-mapping.volume-id','Values':[v.volume_id]}])
                      instance_id = response['Reservations'][0]['Instances'][0]['InstanceId']
                      response = client.describe_instances(InstanceIds=[instance_id])
                      ## Get VPCid of volume attachment
                      vpc_of_instance=response['Reservations'][0]['Instances'][0]['VpcId']
                else:
                      volume_not_in_use = True
                ## if the volume_attachment is the vpc id OR there is no volume_attachment or specifc_vpcid is none
                if ( specific_vpcid == vpc_of_instance ) or ( volume_not_in_use == True ) or (specific_vpcid == "ALL") :
                     try:
                       if skip_tag_key in str(v.tags):
                          logging.warning ('    Skip: %s found: %s',skip_tag_key,str(v.tags))
                          skip_count += 1
                       else:
                          count += 1
                          try: 
                             logging.info ("    Converting: VolumeId: %s VolumeType: %s VolumeSize: %s VolumeIops: %d", v.volume_id,v.volume_type,v.size,v.iops)
                             response=vol_client.modify_volume(DryRun=dryrun, VolumeId=v.volume_id, VolumeType='gp3', Size=v.size, Iops=v.iops)
                             logging.info("     Modify Response: %s",response)
                          except ClientError as e:
                             logging.error("Error in volume modify: %s",e)
                     except:
                       count += 1
                       try: 
                          logging.info ("    Converting: VolumeId: %s VolumeType: %s VolumeSize: %s VolumeIops: %d", v.volume_id,v.volume_type,v.size,v.iops)
                          response=vol_client.modify_volume(DryRun=dryrun, VolumeId=v.volume_id, VolumeType='gp3', Size=v.size, Iops=v.iops)
                          logging.info("     Modify Response: %s",response)
                       except ClientError as e:
                          logging.error("Error in volume modify: %s",e)
                else:
                   logging.warning ( " Skip Incorrect VPC:  %s %s %s %s", v.volume_id,v.volume_type,v.size,v.iops)
                  
                   skip_count += 1
                 
   logging.info('Finished - Converted: %d, Skipped: %d', count, skip_count)

if __name__ == '__main__':
    main(sys.argv[1:])
