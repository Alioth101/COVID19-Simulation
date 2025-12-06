"""
Economic Debug Log Analyzer

This script analyzes the economic debug logs to identify wealth conservation issues
and diagnose the root cause of Government economic collapse.

Usage:
    python analyze_economic_debug.py [--log_file <path>]
"""

import json
import sys
import os
import argparse
from typing import Dict, List, Tuple
import pandas as pd
import numpy as np
from datetime import datetime

def load_economic_log(log_file: str) -> Dict:
    """Load economic debug log from JSON file"""
    print(f"📁 Loading economic log: {log_file}")
    
    if not os.path.exists(log_file):
        print(f"❌ Error: Log file not found: {log_file}")
        sys.exit(1)
    
    with open(log_file, 'r', encoding='utf-8') as f:
        data = json.load(f)
    
    print(f"✓ Loaded successfully")
    print(f"  - Transactions: {data['metadata']['total_transactions']}")
    print(f"  - Wealth snapshots: {data['metadata']['total_snapshots']}")
    print(f"  - Accounting details: {data['metadata']['total_accounting']}")
    
    return data

def analyze_government_accounting(data: Dict):
    """Analyze Government accounting details"""
    
    print("\n" + "="*80)
    print("GOVERNMENT ACCOUNTING ANALYSIS")
    print("="*80)
    
    accounting_details = data['accounting_details']
    
    # Filter Government accounting entries
    gov_accounting = [d for d in accounting_details if d['agent']['type'] == 'Government']
    
    if not gov_accounting:
        print("⚠️ No Government accounting records found")
        return
    
    print(f"\n📊 Found {len(gov_accounting)} Government accounting events")
    
    # Analyze each accounting event
    for i, entry in enumerate(gov_accounting):
        day = entry['day']
        details = entry['details']
        
        print(f"\n【Day {day} Monthly Settlement】")
        print("-"*50)
        
        # Wealth change
        wealth_before = details['wealth_before']
        wealth_after = details['wealth_after']
        total_spent = details['total_spent']
        
        print(f"Government Wealth:")
        print(f"  Before: {wealth_before:,.0f}")
        print(f"  After:  {wealth_after:,.0f}")
        print(f"  Spent:  {total_spent:,.0f}")
        
        # Healthcare
        healthcare = details['healthcare']
        print(f"\nHealthcare:")
        print(f"  Expense recorded: {healthcare['expense_recorded']:,.0f}")
        print(f"  Amount paid:      {healthcare['amount_paid']:,.0f}")
        print(f"  Discrepancy:      {healthcare['discrepancy']:,.0f}")
        if abs(healthcare['discrepancy']) > 1:
            print(f"  ⚠️ Healthcare payment discrepancy detected!")
        
        # Unemployed relief
        unemployed = details['unemployed']
        print(f"\nUnemployed Relief:")
        print(f"  Count: {unemployed['count']}")
        if unemployed['count'] > 0:
            print(f"  Expenses (min/avg/max): {unemployed['expenses']['min']:.0f} / "
                  f"{unemployed['expenses']['avg']:.0f} / {unemployed['expenses']['max']:.0f}")
            print(f"  Total expenses: {unemployed['expenses']['total']:,.0f}")
            print(f"  Amount paid:    {unemployed['amount_paid']:,.0f}")
            print(f"  Discrepancy:    {unemployed['discrepancy']:,.0f}")
            if abs(unemployed['discrepancy']) > 1:
                print(f"  ⚠️ Unemployment payment discrepancy detected!")
        
        # Homeless relief
        homeless = details['homeless']
        print(f"\nHomeless Relief:")
        print(f"  Count: {homeless['count']}")
        if homeless['count'] > 0:
            print(f"  Total expenses: {homeless['expenses']['total']:,.0f}")
            print(f"  Amount paid:    {homeless['amount_paid']:,.0f}")
            print(f"  Discrepancy:    {homeless['discrepancy']:,.0f}")
        
        # Wealth conservation check
        conservation = details['wealth_conservation']
        print(f"\n💰 Wealth Conservation:")
        print(f"  Expected spent: {conservation['expected_spent']:,.0f}")
        print(f"  Actual spent:   {conservation['actual_spent']:,.0f}")
        print(f"  Discrepancy:    {conservation['discrepancy']:,.0f}")
        
        if abs(conservation['discrepancy']) > 1000:
            print(f"  ❌ MAJOR WEALTH CONSERVATION VIOLATION!")
            print(f"     {abs(conservation['discrepancy']):,.0f} wealth disappeared!")

def analyze_wealth_transfers(data: Dict):
    """Analyze wealth transfer patterns"""
    
    print("\n" + "="*80)
    print("WEALTH TRANSFER ANALYSIS")
    print("="*80)
    
    transactions = data['transactions']
    
    # Group transactions by type
    by_type = {}
    for t in transactions:
        if 'type' not in t:
            continue
        tx_type = t['type']
        if tx_type not in by_type:
            by_type[tx_type] = []
        by_type[tx_type].append(t)
    
    print("\n📊 Transaction Summary by Type:")
    print(f"{'Type':<25} {'Count':<10} {'Total Amount':<15} {'Avg Amount':<15}")
    print("-"*70)
    
    for tx_type, txs in sorted(by_type.items()):
        if tx_type == 'PERSON_EXPENSES':
            continue  # Skip expense tracking entries
        
        amounts = [t.get('amount', 0) for t in txs]
        total = sum(amounts)
        avg = total / len(amounts) if amounts else 0
        
        print(f"{tx_type:<25} {len(txs):<10} {total:<15,.0f} {avg:<15,.0f}")
    
    # Analyze unemployment relief transactions
    if 'unemployment_relief' in by_type:
        analyze_relief_transfers(by_type['unemployment_relief'], 'Unemployment')
    
    # Analyze homeless relief transactions
    if 'homeless_relief' in by_type:
        analyze_relief_transfers(by_type['homeless_relief'], 'Homeless')

def analyze_relief_transfers(transactions: List[Dict], relief_type: str):
    """Analyze relief payment transfers in detail"""
    
    print(f"\n📋 {relief_type} Relief Transfer Details:")
    
    # Group by day
    by_day = {}
    for t in transactions:
        day = t['day']
        if day not in by_day:
            by_day[day] = []
        by_day[day].append(t)
    
    for day in sorted(by_day.keys()):
        day_txs = by_day[day]
        
        print(f"\n  Day {day}: {len(day_txs)} payments")
        
        # Check wealth changes
        wealth_changes = []
        house_wealth_changes = []
        
        for tx in day_txs:
            details = tx.get('details', {})
            wealth_change = details.get('wealth_change', 0)
            house_wealth_change = details.get('house_wealth_change', 0)
            
            wealth_changes.append(wealth_change)
            house_wealth_changes.append(house_wealth_change)
        
        # Analyze wealth changes
        non_zero_changes = [w for w in wealth_changes if abs(w) > 0.01]
        non_zero_house_changes = [w for w in house_wealth_changes if abs(w) > 0.01]
        
        print(f"    Payments with wealth increase: {len(non_zero_changes)}/{len(wealth_changes)}")
        print(f"    House wealth increases: {len(non_zero_house_changes)}/{len(house_wealth_changes)}")
        
        if len(non_zero_changes) == 0:
            print(f"    ⚠️ WARNING: No wealth increases despite payments!")
            print(f"    This indicates wealth is disappearing!")
        
        # Calculate total discrepancy
        total_paid = sum(tx['amount'] for tx in day_txs)
        total_received = sum(wealth_changes) + sum(house_wealth_changes)
        discrepancy = total_paid - total_received
        
        print(f"    Total paid: {total_paid:,.0f}")
        print(f"    Total received: {total_received:,.0f}")
        print(f"    Discrepancy: {discrepancy:,.0f}")
        
        if abs(discrepancy) > 1000:
            print(f"    ❌ MAJOR DISCREPANCY: {discrepancy:,.0f} wealth disappeared!")

def analyze_person_expenses(data: Dict):
    """Analyze Person expenses values"""
    
    print("\n" + "="*80)
    print("PERSON EXPENSES ANALYSIS")
    print("="*80)
    
    transactions = data['transactions']
    
    # Filter person expense entries
    expense_entries = [t for t in transactions if t.get('type') == 'PERSON_EXPENSES']
    
    if not expense_entries:
        print("⚠️ No person expense records found")
        return
    
    print(f"\n📊 Found {len(expense_entries)} expense records")
    
    # Group by context
    by_context = {}
    for e in expense_entries:
        context = e.get('context', 'Unknown')
        if context not in by_context:
            by_context[context] = []
        by_context[context].append(e['expenses'])
    
    print("\n📋 Expenses by Context:")
    for context, expenses in by_context.items():
        if expenses:
            print(f"\n  {context}:")
            print(f"    Count: {len(expenses)}")
            print(f"    Min: {min(expenses):,.0f}")
            print(f"    Avg: {sum(expenses)/len(expenses):,.0f}")
            print(f"    Max: {max(expenses):,.0f}")
            
            # Check for abnormal values
            abnormal = [e for e in expenses if e > 10000]
            if abnormal:
                print(f"    ⚠️ Abnormal values (>10000): {len(abnormal)}")
                print(f"       Values: {abnormal[:5]}")

def find_root_cause(data: Dict):
    """Analyze and identify the root cause of wealth issues"""
    
    print("\n" + "="*80)
    print("ROOT CAUSE ANALYSIS")
    print("="*80)
    
    # Check for healthcare timing issue
    print("\n🔍 Checking Healthcare Timing Issue...")
    gov_accounting = [d for d in data['accounting_details'] if d['agent']['type'] == 'Government']
    
    healthcare_issues = []
    for entry in gov_accounting:
        healthcare = entry['details']['healthcare']
        if healthcare['expense_recorded'] > 0 and healthcare['amount_paid'] == 0:
            healthcare_issues.append(entry['day'])
    
    if healthcare_issues:
        print(f"  ❌ Healthcare timing bug confirmed on days: {healthcare_issues}")
        print(f"     Healthcare.expenses was reset before Government could pay")
    else:
        print(f"  ✓ No healthcare timing issues detected")
    
    # Check for wealth conservation violations
    print("\n🔍 Checking Wealth Conservation...")
    conservation_violations = []
    
    for entry in gov_accounting:
        conservation = entry['details']['wealth_conservation']
        if abs(conservation['discrepancy']) > 1000:
            conservation_violations.append({
                'day': entry['day'],
                'discrepancy': conservation['discrepancy']
            })
    
    if conservation_violations:
        print(f"  ❌ Major wealth conservation violations found:")
        for v in conservation_violations:
            print(f"     Day {v['day']}: {v['discrepancy']:,.0f} wealth disappeared")
        
        total_disappeared = sum(abs(v['discrepancy']) for v in conservation_violations)
        print(f"  Total wealth disappeared: {total_disappeared:,.0f}")
    else:
        print(f"  ✓ No major wealth conservation violations")
    
    # Check for wealth transfer failures
    print("\n🔍 Checking Wealth Transfer Mechanism...")
    transactions = data['transactions']
    
    relief_txs = [t for t in transactions if 'relief' in t.get('type', '')]
    failed_transfers = []
    
    for tx in relief_txs:
        details = tx.get('details', {})
        wealth_change = details.get('wealth_change', 0)
        house_wealth_change = details.get('house_wealth_change', 0)
        total_change = wealth_change + house_wealth_change
        
        if abs(total_change) < 0.01 and tx.get('amount', 0) > 0:
            failed_transfers.append(tx)
    
    if failed_transfers:
        print(f"  ❌ Found {len(failed_transfers)} failed wealth transfers")
        print(f"     Government paid but recipients didn't receive the money")
        
        # Sample analysis
        if len(failed_transfers) > 0:
            sample = failed_transfers[0]
            print(f"\n  Sample failed transfer:")
            print(f"    Type: {sample.get('type')}")
            print(f"    Amount paid: {sample.get('amount', 0):,.0f}")
            print(f"    Wealth change: {sample.get('details', {}).get('wealth_change', 0)}")
            print(f"    Has house: {sample.get('details', {}).get('has_house', False)}")
    else:
        print(f"  ✓ Wealth transfers appear to be working")
    
    # Final diagnosis
    print("\n" + "="*80)
    print("FINAL DIAGNOSIS")
    print("="*80)
    
    issues_found = []
    
    if healthcare_issues:
        issues_found.append("Healthcare Timing Bug: Healthcare.expenses reset before payment")
    
    if conservation_violations:
        issues_found.append(f"Wealth Conservation Violation: {total_disappeared:,.0f} wealth disappeared")
    
    if failed_transfers:
        issues_found.append(f"Wealth Transfer Failure: {len(failed_transfers)} payments didn't reach recipients")
    
    if issues_found:
        print("\n❌ CRITICAL ISSUES IDENTIFIED:")
        for i, issue in enumerate(issues_found, 1):
            print(f"\n{i}. {issue}")
        
        print("\n📝 RECOMMENDATIONS:")
        
        if healthcare_issues:
            print("\n• Fix Healthcare Timing:")
            print("  - Save Healthcare.expenses before reset")
            print("  - Or change accounting order (Government first)")
        
        if conservation_violations or failed_transfers:
            print("\n• Fix Wealth Transfer Mechanism:")
            print("  - Check Person.supply() and House.supply() methods")
            print("  - Verify that wealth is correctly added to recipients")
            print("  - Look for any hidden wealth destruction")
        
    else:
        print("\n✓ No critical issues found in the economic system")

def main():
    """Main function"""
    
    parser = argparse.ArgumentParser(description="Analyze economic debug logs")
    parser.add_argument('--log_file', type=str, help='Path to economic debug JSON file')
    
    args = parser.parse_args()
    
    # Find the most recent log file if not specified
    if not args.log_file:
        output_dir = "output/graph_batch"
        if os.path.exists(output_dir):
            log_files = [f for f in os.listdir(output_dir) if f.startswith("economic_debug_") and f.endswith(".json")]
            if log_files:
                log_files.sort()
                args.log_file = os.path.join(output_dir, log_files[-1])
                print(f"📌 Using most recent log file: {args.log_file}")
            else:
                print("❌ No economic debug logs found in output/graph_batch/")
                print("   Run an experiment with ENABLE_ECONOMIC_DEBUG=True first")
                sys.exit(1)
        else:
            print("❌ Output directory not found: output/graph_batch/")
            sys.exit(1)
    
    print("="*80)
    print("ECONOMIC DEBUG LOG ANALYZER")
    print("="*80)
    print()
    
    # Load log file
    data = load_economic_log(args.log_file)
    
    # Run analyses
    analyze_government_accounting(data)
    analyze_wealth_transfers(data)
    analyze_person_expenses(data)
    find_root_cause(data)
    
    print("\n" + "="*80)
    print("Analysis complete!")
    print("="*80)

if __name__ == "__main__":
    main()
