#!/usr/bin/env python3
"""
Ghost Data Still Exists — Autonomous Deletion Audit Agent
HackerRank Orchestrate (October 2026)

Modular CLI entry point and batch runner orchestrating:
  - IntentEngine: Regulatory request intent classification
  - IdentityEngine: Multi-temporal identity graph resolution
  - EvidenceEngine: Multi-modal evidence indexing and extraction
  - PolicyEngine: Policy enforcement, DAG remediation sorting
  - AuditEngine: Unified deletion audit pipeline orchestrator
"""

import argparse
import csv
import os
import sys
from datetime import datetime

# Setup path to import local engines
CURRENT_DIR = os.path.dirname(os.path.abspath(__file__))
REPO_ROOT = os.path.abspath(os.path.join(CURRENT_DIR, '..'))
if CURRENT_DIR not in sys.path:
    sys.path.insert(0, CURRENT_DIR)
if REPO_ROOT not in sys.path:
    sys.path.insert(0, REPO_ROOT)

from engines import (
    DeletionAuditAgent,
    is_deletion_request,
    IdentityResolver,
    EvidenceIndex,
    EvidenceParser,
    sort_steps
)


def run_audit(dataset_dir: str, input_csv: str, output_csv: str):
    """Executes deletion audit across all cases in input_csv and writes formatted output_csv."""
    print(f"Initializing Deletion Audit Agent with dataset from: {dataset_dir}")
    agent = DeletionAuditAgent(dataset_dir)
    
    if not os.path.exists(input_csv):
        print(f"Error: input file {input_csv} does not exist.")
        sys.exit(1)

    print(f"Auditing cases from: {input_csv}")
    rows_out = []
    
    with open(input_csv, mode='r', encoding='utf-8') as f:
        reader = csv.DictReader(f)
        cases = list(reader)

    print(f"Total cases to audit: {len(cases)}")
    start_time = datetime.now()

    for idx, c in enumerate(cases):
        cid = c['case_id']
        status, steps_json = agent.audit_case(c)
        rows_out.append({
            'case_id': cid,
            'deletion_status': status,
            'steps_json': steps_json
        })
        if (idx + 1) % 100 == 0 or (idx + 1) == len(cases):
            print(f"  Processed {idx + 1}/{len(cases)} cases...")

    elapsed = (datetime.now() - start_time).total_seconds()
    print(f"Completed {len(cases)} audits in {elapsed:.2f} seconds ({elapsed / max(1, len(cases))*1000:.2f} ms/case).")

    # Natural numerical sorting by case_id (e.g. case_33 before case_100)
    def case_sort_key(r):
        cid = r['case_id']
        parts = cid.split('_')
        if len(parts) > 1 and parts[-1].isdigit():
            return (parts[0], int(parts[-1]))
        return (cid, 0)

    rows_out.sort(key=case_sort_key)

    print(f"Writing {len(rows_out)} predictions to: {output_csv}")
    with open(output_csv, mode='w', encoding='utf-8', newline='') as f:
        writer = csv.writer(f)
        writer.writerow(['case_id', 'deletion_status', 'steps_json'])
        for r in rows_out:
            writer.writerow([r['case_id'], r['deletion_status'], r['steps_json']])

    print("Audit run finished successfully.")


def main():
    parser = argparse.ArgumentParser(description="Ghost Data Still Exists: Deletion Audit Agent")
    parser.add_argument('--dataset', default='dataset', help='Path to dataset directory')
    parser.add_argument('--input', default='dataset/deletion_requests.csv', help='Path to input deletion requests CSV')
    parser.add_argument('--output', default='output.csv', help='Path to output predictions CSV')
    parser.add_argument('--sample', action='store_true', help='Run on sample dataset and evaluate against ground truth')
    args = parser.parse_args()

    def resolve_p(p):
        if not os.path.isabs(p):
            cand = os.path.join(REPO_ROOT, p)
            if os.path.exists(cand):
                return cand
        return p

    dataset_dir = resolve_p(args.dataset)
    
    if args.sample:
        input_csv = os.path.join(dataset_dir, 'sample_deletion_requests.csv')
        output_csv = os.path.join(REPO_ROOT, 'sample_predictions.csv')
        run_audit(dataset_dir, input_csv, output_csv)
    else:
        input_csv = resolve_p(args.input)
        output_csv = os.path.join(REPO_ROOT, 'output.csv') if args.output == 'output.csv' else args.output
        run_audit(dataset_dir, input_csv, output_csv)


if __name__ == '__main__':
    main()
