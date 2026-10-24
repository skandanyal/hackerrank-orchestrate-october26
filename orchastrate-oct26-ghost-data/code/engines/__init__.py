"""
Ghost Data Still Exists: Core Engine Package.
Exposes decoupled architectural components:
  - IntentEngine: Regulatory request intent classification
  - IdentityEngine: Multi-temporal identity graph resolution
  - EvidenceEngine: Multi-modal evidence indexing and extraction
  - PolicyEngine: Policy enforcement, DAG remediation sorting
  - AuditEngine: Unified deletion audit pipeline orchestrator
"""

from .intent_engine import is_deletion_request
from .identity_engine import IdentityResolver
from .evidence_engine import EvidenceIndex, EvidenceParser
from .policy_engine import sort_steps, FINDING_ORDER, REMEDIATION_ORDER, VERIFICATION_ORDER
from .audit_engine import DeletionAuditAgent

__all__ = [
    'is_deletion_request',
    'IdentityResolver',
    'EvidenceIndex',
    'EvidenceParser',
    'sort_steps',
    'FINDING_ORDER',
    'REMEDIATION_ORDER',
    'VERIFICATION_ORDER',
    'DeletionAuditAgent'
]
