"""
Evidence Extraction & Parsing Engine for Ghost Data Still Exists.
Discovers, indexes, and inspects multi-modal evidence up to the audit_at timestamp:
  - SQLite in-memory databases with schema reflection
  - JSON service exports and snapshot bundles
  - Trace-correlated distributed service logs
  - Plaintext handover files
  - PDF documents
"""

import csv
import json
import os
import re
import sqlite3
import subprocess
from typing import Any, Dict, List, Optional, Set


class EvidenceIndex:
    """Indexes evidence files manifest with parsed timestamps and temporal filtering."""
    def __init__(self, dataset_dir: str):
        self.dataset_dir = dataset_dir
        self.manifest_path = os.path.join(dataset_dir, 'evidence_files.csv')
        self.manifest_rows: List[Dict[str, Any]] = []
        self._load_manifest()

    def _load_manifest(self):
        if not os.path.exists(self.manifest_path):
            return
        with open(self.manifest_path, mode='r', encoding='utf-8') as f:
            reader = csv.DictReader(f)
            for r in reader:
                self.manifest_rows.append({
                    'file_id': r['file_id'],
                    'file_path': r['file_path'],
                    'origin': r['origin'],
                    'captured_at': r['captured_at'],
                })

    def get_candidate_files(self, audit_at: str) -> List[Dict[str, Any]]:
        """Returns evidence captured strictly at or before audit_at cutoff."""
        valid = [r for r in self.manifest_rows if r['captured_at'] <= audit_at]
        valid.sort(key=lambda x: x['captured_at'], reverse=True)
        return valid


class EvidenceParser:
    """Multi-modal evidence file parser extracting user records and resource state."""
    
    @staticmethod
    def parse_file(eid: str, fpath: str, origin: str, user_profile: Dict[str, Any]) -> List[Dict[str, Any]]:
        uid = user_profile['user_id']
        emails = user_profile['emails']
        hashes = user_profile.get('hashes', set())
        phones = user_profile.get('phones', set())
        records: List[Dict[str, Any]] = []

        try:
            # Format 1: Text handover
            if fpath.endswith('.txt'):
                with open(fpath, mode='r', encoding='utf-8') as fp:
                    for line in fp:
                        if not line.strip().startswith('-'):
                            continue
                        parts = [p.strip() for p in line.strip().lstrip('-').split('|')]
                        if len(parts) >= 6:
                            ts, sys_id, res_id, category, st, ident = parts[:6]
                            if ident.lower() in emails or (uid and ident == uid) or ident.lower() in hashes:
                                if category == 'USER_PROFILE':
                                    records.append({'system_id': sys_id, 'resource_id': res_id, 'type': 'ACCOUNT_PROFILE', 'state': 'ABSENT' if st == 'NOT_FOUND' else 'PRESENT', 'evidence_id': eid})
                                elif category == 'SEARCH_INDEX_ENTRY':
                                    if st == 'FOUND':
                                        records.append({'system_id': sys_id, 'resource_id': res_id, 'type': 'REMAINING_RECORD', 'state': 'PRESENT', 'evidence_id': eid})
                                elif category == 'ANALYTICS_PROFILE':
                                    if st == 'IDENTIFIABLE':
                                        records.append({'system_id': sys_id, 'resource_id': res_id, 'type': 'EXPOSED_PII', 'state': 'PRESENT', 'evidence_id': eid})
                                    elif st == 'ANONYMIZED':
                                        records.append({'system_id': sys_id, 'resource_id': res_id, 'type': 'COMPLIANT_ANONYMIZED', 'state': 'ANONYMIZED', 'evidence_id': eid})
                                elif category == 'DATA_FLOW':
                                    if st == 'ACTIVE':
                                        records.append({'system_id': sys_id, 'resource_id': res_id, 'type': 'ACTIVE_DATA_FLOW', 'state': 'ACTIVE', 'evidence_id': eid})
                                    elif st == 'DISABLED':
                                        records.append({'system_id': sys_id, 'resource_id': res_id, 'type': 'COMPLIANT_DISABLED', 'state': 'DISABLED', 'evidence_id': eid})
                                elif category == 'BACKUP_ARCHIVE':
                                    if st == 'ACTIVE':
                                        records.append({'system_id': sys_id, 'resource_id': res_id, 'type': 'RESTORE_RISK', 'state': 'ACTIVE', 'evidence_id': eid})
                                    elif st == 'BLOCKED':
                                        records.append({'system_id': sys_id, 'resource_id': res_id, 'type': 'COMPLIANT_BLOCKED', 'state': 'BLOCKED', 'evidence_id': eid})
                                elif category == 'SECURITY_AUDIT_LOG':
                                    records.append({'system_id': sys_id, 'resource_id': res_id, 'type': 'SECURITY_AUDIT_LOG', 'state': 'PRESENT', 'evidence_id': eid})
                                elif category == 'SUPPORT_MESSAGE':
                                    if st == 'IDENTIFIABLE':
                                        records.append({'system_id': sys_id, 'resource_id': res_id, 'type': 'EXPOSED_PII', 'state': 'PRESENT', 'evidence_id': eid})
                                    elif st == 'REDACTED':
                                        records.append({'system_id': sys_id, 'resource_id': res_id, 'type': 'COMPLIANT_REDACTED', 'state': 'REDACTED', 'evidence_id': eid})
                                elif category == 'SUPPORT_ATTACHMENT':
                                    if st == 'FOUND':
                                        records.append({'system_id': sys_id, 'resource_id': res_id, 'type': 'REMAINING_RECORD', 'state': 'PRESENT', 'evidence_id': eid})

            # Format 2: JSON bundles & reports
            elif fpath.endswith('.json'):
                with open(fpath, mode='r', encoding='utf-8') as fp:
                    data = json.load(fp)

                if 'service_exports' in data:
                    se = data['service_exports']
                    # account_service
                    for item in se.get('account_service', {}).get('profile_lookups', []):
                        if item.get('lookup_key') in emails or item.get('resource_id') == user_profile.get('user_id'):
                            records.append({'system_id': 'account_service', 'resource_id': item['resource_id'], 'type': 'ACCOUNT_PROFILE', 'state': 'ABSENT' if item.get('status_code') == 404 else 'PRESENT', 'evidence_id': eid})
                    # search_service
                    for item in se.get('search_service', {}).get('index_queries', []):
                        if item.get('query') in emails:
                            hits = item.get('hits', {})
                            if hits.get('total', 0) > 0:
                                records.append({'system_id': 'search_service', 'resource_id': item['resource_id'], 'type': 'REMAINING_RECORD', 'state': 'PRESENT', 'evidence_id': eid})
                            else:
                                records.append({'system_id': 'search_service', 'resource_id': item['resource_id'], 'type': 'COMPLIANT_ABSENT', 'state': 'ABSENT', 'evidence_id': eid})
                    # analytics_platform
                    for item in se.get('analytics_platform', {}).get('profiles', []):
                        if item.get('email') in emails or (uid and item.get('customer_reference') == uid):
                            if item.get('email') or item.get('phone'):
                                records.append({'system_id': 'analytics_platform', 'resource_id': item['resource_id'], 'type': 'EXPOSED_PII', 'state': 'PRESENT', 'evidence_id': eid})
                            else:
                                records.append({'system_id': 'analytics_platform', 'resource_id': item['resource_id'], 'type': 'COMPLIANT_ANONYMIZED', 'state': 'ANONYMIZED', 'evidence_id': eid})
                    # support_platform
                    for item in se.get('support_platform', {}).get('tickets', []):
                        if item.get('requester_email') in emails or (uid and item.get('customer_reference') == uid):
                            if item.get('requester_email') or item.get('requester_phone'):
                                records.append({'system_id': 'support_platform', 'resource_id': item['resource_id'], 'type': 'EXPOSED_PII', 'state': 'PRESENT', 'evidence_id': eid})
                            else:
                                records.append({'system_id': 'support_platform', 'resource_id': item['resource_id'], 'type': 'COMPLIANT_REDACTED', 'state': 'REDACTED', 'evidence_id': eid})
                    # integration_service
                    for item in se.get('integration_service', {}).get('connectors', []):
                        if item.get('customer_email') in emails or (uid and item.get('customer_reference') == uid):
                            if item.get('enabled') is True or item.get('enabled') == 1:
                                records.append({'system_id': 'integration_service', 'resource_id': item['resource_id'], 'type': 'ACTIVE_DATA_FLOW', 'state': 'ACTIVE', 'evidence_id': eid})
                            else:
                                records.append({'system_id': 'integration_service', 'resource_id': item['resource_id'], 'type': 'COMPLIANT_DISABLED', 'state': 'DISABLED', 'evidence_id': eid})
                    # backup_service
                    for item in se.get('backup_service', {}).get('restore_entries', []):
                        if item.get('customer_email') in emails or (uid and item.get('customer_reference') == uid):
                            if item.get('restore_allowed') is True or item.get('restore_allowed') == 1:
                                records.append({'system_id': 'backup_service', 'resource_id': item['resource_id'], 'type': 'RESTORE_RISK', 'state': 'ACTIVE', 'evidence_id': eid})
                            else:
                                records.append({'system_id': 'backup_service', 'resource_id': item['resource_id'], 'type': 'COMPLIANT_BLOCKED', 'state': 'BLOCKED', 'evidence_id': eid})
                    # security_service
                    for item in se.get('security_service', {}).get('audit_records', []):
                        if item.get('subject_reference') == uid or any(em in json.dumps(item) for em in emails):
                            records.append({'system_id': 'security_service', 'resource_id': item['resource_id'], 'type': 'SECURITY_AUDIT_LOG', 'state': 'PRESENT', 'evidence_id': eid})
                    # export_service
                    for item in se.get('export_service', {}).get('exports', []):
                        if item.get('owner_email') in emails or (uid and item.get('customer_reference') == uid):
                            records.append({'system_id': 'export_service', 'resource_id': item['resource_id'], 'type': 'REMAINING_RECORD', 'state': 'PRESENT', 'evidence_id': eid})

                elif 'snapshots' in data:
                    for snap in data['snapshots']:
                        dstore = snap.get('data_store')
                        for rec in snap.get('records', []):
                            rec_str = json.dumps(rec)
                            if any(em in rec_str for em in emails) or (uid and uid in rec_str):
                                res_id = rec.get('resource_id')
                                if dstore == 'security_service':
                                    records.append({'system_id': 'security_service', 'resource_id': res_id, 'type': 'SECURITY_AUDIT_LOG', 'state': 'PRESENT', 'evidence_id': eid})
                                elif dstore == 'identity_service':
                                    if rec.get('name') or rec.get('email') or rec.get('phone'):
                                        records.append({'system_id': 'identity_service', 'resource_id': res_id, 'type': 'EXPOSED_PII', 'state': 'PRESENT', 'evidence_id': eid})
                                    else:
                                        records.append({'system_id': 'identity_service', 'resource_id': res_id, 'type': 'COMPLIANT_REDACTED', 'state': 'REDACTED', 'evidence_id': eid})
                                elif dstore == 'account_service':
                                    records.append({'system_id': 'account_service', 'resource_id': res_id, 'type': 'ACCOUNT_PROFILE', 'state': 'PRESENT', 'evidence_id': eid})

                elif 'customer_export_jobs' in str(data):
                    for rec in data.get('records', []):
                        if rec.get('owner_email') in emails:
                            records.append({'system_id': 'export_service', 'resource_id': rec['resource_id'], 'type': 'REMAINING_RECORD', 'state': 'PRESENT', 'evidence_id': eid})

                elif 'customer_analytics' in str(data):
                    for rec in data.get('records', []):
                        if rec.get('email') in emails or (uid and rec.get('customer_reference') == uid):
                            if rec.get('email') or rec.get('phone'):
                                records.append({'system_id': 'analytics_platform', 'resource_id': rec['resource_id'], 'type': 'EXPOSED_PII', 'state': 'PRESENT', 'evidence_id': eid})
                            else:
                                records.append({'system_id': 'analytics_platform', 'resource_id': rec['resource_id'], 'type': 'COMPLIANT_ANONYMIZED', 'state': 'ANONYMIZED', 'evidence_id': eid})

            # Format 3: SQL databases
            elif fpath.endswith('.sql'):
                conn = sqlite3.connect(':memory:')
                with open(fpath, mode='r', encoding='utf-8') as fp:
                    conn.executescript(fp.read())
                cursor = conn.cursor()
                cursor.execute("SELECT name FROM sqlite_master WHERE type='table'")
                tables = [r[0] for r in cursor.fetchall() if r[0] != 'snapshot_scope']

                for tbl in tables:
                    cursor.execute(f"PRAGMA table_info(\"{tbl}\")")
                    cols = [c[1] for c in cursor.fetchall()]
                    cursor.execute(f"SELECT * FROM \"{tbl}\"")
                    rows = cursor.fetchall()
                    for row in rows:
                        row_dict = dict(zip(cols, row))
                        row_str = json.dumps(row_dict).lower()
                        
                        # Handle tables with embedded JSON records (customer_data_read_replica / primary)
                        for json_col in ['record_json', 'payload_json']:
                            if json_col in row_dict and row_dict[json_col]:
                                try:
                                    payload = json.loads(row_dict[json_col])
                                    p_str = json.dumps(payload).lower()
                                    if any(em in p_str for em in emails) or (uid and uid.lower() in p_str):
                                        orig = row_dict.get('origin_system', '')
                                        p_res = payload.get('resource_id', row_dict.get('resource_id'))
                                        if orig == 'account_service':
                                            st = 'PRESENT' if payload.get('account_status') == 'ACTIVE' else 'ABSENT'
                                            records.append({'system_id': 'account_service', 'resource_id': p_res, 'type': 'ACCOUNT_PROFILE', 'state': st, 'evidence_id': eid})
                                        elif orig == 'search_service':
                                            records.append({'system_id': 'search_service', 'resource_id': p_res, 'type': 'REMAINING_RECORD', 'state': 'PRESENT', 'evidence_id': eid})
                                        elif orig == 'analytics_platform':
                                            if payload.get('email') or payload.get('phone'):
                                                records.append({'system_id': 'analytics_platform', 'resource_id': p_res, 'type': 'EXPOSED_PII', 'state': 'PRESENT', 'evidence_id': eid})
                                            else:
                                                records.append({'system_id': 'analytics_platform', 'resource_id': p_res, 'type': 'COMPLIANT_ANONYMIZED', 'state': 'ANONYMIZED', 'evidence_id': eid})
                                        elif orig == 'security_service':
                                            records.append({'system_id': 'security_service', 'resource_id': p_res, 'type': 'SECURITY_AUDIT_LOG', 'state': 'PRESENT', 'evidence_id': eid})
                                except Exception:
                                    pass

                        # Standard schema tables
                        if any(em in row_str for em in emails) or (uid and uid.lower() in row_str):
                            res_id = row_dict.get('resource_id') or row_dict.get('account_id')
                            if 'search' in tbl and 'customer_data' not in tbl:
                                records.append({'system_id': 'search_service', 'resource_id': res_id, 'type': 'REMAINING_RECORD', 'state': 'PRESENT', 'evidence_id': eid})
                            elif 'profile' in tbl and 'customer_data' not in tbl:
                                st = 'PRESENT' if row_dict.get('account_status') == 'ACTIVE' else 'PRESENT'
                                records.append({'system_id': 'account_service', 'resource_id': res_id, 'type': 'ACCOUNT_PROFILE', 'state': st, 'evidence_id': eid})
                            elif 'backup' in tbl:
                                if str(row_dict.get('restore_allowed')) == '1':
                                    records.append({'system_id': 'backup_service', 'resource_id': res_id, 'type': 'RESTORE_RISK', 'state': 'ACTIVE', 'evidence_id': eid})
                                else:
                                    records.append({'system_id': 'backup_service', 'resource_id': res_id, 'type': 'COMPLIANT_BLOCKED', 'state': 'BLOCKED', 'evidence_id': eid})
                            elif 'connector' in tbl:
                                if str(row_dict.get('enabled')) == '1':
                                    records.append({'system_id': 'integration_service', 'resource_id': res_id, 'type': 'ACTIVE_DATA_FLOW', 'state': 'ACTIVE', 'evidence_id': eid})
                                else:
                                    records.append({'system_id': 'integration_service', 'resource_id': res_id, 'type': 'COMPLIANT_DISABLED', 'state': 'DISABLED', 'evidence_id': eid})
                            elif 'security' in tbl or 'audit' in tbl:
                                if 'customer_data' not in tbl:
                                    records.append({'system_id': 'security_service', 'resource_id': res_id, 'type': 'SECURITY_AUDIT_LOG', 'state': 'PRESENT', 'evidence_id': eid})
                            elif 'export' in tbl:
                                records.append({'system_id': 'export_service', 'resource_id': res_id, 'type': 'REMAINING_RECORD', 'state': 'PRESENT', 'evidence_id': eid})
                            elif 'support' in tbl:
                                records.append({'system_id': 'support_platform', 'resource_id': res_id, 'type': 'REMAINING_RECORD', 'state': 'PRESENT', 'evidence_id': eid})

            # Format 4: Logs (trace-id correlated)
            elif fpath.endswith('.log'):
                with open(fpath, mode='r', encoding='utf-8') as fp:
                    lines = fp.readlines()

                traces: Dict[str, List[str]] = {}
                for line in lines:
                    m = re.search(r'trace_id=([a-zA-Z0-9_-]+)', line)
                    if m:
                        t_id = m.group(1)
                        traces.setdefault(t_id, []).append(line)
                    else:
                        traces.setdefault('global', []).append(line)

                for tid, t_lines in traces.items():
                    trace_text = ''.join(t_lines)
                    is_match = any(em in trace_text.lower() for em in emails) or (uid and uid in trace_text) or any(h in trace_text.lower() for h in hashes)
                    if is_match:
                        for line in t_lines:
                            m_res = re.search(r'resource_id=([a-zA-Z0-9_-]+)', line)
                            m_sys = re.search(r'service=([a-zA-Z0-9_-]+)', line)
                            if m_res and m_sys:
                                r_id = m_res.group(1)
                                s_id = m_sys.group(1)
                                if s_id == 'account_service':
                                    if 'completed' in line or 'rows=0' in line or '404' in line:
                                        st = 'ABSENT' if ('404' in line or 'rows=0' in line) else 'PRESENT'
                                        records.append({'system_id': s_id, 'resource_id': r_id, 'type': 'ACCOUNT_PROFILE', 'state': st, 'evidence_id': eid})
                                elif s_id == 'security_service':
                                    records.append({'system_id': s_id, 'resource_id': r_id, 'type': 'SECURITY_AUDIT_LOG', 'state': 'PRESENT', 'evidence_id': eid})
                                elif s_id == 'analytics_platform':
                                    if 'email=null' in line:
                                        records.append({'system_id': s_id, 'resource_id': r_id, 'type': 'COMPLIANT_ANONYMIZED', 'state': 'ANONYMIZED', 'evidence_id': eid})
                                    else:
                                        records.append({'system_id': s_id, 'resource_id': r_id, 'type': 'REMAINING_RECORD', 'state': 'PRESENT', 'evidence_id': eid})
                                elif s_id == 'search_service':
                                    if 'completed' in line and 'hit' in line:
                                        records.append({'system_id': s_id, 'resource_id': r_id, 'type': 'REMAINING_RECORD', 'state': 'PRESENT', 'evidence_id': eid})
                                elif s_id in ('support_platform', 'support_replica'):
                                    if 'pii_scan' in line:
                                        records.append({'system_id': 'support_platform', 'resource_id': r_id, 'type': 'EXPOSED_PII', 'state': 'PRESENT', 'evidence_id': eid})
                                    elif 'completed' in line and 'rows=1' in line:
                                        records.append({'system_id': 'support_platform', 'resource_id': r_id, 'type': 'REMAINING_RECORD', 'state': 'PRESENT', 'evidence_id': eid})
                                elif s_id == 'integration_service':
                                    if 'enabled=true' in line or 'active' in line.lower():
                                        records.append({'system_id': s_id, 'resource_id': r_id, 'type': 'ACTIVE_DATA_FLOW', 'state': 'ACTIVE', 'evidence_id': eid})
                                    elif 'enabled=false' in line:
                                        records.append({'system_id': s_id, 'resource_id': r_id, 'type': 'COMPLIANT_DISABLED', 'state': 'DISABLED', 'evidence_id': eid})
                                elif s_id == 'backup_service':
                                    if 'eligible=true' in line or 'restore_allowed' in line:
                                        records.append({'system_id': s_id, 'resource_id': r_id, 'type': 'RESTORE_RISK', 'state': 'ACTIVE', 'evidence_id': eid})
                                    elif 'eligible=false' in line:
                                        records.append({'system_id': s_id, 'resource_id': r_id, 'type': 'COMPLIANT_BLOCKED', 'state': 'BLOCKED', 'evidence_id': eid})

            # Format 5: Documents (PDF)
            elif fpath.endswith('.pdf'):
                try:
                    out = subprocess.run(['pdftotext', fpath, '-'], stdout=subprocess.PIPE, stderr=subprocess.PIPE, text=True)
                    text = out.stdout
                    if any(em in text.lower() for em in emails) or (uid and uid in text):
                        m_ref = re.search(r'support_[0-9]+', text)
                        if m_ref:
                            records.append({'system_id': 'support_platform', 'resource_id': m_ref.group(0), 'type': 'REMAINING_RECORD', 'state': 'PRESENT', 'evidence_id': eid})
                except Exception:
                    pass

        except Exception:
            pass

        return records
