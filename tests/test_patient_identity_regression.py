"""Regression for labelled identity tables that precede numbered PDF sections."""
from pathlib import Path
from backend.ingestion import parse_file
from backend.security import safe_filename
from backend.report import build_pdf


def test_identity_precedes_numbered_section():
    pages = [('PATIENT NUTRITION ASSESSMENT RECORD\nPatient name\nKemi Adebayo\nPatient reference\nOPD/NUT/26481\n01 | Patient identification and reason for referral\nClinical history follows.', 'page 1')]
    from backend.extraction import extract_document_fields
    result = extract_document_fields(pages)
    assert result['name'] == 'Kemi Adebayo'
    assert result['patient_id'] == 'OPD/NUT/26481'


def test_pdf_filename_uses_patient_name():
    assert safe_filename('Kemi Adebayo', 'OPD/NUT/26481') == 'Kemi_Adebayo_Recommendation.pdf'
