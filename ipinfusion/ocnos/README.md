# IP Infusion OcNOS Ansible Collection

Ansible collection for automating IP Infusion OcNOS.

OcNOS is a network OS for White Box switch. Refer [https://www.ipinfusion.com/products/ocnos/] for the detail.

# Requirements
Ansible 2.9 or newer.

# Using OcNOS collection Modules

## Install
You can install OcNOS collection modules as either way.

To install from Galaxy,
```
$ ansible-galaxy collection install ipinfusion.ocnos
```

Also, it's possible to install it from downloaded tarball.
Once downloaded the OcNOS collection package, run ansible-galaxy command as follows
```
$ ansible-galaxy collection install ipinfusion-ocnos-1.x.x.tar.gz       
Process install dependency map
Starting collection install process
Installing 'ipinfusion.ocnos:1.x.x' to '/home/<someones home>/.ansible/collections/ansible_collections/ipinfusion/ocnos'
```

During installing the modules, it installs other collections like ansible.netcommon and ansible.utils by its dependencies.
If you are installing on somewhere the internet unreachable, you may need to install the dependent collections by manual.

## Using with ansible playbook
The module name is used as ipinfusion.ocnos.<module>.

And you need some ansible vars properly.
The following shows an example of group_vars/ocnos.yml
```
ansible_connection: network_cli
ansible_network_os: ipinfusion.ocnos.ocnos
ansible_become: yes
ansible_become_method: enable
ansible_ssh_user: ocnos
ansible_ssh_pass: ocnos
```

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

When you use OcNOS version 5.0 or later, please specify 'commit' variable as well for configuration switches.
The default value is 'true'.
```
---
- hosts: ocnos

  tasks:
  - name: Set hostname
    ipinfusion.ocnos.ocnos_config:
      lines: 'hostname helloworld'
      commit: yes
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

## ocnos_bgp_facts
ocnos_bgp_facts collects information about BGP. Currently, this modules supports only bgp neighbor.

## ocnos_isis_facts
ocnos_isis_facts collects information about ISIS. Currently, this modules supports only ISIS neighbor.

## ocnos_config_backup
Backup the running configuration of OcNOS Devices into a remote location.
The Module Supports both Virtual Machine and Physical Devices.
The Module only supports SCP and FTP Copy Methods.

## ocnos_config_restore
Restore the OcNOS Configurations from a Remote Location to the Startup Config of OcNOS Devices and Reboots.
The Module Support both VMs and Physical Devices and Supports only SCP and FTP Copy Methods.

## ocnos_iperf3
Configures IPERF3 on OcNOS Devices either as a server or as a Client.
The Module Support both VMs and Physical Devices.
This Module is to be used only for Testing and not to be enabled on Production Devices.
IPERF3 Traffic in OcNOS is rate limited to 20Mbps only.

## ocnos_pcap
Captures Packet on Provided interfaces using Tshark and copies into a remote location.
The Module only captures those packets that are punted to CPU (Control Plane Packets).
The Module support both VMs and Physical Devices.

## ocnos_core_extract
This Module extracts the core files and copies the GDB Logs into a remote location.
This Module Supports both VMs and Physical Devices and supports only SCP and FTP Copy methods.

## ocnos_ts_extract
This Module extracts the Tech Support Files and copies into a remote location.
This Module Supports both VMs and Physical Devices and supports only SCP and FTP Copy methods.

## ocnos_sw_update
This Module updates the OcNOS Software of the Physical Devices.
The Module uses OcNOS sys-update function and only supports http method for image copy operation.

## ocnos_validate
This Module compares the TextFSM output of OcNOS with provided inputs.
The Module returns a list of missing entries between Actual Output and Expected Output.


Please refer the IPI provided documents for the detail.

# Version history
- 1.2.5
  - Additional Action Plugins for OcNOS for Software Update, Config Backup, Packet Capture, TechSupport and Core Extraction
- 1.2.3
  - Avoid error when ocnos_facts is used with ansible_pylibssh
- 1.2.2
  - Fixed to work "src': parameter for both 2.9 after
- 1.2.1
  - Fixed to work "src:" parameter of ocnos_config 
- 1.2.0 
  - Merged WhiteStack contribution which handles error messages correctly.
  - Works with OcNOS 5.0.
  - Fixed to work 'backup'
- 1.1.0
  - Works with Ansible 2.10
- 1.0.4
  - Fixed some nit bugs
- 1.0.3
  - ocnos_bgp_facts and ocnos_isis_facts are supported
- 1.0.2
  - Fixed some nit bugs
- 1.0.1
  - Fixed some nit bugs that some modules didn't work as collection
- 1.0.0
  - Initial version
