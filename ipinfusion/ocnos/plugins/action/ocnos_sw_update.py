# Copyright (C) 2019 IP Infusion
#
# GNU General Public License v3.0+
#
# This program is distributed in the hope that it will be useful,
# but WITHOUT ANY WARRANTY; without even the implied warranty of
# MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE.  See the
# GNU General Public License for more details.
#
# (see COPYING or https://www.gnu.org/licenses/gpl-3.0.txt)
#
# Contains Action Plugin methods for OcNOS Software Update Module
# IP Infusion
#

from ansible.plugins.action import ActionBase
from ansible.errors import AnsibleError
from ansible.utils.display import Display
from datetime import datetime
import re
import time
from netmiko import ConnectHandler
from paramiko.proxy import ProxyCommand

display = Display()

class ActionModule(ActionBase):
    def run(self, tmp=None, task_vars=None):
        
        inventory_hostname = task_vars.get('inventory_hostname')

        required_args = ['update_url']
        missing_args = [arg for arg in required_args if self._task.args.get(arg) is None]

        if missing_args:
            raise AnsibleError(f"Missing required arguments: {', '.join(missing_args)}")

        update_url = self._task.args.get('update_url')
        #if no name-server is provided, use the ipinfusion default.
        name_server = self._task.args.get('name_server','10.16.10.23')

        # Extract OcNOS connection details from inventory
        host = self._task.args.get('ansible_host') or task_vars.get('ansible_host')
        username = self._task.args.get('ansible_ssh_user') or task_vars.get('ansible_ssh_user')
        password = self._task.args.get('ansible_ssh_pass') or task_vars.get('ansible_ssh_pass')
        port = str(self._task.args.get('ansible_port') or task_vars.get('ansible_port') or 22)
        
        connection_dict = {
            'host': host,
            'username': username,
            'password': password,
            'device_type': 'ipinfusion_ocnos'
            }

        #Handle SSH Proxy or Jump Server Setting
        proxy_cmd = (
                self._task.args.get('ansible_ssh_common_args')
                or task_vars.get('ansible_ssh_common_args')
        )
        if proxy_cmd:
             proxy_cmd = proxy_cmd.strip()
             if proxy_cmd.startswith("-o ProxyCommand="):
                 # Remove the prefix
                 proxy_cmd = proxy_cmd.replace("-o ProxyCommand=", "", 1).strip()
                 # Strip surrounding quotes
                 proxy_cmd = proxy_cmd.strip('"').strip("'")
             # Replace %h and %p placeholders with actual host/port
             proxy_cmd = proxy_cmd.replace("%h", host).replace("%p", port)
             connection_dict['sock'] = ProxyCommand(proxy_cmd)
            
        if not all(connection_dict.values()):
            raise AnsibleError("Missing OcNOS connection details in inventory/task vars.")

        result = {'changed': False, 'Update_String': '' ,'failed': False}
        
        try:
            # Try to establish a connection to the DUT using netmiko 
            session = ConnectHandler(**connection_dict)
            
            #Enter into Debian Linux
            session.enable()
            session.send_config_set([f'ip name-server vrf management {name_server}','commit'])
            session.send_command('copy run start',read_timeout=60)
            #Clean up the /installers to make room for new images
            installer_list = session.send_command('show installers')
            if installer_list:
                installer_list = session.send_command('show installers').split('\n')
                image_list = [ i.split('/')[2] for i in installer_list ]
                if len(image_list) > 2:
                    for images in image_list:
                        session.send_command(f'sys-update delete {images}')
                        time.sleep(2)
            update_command = f'sys-update install source-interface eth0 {update_url}'
            output = session.send_command_timing(update_command)
            output = session.send_command_timing('y')
            display.display(output)
            # Below if condition is due to OcNOS DNS resolver timing issue.
            #the condition is hit when only one working name-server entry is in ocnos
            if 'Installer download failed' in output:
                result['Update_String'] = f'Device Failed to upgrade because {output}'
                raise AnsibleError(f"OcNOS Software Upgrade Failed {output}")
            else:
                output = session.send_command_timing('!')
                #display.display(output)
                if '%% Installer download failed' in output:
                    display.display('Now I am here....')
                    result['Update_String'] = f'Device Failed to upgrade because {output}'
                    result['failed'] = True
                    raise AnsibleError(f"OcNOS Software Upgrade Failed: {output}")
                if '%% Device license is not compatible with new software' in output:
                    temp_op = session.send_command_timing('n')
                    result['Update_String'] = f'Device Failed to upgrade because of Software and License incompatibility'
                    result['failed'] = True
                    raise AnsibleError(f"OcNOS Software Upgrade Failed: {output}")
                if '%% Software version you are trying to upgrade is already installed' in output:
                    temp_op = session.send_command_timing('n')
                    display.display('Software is already installed and the device will not reload')
                    result['Update_String'] = f'Device Failed to upgrade as the software version is already installed'
                    result['failed'] = True
                    raise AnsibleError(f"OcNOS Software Upgrade Failed: Software version already installed.")
            #wait for 75 seconds for sysupdate to reload the device   
            display.display('Wait for 75 Seconds for sys-update to reload the device...')
            time.sleep(75)
            try:
                if session.is_alive():
                    display.display('Device failed to reload even after 60 seconds')
                    result['update_string'] = f'Device failed to reload'
                    raise AnsibleError(f"OcNOS Software Upgrade Failed:")
                else:
                    display.display('Device Upgraded and reload process started by sys-update')
                    result['update_string'] = f'Device Upgraded and reloaded'
            except Exception as e:
                if "Broken pipe" in str(e):
                    display.display('Device Upgraded and reload process started by sys-update')
                    result['update_string'] = f'Device Upgraded and reloaded'
                else:
                    raise AnsibleError(f"OcNOS Software Upgrade Failed: {str(e)}")
        
        except Exception as e:
            raise AnsibleError(f"OcNOS Software Upgrade Failed: {str(e)}")
        return result
