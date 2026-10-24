"""
Custom Evaluation Test Suite for Ghost Data Still Exists.
Provides at least 3 novel, realistic evaluation test cases to verify
advanced edge cases (residual tombstone leaks, connector recreation, legal hold retention)
as mandated by the challenge specification.
"""

CUSTOM_TEST_CASES = [
    {
        "case_id": "case_ext_01",
        "email": "elena.rostova@protonmail.com",
        "requested_at": "2026-08-10T10:00:00Z",
        "reported_status": "COMPLETE",
        "reported_at": "2026-08-12T14:00:00Z",
        "audit_at": "2026-08-25T16:00:00Z",
        "request_text": "Please delete my account and erase all my personal data from your systems.",
        "description": "Account tombstone preserved user_id correctly, but leaked residual phone number in secondary profile view.",
        "expected_status": "INCOMPLETE",
        "expected_steps": [
            {
                "step_no": 1,
                "phase": "FINDING",
                "system_id": "account_service",
                "resource_id": "account_9901",
                "operation": "REPORT_EXPOSED_PII",
                "state": "PRESENT",
                "evidence_id": "evidence_ext_01"
            },
            {
                "step_no": 2,
                "phase": "REMEDIATION",
                "system_id": "account_service",
                "resource_id": "account_9901",
                "operation": "REDACT_RECORD",
                "state": "REDACTED",
                "evidence_id": ""
            },
            {
                "step_no": 3,
                "phase": "VERIFICATION",
                "system_id": "account_service",
                "resource_id": "account_9901",
                "operation": "VERIFY_RECORD_REDACTED",
                "state": "REDACTED",
                "evidence_id": ""
            }
        ]
    },
    {
        "case_id": "case_ext_02",
        "email": "marcus.vance@techcorp.io",
        "requested_at": "2026-07-01T09:30:00Z",
        "reported_status": "COMPLETE",
        "reported_at": "2026-07-03T11:00:00Z",
        "audit_at": "2026-07-15T12:00:00Z",
        "request_text": "I request the full erasure of my profile and associated personal data.",
        "description": "Profile deleted from primary DB, but active sync connector recreated search document prior to audit cutoff.",
        "expected_status": "INCOMPLETE",
        "expected_steps": [
            {
                "step_no": 1,
                "phase": "FINDING",
                "system_id": "search_service",
                "resource_id": "search_8812",
                "operation": "REPORT_REMAINING_RECORD",
                "state": "PRESENT",
                "evidence_id": "evidence_ext_02a"
            },
            {
                "step_no": 2,
                "phase": "FINDING",
                "system_id": "integration_service",
                "resource_id": "data_flow_9921",
                "operation": "REPORT_ACTIVE_DATA_FLOW",
                "state": "ACTIVE",
                "evidence_id": "evidence_ext_02b"
            },
            {
                "step_no": 3,
                "phase": "REMEDIATION",
                "system_id": "integration_service",
                "resource_id": "data_flow_9921",
                "operation": "DISABLE_DATA_FLOW",
                "state": "DISABLED",
                "evidence_id": ""
            },
            {
                "step_no": 4,
                "phase": "REMEDIATION",
                "system_id": "search_service",
                "resource_id": "search_8812",
                "operation": "DELETE_RECORD",
                "state": "ABSENT",
                "evidence_id": ""
            },
            {
                "step_no": 5,
                "phase": "VERIFICATION",
                "system_id": "search_service",
                "resource_id": "search_8812",
                "operation": "VERIFY_RECORD_ABSENT",
                "state": "ABSENT",
                "evidence_id": ""
            },
            {
                "step_no": 6,
                "phase": "VERIFICATION",
                "system_id": "integration_service",
                "resource_id": "data_flow_9921",
                "operation": "VERIFY_DATA_FLOW_DISABLED",
                "state": "DISABLED",
                "evidence_id": ""
            }
        ]
    },
    {
        "case_id": "case_ext_03",
        "email": "hannah.weber@berlin-mail.de",
        "requested_at": "2026-06-12T08:00:00Z",
        "reported_status": "COMPLETE",
        "reported_at": "2026-06-14T10:00:00Z",
        "audit_at": "2026-06-28T14:00:00Z",
        "request_text": "Bitte löschen Sie mein Konto und alle damit verbundenen persönlichen Daten endgültig.",
        "description": "Customer account deleted, security audit log retained under statutory compliance rule_12.",
        "expected_status": "COMPLETE",
        "expected_steps": [
            {
                "step_no": 1,
                "phase": "VERIFICATION",
                "system_id": "account_service",
                "resource_id": "account_7734",
                "operation": "VERIFY_RECORD_ABSENT",
                "state": "ABSENT",
                "evidence_id": "evidence_ext_03a"
            },
            {
                "step_no": 2,
                "phase": "VERIFICATION",
                "system_id": "security_service",
                "resource_id": "audit_record_4401",
                "operation": "VERIFY_RECORD_PRESENT",
                "state": "PRESENT",
                "evidence_id": "evidence_ext_03b"
            }
        ]
    }
]
