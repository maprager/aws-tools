#!/bin/bash

# Simple Script to check to see if a bucket exists
# Mark Prager - October 2018

### Check command line argument
if [ "$#" -ne 1 ]; then
    echo "Illegal number of parameters"
    echo "Usage: doesBucketExist.sh <bucketname>"
    exit
fi

### Get bucket name to test
bucketname=$1

### Now check to see if the bucket name exists.
result=$(curl $bucketname.s3.amazonaws.com 2>/dev/null | tr '<>' '  ' | grep Code | awk '{print $3}')
if [ "$result" == "NoSuchBucket" ]; then
  echo "$bucketname does not exist"
else
  echo "$bucketname exists !"
fi
