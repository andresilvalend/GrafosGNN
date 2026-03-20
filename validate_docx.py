#!/usr/bin/env python3
"""
Validation script for DOCX files.
Checks: file existence, valid ZIP structure, contains document.xml, readable content.
"""

import sys
import zipfile
import os
from xml.etree import ElementTree as ET

def validate_docx(filepath):
    """Validate a .docx file"""
    print(f"Validating DOCX: {filepath}")

    # Check file exists
    if not os.path.exists(filepath):
        print(f"ERROR: File does not exist: {filepath}")
        return False

    print(f"✓ File exists (size: {os.path.getsize(filepath)} bytes)")

    # Check if it's a valid ZIP
    try:
        with zipfile.ZipFile(filepath, 'r') as zf:
            print(f"✓ Valid ZIP archive with {len(zf.namelist())} files")

            # Check for document.xml
            if 'word/document.xml' not in zf.namelist():
                print("ERROR: Missing word/document.xml in archive")
                return False
            print("✓ Contains word/document.xml")

            # Try to parse XML
            try:
                xml_content = zf.read('word/document.xml')
                root = ET.fromstring(xml_content)
                print(f"✓ Valid XML structure (root tag: {root.tag})")

                # Count paragraphs
                ns = {'w': 'http://schemas.openxmlformats.org/wordprocessingml/2006/main'}
                paragraphs = root.findall('.//w:p', ns)
                print(f"✓ Found {len(paragraphs)} paragraphs")

                # Try to extract text
                text_elements = root.findall('.//w:t', ns)
                print(f"✓ Found {len(text_elements)} text elements")

                # Sample text
                sample_texts = [t.text for t in text_elements[:5] if t.text]
                if sample_texts:
                    print(f"✓ Sample text: {' '.join(sample_texts)[:80]}...")

                return True
            except ET.ParseError as e:
                print(f"ERROR: Invalid XML: {e}")
                return False

    except zipfile.BadZipFile:
        print("ERROR: Not a valid ZIP file")
        return False
    except Exception as e:
        print(f"ERROR: {e}")
        return False

if __name__ == '__main__':
    filepath = '/sessions/friendly-modest-rubin/mnt/GrafosGNN/BTCS_paper_v2.docx'
    success = validate_docx(filepath)
    sys.exit(0 if success else 1)
