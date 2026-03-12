#!/usr/bin/env python
# Test printer - send sample bracket PDF to a printer

import sys
import os

sys.path.insert(0, os.path.dirname(__file__))

def test_print_bracket():
    """Test printing a bracket PDF to an actual printer."""
    try:
        from backend.services.printer_service import PrinterService
        from backend.services.bracket_pdf_generator import BracketPDFGenerator
        import time
        
        print("=== Testing Bracket Printing ===\n")
        
        # Generate test PDF
        pdf_gen = BracketPDFGenerator()
        os.makedirs("temp", exist_ok=True)
        test_pdf = "temp/test_print_bracket.pdf"
        
        print("1. Generating sample bracket PDF...")
        pdf_path = pdf_gen._create_sample_ko_pdf_realistic(test_pdf)
        print(f"   ✓ PDF created: {pdf_path} ({os.path.getsize(pdf_path)} bytes)\n")
        
        # Get available printers
        print("2. Detecting available printers...")
        printers = PrinterService.get_available_printers()
        print(f"   ✓ Found {len(printers)} printer(s):")
        for i, p in enumerate(printers, 1):
            print(f"     {i}. {p}")
        print()
        
        # Get default printer
        default = PrinterService.get_default_printer()
        if default:
            print(f"3. Default printer: {default}\n")
        else:
            print("3. No default printer configured\n")
        
        # Test printing to a PDF printer
        if printers:
            # Try Microsoft Print to PDF first
            target_printer = None
            for p in printers:
                if "PDF" in p or "pdf" in p:
                    target_printer = p
                    break
            
            if not target_printer:
                target_printer = printers[0]
            
            print(f"4. Testing print to: {target_printer}")
            print(f"   Sending: {pdf_path}\n")
            
            success = PrinterService.print_file(pdf_path, target_printer, copies=1)
            
            if success:
                print(f"   ✓ Print command succeeded!")
                print(f"   ✓ Check your printer '{target_printer}'")
            else:
                print(f"   ✗ Print command failed")
                print(f"   (This may be expected if printer not available or offline)")
        
        print("\n✓✓✓ Print Test Complete! ✓✓✓")
        return True

    except Exception as e:
        print(f"✗ Error: {e}")
        import traceback
        traceback.print_exc()
        return False

if __name__ == '__main__':
    success = test_print_bracket()
    sys.exit(0 if success else 1)
