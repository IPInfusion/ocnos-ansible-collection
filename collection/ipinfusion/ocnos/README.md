# IP Infusion OcNOS Ansible Collection

Ansible collection for automating IP Infusion OcNOS.

OcNOS is a network OS for White Box switch. Refer [https://www.ipinfusion.com/products/ocnos/] for the detail.

# Requirements
Ansible 2.9 or newer.

# Using OcNOS collection Modules

## Install
To install from Galaxy,
```
$ ansible-galaxy collection install ipinfusion.ocnos
```

Also, it's possible to install it from downloaded tarball.
Once downloaded the OcNOS collection package, run ansible-galaxy command as follows
```
$ ansible-galaxy collection install ipinfusion-ocnos-1.0.0.tar.gz       
Process install dependency map
Starting collection install process
Installing 'ipinfusion.ocnos:1.0.0' to '/home/<someones home>/.ansible/collections/ansible_collections/ipinfusion/ocnos'
```

## Using with ansible playbook
The module name is used as ipinfusion.ocnos.<module>.

Examble of a playbook
```
---
- hosts: ocnos

  tasks:
  - name: Test OcNOS Facts
    ipinfusion.ocnos.ocnos_facts:
      gather_subset: all
    register: result

  - name: Show Facts
    debug:
      msg: The version is {{ ansible_net_version }}. HW model is {{ ansible_net_model }}, Neighbor info is {{ ansible_net_neighbors }}
```


# Supported Modules

## ocnos_facts
ocnos_facts collects information of the switch.

## ocnos_commands
ocnos_commands sends commands to the switch. 
'show xxx' commands are typicall used, but it is also usable for other commands which are available on enabled mode on the switch.

## ocnos_config
ocnos_config sends commands for configuration which are available on configure mode.

## ocnos_ping
ocnos_ping does ping from the target node to another node. This module will fail when the ping was not suceeded.


Please refer the IPI provided documents for the detail.

