"""Synthetic ADIME draft contract, patient-context filtering and API regression."""
from __future__ import annotations

import asyncio
import json
from pathlib import Path

import pytest
from fastapi import HTTPException
from fastapi.testclient import TestClient

from backend import rag, retrieval
from backend.main import app
from backend.ingestion import parse_file
from backend.extraction import summarize

ROOT = Path(__file__).resolve().parents[1]


def sample_patient():
    data = (ROOT / 'public' / 'demo-patients.csv').read_bytes()
    patient = parse_file(data, 'demo-patients.csv', 'group')[0]
    patient['evidence'] = summarize(patient)
    return patient


def sample_draft(ids):
    return {
        'assessment': {
            'summary': 'The patient reports a variable eating pattern; verify the record.',
            'key_findings': [{'text': 'A documented meal pattern requires review.', 'source_ids': ids}],
            'missing_information': ['Confirm food ingredients and serving sizes.'],
        },
        'nutrition_diagnosis': {'problem': '', 'etiology': '', 'signs_symptoms': '', 'pes_statement': ''},
        'intervention': {
            'objectives': ['Discuss a practical meal routine.'],
            'meal_options': [],
            'education': ['Discuss meal composition.'],
            'nutrition_prescription': 'Pending clinician assessment',
        },
        'monitoring': {'indicators': ['Review follow-up dietary history.'],
                       'follow_up': 'Agree on a follow-up date with the clinician.'},
        'review': {'safety_flags': ['Confirm allergies prior to suggesting meals.'],
                   'questions': ['Is a complete dietary record available?']},
    }


def test_adime_schema_and_patient_source_ids():
    p = sample_patient()
    evidence = retrieval.assessment_evidence(p)
    result = rag.validate_care_plan(sample_draft([evidence[0]['id']]), evidence)
    assert result['framework'] == 'ADIME draft'
    assert result['nutrition_diagnosis']['status'] == 'needs_clinician_assessment'
    assert result['intervention']['nutrition_prescription'] == 'Pending clinician assessment'
    assert result['guideline_status'].startswith('No curated')
    assert result['assessment']['key_findings'][0]['source_ids'] == [evidence[0]['id']]


def test_unsupported_citation_and_invented_prescription_rejected():
    p = sample_patient()
    evidence = retrieval.assessment_evidence(p)
    bad = sample_draft(['NOT_A_SOURCE'])
    with pytest.raises(HTTPException, match='source_ids'):
        rag.validate_care_plan(bad, evidence)
    bad = sample_draft([evidence[0]['id']])
    bad['intervention']['nutrition_prescription'] = '1500 kcal daily'
    with pytest.raises(HTTPException, match='nutrition_prescription'):
        rag.validate_care_plan(bad, evidence)


def test_financial_layer_excluded_from_model_context_and_plan():
    p = sample_patient()
    p['fields']['budget'] = 'NGN 18,000 weekly'
    p['fields']['lifestyle'] = 'Desk-based work; household budget NGN 18,000; batch cooking on weekends'
    p['chunks'][0]['text'] += '\nHousehold budget NGN 18,000. Work schedule 8am to 5pm.'
    evidence = retrieval.assessment_evidence(p)
    ctx = rag.context_for(p, evidence)
    assert not rag.FINANCIAL.search(ctx)
    assert 'budget' not in json.loads(ctx)['PATIENT_DATA']['fields']
    bad = sample_draft([evidence[0]['id']])
    bad['intervention']['objectives'] = ['Provide cheap meal options.']
    with pytest.raises(HTTPException, match='objectives'):
        rag.validate_care_plan(bad, evidence)


def patient_part_one(source_id):
    return {'opening': 'Discuss the recorded eating pattern and current referral with the nutritionist.',
            'result_explanations': [{'title': 'Diet history', 'explanation': 'Recorded meal timing needs review.', 'source_ids': [source_id]}],
            'action_steps': [
                {'title': 'Review drinks', 'what': 'Review drinks.', 'why': 'Documented beverage pattern.',
                 'how': 'Discuss beverage choices with the nutritionist.', 'source_ids': [source_id]},
                {'title': 'Review meals', 'what': 'Review meal timing.', 'why': 'Documented meal pattern.',
                 'how': 'Record the usual meal timing.', 'source_ids': [source_id]}]}


def patient_part_two(source_id):
    return {'meal_options': [], 'precautions': [
        {'title': 'Confirm allergies', 'details': 'Confirm reported allergies before making changes.',
         'source_ids': [source_id]}],
        'monitoring': ['Review usual eating pattern.'],
        'pending_review': ['Confirm individual nutrition needs.']}


def test_three_inference_calls_return_validated_draft(monkeypatch):
    p = sample_patient()
    evidence = retrieval.assessment_evidence(p)
    calls = []
    async def fake_complete(messages, max_tokens=0):
        calls.append((messages, max_tokens))
        if len(calls) == 1:
            return sample_draft([evidence[0]['id']]), {'completion_tokens': 100}
        if len(calls) == 2:
            return patient_part_one(evidence[0]['id']), {'completion_tokens': 80}
        return patient_part_two(evidence[0]['id']), {'completion_tokens': 70}
    monkeypatch.setattr(rag, 'complete', fake_complete)
    result, usage = asyncio.run(rag.draft_assessment(p, evidence, summarize(p)['missing']))
    assert len(calls) == 3
    assert 'PATIENT_DATA' in calls[0][0][0]['content']
    assert result['status'] == 'pending_clinician_review'
    assert result['patient_plan']['opening']
    assert usage['completion_tokens'] == 250


def test_assessment_api_still_uses_existing_contract(monkeypatch):
    p = sample_patient()
    evidence = retrieval.assessment_evidence(p)
    calls = []
    async def fake_complete(messages, max_tokens=0):
        calls.append(messages)
        if len(calls) == 1:
            return sample_draft([evidence[0]['id']]), {'completion_tokens': 100}
        if len(calls) == 2:
            return patient_part_one(evidence[0]['id']), {}
        return patient_part_two(evidence[0]['id']), {}
    monkeypatch.setattr(rag, 'complete', fake_complete)
    monkeypatch.setattr(rag, 'configured', lambda: True)
    response = TestClient(app).post('/api/assess', json={'patient': p, 'demo_confirmed': True})
    assert response.status_code == 200, response.text
    result = response.json()
    assert result['draft']['framework'] == 'ADIME draft'
    assert result['draft']['patient_plan']['opening']
    assert result['status'] == 'pending_clinician_review'


def test_frontend_has_linked_adime_display_and_no_budget_feature():
    js = (ROOT / 'public' / 'app.js').read_text(encoding='utf8')
    assert "'A. NUTRITION ASSESSMENT'" in js
    assert "'D. PROPOSED NUTRITION DIAGNOSIS'" in js
    assert "'M/E. MONITORING AND EVALUATION'" in js
    assert 'appendSourceLinks' in js
    assert "'Food budget'" not in js
    assert "['budget', 'Budget']" not in js


def test_rejects_explicit_food_allergen_and_wrong_food_classification(monkeypatch):
    p = sample_patient()
    p['fields']['allergies'] = 'Peanut allergy reported by patient.'
    evidence = retrieval.assessment_evidence(p)
    def stub_clinical(ids):
        return sample_draft(ids)

    async def fake_allergen(messages, max_tokens=0):
        content = messages[0]['content']
        if 'CLINICAL_DRAFT:' not in content:
            return stub_clinical([evidence[0]['id']]), {}
        if 'PRACTICAL NUTRITION STEPS' in content.split('\nTASK: ')[-1]:
            return patient_part_one(evidence[0]['id']), {}
        part = patient_part_two(evidence[0]['id'])
        part['meal_options'] = [{'title': 'Lunch', 'details': 'Peanut butter sandwich',
                                 'source_ids': [evidence[0]['id']]}]
        return part, {}
    monkeypatch.setattr(rag, 'complete', fake_allergen)
    with pytest.raises(HTTPException, match='food allergy'):
        asyncio.run(rag.draft_assessment(p, evidence, []))

    async def fake_food(messages, max_tokens=0):
        content = messages[0]['content']
        if 'CLINICAL_DRAFT:' not in content:
            return stub_clinical([evidence[0]['id']]), {}
        if 'PRACTICAL NUTRITION STEPS' in content.split('\nTASK: ')[-1]:
            return patient_part_one(evidence[0]['id']), {}
        part = patient_part_two(evidence[0]['id'])
        part['meal_options'] = [{'title': 'Lunch', 'details': 'Whole grain yam and fish',
                                 'source_ids': [evidence[0]['id']]}]
        return part, {}
    monkeypatch.setattr(rag, 'complete', fake_food)
    with pytest.raises(HTTPException, match='incorrect food classification'):
        asyncio.run(rag.draft_assessment(p, evidence, []))
