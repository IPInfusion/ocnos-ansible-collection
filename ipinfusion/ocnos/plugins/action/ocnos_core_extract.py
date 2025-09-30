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
# Contains Action Plugin methods for OcNOS Core File extraction Module
# IP Infusion
#

from ansible.plugins.action import ActionBase
from ansible.errors import AnsibleError
from ansible.utils.display import Display
import re
import time
from netmiko import ConnectHandler
from paramiko.proxy import ProxyCommand

display = Display()

class ActionModule(ActionBase):
    def run(self, tmp=None, task_vars=None):
        # Collect task arguments
        remote_host = self._task.args.get('remote_host')
        remote_path = self._task.args.get('remote_path')
        remote_username = self._task.args.get('remote_username')
        remote_password = self._task.args.get('remote_password')
        node_type = self._task.args.get('node_type','physical')
        trans = self._task.args.get('transport','scp')

        if trans == 'scp' or trans =='ftp':
            pass
        else:
            raise AnsibleError("Module only supports ftp or scp transport types")

        # Extract OcNOS connection details from inventory
        host = self._task.args.get('ansible_host') or task_vars.get('ansible_host')
        username = self._task.args.get('ansible_ssh_user') or task_vars.get('ansible_ssh_user')
        password = self._task.args.get('ansible_ssh_pass') or task_vars.get('ansible_ssh_pass')
        port = str(self._task.args.get('ansible_port') or task_vars.get('ansible_port') or 22)
        inventory_hostname = task_vars.get('inventory_hostname')

        connection_dict = {
            'host': host,
            'username': username,
            'password': password,
            'device_type': 'ipinfusion_ocnos'
        }

        if not all(connection_dict.values()):
            raise AnsibleError("Missing OcNOS connection details in inventory/task vars.")

        result = {'changed': False, 'copied_files': [], 'copy_stats': '', 'failed': False}

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

        try:
            conn = ConnectHandler(**connection_dict)
            conn.enable()

            core_output = conn.send_command('show cores')
            core_files = re.findall(r'core_.*', core_output)

            if not core_files:
                result['msg'] = "No core files found"
                return result

            core_file_logs = []
            for file in core_files:
                details_output = conn.send_command(f'show core {file} details', read_timeout=60)
                match = re.search(r'core_.*', details_output)
                if match:
                    core_file_logs.append(match.group())
                    #display.display(f'appended {match.group()} to core log list')
                    time.sleep(120)
                    dest_filename = f"{inventory_hostname}_{match.group()}"
                    if node_type == 'vm':
                        copy_cmd = (
                            f"copy filepath /tmp/{match.group()} "
                            f"{trans} {trans}://{remote_username}:{remote_password}@{remote_host}{remote_path}/{dest_filename}"
                        )
                    else:
                        copy_cmd = (
                            f"copy filepath /tmp/{match.group()} "
                            f"{trans} {trans}://{remote_username}:{remote_password}@{remote_host}{remote_path}/{dest_filename} vrf management"
                        )
                    #display.display(f'the copy command is {copy_cmd}')
                    output = conn.send_command(copy_cmd)
                    #display.display(output)
                    time.sleep(10)

                    if "Copy Success" in output or "copy success" in output.lower():
                        result['copied_files'].append(dest_filename)
                        result['copy_stats'] += output
                        result['core_file_location'] = f'{remote_path}@{remote_host}'
                        result['changed'] = True
                    else:
                        raise AnsibleError(f"Copy failed for {core_file}: {output}")

        except Exception as e:
            raise AnsibleError(f"OcNOS core extraction failed: {str(e)}")

        conn.send_command('clear cores')
        return result
