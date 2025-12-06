#!/usr/bin/env python3
"""
Test the NumPy JSON serialization fix in economic_logger
"""

import numpy as np
import json
from covid_abs.economic_logger import economic_logger

def test_numpy_conversion():
    """Test that NumPy types are correctly converted"""
    print("🔍 Testing NumPy type conversion...")
    print("-" * 50)
    
    # Create a test object with various NumPy types
    test_data = {
        "int64": np.int64(42),
        "int32": np.int32(100),
        "float64": np.float64(3.14159),
        "float32": np.float32(2.718),
        "array": np.array([1, 2, 3]),
        "nested": {
            "value": np.int64(999),
            "list": [np.float64(1.1), np.float64(2.2)]
        }
    }
    
    print("📊 Original data types:")
    for key, value in test_data.items():
        print(f"   {key}: {type(value).__name__}")
    
    # Test the conversion function
    converted = economic_logger._convert_numpy(test_data)
    
    print("\n✅ Converted data types:")
    for key, value in converted.items():
        if isinstance(value, dict):
            print(f"   {key}: dict")
            for k, v in value.items():
                print(f"      {k}: {type(v).__name__}")
        else:
            print(f"   {key}: {type(value).__name__}")
    
    # Test JSON serialization
    try:
        json_str = json.dumps(converted, indent=2)
        print("\n✨ JSON serialization successful!")
        print("\n📝 Sample JSON output:")
        print(json_str[:200] + "...")
        return True
    except Exception as e:
        print(f"\n❌ JSON serialization failed: {e}")
        return False

def test_economic_logger():
    """Test the economic logger with NumPy values"""
    print("\n🔍 Testing Economic Logger with NumPy values...")
    print("-" * 50)
    
    # Initialize logger
    import tempfile
    import os
    
    with tempfile.TemporaryDirectory() as tmpdir:
        economic_logger.initialize(enabled=True, output_dir=tmpdir)
        
        # Log some data with NumPy types
        economic_logger.log_transaction(
            iteration=np.int64(10),
            source_type="Test",
            source_id="123",
            target_type="Test",
            target_id="456",
            amount=np.float64(100.50),
            transaction_type="test",
            details={"numpy_value": np.int32(42)}
        )
        
        # Save and check
        try:
            economic_logger.save()
            
            # Read the saved file
            output_file = economic_logger.output_file
            if os.path.exists(output_file):
                with open(output_file, 'r') as f:
                    data = json.load(f)
                print(f"✅ Successfully saved and loaded JSON file")
                print(f"   File: {output_file}")
                print(f"   Transactions: {len(data.get('transactions', []))}")
                return True
            else:
                print(f"❌ Output file not found: {output_file}")
                return False
        except Exception as e:
            print(f"❌ Error: {e}")
            return False

if __name__ == "__main__":
    print("🧪 Testing NumPy JSON Serialization Fix")
    print("=" * 50)
    
    success = True
    
    # Test conversion function
    if not test_numpy_conversion():
        success = False
    
    # Test economic logger
    if not test_economic_logger():
        success = False
    
    print("\n" + "=" * 50)
    if success:
        print("✅ ALL TESTS PASSED!")
        print("\n📋 Next steps:")
        print("1. Sync the fixed economic_logger.py to your server")
        print("2. Re-run the experiment")
        print("3. The economic debug log should save successfully")
    else:
        print("❌ TESTS FAILED! Please check the errors above.")
