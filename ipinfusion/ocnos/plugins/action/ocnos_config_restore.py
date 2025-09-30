# Copyright (C) 2025 IP Infusion
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
# Contains Action Plugin methods for OcNOS Configuration Restore Module
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

        required_args = ['remote_host', 'remote_path', 'remote_username', 'remote_password','cfg_file']
        missing_args = [arg for arg in required_args if self._task.args.get(arg) is None]

        if missing_args:
            raise AnsibleError(f"Missing required arguments: {', '.join(missing_args)}")

        # Get the remote server details from the Playbook
        remote_host = self._task.args.get('remote_host')
        remote_path = self._task.args.get('remote_path')
        remote_username = self._task.args.get('remote_username')
        remote_password = self._task.args.get('remote_password')
        node_type = self._task.args.get('node_type','physical')
        trans = self._task.args.get('transport','scp')
        config_file = self._task.args.get('cfg_file')

        if trans == 'scp' or trans =='ftp':
            pass
        else:
            raise AnsibleError("Module only supports ftp or scp transport types")
        
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
            
        if not all(connection_dict.values()):
            raise AnsibleError("Missing OcNOS connection details in inventory/task vars.")

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

        result = {'changed': False, 'Reboot_String': '' , 'string_op': '','failed': False}
        output_status = []
        string_op = ''
        state=1
        
        try:
            # Try to establish a connection to the DUT using netmiko 
            session = ConnectHandler(**connection_dict)
            
            #Enter into Debian Linux
            session.enable()
            
            if node_type == 'vm':
                copy_cmd = f'copy {trans} {trans}://{remote_username}:{remote_password}@{remote_host}{remote_path}/{config_file} startup-config'
            else:
                copy_cmd = f'copy {trans} {trans}://{remote_username}:{remote_password}@{remote_host}{remote_path}/{config_file} startup-config vrf management'
            output = session.send_command(copy_cmd, expect_string='#', read_timeout=60)
            output_status.append(output)
            if "Copy Success" in output or "copy success" in output.lower():
                state = 0
            
            if state:
                raise AnsibleError(f"Copy failed for {config_file}: {output}")    
            else:
                result['changed'] = True
        
            string_op += output_status[0]
            result['string_op'] = string_op

            output = session.send_command_timing('reload')
            if 'Would you like' in output:
                session.send_command_timing('n')
                session.send_command_timing('y')
            else:
                session.send_command_timing('y')

            try:
                if session.is_alive():
                    result['Reboot_string'] = 'Device Failed to Reboot'
                else:
                    result['Reboot_String'] = 'Device Rebooted Successfully'
            except Exception as e:
                if "Broken pipe" in str(e):
                    result['Reboot_String'] = 'Device Rebooted Successfully (proxy closed)'
                else:
                    raise AnsibleError(f"OcNOS Configuration Restore failed: {str(e)}")

        
        except Exception as e:
            raise AnsibleError(f"OcNOS Configuration Restore failed: {str(e)}")
        return result 
