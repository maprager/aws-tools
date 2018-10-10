# This code is still under construction and being improved continuously - use it at your peril. Oct 10th 2018

# Example lambda.meta file below:
# Begin lambda.meta file
#####################################
# Lambda Configuration              #
#####################################
#f
# _accounts ~ json{ 'accounts' : [ 'all' ] }
#  Explanation: gives a list of accounts ( numbers) where the lambda will be deployed to.
#  'all' - is a reserved name - referring to all accounts
#  'accountNumber' - is the account number itself.
#  Mandatory
#
# _deploymentPath ~ us-east-2
#  Explanation: determins where the lambda will be deployed - can be one of the following values
#  global - meaning global region
#  all-regions - meaning in every region
#  <region-name> - meaning a specific region
#  Mandatory
#
# _state ~ present
#  Explanation: explains whether to add or remove the lambda in question ( present | absent )
#  Mandatory
#
# _target_Path ~ test
#  Explanation: If you want to place the lambda in a sub folder within the bucket
#  Mandatory
#
# _target_File ~ test-9
#  Explanation: The name of the target lambda (main file)
#  Mandatory
#
# _handler ~ test-9.lambda_handler
#  Explanation: The name of the handler the lambda calls
#  Mandatory
#
# _desc    ~ Dummy lambda to just say hello
#  Explanation: The description of the lambda (single line)
#  Optional | Default Value = None
#
# _timeout ~ 30
#  Explanation: The timeout of the lambda in seconds
#  Optional | Default Value = 30
#
# _memory  ~ 128
#  Explanation: the member of the lambda in mb
#  Optional | Default Value = 128
#
# _role    ~ uyaffeLambda
#  The permissions of the lambda - must pre-exist, the name of the roles is given here
#  Mandatory
#
# _language ~ python2.7
#  Explanantion: The language of the lambda - can be one of the following:
#        NODE-JS FAMILY: nodejs|nodejs4.3|nodejs6.10|nodejs8.10|nodejs4.3-edge
#        PYTHON FAMILY: python2.7|python3.6
#        DOTNETCORE FAMILY: dotnetcore1.0|dotnetcore2.0|dotnetcore2.1
#        GO FAMILIY: go1.x
#        JAVA FAMILY: java8
#  Mandatory
#
# _trigger ~ rate(5 minutes)
#  Explanation: The trigger of the lambda - can be one of the following:
#        Scheduled Events:
#        cron(0/5 * * * * *)
#        rate(5 minutes)
#        See more examples at: https://docs.aws.amazon.com/AmazonCloudWatch/latest/events/ScheduledEvents.html
#        Event Patterns: (Examples)
#        json({ "source": [ "aws.ec2" ], "detail-type": [ "EC2 Instance State-change Notification" ] })
#        json({ "source": [ "aws.s3" ], "detail-type": [ "AWS API Call via CloudTrail" ], "detail": { "eventSource": [ "s3.amazonaws.com" ], "eventName": [ "DeleteBucket" ] } })
#        Event patterns can be previewed  in the AWS console or in online documentation
#  Mandatory
#
# _tag ~ json({"StamName" :  "StamValue", "foo" : "bar" })
#  Explanation: Key-Value pairs in json structure
#  Optional | Default Value = None
#
# _env ~ json({"Variables": { "SNSArn": "arn:aws:sns:us-east-2:988483802534:maprager" } })
#  Explanation:: Key-Value pairs in json structure
#  Optional | Default Value = None
#
# _networkAttachment ~ None
#  Optional | Default Value = None
#
# _dontUploadToS3 ~ True | False
#  Explanation: If set to true, the lambda is assumed uploaded to the S3 bucket already and zipped.
#               If set to false, the lambda will assume it is one file, and upload the file.
#  Optional | Default Value = False (i.e upload)
#####################################
# End Lambda Configuration          #
#####################################
### End lambda.meta file

from __future__ import print_function, unicode_literals
import json
import re
import boto3
from io import BytesIO
from gzip import GzipFile
import StringIO
import zipfile
import zlib
import os
import sys
from os import environ
from time import gmtime, strftime

#### Global Variables
codecommit = boto3.client('codecommit')
buff = StringIO.StringIO()  

### Lambda metadata global values.
desc = "None"
timeout=30
memory=128
tag = "None"
myenv = "None"
vpcconfig = "None"
dontUploadToS3 = False
state = 'Present'
s3Bucket = 'None' 
s3Path = 'None'
s3File = 'dummy'
handler = 'None' 
trigger = 'None' 
role = 'None' 
language = 'None'
deploymentPath = 'None'
finalTrigger = 'None'
finalTag = 'None'
finalEnv = 'None'
finalVpcConfig = 'None'
accountToDeployOn = 'None'
myAccount='None'

#### Definition of our Global Region.
global_region="us-east-2"

#### What allregions refer to
# allregions = ['ap-south-1','eu-west-3','eu-west-2','eu-west-1','ap-northeast-2','ap-northeast-1','sa-east-1','ca-central-1','ap-southeast-1','ap-southeast-2','eu-central-1','us-east-1','us-east-2','us-west-1','us-west-2']
allregions = ['eu-west-2','eu-west-1','ca-central-1','ap-southeast-1','ap-southeast-2','eu-central-1','us-east-1','us-east-2','us-west-1','us-west-2']

### Not sure if I need this ....
# allaccounts = ['315899926467','376668106783','879082133162','988483802534', '180234257160', '405770569624', '587793318824','173930319961','087259623654']

def splitall(path):
    allparts = []
    while 1:
        parts = os.path.split(path)
        if parts[0] == path:  # sentinel for absolute paths
            allparts.insert(0, parts[0])
            break
        elif parts[1] == path: # sentinel for relative paths
            allparts.insert(0, parts[1])
            break
        else:
            path = parts[0]
            allparts.insert(0, parts[1])
    return allparts

### The actual function responsible for adding or deleting the lambda.    
def createUpdateLambda(mystate,s3Bucket,s3Path, s3File, desc,language,timeout,memory,handler, role, thisregion,thetrigger,mytags,myenv,myvpcconfig):
    global accountToDeployOn, myAccount, deploymentPath, allregions, trigger,tag,vpcconfig,dontUploadToS3,finalTrigger,finalTag,finalEnv,finalVpcConfig

    if mystate == 'absent':
        print ("Got the absent clause, attempting to delete lambda: ",s3File," in region ", thisregion)
        try:
            # attempt to remove the lambda
            deleteLambda = boto3.client('lambda',region_name=thisregion)
            rc = deleteLambda.delete_function(FunctionName=s3File)
            print (rc)
            return
        except:
           # for some reason the lambda didn't delete 
            print ("Delete Lambda Failed")
            return
    
    ### If you get to this point, then the state required is to make the lambda present.
    bucketName=s3Bucket+"-"+thisregion
    # convert rolename to an arn.
    iam = boto3.resource('iam')
    roleArn = iam.Role(role).arn

    ## Create a lambda based on the uploaded S3 zip
    newLambda = boto3.client('lambda',region_name=thisregion)
    createANewLambda=True
    # Either create a new lambda or update existing one...
    try:
        response = newLambda.create_function( FunctionName=s3File, 
                                          Runtime=language, 
                                          Description=desc,
                                          Timeout=int(timeout),
                                          MemorySize=int(memory),
                                          Role=roleArn, 
                                          Handler=handler,  
                                          Code={'S3Bucket': bucketName, 'S3Key':s3Path+'/'+s3File+'.zip'} )
                                          
        lambdaArn=response['FunctionArn']
        createANewLambda=True
    except:
        response = newLambda.update_function_code( FunctionName=s3File,
                                             S3Bucket = bucketName,
                                             S3Key = s3Path+'/'+s3File+'.zip')
                                             # Publish = True )
        lambdaArn=response['FunctionArn']
        response = newLambda.update_function_configuration(FunctionName=s3File,
                                             Runtime=language, 
                                             Description=desc,
                                             Timeout=int(timeout),
                                             MemorySize=int(memory),
                                             Role=roleArn,
                                             Handler=handler)
        createANewLambda=False           
        
    
    # try to tag the function
    ### Do we remove old tags first ??
    if mytags != "None":
        rc = newLambda.tag_resource(Resource=lambdaArn,Tags=json.loads(mytags))
        print (rc)
    
    
    # try to update lambda with the new environment variables 
    if myenv != "None":
        rc = newLambda.update_function_configuration(FunctionName=s3File,Environment=json.loads(myenv))
        print (rc)
    
    # If connected to a specific VPC - then put in the config here.
    if myvpcconfig != "None":
        print (myvpcconfig)
        rc = newLambda.update_function_configuration(FunctionName=s3File,VpcConfig=json.loads(myvpcconfig))
        print (rc)
    
    # create a cloudwatch event based on the trigger sent - 
    ## this part would need to be dependant on the type of trigger.
    event = boto3.client('events',region_name=thisregion)
    if thetrigger.startswith('cron') or thetrigger.startswith('rate'):
          RuleArn = event.put_rule( Name= s3File+".trigger", ScheduleExpression=str(thetrigger), State='ENABLED', Description="Trigger for lambda:"+s3File)
    else:
          RuleArn = event.put_rule( Name= s3File+".trigger", EventPattern=str(thetrigger), State='ENABLED', Description="Trigger for lambda:"+s3File)

    # Update Triggers
    if createANewLambda == False:
        ### First delete the current target if the lambda is being updated - avoids using versions
        print ("removing existing target")
        event.remove_targets(Rule=s3File+".trigger", Ids=[ s3File ] )
        
    event.put_targets(Rule=s3File+".trigger", Targets=[{'Id': s3File, 'Arn': lambdaArn }])
    
    thetime=strftime("%Y%m%d_%H_%M_%S", gmtime())
    myStatement=s3File+'_'+thetime

    ## Add permissions for executing the lambda
    lambda_client = boto3.client('lambda',region_name=thisregion)
    lambda_response = lambda_client.add_permission(
            FunctionName=s3File,
            StatementId=myStatement,
            Action="lambda:InvokeFunction",
            Principal="events.amazonaws.com",
            SourceArn=RuleArn['RuleArn']
    )
    # print ("add permission response:")
    # print (lambda_response)
    return


### Function - to read a Json string from the comments.
def  readJson(mystring):
    try:
        index1=mystring.find('(')
        index2=mystring.rfind(')')
        return mystring[index1+1:index2]
    except:
        return None    

### Function - to behave like grep to pull out strings from comments.
def grep(large_string, substring):
    for line in (large_string.split('\n')):
        if substring in line:
            return (line)
            
### Function - create a zipfile            
def createZipfile():
    # This is where my zip will be written
    zip_archive = zipfile.ZipFile(buff, mode='w')

    return zip_archive

### Function - close the zipfile    
def closeZipfile(z):
    global accountToDeployOn, myAccount, state, s3Bucket, s3Path, s3File, handler, trigger, role, language, desc, timeout, memory,tag,myenv,vpcconfig,dontUploadToS3
    
    # Write the contents to a temporary file.
    with open('/tmp/'+s3File+".zip", 'w') as f:
         f.write(buff.getvalue())
    z.close()

### Function - upload the zip file to all the regions.    
def uploadZipToS3Buckets():
    global accountToDeployOn, myAccount, deploymentPath, allregions, state, s3Bucket, s3Path, s3File, handler, trigger, role, language, desc, timeout, memory,tag,myenv,vpcconfig,dontUploadToS3,finalTrigger,finalTag,finalEnv,finalVpcConfig

    # print (allregions)
    
    for region in allregions:
        bucketName=s3Bucket+"-"+region    
        print (region)
        s3 = boto3.client ('s3',region_name=region)
        ## Create Bucket if necessary
        try:
             response = s3.create_bucket(ACL='private', Bucket=bucketName,CreateBucketConfiguration= {'LocationConstraint': region } )
        except:
             print ("Bucket might exist already")
             pass
        
        ## Try to create the target path if necessary:
        try:
            response = client.put_object( Bucket=bucketName, Body='', Key=s3Path+'/')
        except:
            print ("Folder might exist already")
            pass
        
        ## Try to upload the new S3 file
        try: 
            response=s3.upload_file("/tmp/"+s3File+".zip", bucketName, s3Path+"/"+s3File+".zip" )
            print (response)
        except:
            print("Cant upload file")  
            pass

### Function -    add a file to the inmem zipfile.
def addFileToZip(zip_archive,file,fileContent):
    ### Zipping feature
    info = zipfile.ZipInfo(file)
    info.external_attr = 0100755 << 16L
    zip_archive.writestr(info, fileContent, zipfile.ZIP_DEFLATED )
    return

### Function = deploy the lambda to the correct locations
def deployLambda():
    global accountToDeployOn, myAccount, deploymentPath, allregions, state, s3Bucket, s3Path, s3File, handler, trigger, role, language, desc, timeout, memory,tag,myenv,vpcconfig,dontUploadToS3,finalTrigger,finalTag,finalEnv,finalVpcConfig
    
    if (myAccount in accountToDeployOn) or ( 'all' in accountToDeployOn ) :
        # Now need to see where to deploy lambda - Global / Regional / PerVPC ?
        # If lambda exists - update code.
        # otherwise create lambda
        if deploymentPath.startswith('all-regions'):
            print ('Deploy on all regions')
            for myregion in allregions:
                createUpdateLambda(state,s3Bucket,s3Path, s3File,desc,language,timeout,memory,handler, role, myregion,finalTrigger,finalTag,finalEnv,finalVpcConfig)
        elif deploymentPath.startswith ('global'):
            print ('Deploy in the global region')
            createUpdateLambda(state,s3Bucket,s3Path, s3File,desc,language,timeout,memory,handler, role, global_region,finalTrigger,finalTag,finalEnv,finalVpcConfig)
        else: 
            ## A region should have been specified - so deploy it to that region only.
            # deploymentPath.startswith ('regions'):
            print ('Deploy in a specific region')
            ## find out which region to deploy in:
            #pathArray=deploymentPath.split('/')
            #print (pathArray)
            regionToDeploy=deploymentPath
            createUpdateLambda(state,s3Bucket,s3Path, s3File,desc,language,timeout,memory,handler, role,regionToDeploy,finalTrigger,finalTag,finalEnv,finalVpcConfig)
    else:
        print ("No need to install in this account", myAccount)

# Function - read the lambda meta data - store in global variables.
def readLambdaMetaData(actualContent):
    
    global accountToDeployOn, myAccount,deploymentPath, state, s3Bucket, s3Path, s3File, handler, trigger, role, language, desc, timeout, memory,tag,myenv,vpcconfig,dontUploadToS3,finalTrigger,finalTag,finalEnv,finalVpcConfig
    
    s3Bucket = environ['S3BucketPrefix']  
    
    # from the content - pull out the pragmas
    # Mandatory Arguments Firsts:
    deploymentPath   = grep (actualContent, "_deploymentPath").split("~")[1].lstrip()
    state            = grep (actualContent, "_state").split("~")[1].lstrip()
#    s3Bucket         = grep (actualContent, "_target_Bucket").split("~")[1].lstrip()
    s3Path           = grep (actualContent, "_target_Path").split("~")[1].lstrip()
    s3File           = grep (actualContent, "_target_File").split("~")[1].lstrip()
    handler          = grep (actualContent, "_handler").split("~")[1].lstrip()
    trigger          = grep (actualContent, "_trigger").split("~")[1].lstrip()
    role             = grep (actualContent, "_role").split("~")[1].lstrip()
    language         = grep (actualContent, "_language").split("~")[1].lstrip()
    accounts         = grep (actualContent, "_accounts").split("~")[1].lstrip()
    
    # Optional Arguments
    ## Default Settings First
    desc = "None"
    timeout=30
    memory=128
    tag = "None"
    myenv = "None"
    vpcconfig = "None"
    dontUploadToS3 = False
    
    try:
           desc       = grep (actualContent, "_desc").split("~")[1].lstrip()
    except:
           pass
           
    try:       
           timeout    = grep (actualContent, "_timeout").split("~")[1].lstrip()
    except:
           pass
    
    try:       
           memory     = grep (actualContent, "_memory").split("~")[1].lstrip()    
    except:
           pass
           
    try:        
           tag        = grep (actualContent, "_tag").split("~")[1].lstrip()  
    except:
           pass
           
    try:        
           myenv      = grep (actualContent, "_env").split("~")[1].lstrip()  
    except:
           pass
           
    try:        
           vpcconfig  = grep (actualContent, "_networkAttachment").split("~")[1].lstrip()  
    except:
           pass    
   
    try:        
           dontUploadToS3  = grep (actualContent, "_dontUploadToS3").split("~")[1].lstrip()  
    except:
           pass     
       
    # pull the trigger out
    if trigger.startswith('cron'):
        finalTrigger=trigger
    elif trigger.startswith('rate'):
        finalTrigger=trigger
    elif trigger.startswith('json'):
        finalTrigger=readJson(trigger)
    else:
        finalTrigger="None"
    #print (finalTrigger)

    # pull the tag out
    if tag != "None":
        finalTag=readJson(tag)
    else:
        finalTag="None"
    
    # pull the environment out
    if myenv != "None":
        finalEnv=readJson(myenv)
    else:
        finalEnv = "None"
    
    if vpcconfig != "None":
        finalVpcConfig = readJson(vpcconfig)
    else:
        finalVpcConfig = "None"
    
    if accounts != 'None':
        accountToDeployOn = readJson(accounts)['accounts']
    else:
        accountToDeployOn = 'all'
    return

### Function - used by child account lambdas - to set up the assume role session
def aws_session(role_arn=None, session_name='my_session'):
    """
    If role_arn is given assumes a role and returns boto3 session
    otherwise return a regular session with the current IAM user/role
    """
    if role_arn:
        client = boto3.client('sts')
        response = client.assume_role(RoleArn=role_arn, RoleSessionName=session_name)
        session = boto3.Session(
            aws_access_key_id=response['Credentials']['AccessKeyId'],
            aws_secret_access_key=response['Credentials']['SecretAccessKey'],
            aws_session_token=response['Credentials']['SessionToken'])
        print(response)
        return session
    else:
        return boto3.Session()
        
#### Function - the main handler of the lambda
def lambda_handler(event, context):
    global global_region, myAccount
    
    ## Get my account id
    myAccount=boto3.client('sts').get_caller_identity().get('Account')
    print ("My Account is:", myAccount)
    
    # Check to see if the lambda type is Parent or Child
    # If Parent - then it is in the main account,
    # If Child - then it is in the child account.
    lambdaType=environ['LambdaType']
    
    if lambdaType == "Parent": 
        codecommit = boto3.client('codecommit')
        # Get the repo name
        #print (event)
        repository = event['Records'][0]['eventSourceARN'].split(':')[5]
    
        # Get the commit Id
        commitId=event['Records'][0]['codecommit']['references'][0]['commit']
        #print("My commit id is: ", commitId)
    else: #child account lambda
        msg = json.loads(event['Records'][0]['Sns']['Message'])
        repository = msg['Records'][0]['eventSourceARN'].split(':')[5]
        print ("Repo to access is: ", repository)
        
        # Get the commit Id
        commitId=msg['Records'][0]['codecommit']['references'][0]['commit']
        print("My commit id is: ", commitId)
    
        role_arn=environ['RoleArn']
        session = aws_session(role_arn=role_arn,session_name="cc-session")
        print (session)

        codecommit = session.client('codecommit')

    # Common part (parent/child) from here
    
    # Get the parent (previous commit)
    response = codecommit.get_commit(repositoryName=repository, commitId=commitId)
    AfterCommitId=response['commit']['parents'][0]
    #print("My parent commit id is: ",AfterCommitId )
    #print(response)
    
    # get the difference between the two commits.
    diffs = codecommit.get_differences(repositoryName=repository, beforeCommitSpecifier=AfterCommitId,afterCommitSpecifier=commitId)
    # print ("The differnces between the two are ", diffs )
    # print (diffs)
    
    # Get  the maindirectory of the lambda.
    maindir=splitall(diffs['differences'][0]['afterBlob']['path'])[0]
    # print (">>>", maindir)
    
    # Initialize the zipfile
    myzip = createZipfile()
    
    ## Get list of files = in the directory to put in the lambda.
    diffs = codecommit.get_differences(repositoryName=repository, afterCommitSpecifier='HEAD',afterPath=maindir)
    print (diffs)
    for i in diffs['differences']:
         file=i['afterBlob']['path']
         fileContent= codecommit.get_blob(repositoryName=repository,blobId=i['afterBlob']['blobId'])
         actualContent=fileContent['content']
         print("Filename:", file )
         # print (actualContent)
         if (file == 'lambda.meta'):
             print ("got lambda.meta")
             ## Read a whole lot of settings:
             readLambdaMetaData(actualContent)
             ## Then add the file to the zip.
             addFileToZip(myzip,file,actualContent)
             print ("=========================")
    
    # close the zipfile - should contain all the files in the directory and below.
    closeZipfile(myzip)
    
    # upload the Zipfile to all S3 buckets.
    uploadZipToS3Buckets()
    
    # now deploy the lambda
    deployLambda()

    return {
        "statusCode": 200,
        "body": json.dumps('Lambda complete')
    }
