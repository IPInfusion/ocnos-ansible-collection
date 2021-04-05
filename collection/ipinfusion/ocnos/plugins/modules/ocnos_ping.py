#!/usr/bin/python
# -*- coding: utf-8 -*-

# GNU General Public License v3.0+ (see COPYING or https://www.gnu.org/licenses/gpl-3.0.txt)

from __future__ import absolute_import, division, print_function
__metaclass__ = type

ANSIBLE_METADATA = {'metadata_version': '1.1',
                    'status': ['preview'],
                    'supported_by': 'community'}

DOCUMENTATION = r'''
---
module: ocnos_ping
short_description: Tests reachability using ping from IPI OcNOS network devices
description:
- Tests reachability using ping from switch to a remote destination.
- For a general purpose network module, see the M(net_ping) module.
- For Windows targets, use the M(win_ping) module instead.
- For targets running Python, use the M(ping) module instead.
author: "IP Infusion OcNOS Ansible Development Team"
version_added: '2.10'
extends_documentation_fragment: ocnos
options:
  count:
    description:
    - Number of packets to send.
    default: 5
  ipproto:
    description:
    - Specify IP protocol.
    choices=[ ip, ipv6 ]
    default: ip
  dest:
    description:
    - The IP Address or hostname (resolvable by switch) of the remote node.
    required: true
  interface:
    description:
    - Specify outgoing interface. This is effective only for IPv6 linklocal address was specified in 'dest'
  state:
    description:
    - Determines if the expected result is success or fail.
    choices: [ absent, present ]
    default: present
  vrf:
    description:
    - The VRF to use for forwarding.
    default: management
notes:
  - For a general purpose network module, see the M(net_ping) module.
  - For Windows targets, use the M(win_ping) module instead.
  - For targets running Python, use the M(ping) module instead.
'''

EXAMPLES = r'''
- name: Test reachability to 10.10.10.10 using default vrf
  ocnos_ping:
    dest: 10.10.10.10

- name: Test reachability to 10.20.20.20 using prod vrf
  ocnos_ping:
    dest: 10.20.20.20
    vrf: prod

- name: Test unreachability to 10.30.30.30 using default vrf
  ocnos_ping:
    dest: 10.30.30.30
    state: absent

- name: Test reachability to 10.40.40.40 using prod vrf and setting count
  ocnos_ping:
    dest: 10.40.40.40
    vrf: prod
    count: 20
'''

RETURN = '''
commands:
  description: Show the command sent.
  returned: always
  type: list
  sample: ["ping\nip\n \n192.168.122.1\n3\n64\n1\n100\n2\n0\nn\nn\n"]
packet_loss:
  description: Percentage of packets lost.
  returned: always
  type: str
  sample: "0%"
packets_rx:
  description: Packets successfully received.
  returned: always
  type: int
  sample: 3
packets_tx:
  description: Packets successfully transmitted.
  returned: always
  type: int
  sample: 3
rtt:
  description: Show RTT stats.
  returned: always
  type: dict
  sample: {"avg": 0.115, "max": 0.135, "min": 0.079}
'''

from ansible.module_utils.basic import AnsibleModule
from ansible_collections.ipinfusion.ocnos.plugins.module_utils.ocnos import run_commands
from ansible_collections.ipinfusion.ocnos.plugins.module_utils.ocnos import get_connection
from ansible_collections.ipinfusion.ocnos.plugins.module_utils.ocnos import ocnos_argument_spec
import re


def main():
    """ main entry point for module execution
    """
    argument_spec = dict(
        count=dict(type="int", default=1),
        ttl=dict(type="int", default=64),
        dest=dict(type="str", required=True),
        source=dict(type="str"),
        ipproto=dict(type="str", choices=["ip", "ipv6"], default="ip"),
        state=dict(type="str", choices=["absent", "present"], default="present"),
        vrf=dict(type="str", default="management"),
        interface=dict(type="str"),
    )
    ipv6addr_re = re.compile(r"^[a-fA-F0-9:]+$")

    argument_spec.update(ocnos_argument_spec)

    module = AnsibleModule(argument_spec=argument_spec)

    count = module.params["count"]
    ttl = module.params["ttl"]
    dest = module.params["dest"]
    vrf = module.params["vrf"]
    ipproto = module.params["ipproto"]
    interface = module.params["interface"]
    source = module.params["source"]

    warnings = list()
    results = {}
    
    outinterface = ""
    if ipv6addr_re.match(dest):
        ipproto = "ipv6"
        lladdr_re = re.compile(r"^[Ff][Ee]80:[a-fA-F0-9:]+$")
        if lladdr_re.match(dest):
            if interface is None:
                module.fail_json(msg="Interface is not specified for IPv6 linklocal address", **results)
                module.exit_json(**results)
                return
            else:
                outinterface = interface + "\n"

    if outinterface is None and interface is not None:
        warnings.append("interface parameter is not effective if dest is not IPv6 linklocal adderss")

    if source is not None:
        warnings.append("source parameter is not effective in OcNOS")

    if warnings:
        results["warnings"] = warnings

    connection = get_connection(module)
    if ipproto == "ip":
        results["commands"] = "ping\n{0}\n{1}\n{2}\n{3}\n{4}\n{5}\n{6}\n{7}\n{8}\n{9}\n{10}\n".format("ip", vrf, dest, count, ttl, 1, 100, 2, 0, "n", "n")
    else:
        results["commands"] = "ping\n{0}\n{1}\n{2}\n{3}\n{4}\n{5}\n{6}\n{7}\n{8}\n{9}\n{10}".format("ipv6", vrf, dest, count, ttl, 1, 100, 2, 0, "n", outinterface)
    ping_results = connection.get(results["commands"])
    ping_results_list = ping_results.split("\n")
    if len(ping_results_list) < 2:
        results["failed"] = True
        module.exit_json(**results)
        return

    stats = ping_results_list[len(ping_results_list) - 2]
    rtts = ping_results_list[len(ping_results_list) - 1]
    if rtts.startswith("%Network is unreachable"):
        loss = 100
        rx = "0"
        tx = "0"
        rtt = {"max": "0", "avg": "0", "min": "0"}
    else:
        loss, rx, tx, rtt = parse_ping(stats, rtts)
        loss = int(loss)
        
    results["packet_loss"] = str(loss) + "%"
    results["packets_rx"] = int(rx)
    results["packets_tx"] = int(tx)
    
    # Convert rtt values to float
    for k, v in rtt.items():
        if rtt[k] is not None:
            rtt[k] = float(v)

    results["rtt"] = rtt

    validate_results(module, loss, results)

    module.exit_json(**results)


def parse_ping(line1, line2):
    """
    Function used to parse the statistical information from the ping response.
    Example of line1: "5 packets transmitted, 5 received, 0% packet loss, time 4114ms"
    Example of line1: "5 packets transmitted, 0 received, +5 errors, 100% packet loss, time 4016ms"
    Exapmle of line2: "rtt min/avg/max/mdev = 0.102/0.139/0.164/0.025 ms"
    Returns the percent of packet loss, received packets, transmitted packets, and RTT dict.
    """
    rate_re = re.compile(r"^(?P<tx>\d+)\s+\w+\s+\w+,\s+(?P<rx>\d+)\s+\w+,(.*|[+]?(?P<err>\d+)\s+\w+,)\s+(?P<pct>\d+)%\s+")
    rtt_re = re.compile(r"^\w+\s+\w+/\w+/\w+/\w+\s+=\s+(?P<min>\d+\.\d+)/(?P<avg>\d+\.\d+)/(?P<max>\d+\.\d+)")

    rate = rate_re.match(line1)
    if rate is not None:
        rtt = rtt_re.match(line2)
    else:
        rate = rate_re.match(line2)
        rtt = None

    if rtt is None:
        rtt_groupdict = {"max": "0", "avg": "0", "min": "0"}
    else:
        rtt_groupdict = rtt.groupdict()

    return rate.group("pct") if rate is not None else 100, \
        rate.group("rx") if rate is not None else 0, \
        rate.group("tx") if rate is not None else 0, \
        rtt_groupdict


def validate_results(module, loss, results):
    """
    This function is used to validate whether the ping results were unexpected per "state" param.
    """
    state = module.params["state"]
    if state == "present" and loss == 100:
        module.fail_json(msg="Ping failed unexpectedly", **results)
    elif state == "absent" and loss < 100:
        module.fail_json(msg="Ping succeeded unexpectedly", **results)


if __name__ == "__main__":
    main()
