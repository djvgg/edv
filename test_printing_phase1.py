#!/usr/bin/env python
# Test script for Phase 1 printing services

import sys
import os

sys.path.insert(0, os.path.dirname(__file__))

def test_printing_services():
    """Test all Phase 1 services."""
    try:
        from backend.services.printer_service import PrinterService
        from backend.services.bracket_pdf_generator import BracketPDFGenerator
        from backend.services.printing_service import PrintingService
        print("✓ All services imported successfully")
        
        # Test instantiation
        printer_svc = PrinterService()
        print("✓ PrinterService instantiated")
        
        pdf_gen = BracketPDFGenerator()
        print("✓ BracketPDFGenerator instantiated")
        
        printing_svc = PrintingService()
        print("✓ PrintingService instantiated")
        
        # Test printer detection
        printers = PrinterService.get_available_printers()
        print(f"✓ Found {len(printers)} printer(s): {printers}")
        
        # Test sample PDF generation
        temp_pdf = "temp/test_bracket.pdf"
        os.makedirs("temp", exist_ok=True)
        pdf_path = pdf_gen._create_sample_ko_pdf(temp_pdf)
        if os.path.exists(pdf_path):
            sz = os.path.getsize(pdf_path)
            print(f"✓ Sample PDF generated: {pdf_path} ({sz} bytes)")
        else:
            print("✗ Sample PDF not created")
            return False
        
        # Test pool PDF
        temp_pdf2 = "temp/test_pool.pdf"
        pdf_path2 = pdf_gen._create_sample_pool_pdf(temp_pdf2)
        if os.path.exists(pdf_path2):
            sz = os.path.getsize(pdf_path2)
            print(f"✓ Sample pool PDF generated: {pdf_path2} ({sz} bytes)")
        else:
            print("✗ Sample pool PDF not created")
            return False
        
        print("\n✓✓✓ All Phase 1 services working correctly! ✓✓✓")
        return True

    except Exception as e:
        print(f"✗ Error: {e}")
        import traceback
        traceback.print_exc()
        return False

if __name__ == '__main__':
    success = test_printing_services()
    sys.exit(0 if success else 1)
