# aws-tools
Tools to be used within AWS

- elb_target_group.MD - Ansible process using AWS tags to set a proxy protocol in a target group (due to lack of support in ansible).

- upcomingScheduledEvents.sh - A script using aws cli, jq and bash to print out in an easy form all the upcoming aws events across all the regions for your account.

- show-orphaned-volumes.py - a python script (to be used in a lambda), to find any orphaned volumes in ones account.

- create_vpc_service_endpoints.sh - a script to create service endpoints on a port in a vpc.

- unused_eips.py - a script to list unuused eips in your region, and release them if required.

- checkIamUserPolicies.py - a lambda script to checkIamUserPolicies - to see if they are secure.

- get_blackholes.sh - shell script to find network blackholes.

- doesBucketExist.sh - Script to check to see if an S3 bucket name is available

- netta_bug  - a silly song based on Israel's Eurovision Song Winner from 2018 

- ms-teams.py - a lambda to notify ms teams on spot instances stops and starts and other instances

- daily-cost.py - a lambda to keep a daily check on your account costs, and to notify you of any changes in ms-teams.
