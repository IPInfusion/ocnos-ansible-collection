# Copyright (C) 2025 IP Infusion
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
# Contains Action Plugin methods for OcNOS Validate Module
# IP Infusion
#

DOCUMENTATION = '''
---
action: ocnos_validate
short_description: Validate parsed CLI output against expected data
version_added: "2.15"
description:
  - Compares expected parsed data with actual CLI output using TextFSM.
  - Supports single or multiple key-based matching.
options:
  expected_data:
    description: Dictionary or list of expected values to validate.
    required: true
    type: list
  actual_data:
    description: Parsed CLI output using TextFSM.
    required: true
    type: list
author:
  - Sharath Samanth (@yourhandle)
'''

EXAMPLES = '''
- name: Validate interface state
  ocnos_validate:
    expected_data:
      - interface: eth0
        admin_state: up
    actual_data: "{{ parsed_show_interface }}"
'''

RETURN = '''
validated:
  description: List of matched entries
  type: list
  returned: always
mismatched:
  description: List of entries that failed validation
  type: list
  returned: when mismatches occur
'''
from ansible.plugins.action import ActionBase
from ansible.errors import AnsibleError


class ActionModule(ActionBase):
    def run(self, tmp=None, task_vars=None):
        if task_vars is None:
            task_vars = {}

        expected_data = self._task.args.get('expected_data')
        actual_data = self._task.args.get('actual_data')
        match_key = self._task.args.get('match_key')
        ignore_keys = self._task.args.get('ignore_keys', [])

        if not isinstance(expected_data, list) or not isinstance(actual_data, list):
            raise AnsibleError("Both expected_data and actual_data must be lists of dictionaries.")
       
        if not match_key:
            raise AnsibleError("match_key is required for unordered comparison.")

        # Check for single match_key, if yes then convert into list
        if isinstance(match_key, str):
            match_key = [match_key]

        # Check for type of match_key to be list
        if not isinstance(match_key, list):
            raise AnsibleError("match_key must be a string or list of strings")

        #composite key function
        def make_key(item, key):
            try:
                return '|'.join([str(item[k]) for k in key])
            except KeyError as e:
                raise AnsibleError(f"Missing match_key '{e.args[0]}' in item: {item}")

        # Build lookup for actual_data by match_key
        actual_lookup = {}
        for i, item in enumerate(actual_data):
            if not isinstance(item, dict):
                raise AnsibleError(f"Item {i} in actual_data is not a dictionary.")
            #key = item.get(match_key)
            key = make_key(item, match_key)
            #if key is None:
             #   raise AnsibleError(f"Item {i} in actual_data is missing match_key '{match_key}'.")
            actual_lookup[key] = item

        differences = []

        for i, expected_item in enumerate(expected_data):
            if not isinstance(expected_item, dict):
                raise AnsibleError(f"Item {i} in expected_data is not a dictionary.")

            #key = expected_item.get(match_key)
            try:
                key = make_key(expected_item, match_key)
            #if key is None:
             #   raise AnsibleError(f"Item {i} in expected_data is missing match_key '{match_key}'.")
            except AnsibleError as e:
                raise AnsibleError(f"Item {i} in expected_data error: {e}")

            actual_item = actual_lookup.get(key)
            if not actual_item:
                differences.append({
                    'key': key,
                    'error': f"No matching item found in actual_data for {match_key}='{key}'"
                })
                continue

            diff = {}
            for k, expected_val in expected_item.items():
                if k in ignore_keys:
                    continue
                actual_val = actual_item.get(k, '__missing__')
                if actual_val != expected_val:
                    diff[k] = {
                        'expected': expected_val,
                        'actual': actual_val
                    }

            if diff:
                differences.append({
                    'key': key,
                    'differences': diff
                })

        return {
            'changed': False,
            'expected_data': expected_data,
            'actual_data': actual_data,
            'differences': differences,
            'ignored_keys': ignore_keys,
            'rc': 1 if differences else 0,
        }

