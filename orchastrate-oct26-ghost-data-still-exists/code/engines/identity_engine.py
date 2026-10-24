"""
Identity Resolution Engine for Ghost Data Still Exists.
Reconstructs complete multi-temporal identity graphs across current profiles (user_identities.csv)
and historical audit logs (user_audit_log.csv), including SHA-256 historical digest calculation.
"""

import csv
import hashlib
import os
from typing import Any, Dict, Optional, Set


class IdentityResolver:
    """Resolves request emails to canonical user_id and builds full multi-temporal identity graph."""
    def __init__(self, identities_path: str, audit_log_path: str):
        self.user_profiles: Dict[str, Dict[str, Any]] = {}
        self.email_to_uid: Dict[str, str] = {}
        self._load_identities(identities_path)
        self._load_audit_log(audit_log_path)
        # Precompute lowercase SHA-256 digests for all known emails
        for uid, p in self.user_profiles.items():
            for em in p['emails']:
                h = hashlib.sha256(em.encode('utf-8')).hexdigest().lower()
                p['hashes'].add(h)

    def _load_identities(self, path: str):
        if not os.path.exists(path):
            return
        with open(path, mode='r', encoding='utf-8') as f:
            reader = csv.DictReader(f)
            for row in reader:
                uid = row['user_id']
                email = str(row['email']).strip().lower() if row.get('email') else None
                phone = str(row['phone']).strip() if row.get('phone') else None
                name = str(row['name']).strip().lower() if row.get('name') else None
                ehash = str(row['email_hash']).strip().lower() if row.get('email_hash') else None
                
                self.user_profiles[uid] = {
                    'user_id': uid,
                    'emails': {email} if email else set(),
                    'phones': {phone} if phone else set(),
                    'names': {name} if name else set(),
                    'hashes': {ehash} if ehash else set(),
                }
                if email:
                    self.email_to_uid[email] = uid

    def _load_audit_log(self, path: str):
        if not os.path.exists(path):
            return
        with open(path, mode='r', encoding='utf-8') as f:
            reader = csv.DictReader(f)
            for row in reader:
                uid = row['user_id']
                if uid not in self.user_profiles:
                    self.user_profiles[uid] = {
                        'user_id': uid,
                        'emails': set(),
                        'phones': set(),
                        'names': set(),
                        'hashes': set(),
                    }
                field = row.get('field_name')
                for val in [row.get('old_value'), row.get('new_value')]:
                    if val and val.strip():
                        v = val.strip()
                        if field == 'email':
                            self.user_profiles[uid]['emails'].add(v.lower())
                            self.email_to_uid[v.lower()] = uid
                        elif field == 'email_hash':
                            self.user_profiles[uid]['hashes'].add(v.lower())
                        elif field == 'phone':
                            self.user_profiles[uid]['phones'].add(v)
                        elif field == 'name':
                            self.user_profiles[uid]['names'].add(v.lower())

    def resolve(self, email: str) -> Optional[Dict[str, Any]]:
        clean_email = str(email).strip().lower()
        uid = self.email_to_uid.get(clean_email)
        if uid and uid in self.user_profiles:
            return self.user_profiles[uid]
        return None
