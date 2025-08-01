#!/usr/bin/python
# -*- coding: utf-8 -*-
#
# Copyright (C) 2020 IP Infusion
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
# Module to Collect facts from OcNOS
# IP Infusion
#
from __future__ import absolute_import, division, print_function
__metaclass__ = type


ANSIBLE_METADATA = {'metadata_version': '1.1',
                    'status': ['preview'],
                    'supported_by': 'community'}

DOCUMENTATION = '''
---
module: ocnos_facts
version_added: "2.10"
author: "IP Infusion OcNOS Ansible Development Team"
short_description: Collect facts from remote devices running IP Infusion OcNOS
description:
  - Collects a base set of device facts from a remote IP Infusion device
    running on OcNOS.  This module prepends all of the
    base network fact keys with C(ansible_net_<fact>).  The facts
    module will always collect a base set of facts from the device
    and can enable or disable collection of additional facts.
extends_documentation_fragment: ocnos
notes:
  - Tested against OcNOS 6.x
options:
  gather_subset:
    description:
      - When supplied, this argument will restrict the facts collected
        to a given subset.  Possible values for this argument include
        all, hardware, config, and interfaces.  Can specify a list of
        values to include a larger subset.  Values can also be used
        with an initial C(M(!)) to specify that a specific subset should
        not be collected.
    type: list
    required: false
    default: '!config'
'''
EXAMPLES = '''
Tasks: The following are examples of using the module ocnos_facts.
---
- name: Test OcNOS Facts
  ocnos_facts:

---
# Collect all facts from the device
- ocnos_facts:
    gather_subset: all

# Collect only the config and default facts
- ocnos_facts:
    gather_subset:
      - config

# Do not collect hardware facts
- ocnos_facts:
    gather_subset:
      - "!hardware"

'''
RETURN = '''
  ansible_net_gather_subset:
    description: The list of fact subsets collected from the device
    returned: always
    type: list
# default
  ansible_net_model:
    description: The model name returned from the IP Infusion OcNOS running device
    returned: always
    type: str
  ansible_net_version:
    description: The OcNOS operating system version running on the remote device
    returned: always
    type: str
  ansible_net_hostname:
    description: The configured hostname of the device
    returned: always
    type: str
  ansible_net_image:
    description: Indicates the active image for the device
    returned: always
    type: str
# hardware
  ansible_net_serialnum:
    description: The serial number of the IP Infusion OcNOS running device
    returned: when hardware is configured
    type: str
  ansible_net_memfree_mb:
    description: The available free memory on the remote device in MB
    returned: when hardware is configured
    type: int
  ansible_net_memtotal_mb:
    description: The total memory on the remote device in MB
    returned: when hardware is configured
    type: int
  ansible_net_cpu
    description: All CPU core model name and load
    returned: when hardware is configured
    type: dict
  ansible_net_vendor
    description: The vendor name of this device
    returned: when hardware is configured
    type: str
  ansible_net_product
    description: The model name of the OcNOS running device. The vendor name is not included
    returned: when hardware is configured
    type: str
# config
  ansible_net_config:
    description: The current active config from the device
    returned: when config is configured
    type: str
# interfaces
  ansible_net_all_ipv4_addresses:
    description: All IPv4 addresses configured on the device
    returned: when interfaces is configured
    type: list
  ansible_net_all_ipv6_addresses:
    description: All IPv6 addresses configured on the device
    returned: when interfaces is configured
    type: list
  ansible_net_interfaces:
    description: A hash of all interfaces running on the system.
      This gives information on description, mac address, mtu, speed,
      duplex and operstatus
    returned: when interfaces is configured
    type: dict
  ansible_net_neighbors:
    description: The list of LLDP neighbors from the remote device
    returned: when interfaces is configured
    type: dict
  ansible_net_lagg
    description: The list of Link aggregations from the remote device
    returned: when interfaces is configured
    type: list
'''

import re
import traceback

from ansible_collections.ipinfusion.ocnos.plugins.module_utils.ocnos import run_commands, ocnos_argument_spec, check_args
from ansible.module_utils._text import to_text
from ansible.module_utils.basic import AnsibleModule
from ansible.module_utils.six import iteritems
from ansible.module_utils.six.moves import zip
from ansible.module_utils.connection import ConnectionError



class FactsBase(object):

    COMMANDS = list()

    def __init__(self, module):
        self.module = module
        self.facts = dict()
        self.responses = None
        self.warnings = []

    def populate(self):
        try:
            self.responses = []
            for cmd in self.COMMANDS:
                try:
                    output = run_commands(self.module, [cmd], check_rc=False)
                    if output and isinstance(output[0], str):
                        if "Command not supported" in output[0]:
                            self.warnings.append(f"Command not supported: {cmd}")
                            self.responses.append(None)
                            continue
                    self.responses.extend(output)
                except ConnectionError as exc:
                    self.warnings.append(f"Failed to execute command '{cmd}': {str(exc)}")
                    self.responses.append(None)
                except Exception as exc:
                    self.warnings.append(f"Unexpected error executing command '{cmd}': {str(exc)}")
                    self.responses.append(None)
        except Exception as exc:
            self.module.fail_json(msg=f"Unexpected error during command execution: {str(exc)}")

    def run(self, cmd):
        try:
            output = run_commands(self.module, [cmd], check_rc=False)
            if output and isinstance(output[0], str) and "Command not supported" in output[0]:
                self.warnings.append(f"Command not supported: {cmd}")
                return None
            return output[0] if output else None
        except ConnectionError as exc:
            self.warnings.append(f"Failed to execute command '{cmd}': {str(exc)}")
            return None
        except Exception as exc:
            self.warnings.append(f"Unexpected error executing command '{cmd}': {str(exc)}")
            return None

    def safe_parse_int(self, value, default="N/A"):
        try:
            return int(value.strip()) if value else default
        except (ValueError, AttributeError):
            return default

    def safe_regex_search(self, pattern, data, group=1, default=None):
        try:
            if not data:
                return default
            match = re.search(pattern, data, re.M | re.I)
            return match.group(group) if match else default
        except (AttributeError, IndexError, re.error) as exc:
            self.warnings.append(f"Regex parsing error: {str(exc)}")
            return default


class Default(FactsBase):

    COMMANDS = ['show version', 'show hostname']

    def populate(self):
        try:
            super(Default, self).populate()
            
            self.facts.update({
                'version': "N/A",
                'model': "N/A",
                'image': "N/A",
                'hostname': "N/A"
            })

            if self.responses and len(self.responses) >= 1 and self.responses[0]:
                data = self.responses[0]
                self.facts['version'] = self.safe_regex_search(r'^ Software Product: OcNOS, Version: (.*)', data) or "N/A"
                self.facts['model'] = self.safe_regex_search(r'^ Hardware Model: (.*)', data) or "N/A"
                self.facts['image'] = self.safe_regex_search(r' Image Filename: (.*)', data) or "N/A"

            if self.responses and len(self.responses) >= 2 and self.responses[1]:
                data_hostname = self.responses[1]
                try:
                    hostname = data_hostname.replace('\n', '').strip()
                    self.facts['hostname'] = hostname if hostname else "N/A"
                except (AttributeError, TypeError):
                    self.warnings.append("Failed to parse hostname data")
                        
        except Exception as exc:
            self.warnings.append(f"Error in Default facts collection: {str(exc)}")


class Hardware(FactsBase):

    COMMANDS = [
        'show hardware-information memory',
        'show system-information board-info',
        'show system-information cpu',
        'show system-information cpu-load',
        'show system sensor',
        "show hardware-information led",
    ]

    def populate(self):
        self.facts.update({
            'memtotal_mb': "N/A",
            'memfree_mb': "N/A",
            'serialnum': "N/A",
            'vendor': "N/A",
            'product': "N/A",
            'cpu': "N/A",
            'ocnos_sensor': "N/A",
            'power_led': "N/A"
        })
        
        try:
            super(Hardware, self).populate()

            if not self.responses:
                self.warnings.append("No hardware command responses received")
                return

            if len(self.responses) > 0 and self.responses[0]:
                data = self.responses[0]
                self.facts['memtotal_mb'] = self.parse_memtotal(data)
                self.facts['memfree_mb'] = self.parse_memfree(data)

            if len(self.responses) > 1 and self.responses[1]:
                data_boardinfo = self.responses[1]
                self.facts['serialnum'] = self.parse_serialnum(data_boardinfo)
                self.facts['vendor'] = self.parse_vendorinfo(data_boardinfo)
                self.facts['product'] = self.parse_productname(data_boardinfo)
                
            if len(self.responses) > 2 and self.responses[2]:
                data_cpu = self.responses[2]
                data_cpuload = self.responses[3] if len(self.responses) > 3 else ""
                self.facts['cpu'] = self.parse_cpu(data_cpu, data_cpuload)

            if len(self.responses) > 4 and self.responses[4] and "Command not supported" not in self.responses[4]:
                data_system = self.responses[4]
                self.facts['ocnos_sensor'] = self.parse_sensor(data_system)

            if len(self.responses) > 5 and self.responses[5] and "Command not supported" not in self.responses[5]:
                data_powerled = self.responses[5]
                self.facts['power_led'] = self.parse_powerled(data_powerled)

        except Exception as exc:
            self.warnings.append(f"Unexpected error in Hardware facts: {str(exc)}")

    def parse_memtotal(self, data):
        match_result = self.safe_regex_search(r'^Total\s*:(.*) MB', data)
        return self.safe_parse_int(match_result) if match_result else "N/A"

    def parse_memfree(self, data):
        match_result = self.safe_regex_search(r'^Free\s*:(.*) MB', data)
        return self.safe_parse_int(match_result) if match_result else "N/A"

    def parse_serialnum(self, data_boardinfo):
        return self.safe_regex_search(r'^Serial Number\s+: (\S+)', data_boardinfo, default="N/A")

    def parse_productname(self, data_boardinfo):
        return self.safe_regex_search(r'^Product Name\s+: (\S+)', data_boardinfo, default="N/A")

    def parse_vendorinfo(self, data_boardinfo):
        return self.safe_regex_search(r'^Vendor Name\s+: (\S+)', data_boardinfo, default="N/A")

    def parse_cpu(self, data_cpu, data_cpuload):
        parsed = dict()
        try:
            if not data_cpu:
                return parsed
                
            for line in data_cpu.split('\n'):
                if len(line) == 0:
                    continue

                match = re.match(r'^Processor\s+:\s(\S+)', line)
                if match:
                    key = match.group(1)
                    parsed[key] = line
                else:
                    match = re.match(r'^Model\s+:\s(.+)', line)
                    if match and key:
                        parsed[key] = match.group(1)
                        key = None

            if data_cpuload:
                for line in data_cpuload.split('\n'):
                    if len(line) == 0:
                        continue
                    match = re.match(r'^CPU core (\S+) Usage\s+:\s(.+)', line)
                    if match:
                        key = match.group(1)
                        if key in parsed:
                            parsed[key] = { "Model": parsed[key], "Load": match.group(2) }

        except Exception as exc:
            self.warnings.append(f"Error parsing CPU information: {str(exc)}")
            
        return parsed

    def parse_sensor(self, data_sensor):
        parsed = {}
        try:
            if not data_sensor:
                return parsed
                
            skip = True
            for line in data_sensor.split('\n'):
                if skip:
                    match = re.match(r'^-+$', line)
                    if match:
                        skip = False
                    continue
                    
                match = re.match(r'^(\S+)\s+\|\s+(\S+)\s+\|\s+([\S\s]+)\s+\|\s+(\S+)\s*\|\s+(\S+)\s+\|\s+(\S+)\s+\|\s+(\S+)\s+\|\s+(\S+)\s+\|\s+(\S+)\s+\|\s+(\S+)', line)
                if match:
                    parsed.update({match.group(1):
                                   {"VALUE": match.group(2), "UNITS": match.group(3).rstrip(), "STATE": match.group(4),
                                    "LNR": match.group(5), "LCR": match.group(6), "LNC": match.group(7),
                                    "UNC": match.group(8), "UCR": match.group(9), "UNR": match.group(10)}})
        except Exception as exc:
            self.warnings.append(f"Error parsing sensor information: {str(exc)}")

        return parsed        

    def parse_powerled(self, data_powerled):
        skipcount = 2
        retvalue = dict()
        try:
            if not data_powerled:
                return retvalue
                
            for line in data_powerled.split('\n'):
                if skipcount > 0:
                    match = re.match(r'^-+$', line)
                    if match:
                        skipcount -= 1
                    continue

                match = re.match(r'^(\S+)\s+(\S+)\s+(.+)$', line)
                if match:
                    retvalue[match.group(1)] = dict(color=match.group(2), description=match.group(3))
        except Exception as exc:
            self.warnings.append(f"Error parsing power LED information: {str(exc)}")
                
        return retvalue


class Config(FactsBase):

    COMMANDS = ['show running-config']

    def populate(self):
        try:
            super(Config, self).populate()
            self.facts['config'] = "N/A"
            
            if self.responses and len(self.responses) > 0 and self.responses[0] and "Command not supported" not in self.responses[0]:
                data = self.responses[0]
                if data and data.strip():
                    self.facts['config'] = data
                else:
                    self.warnings.append("No configuration data received")
        except Exception as exc:
            self.warnings.append(f"Error collecting configuration: {str(exc)}")


class Interfaces(FactsBase):

    COMMANDS = [
        'show interface',
        'show interface brief',
        'show lldp neighbors detail',
        'show interface counters',
        'show interface transceiver',
        'show etherchannel summary'
    ]

    def populate(self):
        try:
            super(Interfaces, self).populate()

            self.facts.update({
                'all_ipv4_addresses': list(),
                'all_ipv6_addresses': list(),
                'interfaces': dict(),
                'neighbors': dict(),
                'lagg': list()
            })

            if not self.responses:
                self.warnings.append("No interface command responses received")
                return

            if len(self.responses) >= 2 and self.responses[0] and self.responses[1]:
                data_interface = self.responses[0]
                data_interface_br = self.responses[1]
                data_interface_counter = self.responses[3] if len(self.responses) > 3 else ""
                data_interface_transceiver = self.responses[4] if len(self.responses) > 4 else ""
                
                if "Command not supported" not in data_interface and "Command not supported" not in data_interface_br:
                    interfaces = self.parse_interfaces(data_interface, data_interface_br, 
                                                     data_interface_counter, data_interface_transceiver)
                    self.facts['interfaces'] = self.populate_interfaces(interfaces)

            if len(self.responses) > 2 and self.responses[2] and "Command not supported" not in self.responses[2]:
                data_neigh_detail = self.responses[2]
                neighbors = self.parse_neighbors(data_neigh_detail)
                self.facts['neighbors'] = self.populate_neighbors(neighbors)

            if len(self.responses) > 5 and self.responses[5] and "Command not supported" not in self.responses[5]:
                data_interface_lagg = self.responses[5]
                self.facts['lagg'] = self.parse_lagg(data_interface_lagg)

        except Exception as exc:
            self.warnings.append(f"Error collecting interface facts: {str(exc)}")

    def populate_neighbors(self, neighbors):
        facts = dict()
        try:
            for key, value in iteritems(neighbors):
                neigh = dict()
                neigh['Remote Chassis ID'] = self.parse_neigh_chasisID(value) or "N/A"
                neigh['Remote Port'] = self.parse_neigh_port(value) or "N/A"
                neigh['Remote System Name'] = self.parse_neigh_sysname(value) or "N/A"
                facts[key] = neigh
        except Exception as exc:
            self.warnings.append(f"Error populating neighbor facts: {str(exc)}")

        return facts

    def populate_interfaces(self, interfaces):
        facts = dict()
        try:
            for key, value in iteritems(interfaces):
                intf = dict()
                intf['description'] = self.parse_description(value) or "N/A"
                intf['macaddress'] = self.parse_macaddress(value) or "N/A"
                intf['mtu'] = self.parse_mtu(value) or "N/A"
                intf['bandwidth'] = self.parse_bandwidth(value) or "N/A"
                intf['mediatype'] = self.parse_mediatype(value) or "N/A"
                intf['duplex'] = self.parse_duplex(value) or "N/A"
                intf['ipv4'] = self.parse_ipv4address(value)
                intf['ipv6'] = self.parse_ipv6address(value)
                intf['lineprotocol'] = self.parse_lineprotocol(value) or "N/A"
                intf['portmode'] = self.parse_portmode(value) or "N/A"
                intf['counter'] = self.parse_counter(value) or {}
                intf['transceiver'] = self.parse_transceiver(value) or []
                intf['vrf'] = self.parse_VRF(value) or "N/A"
                facts[key] = intf
        except Exception as exc:
            self.warnings.append(f"Error populating interface facts: {str(exc)}")
            
        return facts

    def parse_neigh_chasisID(self, data):
        return self.safe_regex_search(r'Chassis id type\s+: (.*)', data)

    def parse_neigh_port(self, data):
        return self.safe_regex_search(r'Port id type\s+: (.*)', data)

    def parse_neigh_sysname(self, data):
        result = self.safe_regex_search(r'System Name\s+: (.*)', data)
        return result if result else "NA"

    def parse_description(self, data):
        return self.safe_regex_search(r'Description: (.*)', data)

    def parse_VRF(self, data):
        return self.safe_regex_search(r'VRF Binding: Associated with (.*)', data)

    def parse_macaddress(self, data):
        return self.safe_regex_search(r'Current HW addr: (.*)', data)

    def parse_mtu(self, data):
        return self.safe_regex_search(r'mtu (\d+) ', data)

    def parse_ipv4address(self, data):
        addrs = []
        try:
            if data:
                matches = re.findall(r'inet (\S+)/(\d+)', data)
                for addr in matches:
                    self.facts['all_ipv4_addresses'].append(addr[0])
                    addrs.append(dict(address=addr[0], masklen=int(addr[1])))
        except Exception as exc:
            self.warnings.append(f"Error parsing IPv4 addresses: {str(exc)}")
        return addrs

    def parse_ipv6address(self, data):
        addrs = []
        try:
            if data:
                matches = re.findall(r'inet6 (\S+)/(\d+)', data)
                for addr in matches:
                    self.facts['all_ipv6_addresses'].append(addr[0])
                    addrs.append(dict(address=addr[0], masklen=int(addr[1])))
        except Exception as exc:
            self.warnings.append(f"Error parsing IPv6 addresses: {str(exc)}")
        return addrs

    def parse_duplex(self, data):
        return self.safe_regex_search(r'duplex-([^\s\(]*)', data)

    def parse_bandwidth(self, data):
        return self.safe_regex_search(r'link-speed (\S*)', data)

    def parse_mediatype(self, data):
        return self.safe_regex_search(r'Hardware is (\S*)', data)

    def parse_lineprotocol(self, data):
        status = self.safe_regex_search(r'Status (up|down)', data)
        if status:
            return status.upper()
        protocol_status = self.safe_regex_search(r'line protocol is (up|down)', data)
        if protocol_status:
            return protocol_status.upper()
        return "N/A"

    def parse_portmode(self, data):
        return self.safe_regex_search(r'Port Mode is (\S*)', data)

    def parse_counter(self, data):
        parsed_counter = dict()
        try:
            if data:
                for line in re.findall(r'COUNTERS\s+([^\n]+)\n', data):
                    match = re.search('([^:]+): (\S*)', line)
                    if match:
                        parsed_counter[match.group(1)] = match.group(2)
        except Exception as exc:
            self.warnings.append(f"Error parsing interface counters: {str(exc)}")
        return parsed_counter

    def parse_lagg(self, data):
        parsed_lagg = []
        try:
            if not data:
                return parsed_lagg
                
            aggregator = dict()
            link = []
            for line in data.split('\n'):
                if re.search(r'^-+$', line):
                    aggregator['link'] = link
                    parsed_lagg.append(aggregator)
                    aggregator = dict()
                    link = []
                else:
                    match = re.search('^\s+Aggregator Type: (\S+)', line)
                    if match:
                        aggregator['AggregatorType'] = match.group(1)
                        continue
                    match = re.search('^\s*Aggregator\s+(\S+)\s+(\S+)', line)
                    if match:
                        aggregator['AggregatorPort'] = match.group(1)
                        aggregator['AggregatorID'] = match.group(2)
                        continue
                    match = re.search('^\s+Admin Key: (.+)$', line)
                    if match:
                        aggregator['AdminKey'] = match.group(1)
                        continue
                    match = re.search('^\s+Link: (.+) sync: (.*)$', line)
                    if match:
                        link.append({"Link": match.group(1), "sync": match.group(2)})
                        continue

            if len(link) > 0:
                aggregator['link'] = link
            if len(aggregator) > 0:
                parsed_lagg.append(aggregator)
        except Exception as exc:
            self.warnings.append(f"Error parsing LAG information: {str(exc)}")
                    
        return parsed_lagg                 
        
    def parse_transceiver(self, data):
        parsed_transceiver = []
        try:
            if not data:
                return parsed_transceiver
                
            for line in re.findall(r'TRANSCEIVERS[0-9]+\s+(.+)', data):
                match = re.search('\s*(\S+)\s+(\S+)\s+(\S+)\s+(\S+)\s+(\S+)\s+(\S+)\s+(\S+)', line)
                if match:
                    parsed_lane = dict()
                    parsed_lane["DDM"] = match.group(1)
                    parsed_lane["Temp"] = match.group(2)
                    parsed_lane["Voltage"] = match.group(3)
                    parsed_lane["Lane"] = match.group(4)
                    parsed_lane["Current"] = match.group(5)
                    parsed_lane["TxPower"] = match.group(6)
                    parsed_lane["RxPower"] = match.group(7)
                    parsed_transceiver.append(parsed_lane)
                else:
                    match = re.search('\s*(\S+)\s+(\S+)\s+(\S+)\s+(\S+)', line)
                    if match and parsed_transceiver:
                        newlane = parsed_transceiver[-1].copy()
                        newlane["Lane"] = match.group(1)
                        newlane["Current"] = match.group(2)
                        newlane["TxPower"] = match.group(3)
                        newlane["RxPower"] = match.group(4)
                        parsed_transceiver.append(newlane)
        except Exception as exc:
            self.warnings.append(f"Error parsing transceiver information: {str(exc)}")

        return parsed_transceiver

    def parse_neighbors(self, neighbors):
        parsed = dict()
        try:
            if not neighbors:
                return parsed
                
            key = ''
            neighbors = ''.join(neighbors)
            for line in neighbors.split('\n'):
                if len(line) == 0:
                    continue
                if line[0] == ' ':
                    if key:
                        parsed[key] += '\n%s' % line
                else:
                    match = re.match(r'^Interface Name\s+:\s(\S+)', line)
                    if match:
                        key = match.group(1)
                        parsed[key] = line
        except Exception as exc:
            self.warnings.append(f"Error parsing neighbor information: {str(exc)}")

        return parsed

    def parse_interfaces(self, data_int, data_int_br, data_int_counter, data_int_tr):
        parsed = dict()
        try:
            key = ''

            if data_int:
                data_int = ''.join(data_int)
                for line in data_int.split('\n'):
                    if len(line) == 0:
                        continue
                    if line[0] == ' ':
                        if key:
                            parsed[key] += '\n%s' % line
                    else:
                        match = re.match(r'^Interface (.*)', line)
                        if match:
                            key = match.group(1)
                            parsed[key] = line

            if data_int_br:
                for line in data_int_br.split('\n'):
                    match = re.match(r'^(\S+)\s+\S+\s+\S+\s+(up|down)\s+', line)
                    if not match:
                        match = re.match(r'^(\S+).*(up|down)', line)
                    if match:
                        key = match.group(1)
                        status = match.group(2).upper()
                        if key in parsed:
                            parsed[key] += '\nStatus %s' % status

            if data_int_counter:
                key = ''
                data_int_counter = ''.join(data_int_counter)
                for line in data_int_counter.split('\n'):
                    if len(line) == 0:
                        key = ''
                        continue
                    if key and line[0] == ' ':
                        if key in parsed:
                            parsed[key] += '\nCOUNTERS %s' % line
                    else:
                        match = re.match(r'^Interface (.*)', line)
                        if match and match.group(1) != "CPU":
                            key = match.group(1)

            if data_int_tr:
                key = ''
                data_int_tr = ''.join(data_int_tr)
                lanenum = 0
                skip = True
                for line in data_int_tr.split('\n'):
                    if skip:
                        match = re.match(r'^-+$', line)
                        if (match):
                            skip = False
                        continue
                        
                    match = re.match(r'^(\S+)\s+(.*)$', line)
                    if match:
                        key = match.group(1)
                        lanenum = 0
                        if key in parsed:
                            parsed[key] += '\nTRANSCEIVERS%d %s' % (lanenum, match.group(2))
                    elif line[0] == ' ' and key:
                        lanenum += 1
                        if key in parsed:
                            parsed[key] += '\nTRANSCEIVERS%d %s' % (lanenum, line)
        except Exception as exc:
            self.warnings.append(f"Error parsing interface data: {str(exc)}")

        return parsed


FACT_SUBSETS = dict(
    default=Default,
    hardware=Hardware,
    interfaces=Interfaces,
    config=Config,
)

VALID_SUBSETS = frozenset(FACT_SUBSETS.keys())


def main():
    argument_spec = dict(
        gather_subset=dict(default=['!config'], type='list')
    )
    argument_spec.update(ocnos_argument_spec)

    module = AnsibleModule(argument_spec=argument_spec,
                         supports_check_mode=True)

    try:
        gather_subset = module.params['gather_subset']

        runable_subsets = set()
        exclude_subsets = set()

        for subset in gather_subset:
            if subset == 'all':
                runable_subsets.update(VALID_SUBSETS)
                continue

            if subset.startswith('!'):
                subset = subset[1:]
                if subset == 'all':
                    exclude_subsets.update(VALID_SUBSETS)
                    continue
                exclude = True
            else:
                exclude = False

            if subset not in VALID_SUBSETS:
                module.fail_json(msg=f'Invalid subset specified: {subset}. Valid subsets are: {", ".join(VALID_SUBSETS)}')

            if exclude:
                exclude_subsets.add(subset)
            else:
                runable_subsets.add(subset)

        if not runable_subsets:
            runable_subsets.update(VALID_SUBSETS)

        runable_subsets.difference_update(exclude_subsets)
        runable_subsets.add('default')

        facts = dict()
        facts['gather_subset'] = list(runable_subsets)

        instances = list()
        warnings = list()
        
        for key in runable_subsets:
            try:
                instance = FACT_SUBSETS[key](module)
                instances.append(instance)
            except Exception as exc:
                warnings.append(f"Failed to initialize {key} facts collector: {str(exc)}")

        for inst in instances:
            try:
                inst.populate()
                facts.update(inst.facts)
                if hasattr(inst, 'warnings'):
                    warnings.extend(inst.warnings)
            except Exception as exc:
                warnings.append(f"Failed to populate facts for {inst.__class__.__name__}: {str(exc)}")

        ansible_facts = dict()
        for key, value in iteritems(facts):
            try:
                ansible_facts['ansible_net_%s' % key] = value
            except Exception as exc:
                warnings.append(f"Failed to process fact key {key}: {str(exc)}")

        check_args(module, warnings)
        module.exit_json(ansible_facts=ansible_facts, warnings=warnings)

    except Exception as exc:
        module.fail_json(msg=f"Unexpected error in main execution: {str(exc)}", 
                        exception=traceback.format_exc())


if __name__ == '__main__':
    main()