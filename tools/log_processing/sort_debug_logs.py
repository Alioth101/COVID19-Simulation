#!/usr/bin/env python3
"""
Debug Log Sorter

This script sorts the debug_cashflow.log file by iteration number
to provide ordered output despite concurrent execution.
"""

import re
import sys
from typing import List, Tuple

def parse_log_line(line: str) -> Tuple[int, str]:
    """
    Parse a log line and extract iteration number
    Returns: (iteration, original_line)
    """
    # Match pattern: [Iter  444 Day18H12] ...
    match = re.match(r'\[Iter\s*(\d+)\s+Day\d+H\d+\]', line)
    if match:
        iteration = int(match.group(1))
        return iteration, line.strip()
    else:
        # If no match, put at the end with a very high iteration number
        return 999999, line.strip()

def sort_debug_log(input_file: str = "debug_cashflow.log", output_file: str = "debug_cashflow_sorted.log"):
    """
    Sort debug log file by iteration number
    """
    try:
        # Read all lines
        with open(input_file, 'r', encoding='utf-8') as f:
            lines = f.readlines()
        
        print(f"📖 Reading {len(lines)} lines from {input_file}")
        
        # Parse and sort
        parsed_lines = []
        for line in lines:
            if line.strip():  # Skip empty lines
                iteration, content = parse_log_line(line)
                parsed_lines.append((iteration, content))
        
        # Sort by iteration number
        parsed_lines.sort(key=lambda x: x[0])
        
        # Write sorted output
        with open(output_file, 'w', encoding='utf-8') as f:
            for iteration, content in parsed_lines:
                f.write(content + '\n')
        
        print(f"✅ Sorted {len(parsed_lines)} log entries")
        print(f"📝 Output written to: {output_file}")
        
        # Show iteration range
        if parsed_lines:
            min_iter = parsed_lines[0][0]
            max_iter = parsed_lines[-1][0]
            print(f"📊 Iteration range: {min_iter} → {max_iter}")
            print(f"📅 Day range: {min_iter//24} → {max_iter//24}")
        
        return True
        
    except FileNotFoundError:
        print(f"❌ Error: File '{input_file}' not found")
        return False
    except Exception as e:
        print(f"❌ Error: {e}")
        return False

def analyze_log_patterns(log_file: str = "debug_cashflow_sorted.log"):
    """
    Analyze patterns in the sorted log
    """
    try:
        with open(log_file, 'r', encoding='utf-8') as f:
            lines = f.readlines()
        
        print(f"\n🔍 Log Analysis:")
        print(f"   Total entries: {len(lines)}")
        
        # Count by type
        house_demand = sum(1 for line in lines if "House.demand" in line)
        house_supply = sum(1 for line in lines if "House.supply" in line)
        person_supply = sum(1 for line in lines if "Person.supply" in line)
        bankruptcy = sum(1 for line in lines if "bankruptcy" in line)
        statistics = sum(1 for line in lines if "STATISTICS RECORDED" in line)
        
        print(f"   House.demand: {house_demand}")
        print(f"   House.supply: {house_supply}")
        print(f"   Person.supply: {person_supply}")
        print(f"   Bankruptcies: {bankruptcy}")
        print(f"   Statistics: {statistics}")
        
        # Show first and last few entries
        print(f"\n📋 First 5 entries:")
        for i, line in enumerate(lines[:5]):
            print(f"   {i+1}. {line.strip()}")
        
        print(f"\n📋 Last 5 entries:")
        for i, line in enumerate(lines[-5:]):
            print(f"   {len(lines)-4+i}. {line.strip()}")
            
    except Exception as e:
        print(f"❌ Analysis error: {e}")

def main():
    """Main function"""
    print("🔧 Debug Log Sorter")
    print("=" * 50)
    
    # Sort the log
    success = sort_debug_log()
    
    if success:
        # Analyze the sorted log
        analyze_log_patterns()
        
        print(f"\n💡 Usage:")
        print(f"   View sorted log: notepad debug_cashflow_sorted.log")
        print(f"   Or use: type debug_cashflow_sorted.log | more")
        
        # Ask if user wants to see a sample
        try:
            response = input(f"\n❓ Show first 20 lines of sorted log? (y/n): ").lower()
            if response == 'y':
                with open("debug_cashflow_sorted.log", 'r', encoding='utf-8') as f:
                    lines = f.readlines()
                print(f"\n📖 First 20 lines:")
                print("-" * 80)
                for i, line in enumerate(lines[:20]):
                    print(line.strip())
                print("-" * 80)
        except KeyboardInterrupt:
            print(f"\n👋 Goodbye!")

if __name__ == "__main__":
    main()
