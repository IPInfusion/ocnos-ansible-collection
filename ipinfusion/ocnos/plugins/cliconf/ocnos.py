# Copyright (C) 2020 IP Infusion.
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
# Contains CLIConf Plugin methods for OcNOS Modules
# IP Infusion
#
from __future__ import (absolute_import, division, print_function)
__metaclass__ = type

DOCUMENTATION = """
---
cliconf: ocnos
short_description: Use ocnos cliconf to run command on IP Infusion OcNOS
description:
  - This ocnos plugin provides low level abstraction APIs for
    sending and receiving CLI commands from IP Infusion OcNOS devices.
"""

import re
import json

from itertools import chain

from ansible.module_utils._text import to_bytes, to_text
from ansible.module_utils.common._collections_compat import Mapping
from ansible_collections.ansible.netcommon.plugins.module_utils.network.common.config import NetworkConfig, dumps
from ansible_collections.ansible.netcommon.plugins.module_utils.network.common.utils import to_list
from ansible.plugins.cliconf import CliconfBase, enable_mode
from ansible.errors import AnsibleConnectionFailure

ignored_errors = [
        re.compile(r"%% L2/L3 mode cannot be explicitly configured on aggregator interfaces"),
        re.compile(r"%% Configuration already exists"),
        re.compile(r"%% VLAN with the same name exists"),
        re.compile(r"%% Port is already aggregated"),
        re.compile(r"%% Cannot configure member interface of port-channel"),
        re.compile(r"%% VLAN/Range Incorrect.Uncreated vlan/s cannot be delete"),
        re.compile(r"%% IP address, if configured, removed due to disabling VRF"),
        re.compile(r"%% BGP is already running,"),
        re.compile(r"%% Bridge 1 already exists "),
        re.compile(r"%% Cannot configure, Remove VRF first"),
        re.compile(r"%% DHCP Client Feature is already Disabled."),
        re.compile(r"%% Extended asn capability is already enabled"),
        re.compile(r"%% Given configuration is already applied on agent/system"),
        re.compile(r"%% Interface already in breakout mode"),
        re.compile(r"%% L2/L3 mode cannot be explicitly configured on aggregator interfaces with member"),
        re.compile(r"%% Link not bound to channel-group"),
        re.compile(r"% Parameter not configured"),
        re.compile(r"%% Port is already aggregated. "),
        re.compile(r"%% QoS is already enabled"),
        re.compile(r"%% Statistics is already enabled"),
        re.compile(r"%% This filter group is already enabled"),
        re.compile(r"%% This set value must be unique"),
        re.compile(r"%% RT cannot be configured without RD configured"),
        re.compile(r"%%VNID already mapped to access-if"),
        re.compile(r"%% All dynamic routes on this physical port will be lost due to this ESI/system mac change"),
]



class Cliconf(CliconfBase):

    def get_device_info(self):
        device_info = {}

        device_info['network_os'] = 'ocnos'
        reply = self.get('show version')
        data = to_text(reply, errors='surrogate_or_strict').strip()

        match = re.search(r'^ Software Product: OcNOS, Version: (.*?)', data, re.M | re.I)
        if match:
            device_info['network_os_version'] = match.group(1)

        match = re.search(r'^Hardware Model: (\S+)', data, re.M | re.I)
        if match:
            device_info['network_os_model'] = match.group(1)

        reply = self.get('show hostname')
        data = to_text(reply, errors='surrogate_or_strict').strip()
        if data:
            device_info['network_os_hostname'] = data
        else:
            device_info['network_os_hostname'] = "NA"

        return device_info

    def get_device_operations(self):
        return {
            'supports_diff_replace': True,
            'supports_commit': True,
            'supports_rollback': False,
            'supports_defaults': False,
            'supports_onbox_diff': False,
            'supports_commit_comment': False,
            'supports_multiline_delimiter': False,
            'supports_diff_match': True,
            'supports_diff_ignore_lines': True,
            'supports_generate_diff': True,
            'supports_replace': False
        }

    def get_option_values(self):
        return {
            'format': ['text'],
            'diff_match': ['line', 'strict', 'exact', 'none'],
            'diff_replace': ['line', 'block'],
            'output': []
        }

    def get_capabilities(self):
        result = super(Cliconf, self).get_capabilities()
        result['rpc'] += ['get_diff', 'run_commands']
        result['device_operations'] = self.get_device_operations()
        result.update(self.get_option_values())
        return json.dumps(result)

    @enable_mode
    def get_config(self, source='running', format='text', flags=None):
        if source not in ('running', 'startup'):
            msg = "fetching configuration from %s is not supported"
            return self.invalid_params(msg % source)
        if source == 'running':
            cmd = 'show running-config'
        else:
            cmd = 'show startup-config'
        return self.send_command(cmd)

    @enable_mode
    def edit_config(self, candidate=None, commit=True, replace=None, comment=None):
        operations = self.get_device_operations()
        self.check_edit_config_capability(operations, candidate, commit, replace, comment)

        resp = {}
        results = []
        requests = []
        for cmd in chain(['configure terminal'], to_list(candidate)):
            #results.append(self.send_command(cmd))
            #requests.append(cmd)
            try:
                requests.append(cmd)
                result = self.send_command(cmd)
                results.append(result)
            except AnsibleConnectionFailure as e:
                pass
                ignored = False
                for regex in ignored_errors:
                    match = regex.search(str(e))
                    if match:
                        ignored = True
                        results.append("IGNORED %s" % str(e))
                        break

                if not ignored:
                    raise e
                    #results.append("ERROR %s" % str(e))
                    #pass

        ignored = True
        if commit:
            commitresult = self.send_command('commit')
            if '% Failed to commit' in commitresult:
                ignored = False
                for regex in ignored_errors:
                    if regex.search(commitresult):
                        ignored = True
                        results.append("IGNORED %s" % commitresult)
                        break

        endresult = self.send_command('end')

        if '%% Un-committed transactions present' in endresult:
            self.send_command('abort transaction')
            self.send_command('end')

        if commit and not ignored:
            raise AnsibleConnectionFailure
            #results.append("ERROR %s" % str(e))
            #pass

        resp['request'] = requests
        resp['response'] = results
        return resp

    def get(self, command, prompt=None, answer=None, sendonly=False, newline=True, check_all=False):
        return self.send_command(command=command, prompt=prompt, answer=answer, sendonly=sendonly, newline=newline, check_all=check_all)

    def get_diff(self, candidate=None, running=None, diff_match='line', diff_ignore_lines=None, path=None, diff_replace='line'):

        diff = {}
        device_operations = self.get_device_operations()
        option_values = self.get_option_values()

        if candidate is None and device_operations['supports_generate_diff']:
            raise ValueError("candidate configuration is required to generate diff")

        if diff_match not in option_values['diff_match']:
            raise ValueError("'match' value %s in invalid, valid values are %s" % (
                diff_match, ', '.join(option_values['diff_match'])))

        if diff_replace not in option_values['diff_replace']:
            raise ValueError("'replace' value %s in invalid, valid values are %s" % (
                diff_replace, ', '.join(option_values['diff_replace'])))

        # prepare candidate configuration
        candidate_obj = NetworkConfig(indent=1)
        candidate_obj.load(candidate)

        if running and diff_match != 'none':
            # running configuration
            running_obj = NetworkConfig(indent=1, contents=running, ignore_lines=diff_ignore_lines)
            configdiffobjs = candidate_obj.difference(running_obj, path=path, match=diff_match, replace=diff_replace)

        else:
            configdiffobjs = candidate_obj.items

        diff['config_diff'] = dumps(configdiffobjs, 'commands') if configdiffobjs else ''
        return diff

    def run_commands(self, commands=None, check_rc=True):
        if commands is None:
            raise ValueError("'commands' value is required")

        responses = list()
        for cmd in to_list(commands):
            if not isinstance(cmd, Mapping):
                cmd = {'command': cmd}

            output = cmd.pop('output', None)
            if output:
                raise ValueError("'output' value %s is not supported for run_commands" % output)

            try:
                out = self.send_command(**cmd)
            except AnsibleConnectionFailure as e:
                if check_rc:
                    raise
                out = getattr(e, 'err', to_text(e))

            responses.append(out)

        return responses

    def set_cli_prompt_context(self):
        """
        Make sure we are in the operational cli mode
        :return: None
        """
        if self._connection.connected:
            out = self._connection.get_prompt()

            if out is None:
                raise AnsibleConnectionFailure(message=u'cli prompt is not identified from the last received'
                                                       u' response window: %s' % self._connection._last_recv_window)

            if to_text(out, errors='surrogate_then_replace').strip().endswith(')#'):
                self._connection.queue_message('vvvv', 'In Config mode, sending exit to device')
                self._connection.send_command('exit')
            else:
                self._connection.send_command('enable')
