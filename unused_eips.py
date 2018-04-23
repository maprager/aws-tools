#!/usr/bin/python
import boto3

### Python code to list unused EIPs, and release them if required
### Mark Prager 2018
###
### ask_user from: https://gist.github.com/garrettdreyfus/8153571
### Main function based on: https://stackoverflow.com/questions/38749484/how-to-list-all-unused-elastic-ips-and-release-them-using-boto3 and adapted to work :)
###
### Works only for your current region defined.
### Feel free to use and adapt.

def ask_user(question):
    check = str(raw_input(question+" ? (y/n): ")).lower().strip()
    try:
       if check[0] == 'y':
          return True
       elif check[0] == 'n':
          return False
       else:
           print('Invalid Input')
           return ask_user()
    except Exception as error:
       print("Please enter valid inputs (y or n)")
       print(error)
       return ask_user(question)

client = boto3.client('ec2')
addresses_dict = client.describe_addresses()
print "The following are unused eip addresses:"
for eip_dict in addresses_dict['Addresses']:
     if "AssociationId" not in eip_dict:
          print eip_dict
          response=ask_user("Would you like to release it")
          if (response == True):
              client.release_address(AllocationId=eip_dict['AllocationId'])
          else:
              print "Ignoring this unused EIP"
              print "WARNING: Unused EIPs cost money - see here for more details:"
              print "https://aws.amazon.com/premiumsupport/knowledge-center/elastic-ip-charges/"
