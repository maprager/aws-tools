################
# This work is still under construction - copy at your peril ! 20/Aug/2018
# Based on Git and CodeCommit for managing site lambda's
################

from __future__ import print_function, unicode_literals
import re
import json
import boto3
from io import BytesIO
from gzip import GzipFile
import StringIO
import zipfile
import zlib
from time import gmtime, strftime

codecommit = boto3.client('codecommit')
global_region="us-east-2"

# allregions = ['ap-south-1','eu-west-3','eu-west-2','eu-west-1','ap-northeast-2','ap-northeast-1','sa-east-1','ca-central-1','ap-southeast-1','ap-southeast-2','eu-central-1','us-east-1','us-east-2','us-west-1','us-west-2']
allregions = ['eu-west-2','eu-west-1','ca-central-1','ap-southeast-1','ap-southeast-2','eu-central-1','us-east-1','us-east-2','us-west-1','us-west-2']

def grep(large_string, substring):
    for line in (large_string.split('\n')):
        if substring in line:
            return (line)
            
            
def uploadFileToAllS3Regions(actualContent,s3File, s3Bucket, s3Path):

    ### Zipping feature
    compression = zipfile.ZIP_DEFLATED 
    # This is where my zip will be written
    buff = StringIO.StringIO()
    zip_archive = zipfile.ZipFile(buff, mode='w')
    info = zipfile.ZipInfo(s3File+".py")
    info.external_attr = 0100755 << 16L
    zip_archive.writestr(info, actualContent, zipfile.ZIP_DEFLATED )
    zip_archive.close()
    
    # Write the contents to a temporary file.
    with open('/tmp/'+s3File+".zip", 'w') as f:
         f.write(buff.getvalue())
         
    for region in allregions:
        bucketName=s3Bucket+"-"+region    
        print (region)
        s3 = boto3.client ('s3',region_name=region)
        ## Create Bucket if necessary
        try:
             response = s3.create_bucket(ACL='private', Bucket=bucketName,CreateBucketConfiguration= {'LocationConstraint': region } )
        except:
             # print ("Bucket might exist already")
             pass
        
        ## Try to create the target path if necessary:
        try:
            response = client.put_object( Bucket=bucketName, Body='', Key=s3Path+'/')
        except:
            pass
            # print ("Folder might exist already")

        
        ## Try to upload the new S3 file
        try: 
          response=s3.upload_file("/tmp/"+s3File+".zip", bucketName, s3Path+"/"+s3File+".zip" )
        except:
          print("Cant upload file")
          
    return
    
def createUpdateLambda(mystate,s3Bucket,s3Path, s3File, desc,language,timeout,memory,handler, role, thisregion,thetrigger,mytags,myenv,myvpcconfig):
    
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
    
    bucketName=s3Bucket+"-"+thisregion
    # convert rolename to an arn.
    iam = boto3.resource('iam')
    roleArn = iam.Role(role).arn
    # print (roleArn)
    
    ## Now that the s3zip is uploaded - create another lambda based on that s3 zipfile
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
    
    
    # try to update lambda with the new environment variables ?
    if myenv != "None":
        rc = newLambda.update_function_configuration(FunctionName=s3File,Environment=json.loads(myenv))
        print (rc)
    
   
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
    # print (RuleArn['RuleArn'])
    
    print(createANewLambda)
    if createANewLambda == False:
        ### First delete the current target if the lambda is being updated - avoids using versions
        print ("removing existing target")
        event.remove_targets(Rule=s3File+".trigger", Ids=[ s3File ] )
        
    event.put_targets(Rule=s3File+".trigger", 
                      Targets=[{
                            'Id': s3File, 
                            'Arn': lambdaArn
                      }] 
                      )
    
    thetime=strftime("%Y%m%d_%H_%M_%S", gmtime())
    myStatement=s3File+'_'+thetime

    lambda_client = boto3.client('lambda',region_name=thisregion)
    lambda_response = lambda_client.add_permission(
            FunctionName=s3File,
            StatementId=myStatement,
            Action="lambda:InvokeFunction",
            Principal="events.amazonaws.com",
            SourceArn=RuleArn['RuleArn']
    )
    print ("add permission response:")
    print (lambda_response)
    return

def  readJson(mystring):
    try:
        index1=mystring.find('(')
        index2=mystring.rfind(')')
        return mystring[index1+1:index2]
    except:
        return None

def lambda_handler(event, context):
    global global_region
    #print (event)
    
    # Get the repo name
    repository = event['Records'][0]['eventSourceARN'].split(':')[5]
    
    # Get the commit Id
    commitId=event['Records'][0]['codecommit']['references'][0]['commit']
    #print("My commit id is: ", commitId)
    
    # Get the parent (previous commit)
    response = codecommit.get_commit(repositoryName=repository, commitId=commitId)
    AfterCommitId=response['commit']['parents'][0]
    #print("My parent commit id is: ",AfterCommitId )
    #print(response)
    
    # get the difference between the two commits.
    diffs = codecommit.get_differences(repositoryName=repository, beforeCommitSpecifier=AfterCommitId,afterCommitSpecifier=commitId)
    # print ("The differnces between the two are ", diffs )
    deploymentPath=diffs['differences'][0]['afterBlob']['path']
    #print(deploymentPath)
    
    
    # Get the file contets of the change - hopefully one lambda
    fileContent=codecommit.get_blob(repositoryName=repository,blobId=diffs['differences'][0]['afterBlob']['blobId'])
    #print("The content of the file changed are: ", fileContent['content'])
    
    actualContent=fileContent['content']
    # from the content - pull out the pragmas
    # Mandatory Arguments Firsts:
    state      = grep (actualContent, "_state").split("~")[1].lstrip()
    s3Bucket   = grep (actualContent, "_target_Bucket").split("~")[1].lstrip()
    s3Path     = grep (actualContent, "_target_Path").split("~")[1].lstrip()
    s3File     = grep (actualContent, "_target_File").split("~")[1].lstrip()
    handler    = grep (actualContent, "_handler").split("~")[1].lstrip()
    trigger    = grep (actualContent, "_trigger").split("~")[1].lstrip()
    role       = grep (actualContent, "_role").split("~")[1].lstrip()
    language   = grep (actualContent, "_language").split("~")[1].lstrip() 
    
    # Optional Arguments
    ## Default Settings First
    desc = "None"
    timeout=30
    memory=128
    tag = "None"
    myenv = "None"
    vpcconfig = "None"
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
        
    # Uploade the new zipped file to all s3 regions
    uploadFileToAllS3Regions(actualContent,s3File, s3Bucket, s3Path)
    
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
    elif deploymentPath.startswith ('regions'):
        print ('Deploy in a specific region')
        ## find out which region to deploy in:
        pathArray=deploymentPath.split('/')
        print (pathArray)
        regionToDeploy=pathArray[1]
        createUpdateLambda(state,s3Bucket,s3Path, s3File,desc,language,timeout,memory,handler, role,regionToDeploy,finalTrigger,finalTag,finalEnv,finalVpcConfig)
        
    return 'Return from lambda_handler dummy'
