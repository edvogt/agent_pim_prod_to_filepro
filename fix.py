#!/usr/bin/env python3
import re
import sys
from pathlib import Path

def fix_models_py(file_path):
    with open(file_path, 'r', encoding='utf-8') as f:
        content = f.read()
    original = content
    
    # Add Optional to imports
    if 'from typing import' in content:
        typing_match = re.search(r'from typing import([^\n]*)', content)
        if typing_match and 'Optional' not in typing_match.group(1):
            content = re.sub(r'(from typing import[^\n]*)', r'\1, Optional', content, count=1)
    
    # Fix field types
    content = re.sub(r'(\s*)description_medium:\s*str\s*=\s*Field\(', r'\1description_medium: Optional[str] = Field(', content)
    content = re.sub(r'(\s*)specifications_wysiwyg:\s*str\s*=\s*Field\(', r'\1specifications_wysiwyg: Optional[str] = Field(', content)
    content = re.sub(r'(\s*)whats_in_box:\s*str\s*=\s*Field\(', r'\1whats_in_box: Optional[str] = Field(', content)
    
    if content != original:
        with open(file_path, 'w', encoding='utf-8') as f:
            f.write(content)
        print(f"✅ Fixed {file_path}")
        return True
    print(f"ℹ️  No changes in {file_path}")
    return False

def fix_pimcore_client_py(file_path):
    with open(file_path, 'r', encoding='utf-8') as f:
        lines = f.readlines()
    
    content = ''.join(lines)
    if 'node_data.get("Description_Medium") is None' in content:
        print(f"ℹ️  {file_path} already fixed")
        return False
    
    new_lines = []
    inserted = False
    for line in lines:
        new_lines.append(line)
        if not inserted and ('node_data = item["node"].copy()' in line or "node_data = item['node'].copy()" in line):
            new_lines.append('        # Handle None values for optional string fields - convert to empty strings\n')
            new_lines.append('        if node_data.get("Description_Medium") is None:\n')
            new_lines.append('            node_data["Description_Medium"] = ""\n')
            new_lines.append('        if node_data.get("Specifications_WYSIWYG") is None:\n')
            new_lines.append('            node_data["Specifications_WYSIWYG"] = ""\n')
            new_lines.append('        if node_data.get("WhatsInBox") is None:\n')
            new_lines.append('            node_data["WhatsInBox"] = ""\n')
            inserted = True
    
    if not inserted:
        print(f"⚠️  Could not find insertion point")
        return False
    
    with open(file_path, 'w', encoding='utf-8') as f:
        f.writelines(new_lines)
    print(f"✅ Fixed {file_path}")
    return True

if __name__ == '__main__':
    base = Path(sys.argv[1]) if len(sys.argv) > 1 else Path('/var/www/html/agent_pimcore_push_to_shopify')
    fix_models_py(base / 'models.py')
    fix_pimcore_client_py(base / 'pimcore_client.py')
    print("✅ Done!")
