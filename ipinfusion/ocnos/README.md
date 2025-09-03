## License

This project is licensed under the GNU General Public License v3.0 (GPL-3.0).  
You may obtain a copy of the license at the LICENSE file or from [https://www.gnu.org/licenses/gpl-3.0.txt](https://www.gnu.org/licenses/gpl-3.0.txt).

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


Please refer the IPI provided documents for the detail.

# Version history
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
