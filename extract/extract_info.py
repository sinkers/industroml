#!/usr/bin/env python3
"""
Script to extract information from industrial diagrams (SLD, P&ID, network diagrams)
and convert to IndustroML format using GPT-4 vision capabilities.

Requirements:
- Extract all individual components with unique identifiers
- Mark uncertain components for human review
- Output valid IndustroML format for UI compatibility
- Use GPT-4 with comprehensive prompting
- Validate against IndustroML schema
"""

import os
import sys
import json
import argparse
import base64
from pathlib import Path
from typing import Dict, List, Any, Optional
import urllib.request
import urllib.parse

# Load environment variables if available
try:
    from dotenv import load_dotenv
    # Try to load from current directory first, then extract subdirectory
    if os.path.exists('.env'):
        load_dotenv()
    elif os.path.exists('extract/.env'):
        load_dotenv('extract/.env')
    else:
        load_dotenv()  # Default behavior
except ImportError:
    pass

# Try to import optional dependencies
try:
    import requests
    HAS_REQUESTS = True
except ImportError:
    HAS_REQUESTS = False
    
try:
    import jsonschema
    HAS_JSONSCHEMA = True
except ImportError:
    HAS_JSONSCHEMA = False

class IndustroMLExtractor:
    def __init__(self, require_api_key: bool = True):
        if require_api_key:
            self.api_key = os.getenv('OPENAI_API_KEY')
            if not self.api_key:
                raise ValueError("OPENAI_API_KEY not found in environment variables")
        else:
            self.api_key = None
        
        self.base_url = "https://api.openai.com/v1/chat/completions"
        self.model = "gpt-5"  # GPT-4 with vision
        
        # Load IndustroML schema for validation
        schema_path = Path(__file__).parent.parent / "industroml.schema.json"
        with open(schema_path) as f:
            self.schema = json.load(f)

    def encode_image(self, image_path: str) -> str:
        """Encode image or PDF to base64 for API"""
        # Handle PDF files by converting first page to image
        if image_path.lower().endswith('.pdf'):
            try:
                from PIL import Image
                import fitz  # PyMuPDF
                
                # Open PDF and get first page
                doc = fitz.open(image_path)
                page = doc[0]
                
                # Convert to image
                pix = page.get_pixmap()
                img_data = pix.tobytes("png")
                
                # Encode to base64
                return base64.b64encode(img_data).decode('utf-8')
                
            except ImportError:
                raise Exception("PDF support requires PyMuPDF. Install with: pip install PyMuPDF")
        else:
            # Handle regular image files
            with open(image_path, "rb") as image_file:
                return base64.b64encode(image_file.read()).decode('utf-8')

    def get_extraction_prompt(self, diagram_type: str = "industrial") -> str:
        """Generate comprehensive prompt for diagram extraction"""
        
        # Get valid enum values from loaded schema
        valid_domains = self.schema["$defs"]["domain"]["enum"]
        valid_asset_kinds = self.schema["$defs"]["assetKind"]["enum"] 
        valid_mediums = self.schema["$defs"]["medium"]["enum"]
        valid_container_types = self.schema["$defs"]["containerType"]["enum"]
        valid_connection_types = self.schema["$defs"]["connectionType"]["enum"]
        
        if diagram_type == "network":
            return f"""
You are a network engineering assistant analyzing network diagrams for technical documentation.

TASK: Analyze this network diagram and extract all network infrastructure components and their connections.

NETWORK ANALYSIS APPROACH:
- Identify all network equipment symbols and devices
- Categorize equipment types (switches, routers, firewalls, servers, access points)
- Map network hierarchy (core, distribution, access layers)
- Document network connections and link types
- Extract device labels, model numbers, and identifiers

EXPECTED OUTPUT FORMAT: Return valid IndustroML JSON with these sections:
- meta: Document metadata with format "IndustroML", version "0.1", site name
- containers: Network zones/VLANs (use types: {valid_container_types})
- assets: Network devices (use domains: {valid_domains}, kinds: ethernet_switch, router, firewall, server, access_point)
- interfaces: Network ports (use mediums: {valid_mediums})
- connections: Network links (use types: {valid_connection_types})

Count all visible network devices and extract their actual labels and specifications.
Return only the JSON structure analyzing this specific network diagram."""

        elif diagram_type == "electrical":
            return f"""
You are an electrical engineering assistant analyzing electrical diagrams for technical documentation.

TASK: Analyze this electrical diagram and extract all electrical components and their connections.

ELECTRICAL ANALYSIS APPROACH:
- Identify electrical symbols (transformers, breakers, switches, motors)
- Map power distribution hierarchy (high voltage to low voltage)
- Document electrical connections and cable types
- Extract component ratings, specifications, and identifiers
- Identify control circuits and protection devices

EXPECTED OUTPUT FORMAT: Return valid IndustroML JSON with these sections:
- meta: Document metadata with format "IndustroML", version "0.1", site name
- containers: Electrical panels/substations (use types: {valid_container_types})
- assets: Electrical components (use domains: {valid_domains}, kinds from electrical types)
- interfaces: Electrical terminals (use mediums: {valid_mediums})
- connections: Electrical connections (use types: {valid_connection_types})

Extract all visible electrical components with their actual labels and specifications.
Return only the JSON structure analyzing this specific electrical diagram."""

        elif diagram_type == "mechanical":
            return f"""
You are a mechanical engineering assistant analyzing mechanical diagrams for technical documentation.

TASK: Analyze this mechanical diagram and extract all mechanical components and their connections.

MECHANICAL ANALYSIS APPROACH:
- Identify mechanical symbols (pumps, valves, tanks, pipes, motors)
- Map process flow and mechanical connections
- Document piping, instrumentation, and mechanical linkages
- Extract component specifications and identifiers
- Identify process control elements

EXPECTED OUTPUT FORMAT: Return valid IndustroML JSON with these sections:
- meta: Document metadata with format "IndustroML", version "0.1", site name
- containers: Process areas/systems (use types: {valid_container_types})
- assets: Mechanical components (use domains: {valid_domains}, kinds from mechanical types)
- interfaces: Mechanical connections (use mediums: {valid_mediums})
- connections: Process connections (use types: {valid_connection_types})

Extract all visible mechanical components with their actual labels and specifications.
Return only the JSON structure analyzing this specific mechanical diagram."""

        else:
            return f"""
You are a technical documentation assistant helping with industrial system analysis.

TASK: Analyze this {diagram_type} engineering diagram and extract component information for technical documentation purposes.

TECHNICAL ANALYSIS APPROACH:
- Identify all visible components and symbols
- Extract component specifications and model information
- Document connections and relationships between components
- Record any visible technical specifications and identifiers

EXPECTED OUTPUT FORMAT: Return valid IndustroML JSON with these sections:
- meta: Document metadata with format "IndustroML", version "0.1", site name
- containers: Logical groupings (use types: {valid_container_types})
- assets: Components (use domains: {valid_domains}, kinds: {valid_asset_kinds})
- interfaces: Component ports (use mediums: {valid_mediums})
- connections: Component links (use types: {valid_connection_types})

Extract all visible components with their actual labels and specifications.
Return only the JSON structure analyzing this specific diagram."""

    def extract_from_image(self, image_path: str, diagram_type: str = "industrial") -> Dict[str, Any]:
        """Extract IndustroML data from diagram image using GPT-4 Vision"""
        
        # Encode image
        base64_image = self.encode_image(image_path)
        
        # Prepare API request
        headers = {
            "Content-Type": "application/json",
            "Authorization": f"Bearer {self.api_key}"
        }
        
        payload = {
            "model": self.model,
            "messages": [
                {
                    "role": "user", 
                    "content": [
                        {
                            "type": "text",
                            "text": self.get_extraction_prompt(diagram_type)
                        },
                        {
                            "type": "image_url",
                            "image_url": {
                                "url": f"data:image/png;base64,{base64_image}",
                                "detail": "high"
                            }
                        }
                    ]
                }
            ],
            "max_completion_tokens": 4000
        }
        
        # Make API request
        if HAS_REQUESTS:
            response = requests.post(self.base_url, headers=headers, json=payload)
            
            if response.status_code != 200:
                raise Exception(f"API request failed: {response.status_code} - {response.text}")
            
            result = response.json()
        else:
            # Fallback to urllib
            req = urllib.request.Request(self.base_url, 
                                       data=json.dumps(payload).encode('utf-8'),
                                       headers=headers)
            with urllib.request.urlopen(req) as response:
                if response.status != 200:
                    raise Exception(f"API request failed: {response.status}")
                result = json.loads(response.read().decode('utf-8'))
        
        content = result['choices'][0]['message']['content']
        
        # Parse JSON from response (handle various formats)
        json_str = content.strip()
        
        # Handle markdown code blocks
        if '```json' in json_str:
            json_start = json_str.find('```json') + 7
            json_end = json_str.find('```', json_start)
            json_str = json_str[json_start:json_end].strip()
        elif '```' in json_str:
            # Handle plain code blocks
            json_start = json_str.find('```') + 3
            json_end = json_str.rfind('```')
            json_str = json_str[json_start:json_end].strip()
        
        # Find JSON object bounds if mixed with text
        if not json_str.startswith('{'):
            start_pos = json_str.find('{')
            if start_pos != -1:
                json_str = json_str[start_pos:]
                
        if not json_str.endswith('}'):
            end_pos = json_str.rfind('}')
            if end_pos != -1:
                json_str = json_str[:end_pos+1]
        
        try:
            return json.loads(json_str)
        except json.JSONDecodeError as e:
            raise Exception(f"Failed to parse JSON response: {e}\nResponse content: {content[:500]}...")

    def validate_output(self, data: Dict[str, Any]) -> tuple[bool, List[str]]:
        """Validate extracted data against IndustroML schema"""
        errors = []
        
        # Check required top-level fields
        required_fields = ["meta", "containers", "assets", "interfaces", "connections"]
        for field in required_fields:
            if field not in data:
                errors.append(f"Missing required field: {field}")
        
        # Validate meta section
        if "meta" in data:
            meta = data["meta"]
            if meta.get("format") != "IndustroML":
                errors.append("meta.format must be 'IndustroML'")
            if not meta.get("version"):
                errors.append("meta.version is required")
        
        # Validate asset kinds against schema
        valid_kinds = self.schema["$defs"]["assetKind"]["enum"]
        for asset in data.get("assets", []):
            if "kind" in asset and asset["kind"] not in valid_kinds:
                errors.append(f"Invalid asset kind: {asset['kind']} for asset {asset.get('id')}")
        
        # Validate domains
        valid_domains = self.schema["$defs"]["domain"]["enum"] 
        for asset in data.get("assets", []):
            if "domain" in asset and asset["domain"] not in valid_domains:
                errors.append(f"Invalid domain: {asset['domain']} for asset {asset.get('id')}")
        
        # Validate mediums
        valid_mediums = self.schema["$defs"]["medium"]["enum"]
        for interface in data.get("interfaces", []):
            if "medium" in interface and interface["medium"] not in valid_mediums:
                errors.append(f"Invalid medium: {interface['medium']} for interface {interface.get('id')}")
        
        return len(errors) == 0, errors

    def process_file(self, input_path: str, output_path: Optional[str] = None, diagram_type: str = "industrial") -> Dict[str, Any]:
        """Process a single diagram file"""
        print(f"Processing {input_path}...")
        
        # Extract data using GPT-4 Vision
        extracted_data = self.extract_from_image(input_path, diagram_type)
        
        # Add extraction metadata
        if "meta" not in extracted_data:
            extracted_data["meta"] = {}
        extracted_data["meta"]["source_file"] = os.path.basename(input_path)
        extracted_data["meta"]["extraction_timestamp"] = str(Path(input_path).stat().st_mtime)
        
        # Validate against schema
        is_valid, validation_errors = self.validate_output(extracted_data)
        
        if validation_errors:
            print("⚠️  Validation warnings:")
            for error in validation_errors:
                print(f"   - {error}")
            
            # Add validation notes to meta
            extracted_data["meta"]["validation_warnings"] = validation_errors
        
        if is_valid:
            print("✅ Extraction completed successfully")
        else:
            print("❌ Extraction has validation errors - manual review required")
        
        # Save output
        if output_path:
            with open(output_path, 'w') as f:
                json.dump(extracted_data, f, indent=2)
            print(f"Output saved to: {output_path}")
        
        return extracted_data

def main():
    parser = argparse.ArgumentParser(description="Extract IndustroML data from industrial diagrams")
    parser.add_argument("input", nargs="?", help="Path to diagram image file")
    parser.add_argument("-o", "--output", help="Output JSON file path")
    parser.add_argument("-t", "--type", default="industrial", 
                       choices=["electrical", "mechanical", "network", "pid", "industrial"],
                       help="Diagram type for specialized extraction")
    parser.add_argument("--validate-only", help="Validate existing JSON file against schema")
    
    args = parser.parse_args()
    
    try:
        if args.validate_only:
            extractor = IndustroMLExtractor(require_api_key=False)
        else:
            extractor = IndustroMLExtractor(require_api_key=True)
        
        if args.validate_only:
            # Validate existing file
            with open(args.validate_only) as f:
                data = json.load(f)
            is_valid, errors = extractor.validate_output(data)
            
            if is_valid:
                print("✅ File is valid IndustroML")
            else:
                print("❌ Validation errors:")
                for error in errors:
                    print(f"   - {error}")
            return
        
        if not args.input:
            parser.error("input is required when not using --validate-only")
        
        # Extract from image
        result = extractor.process_file(args.input, args.output, args.type)
        
        # Print summary
        print(f"\nExtraction Summary:")
        print(f"  Assets: {len(result.get('assets', []))}")
        print(f"  Containers: {len(result.get('containers', []))}")
        print(f"  Interfaces: {len(result.get('interfaces', []))}")
        print(f"  Connections: {len(result.get('connections', []))}")
        
        if "uncertain_items" in result.get("meta", {}):
            uncertain = result["meta"]["uncertain_items"]
            if uncertain:
                print(f"  ⚠️  Uncertain items requiring review: {len(uncertain)}")
                for item in uncertain:
                    print(f"     - {item}")
        
    except Exception as e:
        print(f"Error: {e}")
        sys.exit(1)

if __name__ == "__main__":
    main()