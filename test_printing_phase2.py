#!/usr/bin/env python
# Test Phase 2 - Realistic bracket PDF generation

import sys
import os

sys.path.insert(0, os.path.dirname(__file__))

def test_phase2():
    """Test Phase 2: Realistic bracket PDF generation."""
    try:
        from backend.services.bracket_pdf_generator import BracketPDFGenerator
        from backend.services.printing_service import PrintingService
        print("✓ Services imported successfully")
        
        # Create PDFs with realistic brackets
        pdf_gen = BracketPDFGenerator()
        os.makedirs("temp", exist_ok=True)
        
        # Test KO bracket
        ko_pdf = "temp/phase2_ko_bracket.pdf"
        ko_path = pdf_gen._create_sample_ko_pdf_realistic(ko_pdf)
        if os.path.exists(ko_path):
            sz = os.path.getsize(ko_path)
            print(f"✓ Realistic KO bracket PDF: {ko_path} ({sz} bytes)")
        else:
            print("✗ KO PDF not created")
            return False
        
        # Test pool bracket
        pool_pdf = "temp/phase2_pool_bracket.pdf"
        pool_path = pdf_gen._create_sample_pool_pdf_realistic(pool_pdf)
        if os.path.exists(pool_path):
            sz = os.path.getsize(pool_path)
            print(f"✓ Realistic pool bracket PDF: {pool_path} ({sz} bytes)")
        else:
            print("✗ Pool PDF not created")
            return False
        
        # Test printing service retrieves printers
        printing_svc = PrintingService()
        printers = printing_svc.get_available_printers()
        print(f"✓ Printer service found {len(printers)} printer(s)")
        if printers:
            for p in printers:
                print(f"  - {p}")
        
        print("\n✓✓✓ Phase 2 Complete - Realistic PDFs generated! ✓✓✓")
        return True

    except Exception as e:
        print(f"✗ Error: {e}")
        import traceback
        traceback.print_exc()
        return False

if __name__ == '__main__':
    success = test_phase2()
    sys.exit(0 if success else 1)
