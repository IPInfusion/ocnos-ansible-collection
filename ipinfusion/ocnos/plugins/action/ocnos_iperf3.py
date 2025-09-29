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
# Contains Action Plugin methods for OcNOS IPERF3 Module
# IP Infusion
#

from ansible.plugins.action import ActionBase
from ansible.errors import AnsibleActionFail
from ansible.utils.display import Display
from netmiko import ConnectHandler
import time
import re
import paramiko
from paramiko.proxy import ProxyCommand

display = Display()

class ActionModule(ActionBase):

    def run(self, tmp=None, task_vars=None):
        result = super().run(tmp, task_vars)
        cmd = self._task.args.get('cmd')

        if not cmd:
            raise AnsibleActionFail("Missing required argument: cmd")

        # Get connection data from inventory
        host = self._task.args.get('ansible_host') or task_vars.get('ansible_host')
        username = self._task.args.get('ansible_ssh_user', 'ocnos') or task_vars.get('ansible_ssh_user')
        password = self._task.args.get('ansible_ssh_pass', 'ocnos') or task_vars.get('ansible_ssh_pass')
        port = str(self._task.args.get('ansible_port') or task_vars.get('ansible_port') or 22)
        device_type = 'ipinfusion_ocnos'

        if not host:
            raise AnsibleActionFail("Missing 'ansible_host' in inventory for the target")

        # Prepare connection
        conn = dict(
            host=host,
            username=username,
            password=password,
            device_type=device_type,
        )

        # Handle jump host (ansible_ssh_common_args → ProxyCommand)
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

            conn['sock'] = ProxyCommand(proxy_cmd)

        try:
            device = ConnectHandler(**conn)
            device.enable()

            # Enter shell
            device.send_command('start-shell', expect_string=r'\$')
            time.sleep(1)
            device.send_command('su -', expect_string='Password:')
            device.send_command('root', expect_string=r'#')

            # kill command if nothing given
            try:
                cmd.split()[1]
            except:
                cmd = "kill -9 `ps aux | grep iperf | grep -v grep | awk '{print $2}'`"

            # Server mode: run in background
            if '-s' in cmd.split():
                cmd = f'nohup {cmd} >/dev/null 2>/dev/null &'

            # get the timer pattern from the iperf3 cmd to adjust the read_timeout
            timer_pattern = re.compile(r'-t\s\d+')
            try:
                if re.findall(timer_pattern, cmd)[0].split()[1]:
                    timeout = int(re.findall(timer_pattern, cmd)[0].split()[1])
                    timeout += 10  # tolerance
            except:
                timeout = 30

            iperf_output = device.send_command(cmd, expect_string=r'#', read_timeout=timeout)
            device.disconnect()

            result['cmd'] = cmd
            clean_output = re.sub(r'\x1B(?:[@-Z\\-_]|\[[0-?]*[ -/]*[@-~])', '', iperf_output)
            result['output'] = clean_output.strip().splitlines()

            if 'nohup' in cmd:
                result['changed'] = True
                return result

            if 'iperf Done.' in iperf_output:
                result['changed'] = True
                result['success'] = True
            elif 'iperf3' in iperf_output:
                result['changed'] = True
                result['success'] = False
                result['failed'] = True
            else:
                result['changed'] = True
                result['success'] = True

        except Exception as e:
            result['failed'] = True
            result['msg'] = f"Failed to run iperf3 {e}"

        return result

