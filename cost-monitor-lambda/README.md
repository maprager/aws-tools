# Cost Monitoring Lambda

## Description
The following code creates a cost monitoring lambda
The lambda sends a message to a HookURL that posts warning messages to an MS-teams channel. 

## Variables
There are four variables that need to be set up:

- region - the region where the lambda will be located
- hookURL - the MS-Teams Web connector address
- avgCost - The daily average cost of your tenant ( in $) 
- threshold - the percentage difference upon which an alert will be generated 

## For example - 
If your daily cost is $100 
and Your Threshold is 20 (%)
If your daily cost rises above $120 you will get an alert to the MS-Teams channel of your choice.

## Installation 
After downloading:
 - Create an environment.yml file for example
 ```
    region: eu-west-1
    threshold: "20"
    avgCost: "100"
    hookURL:  https://outlook.office.com/webhook/<Your MS-Teams WebHook>
```
 -   Run:
 ``` 
 ansible-playbook main.yaml -e@environement.yml 
```
