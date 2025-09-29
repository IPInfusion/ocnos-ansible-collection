# IP Infusion OcNOS Ansible Collection

Ansible collection for automating IP Infusion OcNOS.

OcNOS is a network OS for White Box switches. Refer https://www.ipinfusion.com/products for details.

The OcNOS Ansible Collection can be installed via https://galaxy.ansible.com/ipinfusion/ocnos.

# Requirements
Ansible 2.9 or newer.

# Using OcNOS collection Modules

## Install
You can install OcNOS collection modules through these methods:

Install from Galaxy:
```
$ ansible-galaxy collection install ipinfusion.ocnos
```

Install from the downloaded tarball:

Once downloaded run ansible-galaxy command as follows
```
$ ansible-galaxy collection install ipinfusion-ocnos-1.x.x.tar.gz       
Process install dependency map
Starting collection install process
Installing 'ipinfusion.ocnos:1.x.x' to '/home/<someones home>/.ansible/collections/ansible_collections/ipinfusion/ocnos'
```

During the installation of the modules, other collections may install such as ansible.netcommon and ansible.utils as dependencies.

If there is no external connectivity, it may be required to install the dependent collections manually.

## Using an ansible playbook
The module name is used as ipinfusion.ocnos.<module>.

And you need to define properly define ansible vars.
The following shows an example of group_vars/ocnos.yml
```
ansible_connection: network_cli
ansible_network_os: ipinfusion.ocnos.ocnos
ansible_become: yes
ansible_become_method: enable
ansible_ssh_user: ocnos
ansible_ssh_pass: ocnos
```

Examble playbook
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
'show xxx' commands are typically used, but it is also usable for other commands which are available through "enable" mode on the switch.

## ocnos_config
ocnos_config sends commands for configuration which are available in "configure" mode.

## ocnos_ping
ocnos_ping does ping from the target node to another node. This module will fail when the ping fails.

## ocnos_bgp_facts
ocnos_bgp_facts collects information about BGP. Currently, this modules only supports bgp neighbor.

## ocnos_isis_facts
ocnos_isis_facts collects information about ISIS. Currently, this modules only supports ISIS neighbor.

## ocnos_config_backup
Action Plugin that copies OcNOS Running Configuration into a remote location.

## ocnos_config_restore
Action Plugin that copies a configuration file from remote location to OcNOS Startup configuration.

## ocnos_pcap
Action Plugin that Captures OcNOS Interface's control plane packets and copy into remote location.

## ocnos_sw_update
Action Plugin that updates the OcNOS Software using sys-update http method.

## ocnos_core_extract
Action Plugin that extracts crash files (Cores) and exports the GDB Log into remote location.

## ocnos_ts_extract
Action Plugin that extracts OcNOS TechSupport files and exports into remote location.

## ocnos_iperf3
Action Plugin that enables IPERF3 on OcNOS Devices either as a server or as a client.
This plugin is strictly for testing purposes and not recommended for Production Deployments.
OcNOS Rate Limits the CPU packets to 20Mbps

## ocnos_validate
Action Plugin that compares the Actual Output and the Expected Output of OcNOS Show commands.


Please refer to the IPI provided documentation available at https://documentation.ipinfusion.com/home/Content/LibraryPages/Library.htm for more detail.
