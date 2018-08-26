# Getting Around ansible limitations using AWS tags.

# Problem -
Ansible 2.6.2 doesn't support proxy-protocol-v2 settings when creating or modifying target groups.

# Solution -
Work around the problem using AWS tags -

Assuming my inventory file contains the following variable:

```
nlb_target_groups:
      - group:
          prefix: HTTPS
          port: 443
          type: 'instance'
          proxy-protocol-v2: True
      - group:
          prefix: Web
          port: 80
          type: 'instance'
          proxy-protocol-v2: False
      - group:
          prefix: AnotherWeb
          port: 8080
          type: 'instance'
          proxy-protocol-v2: False
      - group:
          prefix: HTTPS2
          port: 8443
          type: 'instance'
          proxy-protocol-v2: True
```
Create the target groups with:

``
# Step1  - Create the target groups
- name: Create target groups depending on type of main vpc port
  elb_target_group:
    name: "{{item['group']['prefix']}}-myvpc-tg"
    port: "{{item['group']['port']}}"
    protocol: tcp
    target_type: "{{item['group']['type']}}"
    vpc_id: vpc-12345678
    state: present
    tags:
        Name: "{{item['group']['prefix']}}-myvpc-tg"
        proxy_protocol_v2_enabled: "{{item['group']['proxy-protocol-v2']}}"
  with_items: "{{nlb_target_groups}}"
  register: my_nlb_target_groups
  
## Step 2 - Set the proxy protocol to true when necessary due to lack of support in ansible
- name: Manually alter the target group for proxy-protocol v2 if necessary
  shell:  aws elbv2 modify-target-group-attributes --target-group-arn "{{item['target_group_arn']}}" --attributes Key=proxy_protocol_v2.enabled,Value=true
  when: item['tags']['proxy_protocol_v2_enabled'] == "True"
  with_items: "{{my_nlb_target_groups['results']}} 
```
