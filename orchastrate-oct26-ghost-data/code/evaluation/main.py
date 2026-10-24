"""
Evaluation and Correctness Test Runner for Ghost Data Still Exists.
Compares candidate predictions against ground truth (sample_output.csv and custom_test_suite.py)
and computes case-level, step-level, field-level, and sequence accuracy metrics.
"""

import json
import os
import sys
from typing import List, Dict, Any, Tuple
import pandas as pd

try:
    from custom_test_suite import CUSTOM_TEST_CASES
except ImportError:
    from code.evaluation.custom_test_suite import CUSTOM_TEST_CASES


def evaluate_predictions(pred_df: pd.DataFrame, gt_df: pd.DataFrame) -> Dict[str, Any]:
    """
    Evaluates pred_df against gt_df across:
      - status_accuracy
      - step_precision, step_recall, step_f1
      - field_accuracy
      - sequence_accuracy
    """
    gt_map = {row['case_id']: row for _, row in gt_df.iterrows()}
    
    total_cases = 0
    correct_status = 0
    
    total_expected_steps = 0
    total_predicted_steps = 0
    total_matched_steps = 0
    
    total_fields = 0
    correct_fields = 0
    
    total_seq_eval = 0
    correct_seq = 0
    
    step_fields = ['phase', 'system_id', 'resource_id', 'operation', 'state', 'evidence_id']
    
    for _, pred_row in pred_df.iterrows():
        cid = pred_row['case_id']
        if cid not in gt_map:
            continue
            
        gt_row = gt_map[cid]
        total_cases += 1
        
        # 1. Status Accuracy
        p_status = str(pred_row['deletion_status']).strip()
        g_status = str(gt_row['deletion_status']).strip()
        if p_status == g_status:
            correct_status += 1
            
        # Parse steps
        try:
            p_steps = json.loads(pred_row['steps_json']) if isinstance(pred_row['steps_json'], str) else pred_row['steps_json']
        except Exception:
            p_steps = []
            
        try:
            g_steps = json.loads(gt_row['steps_json']) if isinstance(gt_row['steps_json'], str) else gt_row['steps_json']
        except Exception:
            g_steps = []
            
        total_predicted_steps += len(p_steps)
        total_expected_steps += len(g_steps)
        
        # Step matching: match on (phase, system_id, resource_id, operation)
        def step_key(s):
            return (s.get('phase'), s.get('system_id'), s.get('resource_id'), s.get('operation'))
            
        g_keyed = {step_key(s): s for s in g_steps}
        p_keyed = {step_key(s): s for s in p_steps}
        
        matched_keys = set(g_keyed.keys()).intersection(set(p_keyed.keys()))
        total_matched_steps += len(matched_keys)
        
        # Field accuracy on matched steps
        for k in matched_keys:
            gs = g_keyed[k]
            ps = p_keyed[k]
            for f in step_fields:
                total_fields += 1
                if gs.get(f) == ps.get(f):
                    correct_fields += 1
                    
        # Sequence accuracy: check if sequence of step_keys matches exactly
        if len(g_steps) > 0 or len(p_steps) > 0:
            total_seq_eval += 1
            g_seq = [step_key(s) for s in g_steps]
            p_seq = [step_key(s) for s in p_steps]
            if g_seq == p_seq:
                correct_seq += 1

    precision = total_matched_steps / total_predicted_steps if total_predicted_steps > 0 else 1.0
    recall = total_matched_steps / total_expected_steps if total_expected_steps > 0 else 1.0
    f1 = (2 * precision * recall) / (precision + recall) if (precision + recall) > 0 else 0.0
    status_acc = correct_status / total_cases if total_cases > 0 else 0.0
    field_acc = correct_fields / total_fields if total_fields > 0 else 1.0
    seq_acc = correct_seq / total_seq_eval if total_seq_eval > 0 else 1.0
    
    return {
        "total_cases": total_cases,
        "status_accuracy": status_acc,
        "precision": precision,
        "recall": recall,
        "f1": f1,
        "field_accuracy": field_acc,
        "sequence_accuracy": seq_acc,
        "matched_steps": total_matched_steps,
        "expected_steps": total_expected_steps,
        "predicted_steps": total_predicted_steps
    }


def main():
    import argparse
    parser = argparse.ArgumentParser(description="Evaluation Suite for Ghost Data Still Exists")
    parser.add_argument("--pred", type=str, default=None, help="Path to predictions CSV file to evaluate against sample ground truth")
    args = parser.parse_args()

    print("=== Ghost Data Still Exists: Evaluation Suite ===")
    sample_gt_path = "dataset/sample_output.csv"
    if not os.path.exists(sample_gt_path):
        sample_gt_path = "../../dataset/sample_output.csv"
        
    if os.path.exists(sample_gt_path):
        gt_df = pd.read_csv(sample_gt_path)
        print(f"Loaded {len(gt_df)} sample ground truth cases from {sample_gt_path}.")
        
        # Self-test baseline
        metrics = evaluate_predictions(gt_df, gt_df)
        print("\nBaseline Self-Test Results (Ideal 100%):")
        for k, v in metrics.items():
            if isinstance(v, float):
                print(f"  {k:20s}: {v*100:6.2f}%")
            else:
                print(f"  {k:20s}: {v}")

        if args.pred and os.path.exists(args.pred):
            pred_df = pd.read_csv(args.pred)
            eval_metrics = evaluate_predictions(pred_df, gt_df)
            print(f"\nEvaluation Results for {args.pred}:")
            for k, v in eval_metrics.items():
                if isinstance(v, float):
                    print(f"  {k:20s}: {v*100:6.2f}%")
                else:
                    print(f"  {k:20s}: {v}")
    else:
        print("Sample ground truth file not found.")
        
    print(f"\nLoaded {len(CUSTOM_TEST_CASES)} custom test cases.")
    for tc in CUSTOM_TEST_CASES:
        desc = tc.get('description', tc.get('title', ''))
        print(f"  - [{tc['case_id']}] {desc}: Expected {tc['expected_status']} ({len(tc['expected_steps'])} steps)")


if __name__ == "__main__":
    main()
