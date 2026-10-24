"""
Intent Classification Engine for Ghost Data Still Exists.
Deterministically identifies whether a request text authorizes data deletion (GDPR Art. 17)
or represents a non-deletion action (GDPR Art. 15 SAR, Art. 16 Rectification, Art. 20 Portability, marketing opt-outs).
"""

import re

NON_DELETION_PATTERNS = [
    r'download my account information',
    r'can\'t access my profile',
    r'cannot access my profile',
    r'misspelled',
    r'out of date',
    r'stop the promotional emails',
    r'remove me from marketing lists only',
    r'what personal information you (hold|have)',
    r'copy of last year\'s invoices',
    r'change the email address',
    r'copy of the information held',
    r'keep the account as it is',
    r'leave the account active',
    r'do not close the account',
    r'don\'t delete or change anything',
    r'not asking for deletion',
    r'not a request to erase',
    r'update it to',
    r'still need the account',
    r'still use it',
    r'in a portable format',
    r'resetting the login',
    r'leave my profile and purchase history in place',
    r'correct it without removing',
]


def is_deletion_request(text: str) -> bool:
    """Deterministically identifies non-deletion requests (GDPR Articles 15, 16, 20, opt-outs)."""
    t = str(text).lower()
    for pat in NON_DELETION_PATTERNS:
        if re.search(pat, t):
            return False
    return True
