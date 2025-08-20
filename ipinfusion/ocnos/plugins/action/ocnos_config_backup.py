from ansible.plugins.action import ActionBase
from ansible.errors import AnsibleError
from ansible.utils.display import Display
from datetime import datetime
import re
import time
from netmiko import ConnectHandler

display = Display()

class ActionModule(ActionBase):
    def run(self, tmp=None, task_vars=None):
        
        inventory_hostname = task_vars.get('inventory_hostname')

        required_args = ['remote_host', 'remote_path', 'remote_username', 'remote_password', 'node_type']
        missing_args = [arg for arg in required_args if self._task.args.get(arg) is None]

        if missing_args:
            raise AnsibleError(f"Missing required arguments: {', '.join(missing_args)}")

        # Get the remote server details from the Playbook
        remote_host = self._task.args.get('remote_host')
        remote_path = self._task.args.get('remote_path')
        remote_username = self._task.args.get('remote_username')
        remote_password = self._task.args.get('remote_password')
        node_type = self._task.args.get('node_type')
        
        # Extract OcNOS connection details from inventory
        host = self._task.args.get('ansible_host') or task_vars.get('ansible_host')
        username = self._task.args.get('ansible_ssh_user') or task_vars.get('ansible_ssh_user')
        password = self._task.args.get('ansible_ssh_pass') or task_vars.get('ansible_ssh_pass')
        
        connection_dict = {
            'host': host,
            'username': username,
            'password': password,
            'device_type': 'ipinfusion_ocnos'
            }
            
        if not all(connection_dict.values()):
            raise AnsibleError("Missing OcNOS connection details in inventory/task vars.")

        result = {'changed': False, 'copied_files': [], 'failed': False}
        
        try:
            # Try to establish a connection to the DUT using netmiko 
            session = ConnectHandler(**connection_dict)
            
            #Enter into Debian Linux
            session.enable()
            
            time_stamp = str(datetime.now()).split('.')[0].replace(' ','_')
            cmd_list = []

            json_cmd = f'show json running > /var/log/{inventory_hostname}_{time_stamp}.json'
            cmd_list.append(json_cmd)
            xml_cmd = f'show xml running > /var/log/{inventory_hostname}_{time_stamp}.xml'
            cmd_list.append(xml_cmd)
            cli_cmd =  f'show running > /var/log/{inventory_hostname}_{time_stamp}.cfg'
            cmd_list.append(cli_cmd)

            for cmds in cmd_list:
                display.display(f'dumping {cmds}')
                session.send_command(cmds)
                time.sleep(60)
            
            file_list = [f'{inventory_hostname}_{time_stamp}.json', f'{inventory_hostname}_{time_stamp}.xml', f'{inventory_hostname}_{time_stamp}.cfg']
            state = 1
            copy_list = []

            for file in file_list:
                copy_list.append(file)
                if node_type == 'vm':
                    copy_cmd = f'copy filepath /var/log/{file} scp scp://{remote_username}:{remote_password}@{remote_host}{remote_path}/{file}'
                else:
                    copy_cmd = f'copy filepath /var/log/{file} scp scp://{remote_username}:{remote_password}@{remote_host}{remote_path}/{file} vrf management'
                output = session.send_command(copy_cmd, expect_string='#', read_timeout=60)
                display.display(f'copying file {file} to {remote_host} and then wait for 30 seconds')
                time.sleep(30)
                if "Copy Success" in output or "copy success" in output.lower():
                    state = 0
            
                if state:
                    raise AnsibleError(f"Copy failed for {file}: {output}")    
                else:
                    result['changed'] = True
        
            result['copied_files'].append(copy_list)
        
        except Exception as e:
            raise AnsibleError(f"OcNOS Configuration Backup failed: {str(e)}")
        return result        
