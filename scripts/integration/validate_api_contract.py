
import sys
import os
import re
import importlib
import inspect
from pathlib import Path
from typing import List, Dict, Any, Type
from pydantic import BaseModel
from datetime import datetime

# Add backend to sys.path
BACKEND_DIR = Path(__file__).resolve().parent.parent.parent / "backend"
sys.path.append(str(BACKEND_DIR))

try:
    from app.schemas.case import Case
    from app.schemas.document import Document
    from app.schemas.user import User
    from app.schemas.tag import Tag
    from app.schemas.summary import Summary
    from app.schemas.token import Token
    # Client schema seems missing, we will check generic existence
except ImportError as e:
    print(f"Error importing schemas: {e}")
    sys.exit(1)

FRONTEND_TYPES_FILE = Path(__file__).resolve().parent.parent.parent / "frontend/src/types.ts"

def parse_typescript_interfaces(file_path: Path) -> Dict[str, Dict[str, str]]:
    """
    Parses TypeScript interfaces to extract field names and types.
    Returns a dictionary: {InterfaceName: {field_name: type_string}}
    """
    with open(file_path, 'r', encoding='utf-8') as f:
        content = f.read()

    interfaces = {}
    # Regex to find interface blocks
    # export interface Name { ... }
    interface_pattern = re.compile(r'export interface (\w+) \{(.*?)\}', re.DOTALL)
    
    for match in interface_pattern.finditer(content):
        name = match.group(1)
        body = match.group(2)
        fields = {}
        
        # Parse fields: name: type; or name?: type;
        field_pattern = re.compile(r'\s*(\w+)(\??)\s*:\s*([^;]+);')
        for field_match in field_pattern.finditer(body):
            field_name = field_match.group(1)
            is_optional = field_match.group(2) == '?'
            field_type = field_match.group(3).strip()
            
            # clean type
            fields[field_name] = {
                "type": field_type,
                "optional": is_optional
            }
        
        interfaces[name] = fields
        
    return interfaces

def get_pydantic_fields(model: Type[BaseModel]) -> Dict[str, Dict[str, Any]]:
    """
    Extracts fields from a Pydantic model.
    """
    fields = {}
    for name, field in model.model_fields.items():
        type_name = str(field.annotation)
        is_optional = False
        # Simplified optional check (not perfect for all typing.Optional cases)
        if "Optional" in type_name or "NoneType" in type_name:
            is_optional = True
            
        fields[name] = {
            "type": type_name,
            "optional": is_optional
        }
    return fields

def compare_models(ts_interfaces: Dict[str, Any], py_models: Dict[str, Type[BaseModel]]):
    report = []
    
    for name, py_model in py_models.items():
        if name not in ts_interfaces:
            report.append(f"[WARNING] Pydantic model '{name}' has no corresponding TypeScript interface.")
            continue
            
        ts_fields = ts_interfaces[name]
        py_fields = get_pydantic_fields(py_model)
        
        report.append(f"--- Checking {name} ---")
        
        # Check for missing fields in TS
        for py_field, py_info in py_fields.items():
            if py_field not in ts_fields:
                 # Check if it's excluded from JSON export (not easily checking config here, assuming standard)
                 report.append(f"[ERROR] Logic mismatch: Field '{py_field}' exists in Backend but NOT in Frontend.")
            else:
                # Type check (very basic mapping)
                ts_info = ts_fields[py_field]
                # Compare optionality
                # Note: Pydantic Optional doesn't always map to TS optional '?', but often 'type | null'.
                # We interpret TS '?' as optional.
                
                # if py_info['optional'] and not ts_info['optional']:
                #     report.append(f"[WARN] Field '{py_field}' is Optional in Backend but Required in Frontend.")
                pass

        # Check for extra fields in TS
        for ts_field in ts_fields:
            if ts_field not in py_fields:
                report.append(f"[ERROR] Logic mismatch: Field '{ts_field}' exists in Frontend but NOT in Backend.")

    return "\n".join(report)

def main():
    print("Parsing TypeScript interfaces...")
    ts_interfaces = parse_typescript_interfaces(FRONTEND_TYPES_FILE)
    print(f"Found {len(ts_interfaces)} interfaces: {list(ts_interfaces.keys())}")

    models_to_check = {
        "User": User,
        "Case": Case,
        "Document": Document,
        "Tag": Tag,
        "Summary": Summary,
        "Token": Token
    }
    
    print("Comparing models...")
    report = compare_models(ts_interfaces, models_to_check)
    
    print("\n=== VALIDATION REPORT ===\n")
    print(report)
    
    report_file = Path("docs/API_CONTRACT.md")
    report_file.parent.mkdir(exist_ok=True)
    with open(report_file, "w") as f:
        f.write("# API Contract Validation Report\n\n")
        f.write(report)
    print(f"\nReport saved to {report_file}")

if __name__ == "__main__":
    main()
