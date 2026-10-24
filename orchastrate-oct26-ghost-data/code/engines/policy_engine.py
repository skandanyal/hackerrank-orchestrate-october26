"""
Policy & Remediation Engine for Ghost Data Still Exists.
Enforces deletion_rules.csv constraints, tombstone sanitization,
and strict DAG-ordered remediation planning and verification check synthesis.
"""

from typing import Any, Dict, List

FINDING_ORDER = [
    'REPORT_REMAINING_RECORD',
    'REPORT_EXPOSED_PII',
    'REPORT_ACTIVE_DATA_FLOW',
    'REPORT_RESTORE_RISK'
]

REMEDIATION_ORDER = [
    'DISABLE_DATA_FLOW',
    'BLOCK_RESTORE',
    'DELETE_RECORD',
    'REDACT_RECORD',
    'ANONYMIZE_RECORD'
]

VERIFICATION_ORDER = [
    'VERIFY_RECORD_ABSENT',
    'VERIFY_RECORD_PRESENT',
    'VERIFY_RECORD_REDACTED',
    'VERIFY_RECORD_ANONYMIZED',
    'VERIFY_DATA_FLOW_DISABLED',
    'VERIFY_RESTORE_BLOCKED'
]


def sort_steps(steps: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
    """
    Sorts findings, remediations, and verification checks strictly per the challenge DAG:
      1. FINDING -> REMEDIATION -> VERIFICATION
      2. Follows operation priority specified in problem_statement.md
      3. Breaks ties deterministically by system_id then resource_id
      4. Assigns consecutive 1-based step_no
    """
    phase_order = {'FINDING': 1, 'REMEDIATION': 2, 'VERIFICATION': 3}
    
    def step_sort_key(s: Dict[str, Any]):
        p_val = phase_order.get(s['phase'], 99)
        op = s['operation']
        if s['phase'] == 'FINDING':
            op_val = FINDING_ORDER.index(op) if op in FINDING_ORDER else 99
        elif s['phase'] == 'REMEDIATION':
            op_val = REMEDIATION_ORDER.index(op) if op in REMEDIATION_ORDER else 99
        else:
            op_val = VERIFICATION_ORDER.index(op) if op in VERIFICATION_ORDER else 99
            
        sys_id = s.get('system_id', '')
        res_id = s.get('resource_id', '')
        return (p_val, op_val, sys_id, res_id)

    sorted_list = sorted(steps, key=step_sort_key)
    for idx, s in enumerate(sorted_list):
        s['step_no'] = idx + 1
    return sorted_list
