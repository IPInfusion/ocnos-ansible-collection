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
  - Tested against OcNOS 1.3.9
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
    returned: always
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
import copy

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
        self.PERSISTENT_COMMAND_TIMEOUT = 60

    def populate(self):
        self.responses = run_commands(self.module, self.COMMANDS,
                                      check_rc=False)

    def run(self, cmd):
        return run_commands(self.module, cmd, check_rc=False)


class Default(FactsBase):

    COMMANDS = ['show version', 'show hostname']

    def populate(self):
        super(Default, self).populate()
        data = self.responses[0]
        data_hostname = self.responses[1].replace('\n', '')
        if data:
            self.facts['version'] = self.parse_version(data)
            self.facts['model'] = self.parse_model(data)
            self.facts['image'] = self.parse_image(data)
        if data_hostname:
            self.facts['hostname'] = data_hostname
        else:
            self.facts['hostname'] = "NA"

    def parse_version(self, data):
        match = re.search(r'^ Software Product: OcNOS, Version: (.*)', data, re.M | re.I)
        if match:
            return match.group(1)

    def parse_model(self, data):
        match = re.search(r'^ Hardware Model: (.*)', data, re.M | re.I)
        if match:
            return match.group(1)

    def parse_image(self, data):
        match = re.search(r' Image Filename: (.*)', data, re.M | re.I)
        if match:
            return match.group(1)


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
        self.facts['memtotal_mb'] = "N/A"
        self.facts['memfree_mb'] = "N/A"
        self.facts['serialnum'] = "N/A"
        self.facts['vendor'] = "N/A"
        self.facts['product'] = "N/A"
        self.facts['cpu'] = "N/A"
        self.facts['ocnos_sensor'] = "N/A"
        self.facts['power_led'] = "N/A"
        try:
            super(Hardware, self).populate()

            data = self.responses[0]
            if data:
                self.facts['memtotal_mb'] = self.parse_memtotal(data)
                self.facts['memfree_mb'] = self.parse_memfree(data)

            data_boardinfo = self.responses[1]
            if data_boardinfo:
                self.facts['serialnum'] = self.parse_serialnum(data_boardinfo)
                self.facts['vendor'] = self.parse_vendorinfo(data_boardinfo)
                self.facts['product'] = self.parse_productname(data_boardinfo)
                
            data_cpu = self.responses[2]
            data_cpuload = self.responses[3]
            if data_cpu:
                self.facts['cpu'] = self.parse_cpu(data_cpu, data_cpuload)

            data_system = self.responses[4]
            if data_system:
                self.facts['ocnos_sensor'] = self.parse_sensor(data_system)

            data_powerled = self.responses[5]
            if data_powerled:
                self.facts['power_led'] = self.parse_powerled(data_powerled)

        except ConnectionError as exc:
            pass

    def parse_memtotal(self, data):
        match = re.search(r'^Total\s*:(.*) MB', data, re.M | re.I)
        if match:
            return int(match.group(1))

    def parse_memfree(self, data):
        match = re.search(r'^Free\s*:(.*) MB', data, re.M | re.I)
        if match:
            return int(match.group(1))

    def parse_serialnum(self, data_boardinfo):
        match = re.search(r'^Serial Number\s+: (\S+)', data_boardinfo, re.M | re.I)
        if match:
            return match.group(1)

    def parse_productname(self, data_boardinfo):
        match = re.search(r'^Product Name\s+: (\S+)', data_boardinfo, re.M | re.I)
        if match:
            return match.group(1)

    def parse_vendorinfo(self, data_boardinfo):
        match = re.search(r'^Vendor Name\s+: (\S+)', data_boardinfo, re.M | re.I)
        if match:
            return match.group(1)

    def parse_cpu(self, data_cpu, data_cpuload):
        parsed = dict()
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

        for line in data_cpuload.split('\n'):
            if len(line) == 0:
                continue
            match = re.match(r'^CPU core (\S+) Usage\s+:\s(.+)', line)
            if match:
                key = match.group(1)
                parsed[key] = { "Model": parsed[key], "Load": match.group(2) }

        return parsed

    # Parse sensor info such as temeratures for Ufi 'show system sensor'
    def parse_sensor(self, data_sensor):
        parsed = {}
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

        return parsed        

    # Parse power led info for Ufi 'show hardware-information led'
    def parse_powerled(self, data_powerled):
        skipcount = 2
        retvalue = dict()
        for line in data_powerled.split('\n'):
            if skipcount > 0:
                match = re.match(r'^-+$', line)
                if match:
                    skipcount -= 1
                continue

            match = re.match(r'^(\S+)\s+(\S+)\s+(.+)$', line)
            if match:
                retvalue[match.group(1)] = dict(color=match.group(2), description=match.group(3))
                
        return retvalue


class Config(FactsBase):

    COMMANDS = ['show running-config']

    def populate(self):
        super(Config, self).populate()
        data = self.responses[0]
        if data:
            self.facts['config'] = data


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
        super(Interfaces, self).populate()

        self.facts['all_ipv4_addresses'] = list()
        self.facts['all_ipv6_addresses'] = list()

        data_interface = self.responses[0]
        data_interface_br = self.responses[1]
        data_neigh_detail = self.responses[2]
        data_interface_counter = self.responses[3]
        data_interface_transceiver = self.responses[4]
        data_interface_lagg = self.responses[5]
        if data_interface and data_interface_br:
            interfaces = self.parse_interfaces(data_interface, data_interface_br, data_interface_counter, data_interface_transceiver)
            self.facts['interfaces'] = self.populate_interfaces(interfaces)
        if data_neigh_detail:
            neighbors = self.parse_neighbors(data_neigh_detail)
            self.facts['neighbors'] = self.populate_neighbors(neighbors)
        if data_interface_lagg:
            self.facts['lagg'] = self.parse_lagg(data_interface_lagg)

    def populate_neighbors(self, neighbors):
        facts = dict()
        for key, value in iteritems(neighbors):
            neigh = dict()
            neigh['Remote Chassis ID'] = self.parse_neigh_chasisID(value)
            neigh['Remote Port'] = self.parse_neigh_port(value)
            neigh['Remote System Name'] = self.parse_neigh_sysname(value)

            facts[key] = neigh

        return facts

    def populate_interfaces(self, interfaces):
        facts = dict()
        for key, value in iteritems(interfaces):
            intf = dict()
            intf['description'] = self.parse_description(value)
            intf['macaddress'] = self.parse_macaddress(value)
            intf['mtu'] = self.parse_mtu(value)
            intf['bandwidth'] = self.parse_bandwidth(value)
            intf['mediatype'] = self.parse_mediatype(value)
            intf['duplex'] = self.parse_duplex(value)
            intf['ipv4'] = self.parse_ipv4address(value)
            intf['ipv6'] = self.parse_ipv6address(value)
            intf['lineprotocol'] = self.parse_lineprotocol(value)
            intf['portmode'] = self.parse_portmode(value)
            intf['counter'] = self.parse_counter(value)
            intf['transceiver'] = self.parse_transceiver(value)
            intf['vrf'] = self.parse_VRF(value)
            '''
            intf['operstatus'] = self.parse_operstatus(value)
            intf['type'] = self.parse_type(value)
            '''

            facts[key] = intf
        return facts

    def parse_neigh_chasisID(self, data):
        match = re.search(r'Chassis id type\s+: (.*)', data)
        if match:
            return match.group(1)

    def parse_neigh_port(self, data):
        match = re.search(r'Port id type\s+: (.*)', data)
        if match:
            return match.group(1)

    def parse_neigh_sysname(self, data):
        match = re.search(r'System Name\s+: (.*)', data)
        if match:
            return match.group(1)
        else:
            return "NA"

    def parse_description(self, data):
        match = re.search(r'Description: (.*)', data)
        if match:
            return match.group(1)

    def parse_VRF(self, data):
        match = re.search(r'VRF Binding: Associated with (.*)', data)
        if match:
            return match.group(1)

    def parse_macaddress(self, data):
        match = re.search(r'Current HW addr: (.*)', data)
        if match:
            return match.group(1)

    def parse_mtu(self, data):
        match = re.search(r'mtu (\d+) ', data)
        if match:
            return match.group(1)

    def parse_ipv4address(self, data):
        addrs = re.findall(r'inet (\S+)/(\d+)', data)
        retaddrs = []
        for addr in addrs:
            self.facts['all_ipv4_addresses'].append(addr[0])
            retaddrs.append(dict(address=addr[0], masklen=int(addr[1])))
        return retaddrs

    def parse_ipv6address(self, data):
        addrs = re.findall(r'inet6 (\S+)/(\d+)', data)
        retaddrs = []
        for addr in addrs:
            self.facts['all_ipv6_addresses'].append(addr[0])
            retaddrs.append(dict(address=addr[0], masklen=int(addr[1])))
        return retaddrs

    def parse_duplex(self, data):
        match = re.search(r'duplex-([^\s\(]*)', data)
        if match:
            return match.group(1)

    def parse_bandwidth(self, data):
        match = re.search(r'link-speed (\S*)', data)
        if match:
            return match.group(1)

    def parse_mediatype(self, data):
        match = re.search(r'Hardware is (\S*)', data)
        if match:
            return match.group(1)

    def parse_lineprotocol(self, data):
        match = re.search(r'Status (\S*)', data)
        if match:
            return match.group(1)

    def parse_portmode(self, data):
        match = re.search(r'Port Mode is (\S*)', data)
        if match:
            return match.group(1)

    def parse_counter(self, data):
        parsed_counter = dict()
        for line in re.findall(r'COUNTERS\s+([^\n]+)\n', data):
            match = re.search('([^:]+): (\S*)', line)
            if match:
                parsed_counter[match.group(1)] = match.group(2)
        return parsed_counter

    def parse_lagg(self, data):
        parsed_lagg = []
        aggregator = dict()
        link = []
        for line in data.split('\n'):
            if re.search(r'^-+$', line):
                ## separator
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
                    
        return parsed_lagg                 
        
    def parse_transceiver(self, data):
        parsed_transceiver = []
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
                if match:
                    newlane = parsed_lane.copy()
                    newlane["Lane"] = match.group(1)
                    newlane["Current"] = match.group(2)
                    newlane["TxPower"] = match.group(3)
                    newlane["RxPower"] = match.group(4)
                    parsed_transceiver.append(newlane)

        return parsed_transceiver

    def parse_neighbors(self, neighbors):
        parsed = dict()
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

        return parsed

    def parse_interfaces(self, data_int, data_int_br, data_int_counter, data_int_tr):
        parsed = dict()
        key = ''

        data_int = ''.join(data_int)
        for line in data_int.split('\n'):
            if len(line) == 0:
                continue
            if line[0] == ' ':
                parsed[key] += '\n%s' % line
            else:
                match = re.match(r'^Interface (.*)', line)
                if match:
                    key = match.group(1)
                    parsed[key] = line

        for line in data_int_br.split('\n'):
            match = re.match(r'^(\S+).*(up|down)', line)
            if match:
                key = match.group(1)
                parsed[key] += '\nStatus %s' % match.group(2)

        key = ''
        data_int_counter = ''.join(data_int_counter)
        for line in data_int_counter.split('\n'):
            if len(line) == 0:
                key = ''
                continue
            if key and line[0] == ' ':
                parsed[key] += '\nCOUNTERS %s' % line
            else:
                match = re.match(r'^Interface (.*)', line)
                if match and match.group(1) != "CPU":
                    key = match.group(1)

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
                parsed[key] += '\nTRANSCEIVERS%d %s' % (lanenum, match.group(2))
            elif line[0] == ' ':
                lanenum += 1
                parsed[key] += '\nTRANSCEIVERS%d %s' % (lanenum, line)

        return parsed


FACT_SUBSETS = dict(
    default=Default,
    hardware=Hardware,
    interfaces=Interfaces,
    config=Config,
)

VALID_SUBSETS = frozenset(FACT_SUBSETS.keys())

PERSISTENT_COMMAND_TIMEOUT = 60


def main():
    """main entry point for module execution
    """
    argument_spec = dict(
        gather_subset=dict(default=['!config'], type='list')
    )

    argument_spec.update(ocnos_argument_spec)

    module = AnsibleModule(argument_spec=argument_spec,
                           supports_check_mode=True)

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
            module.fail_json(msg='Bad subset')

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
    for key in runable_subsets:
        instances.append(FACT_SUBSETS[key](module))

    for inst in instances:
        inst.populate()
        facts.update(inst.facts)

    ansible_facts = dict()
    for key, value in iteritems(facts):
        key = 'ansible_net_%s' % key
        ansible_facts[key] = value

    warnings = list()
    check_args(module, warnings)

    module.exit_json(ansible_facts=ansible_facts, warnings=warnings)


if __name__ == '__main__':
    main()
