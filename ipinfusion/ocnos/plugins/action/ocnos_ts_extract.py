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
# Contains Action Plugin methods for OcNOS TechSupport Extraction Module
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
        
        # Get the remote server details from the Playbook
        remote_host = self._task.args.get('remote_host')
        remote_path = self._task.args.get('remote_path')
        remote_username = self._task.args.get('remote_username')
        remote_password = self._task.args.get('remote_password')
        node_type = self._task.args.get('node_type','physical')
        
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

        result = {'changed': False, 'copied_files': [], 'failed': False}
        
        #Compile the Tech Support File Pattern
        ts_file_pat = re.compile(r'\S+_tech_support.*')
        
        try:
            # Try to establish a connection to the DUT using netmiko 
            session = ConnectHandler(**connection_dict)
            
            #Enter into Debian Linux
            session.enable()
            session.send_command('start-shell',expect_string='$')
            
            #Privilege Escalation to root
            session.send_command('su -', expect_string='Password:')
            session.send_command('root', expect_string='#')
            
            #Change Directory to /var/log where Tech Support Files are stored
            session.send_command('cd /var/log',expect_string='#',read_timeout=30)
            
            #Gather previous tech support files
            output = session.send_command('ls')
            
            file_list = []
            for files in output.split():
                match = re.match(ts_file_pat, files)
                if match:
                     file_list.append(match.group())
            
            #clean up the files
            if len(file_list) > 0:
                for files in file_list:
                    session.send_command(f'rm -f {files}')

            session.send_command("cmlsh -e 'show techsupport all'")
            state = 1
            
            result['copy_stat'] =''

            #iterate to check the TS File status every 10 seconds for 10 attempts
            for i in range(0,10):
                ts_status = session.send_command("cmlsh -e 'show techsupport status'")
                #Action block when TS File is completed
                if 'Is Complete' in ts_status:
                    output = session.send_command('ls')
                    file_list = []
                    for files in output.split():
                        match = re.match(ts_file_pat, files)
                        if match:
                            file_list.append(match.group())
                            if node_type == 'vm':
                                copy_cmd = f'copy filepath /var/log/{file_list[0]} scp scp://{remote_username}:{remote_password}@{remote_host}{remote_path}/{file_list[0]}'
                            else:

                                copy_cmd = f'copy filepath /var/log/{file_list[0]} scp scp://{remote_username}:{remote_password}@{remote_host}{remote_path}/{file_list[0]} vrf management'
                            session.send_command('exit',expect_string='$')
                            session.send_command('exit',expect_string='#')
                            output = session.send_command(copy_cmd, expect_string='#', read_timeout=60)
                            state = 0
                    #break from iterating loop
                    break
                else:
                    #display.display('Still Waiting..')
                    time.sleep(10)

            if 'Failed' in output:
                state = 1
            
            if state:
                raise AnsibleError(f"Copy failed for {file_list[0]}: {output}")    
            else:
                result['copied_files'].append(file_list[0])
                result['TS_File_Location'] = f'{remote_path}@{remote_host}'
                result['copy_stat'] += output
                result['changed'] = True
        
        except Exception as e:
            raise AnsibleError(f"OcNOS TechSupport extraction failed: {str(e)}")
        return result        
