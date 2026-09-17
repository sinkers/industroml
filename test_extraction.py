#!/usr/bin/env python3
"""
Test script for the IndustrialML extraction functionality.
Demonstrates usage and validates output.
"""

import os
import json
from pathlib import Path
from extract.extract_info import IndustroMLExtractor

def test_validation():
    """Test the validation functionality with existing files"""
    print("Testing IndustrialML validation...")
    
    extractor = IndustroMLExtractor(require_api_key=False)
    
    # Test files
    test_files = [
        "gt01_complete.json",
        "reference/gt01_network.json", 
        "reference/gt01_components.json"
    ]
    
    for file_path in test_files:
        if os.path.exists(file_path):
            print(f"\nValidating {file_path}:")
            try:
                with open(file_path) as f:
                    data = json.load(f)
                
                is_valid, errors = extractor.validate_output(data)
                
                if is_valid:
                    print("  ✅ Valid IndustroML format")
                else:
                    print("  ❌ Validation errors:")
                    for error in errors[:5]:  # Show first 5 errors
                        print(f"    - {error}")
                    if len(errors) > 5:
                        print(f"    ... and {len(errors)-5} more errors")
                        
            except Exception as e:
                print(f"  ❌ Error reading file: {e}")
        else:
            print(f"  ⚠️  File not found: {file_path}")

def demonstrate_usage():
    """Show usage examples"""
    print("\n" + "="*60)
    print("USAGE EXAMPLES:")
    print("="*60)
    
    print("\n1. Extract from diagram image:")
    print("   python3 extract/extract_info.py diagram.png -o output.json")
    
    print("\n2. Extract with specific diagram type:")
    print("   python3 extract/extract_info.py network.png -t network -o network_data.json")
    
    print("\n3. Validate existing file:")
    print("   python3 extract/extract_info.py --validate-only data.json")
    
    print("\n4. Available diagram types:")
    print("   - electrical: Electrical single-line diagrams")
    print("   - mechanical: P&ID mechanical diagrams")
    print("   - network: Network topology diagrams") 
    print("   - pid: Process & instrumentation diagrams")
    print("   - industrial: Generic industrial diagrams")

if __name__ == "__main__":
    print("IndustrialML Extraction Tool Test")
    print("=" * 40)
    
    test_validation()
    demonstrate_usage()
    
    print(f"\n" + "="*60)
    print("AVAILABLE TEST FILES:")
    print("="*60)
    
    # List available image files for testing
    image_files = []
    for pattern in ["**/*.png", "**/*.jpg", "**/*.jpeg"]:
        for file_path in Path("reference").glob(pattern):
            if file_path.is_file():
                image_files.append(str(file_path))
    
    if image_files:
        print("Found test image files:")
        for img in image_files[:10]:  # Show first 10
            print(f"  - {img}")
        if len(image_files) > 10:
            print(f"  ... and {len(image_files)-10} more files")
    else:
        print("No image files found in reference/ directory")
        
    print(f"\nTo test extraction, set OPENAI_API_KEY and run:")
    print(f"python3 extract/extract_info.py reference/gt01/network.png -o test_output.json")