# Correctness Verification Specification
**Ghost Data Still Exists — Automated Multi-Phase Verification Framework**

This document specifies the validation criteria, automated metrics, and test gates used to verify the deletion-audit agent across each development phase.

---

## 1. Quantitative Verification Metrics

The agent's outputs are evaluated against known ground-truth records across four hierarchical levels:

### 1.1 Case-Level Status Accuracy ($A_{status}$)
$$\text{Accuracy}_{status} = \frac{\sum_{i=1}^{N} \mathbb{I}(\hat{y}_i = y_i)}{N}$$
- Compares the predicted `deletion_status` $\in \{\text{COMPLETE}, \text{INCOMPLETE}, \text{NOT\_APPLICABLE}\}$ against canonical labels.
- **Passing Target**: $100\%$ on the 32 sample cases and non-deletion benchmarks.

### 1.2 Step-Level Precision & Recall ($P_{step}, R_{step}, F_{1}$)
$$\text{Precision} = \frac{|\hat{S} \cap S|}{|\hat{S}|}, \quad \text{Recall} = \frac{|\hat{S} \cap S|}{|S|}, \quad F_1 = \frac{2 \cdot P \cdot R}{P + R}$$
- Evaluates whether the set of detected findings, remediation operations, and verification checks matches the ground truth without hallucinating extra steps or missing required actions.
- **Passing Target**: $F_1 = 1.0$ across sample benchmarks.

### 1.3 Field-Level Exact Accuracy ($A_{fields}$)
$$\text{Accuracy}_{field} = \frac{1}{|S|} \sum_{s \in S} \prod_{f \in F} \mathbb{I}(\hat{s}[f] == s[f])$$
- Where $F = \{\text{phase}, \text{system\_id}, \text{resource\_id}, \text{operation}, \text{state}, \text{evidence\_id}\}$.
- Any discrepancy in naming convention, missing evidence pointer, or state mismatch causes a failure.
- **Passing Target**: $100\%$ field match.

### 1.4 Sequence Accuracy ($A_{seq}$)
$$\text{Sequence Match} = \mathbb{I}(\text{TupleSequence}(\hat{S}) == \text{TupleSequence}(S))$$
- Verifies that the ordered array structure strictly complies with:
  1. `FINDING` $\to$ `REMEDIATION` $\to$ `VERIFICATION`
  2. Operation priority order per phase (as defined in `problem_statement.md`)
  3. Tie-breaker sorting: `system_id` ascending, then `resource_id` ascending.
- **Passing Target**: $100\%$ sequence concordance.

---

## 2. Phase-by-Phase Verification Gates

| Phase | Module Under Test | Input Data | Expected Invariants & Assertions | Pass Criteria |
|---|---|---|---|---|
| **Gate 1** | **Intent Classifier** | `sample_deletion_requests.csv` + Cases 533–542 in `deletion_requests.csv` | - 32/32 sample requests classified as `DELETION`<br>- Cases 533–542 classified as `NOT_APPLICABLE`<br>- Output `steps_json = []` for all `NOT_APPLICABLE` | Zero false positives, Zero false negatives |
| **Gate 2** | **Identity Resolver** | `user_identities.csv` + `user_audit_log.csv` | - All request emails resolve to unique `user_id`<br>- Historical emails/phones/hashes fully recovered<br>- SHA-256 hash recalculated and matches canonical records | 100% graph connectivity, no orphan identities |
| **Gate 3** | **Temporal Evidence Ingestion** | `evidence_files.csv` + `dataset/evidence/*` | - Any file with `captured_at > audit_at` is strictly rejected<br>- SQLite databases load with 0 PRAGMA/foreign key violations<br>- JSON bundles, text logs, and PDFs parse deterministically | Zero temporal leakage, 100% parse success |
| **Gate 4** | **Policy & Hazard Auditor** | `deletion_rules.csv` + `system_activity.csv` + parsed evidence | - Detects lingering customer profiles, search documents, un-anonymized analytics<br>- Identifies enabled connectors (`enabled=1`) as `REPORT_ACTIVE_DATA_FLOW`<br>- Identifies unblocked backups (`restore_allowed=1`) as `REPORT_RESTORE_RISK`<br>- Retains compliant audit logs as `VERIFY_RECORD_PRESENT` | Status matches `sample_output.csv` (10/10 COMPLETE, 22/22 INCOMPLETE) |
| **Gate 5** | **Step Synthesizer & Formatter** | Raw audit findings | - Consecutive numbering starting at 1 (`step_no = 1, 2, ...`)<br>- `evidence_id` non-empty only for findings and COMPLETE verification<br>- `evidence_id = ""` for proposed remediation and post-remediation verification in INCOMPLETE cases | Exact schema validation & 100% sequence match |

---

## 3. Test Suites & Benchmarks

### Suite A: Official Sample Benchmark (32 Cases)
- `dataset/sample_deletion_requests.csv` evaluated against `dataset/sample_output.csv`.
- Covers single-system deletions, multi-system failures, failover replica drift, sync connector risks, backup restore risks, and tombstone accounts.

### Suite B: Official Non-Deletion Benchmark (10 Cases)
- Cases 533–542 in `dataset/deletion_requests.csv`.
- Validates that non-deletion intents (GDPR Article 15 access, GDPR Article 20 data portability, GDPR Article 16 rectification, marketing opt-out, invoice retrieval) produce `NOT_APPLICABLE` and `steps_json = []`.

### Suite C: Custom Participant Test Suite (3 Novel Synthetic Edge Cases)
Defined in [`code/evaluation/custom_test_suite.py`](file:///home/skandan-c-y/PycharmProjects/hackerrank-orchestrate-october26/code/evaluation/custom_test_suite.py):
1. **Case EXT-01 (Tombstone with Residual PII Leak)**:
   - Account service preserved a tombstone, but inadvertently retained the user's telephone number while removing name and email.
   - Expected: `INCOMPLETE`, `REPORT_EXPOSED_PII` on `account_service`, remediation `REDACT_RECORD`, verification `VERIFY_RECORD_REDACTED`.
2. **Case EXT-02 (Post-Report Active Connector Resurrection)**:
   - Deletion reported `COMPLETE` at $T_1$, but at $T_2$ ($T_1 < T_2 \le \text{audit\_at}$), a sync connector was re-enabled and indexed user records into `search_service`.
   - Expected: `INCOMPLETE`, `REPORT_ACTIVE_DATA_FLOW` on `integration_service` + `REPORT_REMAINING_RECORD` on `search_service`.
3. **Case EXT-03 (Multi-lingual Disputed Order & Legal Hold Preservation)**:
   - Request submitted in German requesting deletion. Finance has an active legal hold on transaction records (`rule_13`).
   - Expected: `COMPLETE` if non-financial data is deleted and legal hold record is retained (`VERIFY_RECORD_PRESENT`).

---

## 4. Execution Command for Verification

To run the complete verification suite at any time:

```bash
python3 code/evaluation/main.py
```
