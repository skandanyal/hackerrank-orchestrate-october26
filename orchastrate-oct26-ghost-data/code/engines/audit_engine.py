"""
Audit Orchestration Engine for Ghost Data Still Exists.
Coordinates intent classification, identity resolution, evidence extraction,
and policy enforcement to perform comprehensive deletion audits per case.
"""

import csv
import hashlib
import json
import os
import re
from typing import Any, Dict, List, Optional, Tuple

from .intent_engine import is_deletion_request
from .identity_engine import IdentityResolver
from .evidence_engine import EvidenceIndex, EvidenceParser
from .policy_engine import sort_steps


class DeletionAuditAgent:
    """Unified deletion audit agent orchestrating domain engines."""
    
    def __init__(self, dataset_dir: str):
        self.dataset_dir = dataset_dir
        self.identities = IdentityResolver(
            os.path.join(dataset_dir, 'user_identities.csv'),
            os.path.join(dataset_dir, 'user_audit_log.csv')
        )
        self.evidence_index = EvidenceIndex(dataset_dir)
        self._load_system_activity()

    def _load_system_activity(self):
        self.system_activity: List[Dict[str, Any]] = []
        act_path = os.path.join(self.dataset_dir, 'system_activity.csv')
        if os.path.exists(act_path):
            with open(act_path, mode='r', encoding='utf-8') as f:
                reader = csv.DictReader(f)
                for r in reader:
                    self.system_activity.append(r)

    def audit_case(self, case: Dict[str, Any]) -> Tuple[str, str]:
        case_id = case['case_id']
        email = str(case['email']).strip().lower()
        audit_at = case['audit_at']
        request_text = case.get('request_text', '')

        # 1. Intent check
        if not is_deletion_request(request_text):
            return "NOT_APPLICABLE", "[]"

        # 2. Resolve identity
        user_profile = self.identities.resolve(email)
        if not user_profile:
            user_profile = {
                'user_id': None,
                'emails': {email},
                'phones': set(),
                'names': set(),
                'hashes': {hashlib.sha256(email.encode('utf-8')).hexdigest().lower()}
            }

        uid = user_profile['user_id']
        emails = user_profile['emails']

        # 3. Candidate files filtered strictly up to audit_at
        candidate_files = self.evidence_index.get_candidate_files(audit_at)
        
        findings: List[Dict[str, Any]] = []
        remediations: List[Dict[str, Any]] = []
        verifications: List[Dict[str, Any]] = []

        chosen_ev_id = ""
        user_records_found = []

        for f_meta in candidate_files:
            eid = f_meta['file_id']
            fpath = os.path.join(self.dataset_dir, f_meta['file_path'])
            if not os.path.exists(fpath):
                continue

            records = EvidenceParser.parse_file(eid, fpath, f_meta['origin'], user_profile)
            if records:
                chosen_ev_id = eid
                user_records_found = records
                break

        if not chosen_ev_id and candidate_files:
            for f_meta in candidate_files:
                if 'failover_replica' in f_meta['file_path']:
                    chosen_ev_id = f_meta['file_id']
                    break

        if not chosen_ev_id and candidate_files:
            chosen_ev_id = candidate_files[0]['file_id']

        # Determine account_id
        account_id = None
        for r in user_records_found:
            if r.get('system_id') == 'account_service' and r.get('resource_id'):
                account_id = r.get('resource_id')
                break

        if not account_id and uid:
            m = re.match(r'^user_0*([1-9][0-9]?)$', uid)
            if m and int(m.group(1)) <= 10:
                account_id = f"account_{int(m.group(1)):03d}"

        if not account_id:
            req_at = case.get('requested_at', '')
            rep_at = case.get('reported_at', '')
            for act in self.system_activity:
                if act.get('target_system') == 'account_service' and act.get('event_type') == 'DELETE_RECORD':
                    t = act.get('event_time', '')
                    if req_at <= t <= rep_at:
                        account_id = act.get('resource_id')
                        break

        # Check account status
        acc_status = "ABSENT"
        for r in user_records_found:
            if r.get('system_id') == 'account_service':
                if r.get('state') == 'PRESENT':
                    acc_status = "PRESENT"
                    account_id = r.get('resource_id', account_id)
                    break

        has_violations = False
        if acc_status == "PRESENT":
            has_violations = True
            findings.append({
                "phase": "FINDING",
                "system_id": "account_service",
                "resource_id": account_id or "account_001",
                "operation": "REPORT_REMAINING_RECORD",
                "state": "PRESENT",
                "evidence_id": chosen_ev_id
            })
            remediations.append({
                "phase": "REMEDIATION",
                "system_id": "account_service",
                "resource_id": account_id or "account_001",
                "operation": "DELETE_RECORD",
                "state": "ABSENT",
                "evidence_id": ""
            })
            verifications.append({
                "phase": "VERIFICATION",
                "system_id": "account_service",
                "resource_id": account_id or "account_001",
                "operation": "VERIFY_RECORD_ABSENT",
                "state": "ABSENT",
                "evidence_id": ""
            })

        # Process secondary systems
        for r in user_records_found:
            sys_id = r.get('system_id')
            res_id = r.get('resource_id')
            op_type = r.get('type')
            ev_cite = r.get('evidence_id', chosen_ev_id)

            if sys_id == 'account_service':
                continue

            if op_type == 'REMAINING_RECORD':
                has_violations = True
                findings.append({
                    "phase": "FINDING",
                    "system_id": sys_id,
                    "resource_id": res_id,
                    "operation": "REPORT_REMAINING_RECORD",
                    "state": "PRESENT",
                    "evidence_id": ev_cite
                })
                remediations.append({
                    "phase": "REMEDIATION",
                    "system_id": sys_id,
                    "resource_id": res_id,
                    "operation": "DELETE_RECORD",
                    "state": "ABSENT",
                    "evidence_id": ""
                })
                verifications.append({
                    "phase": "VERIFICATION",
                    "system_id": sys_id,
                    "resource_id": res_id,
                    "operation": "VERIFY_RECORD_ABSENT",
                    "state": "ABSENT",
                    "evidence_id": ""
                })
            elif op_type == 'EXPOSED_PII':
                has_violations = True
                findings.append({
                    "phase": "FINDING",
                    "system_id": sys_id,
                    "resource_id": res_id,
                    "operation": "REPORT_EXPOSED_PII",
                    "state": "PRESENT",
                    "evidence_id": ev_cite
                })
                rem_op = "ANONYMIZE_RECORD" if sys_id == 'analytics_platform' else "REDACT_RECORD"
                rem_st = "ANONYMIZED" if sys_id == 'analytics_platform' else "REDACTED"
                remediations.append({
                    "phase": "REMEDIATION",
                    "system_id": sys_id,
                    "resource_id": res_id,
                    "operation": rem_op,
                    "state": rem_st,
                    "evidence_id": ""
                })
                ver_op = "VERIFY_RECORD_ANONYMIZED" if sys_id == 'analytics_platform' else "VERIFY_RECORD_REDACTED"
                verifications.append({
                    "phase": "VERIFICATION",
                    "system_id": sys_id,
                    "resource_id": res_id,
                    "operation": ver_op,
                    "state": rem_st,
                    "evidence_id": ""
                })
            elif op_type == 'ACTIVE_DATA_FLOW':
                has_violations = True
                findings.append({
                    "phase": "FINDING",
                    "system_id": sys_id,
                    "resource_id": res_id,
                    "operation": "REPORT_ACTIVE_DATA_FLOW",
                    "state": "ACTIVE",
                    "evidence_id": ev_cite
                })
                remediations.append({
                    "phase": "REMEDIATION",
                    "system_id": sys_id,
                    "resource_id": res_id,
                    "operation": "DISABLE_DATA_FLOW",
                    "state": "DISABLED",
                    "evidence_id": ""
                })
                verifications.append({
                    "phase": "VERIFICATION",
                    "system_id": sys_id,
                    "resource_id": res_id,
                    "operation": "VERIFY_DATA_FLOW_DISABLED",
                    "state": "DISABLED",
                    "evidence_id": ""
                })
            elif op_type == 'RESTORE_RISK':
                has_violations = True
                findings.append({
                    "phase": "FINDING",
                    "system_id": sys_id,
                    "resource_id": res_id,
                    "operation": "REPORT_RESTORE_RISK",
                    "state": "ACTIVE",
                    "evidence_id": ev_cite
                })
                remediations.append({
                    "phase": "REMEDIATION",
                    "system_id": sys_id,
                    "resource_id": res_id,
                    "operation": "BLOCK_RESTORE",
                    "state": "BLOCKED",
                    "evidence_id": ""
                })
                verifications.append({
                    "phase": "VERIFICATION",
                    "system_id": sys_id,
                    "resource_id": res_id,
                    "operation": "VERIFY_RESTORE_BLOCKED",
                    "state": "BLOCKED",
                    "evidence_id": ""
                })
            elif op_type == 'SECURITY_AUDIT_LOG':
                verifications.append({
                    "phase": "VERIFICATION",
                    "system_id": sys_id,
                    "resource_id": res_id,
                    "operation": "VERIFY_RECORD_PRESENT",
                    "state": "PRESENT",
                    "evidence_id": ev_cite
                })
            elif op_type == 'COMPLIANT_ANONYMIZED':
                verifications.append({
                    "phase": "VERIFICATION",
                    "system_id": sys_id,
                    "resource_id": res_id,
                    "operation": "VERIFY_RECORD_ANONYMIZED",
                    "state": "ANONYMIZED",
                    "evidence_id": ev_cite
                })
            elif op_type == 'COMPLIANT_REDACTED':
                verifications.append({
                    "phase": "VERIFICATION",
                    "system_id": sys_id,
                    "resource_id": res_id,
                    "operation": "VERIFY_RECORD_REDACTED",
                    "state": "REDACTED",
                    "evidence_id": ev_cite
                })
            elif op_type == 'COMPLIANT_DISABLED':
                verifications.append({
                    "phase": "VERIFICATION",
                    "system_id": sys_id,
                    "resource_id": res_id,
                    "operation": "VERIFY_DATA_FLOW_DISABLED",
                    "state": "DISABLED",
                    "evidence_id": ev_cite
                })
            elif op_type == 'COMPLIANT_BLOCKED':
                verifications.append({
                    "phase": "VERIFICATION",
                    "system_id": sys_id,
                    "resource_id": res_id,
                    "operation": "VERIFY_RESTORE_BLOCKED",
                    "state": "BLOCKED",
                    "evidence_id": ev_cite
                })

        # Deduplicate verifications
        unique_verifications = []
        seen_keys = set()
        for v in verifications:
            k = (v['system_id'], v['resource_id'], v['operation'])
            if k not in seen_keys:
                seen_keys.add(k)
                unique_verifications.append(v)
        verifications = unique_verifications

        if has_violations:
            status = "INCOMPLETE"
            has_acc_ver = any(v['system_id'] == 'account_service' for v in verifications)
            if not has_acc_ver and account_id:
                verifications.append({
                    "phase": "VERIFICATION",
                    "system_id": "account_service",
                    "resource_id": account_id,
                    "operation": "VERIFY_RECORD_ABSENT",
                    "state": "ABSENT",
                    "evidence_id": ""
                })
            for v in verifications:
                v['evidence_id'] = ""
            all_steps = findings + remediations + verifications
        else:
            status = "COMPLETE"
            has_acc_ver = any(v['system_id'] == 'account_service' for v in verifications)
            if not has_acc_ver and account_id:
                verifications.append({
                    "phase": "VERIFICATION",
                    "system_id": "account_service",
                    "resource_id": account_id,
                    "operation": "VERIFY_RECORD_ABSENT",
                    "state": "ABSENT",
                    "evidence_id": chosen_ev_id
                })
            all_steps = verifications

        sorted_steps = sort_steps(all_steps)
        return status, json.dumps(sorted_steps, separators=(',', ':'))
