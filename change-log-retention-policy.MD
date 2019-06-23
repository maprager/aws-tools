# Saving money - by changing log retentions

# Problem -
Cloudwatch logs are created automatically without log expirations. Recently, I discovered that I was paying a lot of money for logs that were essentially just sitting there, because they were unexpired, and have been sitting in our account gathering dust. 
By just changing the expiration of logs to say , seven days - we could save a lot of money.

# Solution -
By running the following simple bash script, the expiration of the cloudwatch logs can be changed -


```
#!/bin/bash

for region in `aws ec2 describe-regions | grep RegionName | tr '"' ' ' | awk '{print $3}'`
do
  echo "Changing expiry on region: $region"
  for logGroup in `aws logs describe-log-groups --region $region | grep logGroupName | tr '"' ' ' | awk '{print $3}'`
   do
	  echo "Changing LogGroup: $logGroup in region: $region"
          aws logs put-retention-policy --log-group-name $logGroup --retention-in-days 7 --region $region 
   done
done
