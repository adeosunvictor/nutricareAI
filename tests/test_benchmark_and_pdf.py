"""Portfolio showcase: reproducible retrieval and real supplied PDF regression."""
from pathlib import Path
import io
from fastapi.testclient import TestClient
from pypdf import PdfReader
from backend.main import app
from backend.benchmark import run_benchmark
from backend.ingestion import parse_file
from backend.report import build_pdf
from backend.security import safe_filename

SOURCE = Path('/mnt/data/Kemi_Adebayo_Patient_Nutrition_Record(1).pdf')


def test_benchmark_is_computed_and_transparent():
    response = TestClient(app).get('/api/evaluation')
    assert response.status_code == 200
    result = response.json()
    assert result == run_benchmark()
    assert result['cases'] == len(result['results'])
    assert result['answer_relevance'] is None
    assert result['groundedness'] is None
    assert 0 <= result['recall_at_k'] <= 1


def test_patient_record_roundtrip_when_supplied():
    if not SOURCE.exists():
        import pytest
        pytest.skip('User-supplied PDF is only available in the project review workspace')
    patient = parse_file(SOURCE.read_bytes(), SOURCE.name, 'single')[0]
    assert patient['name'] == 'Kemi Adebayo'
    assert safe_filename(patient['name'], patient['id']) == 'Kemi_Adebayo_Recommendation.pdf'
    pdf = build_pdf(patient, 'WELCOME\nReview dietary patterns with the nutritionist.\nMONITORING AND FOLLOW-UP\nRecord meals for review.', 'Reviewer')
    text = '\n'.join(page.extract_text() or '' for page in PdfReader(io.BytesIO(pdf)).pages)
    assert 'Kemi Adebayo' in text
    assert 'Patient name not found' not in text
