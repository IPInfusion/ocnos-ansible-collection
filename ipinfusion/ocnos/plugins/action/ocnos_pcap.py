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
# Contains Action Plugin methods for OcNOS Packet Capture Module
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

        required_args = ['remote_host', 'remote_path', 'remote_username', 'remote_password','capture_interfaces','capture_timeout']
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
        capture_interfaces = self._task.args.get('capture_interfaces')
        capture_timeout = self._task.args.get('capture_timeout')

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

        result = {'changed': False, 'copied_files': [], 'failed': False}

        proxy_cmd = (
                self._task.args.get('ansible_ssh_common_args')
                or task_vars.get('ansible_ssh_common_args')
        )        

        #Handle SSH Proxy or Jump Server Setting
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
            # Try to establish a connection to the DUT using netmiko 
            session = ConnectHandler(**connection_dict)

            #Enter into Debian Linux
            session.enable()

            #Enter the OcNOS Debian Shell
            session.send_command('start-shell',expect_string='$')

            #Escalate Privliges to root for capture using tshark
            session.send_command('su -',expect_string='Password:')
            session.send_command('root',expect_string='#')

            #Function to get the tshark PIDs (stale or old) if running and kill it before starting new.
            def get_and_kill_tshark_pids():
                raw_ts_pids = session.send_command('pidof tshark')
                ts_pids = re.sub(r'\x1B\[[0-?]*[ -/]*[@-~]', '', raw_ts_pids).strip()
                for pids in ts_pids.split():
                    session.send_command(f'kill -9 {pids}')
                    time.sleep(2)

            # Make sure the stale tshark pids are killed
            get_and_kill_tshark_pids()

            #construct tshark string based on the input interface
            ts_string = []
            for interfaces in capture_interfaces.split():
                ts_string.append(f"tshark -i {interfaces} -w /var/log/{inventory_hostname}_{interfaces}.pcap >/dev/null 2> /dev/null &")
            
            time_stamp = str(datetime.now()).split('.')[0].replace(' ','_')

            def time_stamper(file, time_stamp):
                m = file.split('.')
                m.insert(1,time_stamp)
                file_name = m[0]+'_'+m[1]+'.'+m[2]
                return file_name
            
            for strings in ts_string:
                display.display(f'Capture Started on {strings.split()[2]}')
                session.send_command(strings)
                time.sleep(1)

            #wait for packet capture to complete and then kill the tshark PIDs
            display.display(f'Waiting for {capture_timeout} seconds for Captures to complete')
            time.sleep(capture_timeout)
           
            # cleanup the tshark pids
            get_and_kill_tshark_pids()

            #come back to ocnos prompt
            session.send_command('exit',expect_string='$')
            session.send_command('exit',expect_string='#')

            # File Copy operation to remote locations
            file_list = []
            for interface_caps in capture_interfaces.split():
                file_list.append(f'{inventory_hostname}_{interface_caps}.pcap')
            state = 1
            copy_list = []
        

            for file in file_list:
                export_file = time_stamper(file,time_stamp)
                copy_list.append(export_file)
                if node_type == 'vm':
                    copy_cmd = f'copy filepath /var/log/{file} {trans} {trans}://{remote_username}:{remote_password}@{remote_host}{remote_path}/{export_file}'
                else:
                    copy_cmd = f'copy filepath /var/log/{file} {trans} {trans}://{remote_username}:{remote_password}@{remote_host}{remote_path}/{export_file} vrf management'
                output = session.send_command(copy_cmd, expect_string='#', read_timeout=60)
                display.display(f'copying file {file} to {remote_host} and then wait for 5 seconds')
                time.sleep(5)
                if "Copy Success" in output or "copy success" in output.lower():
                    state = 0
            
                if state:
                    raise AnsibleError(f"Copy failed for {file}: {output}")    
                else:
                    result['changed'] = True
        
            result['copied_files'].append(copy_list)
            session.disconnect()
        
        except Exception as e:
            raise AnsibleError(f"OcNOS Packet Capture failed: {str(e)}")
        return result        
