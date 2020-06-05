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
# Module to Collect IS-IS information from OcNOS
# IP Infusion
#
from __future__ import absolute_import, division, print_function
__metaclass__ = type


ANSIBLE_METADATA = {'metadata_version': '1.1',
                    'status': ['preview'],
                    'supported_by': 'community'}

DOCUMENTATION = '''
---
'''
RETURN = '''
'''
import re
from ansible_collections.ipinfusion.ocnos.plugins.module_utils.ocnos import run_commands, ocnos_argument_spec, check_args
from ansible.module_utils.basic import AnsibleModule
from ansible.module_utils.six import iteritems

class ISISFactsBase(object):

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


class ISISNeighbor(ISISFactsBase):

    COMMANDS = ['show clns neighbors']

    def populate(self):
        super(ISISNeighbor, self).populate()
        data = self.responses[0]
        if data:
            self.facts['isis_neighbor'] = self.parse_isis_neighbor(data)

    def parse_isis_neighbor(self, data):
        isisneighborlines = data.split('\n')
        isisneighbors = dict()
        '''
        neighbor = ''
        '''
        skip = True
        for line in isisneighborlines:
            if skip:
                match = re.search(r'^System Id', line)
                if match:
                    skip = False
                continue

            match = re.search(r'(\S+)\s+(\S+)\s+(\S+)\s+(\S+)\s+(\S+)\s+(\S+)\s+(\S+)', line)
            if match:
                isisneighbors.update({match.group(1): {
                    "Interface": match.group(2),
                    "SNPA": match.group(3),
                    "State": match.group(4),
                    "Holdtime": match.group(5),
                    "Type": match.group(6),
                    "Protocol": match.group(7)}})

        return isisneighbors


FACT_SUBSETS = dict(
    neighbor=ISISNeighbor,
)

VALID_SUBSETS = frozenset(FACT_SUBSETS.keys())

PERSISTENT_COMMAND_TIMEOUT = 60


def main():
    """main entry point for module execution
    """
    argument_spec = dict(
        gather_subset=dict(default=['!neighbor'], type='list')
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
#    runable_subsets.add('default')

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
