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
# Module to Collect BGP information from OcNOS
# IP Infusion
#
from __future__ import absolute_import, division, print_function
__metaclass__ = type


ANSIBLE_METADATA = {'metadata_version': '1.1',
                    'status': ['preview'],
                    'supported_by': 'community'}

DOCUMENTATION = '''
---
module: ocnos_bgp_facts
version_added: "2.9"
author: "IP Infusion OcNOS Ansible Development Team"
short_description: Collect BGP status
description:
  - Collets the current BGP status from IP Infusion OcNOS. The
    current version only supports BGP neighbor status.
    The BGP neighbor status is collected by OcNOS 'show bgp neighbor'
    command and be prepended to C(ansible_net_bgp_neighbor).
'''
EAMPLES = '''
The following is an example of using the module ocnos_bgp_facts.
---
  - name: Test BGP neighbor
    ipinfusion.ocnos.ocnos_bgp_facts:
      gather_subset: neighbor
    register: result

  - name: Show bgp Facts
    debug:
      msg: "{{ result }}"

'''
RETURN = '''
  ansible_net_bgp_neighbor:
    description: BGP neighbor status collected from the device
    returned: alwas
    type: dict
'''

import re
from ansible_collections.ipinfusion.ocnos.plugins.module_utils.ocnos import run_commands, ocnos_argument_spec, check_args
from ansible.module_utils.basic import AnsibleModule
from ansible.module_utils.six import iteritems

class BgpFactsBase(object):

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


class BgpNeighbor(BgpFactsBase):

    COMMANDS = ['show bgp neighbor']

    def populate(self):
        super(BgpNeighbor, self).populate()
        data = self.responses[0]
        if data:
            self.facts['bgp_neighbor'] = self.parse_bgp_neighbor(data)

    def parse_bgp_neighbor(self, data):
        bgpneighborlines = data.split('\n')
        bgpneighbors = dict()
        addressFamily = ''
        capabilityMode = False
        neighbor = ''
        for line in bgpneighborlines:
            match = re.search(r'^BGP neighbor is (\S+), (vrf \S+, |)remote AS (\S+), local AS (\S+), (\S+)', line)
            if match:
                if neighbor != match.group(1):
                    addressFamily = ''
                    neighbor = match.group(1)
                    bgpneighbors[neighbor] = {
                        "remoteAS": match.group(3),
                        "localAS": match.group(4),
                    }
                    if len(match.group(2)) > 0:
                        match = re.search(r'vrf (\S+),', match.group(2))
                        bgpneighbors[neighbor]["vrf"] = match.group(1)
                    continue

            match = re.search(r'Neighbor capabilities:', line)
            if match:
                capabilityMode = True
                bgpneighbors[neighbor].update({"capabilities": {}})
                continue

            if capabilityMode:
                match = re.search(r'^ {4}(\S.+)', line)
                if match:
                    str = match.group(1)
                    match = re.search(r'(.+)[ ]*: (.*)', str)
                    if match:
                        capabilityKey = re.sub(r' (.)', lambda c:c.group(1).upper(), match.group(1))
                        bgpneighbors[neighbor]["capabilities"].update({capabilityKey: match.group(2)})
                        continue
                else:
                    capabilityMode = False
                    
            match = re.search(r'For address family: (\S+ \S+)', line)
            if match:
                addressFamily = match.group(1)
                if "addressFamily" in bgpneighbors[neighbor]:
                    bgpneighbors[neighbor]["addressFamily"].update({addressFamily: {}})
                else:
                    bgpneighbors[neighbor].update({"addressFamily" : {addressFamily: {}}})
                addressFamilyPrefixList = ''                    
                continue
                              

            if len(addressFamily) > 0:
                if len(line) == 0:
                    adressFamily = ''
                    continue

                if len(addressFamilyPrefixList) > 0:
                    match = re.search(r"^   seq (.+)$", line)
                    if match:
                        bgpneighbors[neighbor]["addressFamily"][addressFamily][addressFamilyPrefixList].append(match.group(1))
                        continue
                    else:
                        addressfamilyPrefixList = ''
                    
                match = re.search(r'BGP table version (\S+), neighbor version (\S+)', line)
                if match:
                    bgpneighbors[neighbor]["addressFamily"][addressFamily].update({
                        "BGPtableVersion": int(match.group(1)),
                        "neighborVersion": int(match.group(2)),
                        })
                    continue

                match = re.search(r'Index (\S+), Offset (\S+), Mask (\S+)', line)
                if match:
                    bgpneighbors[neighbor]["addressFamily"][addressFamily].update({
                        "index": int(match.group(1)),
                        "offset": int(match.group(2)),
                        "mask": match.group(3),
                        })
                    continue

                match = re.search(r'(\S+) peer-group member', line)
                if match:
                    bgpneighbors[neighbor]["addressFamily"][addressFamily].update({
                        "peerGroupMember": match.group(1),
                        })
                    continue

                match = re.search(r'Graceful restart: (.+)', line)
                if match:
                    bgpneighbors[neighbor]["addressFamily"][addressFamily].update({
                        "GracefulRestart": match.group(1),
                        })
                    continue

                match = re.search(r'^    Outbound Route Filter \(ORF\) type \((64|128)\) Prefix-list:', line)
                if match:
                    orfTypePrefix = match.group(1)
                    continue

                match = re.search(r'^      Send-mode: (.+)', line)
                if match and len(orfTypePrefix) > 0:
                    bgpneighbors[neighbor]["addressFamily"][addressFamily].update({
                        "ORFType%sSendMode" % orfTypePrefix: match.group(1),
                        })
                    continue

                match = re.search(r'^      Receive-mode: (.+)', line)
                if match and len(orfTypePrefix) > 0:
                    bgpneighbors[neighbor]["addressFamily"][addressFamily].update({
                        "ORFType%sReceiveMode" % orfTypePrefix: match.group(1),
                        })
                    continue

                match = re.search(r'(ip.*) prefix-list (.+): \S+ entries', line)
                if match:
                    addressFamilyPrefixList = match.group(1) + "ipPrefixList_" + match.group(2)
                    bgpneighbors[neighbor]["addressFamily"][addressFamily].update({
                        addressFamilyPrefixList: []
                        })
                    continue
                    
                match = re.search(r'^  Outbound Route Filter \(ORF\): (.+)', line)
                if match and len(orfTypePrefix) > 0:
                    bgpneighbors[neighbor]["addressFamily"][addressFamily].update({
                        "ORF": match.group(1),
                        })
                    continue

                match = re.search(
                    r'  (First update is deferred until ORF or ROUTE-REFRESH is received'
                    '|Route-Reflector Client'
                    '|Route-Server Client'
                    '|Inbound soft reconfiguration allowed'
                    '|Private AS number removed from updates to this neighbor'
                    '|NEXT_HOP is always this router'
                    '|AS_PATH is propagated unchanged to this neighbor'
                    '|NEXT_HOP is propagated unchanged to this neighbor'
                    '|MED is propagated unchanged to this neighbor'
                    ')', line)
                if match:
                    if not 'flags' in bgpneighbors[neighbor]["addressFamily"][addressFamily]:
                        bgpneighbors[neighbor]["addressFamily"][addressFamily].update({"flags": []})
                    bgpneighbors[neighbor]["addressFamily"][addressFamily]["flags"].append(match.group(1))

                match = re.search(r'Community attribute sent to this neighbor \((\S+)\)', line)
                if match:
                    bgpneighbors[neighbor]["addressFamily"][addressFamily].update({
                        "communityAttribute": match.group(1),
                        })
                    continue

                match = re.search(
                    r'^  (Default information originate, '
                    '|Weight'
                    '|Incoming update prefix filter list is '
                    '|Outgoing update prefix filter list is '
                    '|Incoming update network filter list is '
                    '|Outgoing update network filter list is '
                    '|Incoming update AS path filter list is '
                    '|Outgoing update AS path filter list is '
                    '|Route map for incoming advertisements is '
                    '|Route map for outgoing advertisements is '
                    '|Route map for selective unsuppress is )'
                    '(.+)$', line)
                if match:
                    key = re.sub(r' (.)', lambda c:c.group(1).upper(), match.group(1).replace(' is ', ''))
                    bgpneighbors[neighbor]["addressFamily"][addressFamily].update({key: match.group(2)})

                    continue
                    
                match = re.search(r'(\S+) accepted prefixes', line)
                if match:
                    bgpneighbors[neighbor]["addressFamily"][addressFamily].update({
                        "acceptedPrefixes": int(match.group(1)),
                        })
                    continue

                match = re.search(r'(\S+) announced prefixes', line)
                if match:
                    bgpneighbors[neighbor]["addressFamily"][addressFamily].update({
                        "announcedPrefixes": int(match.group(1)),
                        })
                    continue

            match = re.search(r'Description: (.+)', line)
            if match:
                bgpneighbors[neighbor]["Description"] = match.group(1)
                continue

            match = re.search(r'Member of peer-group (\S+) for session parameters', line)
            if match:
                bgpneighbors[neighbor]["MemberOfPeerGroup"] = match.group(1)
                continue

            match = re.search(r'BGP version (\S+), local router ID (\S+), remote router ID (\S+)', line)
            if match:
                bgpneighbors[neighbor].update({
                    "BGPversion": match.group(1),
                    "localRouterID": match.group(2),
                    "remoteRouterID": match.group(3),
                    })
                continue

            match = re.search(r'BGP state = (\S+)\s*(.*)', line)
            if match:
                state = match.group(1)
                if state == 'Established,':
                    state = "Established"
                    upfor = match.group(2)
                    match = re.search(r'up for (\S+)', upfor)
                    if match:
                        bgpneighbors[neighbor].update({
                            "EstablishedUpFor": match.group(1),
                        })
                bgpneighbors[neighbor].update({
                    "state": state,
                    })
                continue

            match = re.search(r'Last read (\S+), hold time is (\S+), keepalive interval is (\S+) seconds', line)
            if match:
                bgpneighbors[neighbor].update({
                    "lastRead" : match.group(1),
                    "holdTime": int(match.group(2)),
                    "keepAlive": int(match.group(3)),
                    })
                continue

            match = re.search(r'Configured hold time is (\S+), keepalive interval is (\S+) seconds', line)
            if match:
                bgpneighbors[neighbor].update({
                    "configuredHoldTime": int(match.group(1)),
                    "configuredKeepAlive": int(match.group(2)),
                    })
                continue

            match = re.search(r'Received (\S+) messages, (\S+) notifications, (\S+) in queue', line)
            if match:
                bgpneighbors[neighbor].update({"Received": {
                    "messages" : int(match.group(1)),
                    "notifications": int(match.group(2)),
                    "InQueue": int(match.group(3)),
                    }})
                continue

            match = re.search(r'Sent (\S+) messages, (\S+) notifications, (\S+) in queue', line)
            if match:
                bgpneighbors[neighbor].update({"Sent": {
                    "messages" : int(match.group(1)),
                    "notifications": int(match.group(2)),
                    "InQueue": int(match.group(3)),
                    }})
                continue

            match = re.search(r'Route refresh request: received (\S+), sent (\S+)', line)
            if match:
                bgpneighbors[neighbor].update({"routeRefreshRequest": {
                    "received" : int(match.group(1)),
                    "sent": int(match.group(2)),
                    }})
                continue

            match = re.search(r'Minimum time between advertisement runs is (\S+) seconds', line)
            if match:
                bgpneighbors[neighbor].update({
                    "minTimeBetweenAdv" : int(match.group(1)),
                    })
                continue

            match = re.search(r'Update source is (\S+)', line)
            if match:
                bgpneighbors[neighbor].update({
                    "updateSource" : match.group(1),
                    })
                continue

            match = re.search(r'Bidirectional Forwarding Detection is (\S+)', line)
            if match:
                bgpneighbors[neighbor].update({
                    "BFD" : match.group(1),
                    })
                continue

            match = re.search(r'Connections established (\S+); dropped (\S+)', line)
            if match:
                bgpneighbors[neighbor].update({
                    "connections": {
                        "established": int(match.group(1)),
                        "dropped": int(match.group(2)),
                    }})
                continue

            match = re.search(r'Local host: (\S+), Local port: (\S+)', line)
            if match:
                bgpneighbors[neighbor].update({
                    "local": {
                        "host": match.group(1),
                        "port": int(match.group(2)),
                    }})
                continue

            match = re.search(r'Foreign host: (\S+), Foreign port: (\S+)', line)
            if match:
                bgpneighbors[neighbor].update({
                    "foreign": {
                        "host": match.group(1),
                        "port": int(match.group(2)),
                    }})
                continue

            match = re.search(r'^  Remote restart time is (\S+) sec', line)
            if match:
                bgpneighbors[neighbor].update({
                        "gracefulRestartRemoteRestartTime": int(match.group(1)),
                    })
                continue

            match = re.search(r'^  Re-established, (.+)', line)
            if match:
                bgpneighbors[neighbor].update({
                        "gracefulRestartReastablishedStatus": match.group(1),
                    })
                continue

            match = re.search(r'External BGP neighbor may be up to (\S+) hops away', line)
            if match:
                bgpneighbors[neighbor].update({
                        "externalBGPHops": int(match.group(1)),
                    })
                continue

            match = re.search(r'Nexthop: (\S+)', line)
            if match:
                bgpneighbors[neighbor].update({
                        "nexthop": match.group(1),
                    })
                continue

            match = re.search(r'Nexthop global: (\S+)', line)
            if match:
                bgpneighbors[neighbor].update({
                        "nexthopGlobal": match.group(1),
                    })
                continue

            match = re.search(r'Nexthop local: (\S+)', line)
            if match:
                bgpneighbors[neighbor].update({
                        "nexthopLinklocal": match.group(1),
                    })
                continue

            match = re.search(r'BGP connection: (.+)', line)
            if match:
                bgpneighbors[neighbor].update({
                        "BGPConnection": match.group(1),
                    })
                continue

            match = re.search(r'Next connect timer due in (\S+) seconds', line)
            if match:
                bgpneighbors[neighbor].update({
                        "nextConnectTimer": int(match.group(1)),
                    })
                continue

            match = re.search(r'Capability error: (.+)', line)
            if match:
                bgpneighbors[neighbor].update({
                        "capabilityError": match.group(1),
                    })
                continue
                
            match = re.search(r'Last Reset: (\S+), due to (.+)', line)
            if match:
                bgpneighbors[neighbor].update({
                        "lastReset": match.group(1),
                        "lastResetDueTo": match.group(2),
                    })
                continue

            match = re.search(r'Notification Error Message: \((.+)\)', line)
            if match:
                bgpneighbors[neighbor].update({
                        "notificationError": match.group(1),
                    })
                continue
                
        return bgpneighbors


FACT_SUBSETS = dict(
    neighbor=BgpNeighbor,
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
