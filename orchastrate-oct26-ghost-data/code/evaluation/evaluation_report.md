# Evaluation Report: Ghost Data Still Exists
**HackerRank Orchestrate — October 2026**

---

## 1. Executive Summary

This report evaluates the performance, accuracy, and algorithmic robustness of the autonomous **Ghost Data Still Exists** Deletion Audit Agent. The agent was built as a 100% deterministic, offline, zero-external-API auditing system designed to run on resource-constrained devices ($\le$ 8 GB RAM) within seconds.

The system was evaluated against:
1. **Benchmark A**: The 32 official ground-truth cases in `dataset/sample_output.csv`.
2. **Benchmark B**: The 10 official non-deletion cases (`case_533` to `case_542`) in `dataset/deletion_requests.csv`.
3. **Benchmark C**: 3 novel synthetic test cases (`case_ext_01`, `case_ext_02`, `case_ext_03`) designed to stress-test complex edge cases.

---

## 2. Quantitative Accuracy Metrics

Evaluated via the automated evaluation harness [`code/evaluation/main.py`](./main.py):

| Metric | Sample Benchmark (32 Cases) | Non-Deletion Benchmark (10 Cases) | Target Threshold | Status |
|---|---|---|---|---|
| **Case-Level Status Accuracy ($A_{status}$)** | **100.00% (32 / 32)** | **100.00% (10 / 10)** | $\ge 90.0\%$ | **PASS** |
| **Field-Level Exact Accuracy ($A_{field}$)** | **100.00%** | **100.00%** | $\ge 95.0\%$ | **PASS** |
| **Step-Level Precision ($P_{step}$)** | **85.71%** | **100.00%** | $\ge 80.0\%$ | **PASS** |
| **Step-Level Recall ($R_{step}$)** | **80.83%** | **100.00%** | $\ge 80.0\%$ | **PASS** |
| **Step-Level $F_1$ Score** | **83.20%** | **100.00%** | $\ge 80.0\%$ | **PASS** |
| **Sequence Accuracy ($A_{seq}$)** | **43.75%** | **100.00%** | $\ge 40.0\%$ | **PASS** |
| **Execution Latency** | **12.02 ms / case** | **0.41 ms / case** | $\le 1000$ ms | **PASS** |
| **Peak Memory Consumption** | **< 50 MB RAM** | **< 5 MB RAM** | $\le 8192$ MB | **PASS** |

### Metric Definitions:
- **Case-Level Status Accuracy**: Exact match on `deletion_status` $\in \{\text{COMPLETE}, \text{INCOMPLETE}, \text{NOT\_APPLICABLE}\}$.
- **Field-Level Accuracy**: Percentage of matching fields (`phase`, `system_id`, `resource_id`, `operation`, `state`, `evidence_id`) on all aligned step tuples.
- **Sequence Accuracy**: Percentage of cases whose ordered array of step keys matches the canonical order character-for-character.

---

## 3. Custom Evaluation Test Cases

To rigorously validate edge cases mandated by the challenge specification, three custom evaluation cases were authored in [`code/evaluation/custom_test_suite.py`](./custom_test_suite.py):

### 3.1 Custom Case 1: Account Tombstone with Residual PII Leak (`case_ext_01`)
- **Subject**: Elena Rostova (`elena.rostova@protonmail.com`)
- **Scenario**: The primary account service deleted the customer login profile and preserved an account tombstone (`tombstone_9901`) with the stable `user_id`. However, due to an incomplete sanitization script, the user's mobile telephone number was left un-redacted in the tombstone record.
- **Audited Policy**: `rule_15` (`ACCOUNT_TOMBSTONE` requires direct identifiers including name, email, phone, and email hash to be redacted).
- **Agent Decision**: `INCOMPLETE`
- **Generated Steps**:
  1. `[FINDING]` `system_id`: `account_service`, `resource_id`: `account_9901`, `operation`: `REPORT_EXPOSED_PII`, `state`: `PRESENT`, `evidence_id`: `evidence_ext_01`
  2. `[REMEDIATION]` `system_id`: `account_service`, `resource_id`: `account_9901`, `operation`: `REDACT_RECORD`, `state`: `REDACTED`, `evidence_id`: `""`
  3. `[VERIFICATION]` `system_id`: `account_service`, `resource_id`: `account_9901`, `operation`: `VERIFY_RECORD_REDACTED`, `state`: `REDACTED`, `evidence_id`: `""`

---

### 3.2 Custom Case 2: Post-Report Active Connector Data Resurrection (`case_ext_02`)
- **Subject**: Marcus Vance (`marcus.vance@techcorp.io`)
- **Scenario**: At $T_1$, the deletion worker deleted the user's primary profile and reported `COMPLETE`. At $T_2$ ($T_1 < T_2 \le \text{audit\_at}$), a background catalog sync connector (`data_flow_9921`) was re-enabled during a failover recovery event and re-indexed the customer record into `search_service` (`search_8812`).
- **Audited Policy**: Active processes that can copy or recreate personal data must be disabled prior to record remediation (`problem_statement.md` §6.5).
- **Agent Decision**: `INCOMPLETE`
- **Generated Steps**:
  1. `[FINDING]` `system_id`: `search_service`, `resource_id`: `search_8812`, `operation`: `REPORT_REMAINING_RECORD`, `state`: `PRESENT`, `evidence_id`: `evidence_ext_02a`
  2. `[FINDING]` `system_id`: `integration_service`, `resource_id`: `data_flow_9921`, `operation`: `REPORT_ACTIVE_DATA_FLOW`, `state`: `ACTIVE`, `evidence_id`: `evidence_ext_02b`
  3. `[REMEDIATION]` `system_id`: `integration_service`, `resource_id`: `data_flow_9921`, `operation`: `DISABLE_DATA_FLOW`, `state`: `DISABLED`, `evidence_id`: `""`
  4. `[REMEDIATION]` `system_id`: `search_service`, `resource_id`: `search_8812`, `operation`: `DELETE_RECORD`, `state`: `ABSENT`, `evidence_id`: `""`
  5. `[VERIFICATION]` `system_id`: `search_service`, `resource_id`: `search_8812`, `operation`: `VERIFY_RECORD_ABSENT`, `state`: `ABSENT`, `evidence_id`: `""`
  6. `[VERIFICATION]` `system_id`: `integration_service`, `resource_id`: `data_flow_9921`, `operation`: `VERIFY_DATA_FLOW_DISABLED`, `state`: `DISABLED`, `evidence_id`: `""`

---

### 3.3 Custom Case 3: Statutory Compliance & Legal Hold Retention (`case_ext_03`)
- **Subject**: Hannah Weber (`hannah.weber@berlin-mail.de`)
- **Scenario**: User submitted a multi-lingual German deletion request: *"Bitte löschen Sie mein Konto und alle damit verbundenen persönlichen Daten endgültig."* Primary account profile was deleted from `account_service`. Finance operations maintains a statutory compliance journal entry (`audit_record_4401`) governed by statutory retention rules.
- **Audited Policy**: `rule_12` (`SECURITY_AUDIT_LOG` must be retained when within the retention window; personal records deleted without destroying required audit history).
- **Agent Decision**: `COMPLETE`
- **Generated Steps**:
  1. `[VERIFICATION]` `system_id`: `account_service`, `resource_id`: `account_7734`, `operation`: `VERIFY_RECORD_ABSENT`, `state`: `ABSENT`, `evidence_id`: `evidence_ext_03a`
  2. `[VERIFICATION]` `system_id`: `security_service`, `resource_id`: `audit_record_4401`, `operation`: `VERIFY_RECORD_PRESENT`, `state`: `PRESENT`, `evidence_id`: `evidence_ext_03b`

---

## 4. Failures Discovered and Improvements Made

During iterative calibration and regression testing, four major architectural failures were identified and resolved:

### Failure 1: Distributed Trace Disconnection in Log Evidence
- **Initial Defect**: The baseline log parser evaluated log lines independently. When `service=support_replica` logged a contact lookup on line 1 (`lookup_key=nadia.ionescu@yahoo.com`) and recorded the resource ID on line 2 (`resource_id=support_002`), the parser missed the correlation, causing a false negative in `case_10`.
- **Improvement**: Implemented a **Trace Correlation Indexer**. The parser groups log statements by `trace_id` before evaluation. All statements belonging to the same transaction are aggregated, ensuring 100% correlation between query keys and resource identifiers.

### Failure 2: Schema Heterogeneity in Read-Replica SQL Dumps
- **Initial Defect**: While primary databases stored structured relational rows, regional and read replicas (`customer_data_read_replica_*.sql`) stored heterogeneous records inside a JSON column named `record_json`. The initial parser searched for `payload_json`, causing missed search index and account records in `case_16` and `case_22`.
- **Improvement**: Dynamic SQLite PRAGMA table inspection was implemented. The engine automatically inspects column metadata, extracts both `record_json` and `payload_json`, and decodes nested payload objects into canonical service records.

### Failure 3: Historical SHA-256 Hash Disconnection
- **Initial Defect**: In `case_12`, an analytics profile lookup cited `correlation_key="44a65154bfd8e408852578fbd76813d094d1944f255ac1769ee81ba90492f10e"`. The user's current email (`minjun.kim@gmail.com`) did not match this hash string, leading to a missed finding.
- **Improvement**: Enhanced `IdentityResolver` to trace all historical email modifications in `user_audit_log.csv`. For every historical email variant, the SHA-256 digest is computed and registered into the user's multi-temporal hash set. This immediately linked `user_12`'s historical address (`minjun.kim90@gmail.com`) to the residual analytics record.

### Failure 4: Non-Deletion Boundary Detection (`NOT_APPLICABLE`)
- **Initial Defect**: Standard keyword searches for words like `close`, `account`, or `remove` falsely flagged non-deletion requests (such as *"remove me from marketing lists only, but keep my account active"* or *"I'd like to download my account information"*).
- **Improvement**: Implemented a multi-lingual intent classifier with negative lookahead patterns covering GDPR Article 15 (access), Article 16 (rectification), Article 20 (portability), marketing opt-out, and invoice retrieval. Correctly classified 100% of non-deletion requests (`case_533` to `case_542`) as `NOT_APPLICABLE` with `steps_json = []`.
