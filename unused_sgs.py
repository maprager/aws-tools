#!/usr/bin/python
import boto3
from prettytable import PrettyTable

DEBUG = False
def check_instance_security_groups(region):
	global DEBUG
	# From here: https://stackoverflow.com/questions/41146114/boto3-searching-unused-security-groups
	## This part gives us the list of all the SGs that are not used by ec2 instances - in unused_sgs
	## Copied from Stack Overflow

	### This should always be the first function called.
	if DEBUG: print 'Checking ec2 instances first'
	ec2 = boto3.resource('ec2', region_name=region)
	sgs = list(ec2.security_groups.all())
	insts = list(ec2.instances.all())
	all_sgs = set([sg.group_id for sg in sgs])
	all_inst_sgs = set([sg['GroupId'] for inst in insts for sg in inst.security_groups])
	unused_sgs = all_sgs - all_inst_sgs
	if DEBUG: print 'Total SGs:', len(all_sgs)
	if DEBUG: print 'SGS attached to instances:', len(all_inst_sgs)
	if DEBUG: print 'Orphaned SGs from instances:', len(unused_sgs)
	if DEBUG: print 'Unattached SGs from instances:', unused_sgs
	return unused_sgs

def check_eni_security_groups(region,sglist):
        global DEBUG
	# Now check in ENIs
	if DEBUG: print 'Now checking leftovers in ENIs'
	unused_sgs=[]
	ec2_client = boto3.client('ec2', region_name=region)
	for sg in sglist:
	   response=ec2_client.describe_network_interfaces( Filters= [{ 'Name' : 'group-id', 'Values': [sg] }] )
	   lengthOfResponse = (len(response['NetworkInterfaces']))
	   if lengthOfResponse == 0:
	       unused_sgs.append(sg)
	if DEBUG: print 'Total Checked SGs:', len(sglist)
	if DEBUG: print 'Orphaned SGs:', len(unused_sgs)
	if DEBUG: print 'Orphaned ENI SG names:', unused_sgs
        return unused_sgs

def check_elb_security_groups(region,sglist):
        global DEBUG
	# Now check load balancers elb
	if DEBUG: print 'Now checking elbs'

	# No filtering on the elb boto command (brilliant work AWS!)
	# So, get list of all SGs from all ELBs - even if no instances attached
	listOfElbSgs=[]
	elb_client = boto3.client('elb', region_name=region)
	response=elb_client.describe_load_balancers ()
	for i in response['LoadBalancerDescriptions']:
   		ll=i['SecurityGroups']
   		for j in ll:
	       		listOfElbSgs.append(j)
	if DEBUG: print ("ELB Security Groups SGs: ",listOfElbSgs)

	unused_sgs=[]
	for sg in sglist:
     		if sg not in listOfElbSgs:
	        	unused_sgs.append(sg)
	if DEBUG: print 'Total Checked SGs:', len(sglist)
	if DEBUG: print 'Orphaned SGs:', len(unused_sgs)
	if DEBUG: print 'Orphaned SG names from elbs:', unused_sgs
        return unused_sgs

def check_autoscaling_security_groups(region,sglist):
        global DEBUG
	## Now check autoscaling launch configurations
	if DEBUG: print 'Now checking lc'
	listOflcSgs=[]
	lc_client = boto3.client('autoscaling', region_name=region)
	response=lc_client.describe_launch_configurations()
	for i in response['LaunchConfigurations']:
	   ll=i['SecurityGroups']
	   for j in ll:
	       listOflcSgs.append(j)
	if DEBUG: print ("Autoscaling launch configurations SGs: ",listOflcSgs)

	unused_sgs=[]
	for sg in sglist:
	     if sg not in listOflcSgs:
		unused_sgs.append(sg)
	if DEBUG: print 'Total Checked SGs:', len(unused_sgs)
	if DEBUG: print 'Orphaned SGs:', len(unused_sgs)
	if DEBUG: print 'Orphaned SG names from elbs:', unused_sgs
	return unused_sgs

def check_vpc_endpoint_security_groups(region,sglist):
        global DEBUG
	### Now check the VPC endpoints
	if DEBUG: print 'Now check VPC endpoint SGs'
	listOfEPsgs=[]
	ec2_client = boto3.client('ec2', region_name=region)
	response=ec2_client.describe_vpc_endpoints()
	for i in response['VpcEndpoints']:
	   ll=i['Groups']
	   for j in ll:
	       listOfEPsgs.append(j['GroupId'])
	if DEBUG: print ("VPCendpoints SGs: ",listOfEPsgs)

	unused_sgs=[]
	for sg in sglist:
	     if sg not in listOfEPsgs:
		unused_sgs.append(sg)
	if DEBUG: print 'Total Checked SGs:', len(sglist)
	if DEBUG: print 'Orphaned SGs:', len(unused_sgs)
	if DEBUG: print 'Orphaned SG names from endpoints:', unused_sgs
	return unused_sgs

def check_rds_security_groups(region,sglist):
        global DEBUG
	### Now check RDS
	if DEBUG: print 'Now checking rds'
	listOfRDSgs=[]
	rds_client = boto3.client('rds', region_name=region)
	response=rds_client.describe_db_instances()
	for i in response['DBInstances']:
	   ll=i['VpcSecurityGroups']
	   for j in ll:
	       listOfRDSgs.append(j['VpcSecurityGroupId'])
	if DEBUG: print ("RDS Security Groups: ", listOfRDSgs)
	unused_sgs=[]
	for sg in sglist:
	     if sg not in listOfRDSgs:
		unused_sgs.append(sg)
	if DEBUG: print 'Total Checked SGs:', len(sglist)
	if DEBUG: print 'Orphaned SGs:', len(unused_sgs)
	if DEBUG: print 'Orphaned SG names from RDS:', unused_sgs
	return unused_sgs

def check_security_groups_for_security_groups(region,sglist):
        global DEBUG
	### Now check within security groups - as they might list them too.
	if DEBUG: print "now check all security groups that have a security group as a source"
	listOfSourcedSGs=[]
	ec2_client = boto3.client('ec2', region_name=region)
	response=ec2_client.describe_security_groups()
	for i in response['SecurityGroups']:
	    for j in i['IpPermissions']:
		if j['UserIdGroupPairs'] != []:
		    listOfSourcedSGs.append(j['UserIdGroupPairs'][0]['GroupId'])
	unused_sgs=[]
	for sg in sglist:
	     if sg not in listOfSourcedSGs:
		unused_sgs.append(sg)
	if DEBUG: print 'Total Checked SGs:', len(sglist)
	if DEBUG: print 'Orphaned SGs:', len(unused_sgs)
	if DEBUG: print 'Orphaned SG names from SGs:', unused_sgs
	return unused_sgs


def check_lambda_security_groups(region,sglist):
        global DEBUG
	### Also check Lambdas
	lambdaC = boto3.client('lambda', region_name=region)
	response=lambdaC.list_functions(MaxItems=200)
	lambdasglist=[]
	for i in response['Functions']:
	    if 'VpcConfig' in i:
		if i['VpcConfig']['VpcId'] != '':
		       lambdaSecurityGroups = i['VpcConfig']['SecurityGroupIds']
		       for k in lambdaSecurityGroups:
			     lambdasglist.append(k)
	unused_sgs=[]
	for sg in sglist:
	     if sg not in lambdasglist:
		unused_sgs.append(sg)
	if DEBUG: print 'Total Checked SGs:', len(sglist)
	if DEBUG: print 'Orphaned SGs:', len(unused_sgs)
	if DEBUG: print 'Orphaned SG names from SGs:', unused_sgs
	return unused_sgs

def printout_unused_security_groups(region,unused_sgs):
        print "Region: " , region
	print "Number of Unused Security Groups: ", len (unused_sgs)
        #print "The unused sgs: ", unused_sgs
	if len(unused_sgs) != 0
		ec2_client = boto3.client('ec2', region_name=region)
		response=ec2_client.describe_security_groups(GroupIds=unused_sgs)
		t = PrettyTable(['Group Name', 'GroupId', 'VPC ID'] )
        	for i in response['SecurityGroups']:
			t.add_row([i['GroupName'], i['GroupId'] , i['VpcId']] )
        	print t
        return

# List all regions
client = boto3.client('ec2')
allregions = [region['RegionName'] for region in client.describe_regions()['Regions']]
if DEBUG:
	allregions = []
	allregions. append('us-east-2')
for region in allregions:
        unused_sgs=[]
	unused_sgs=check_instance_security_groups(region)
	unused_sgs=check_eni_security_groups(region,unused_sgs)
	unused_sgs=check_elb_security_groups(region,unused_sgs)
	unused_sgs=check_autoscaling_security_groups(region,unused_sgs)
	unused_sgs=check_vpc_endpoint_security_groups(region,unused_sgs)
	unused_sgs=check_rds_security_groups(region,unused_sgs)
	unused_sgs=check_security_groups_for_security_groups(region,unused_sgs)
	unused_sgs=check_lambda_security_groups(region,unused_sgs)
        printout_unused_security_groups(region,unused_sgs)
