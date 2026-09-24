"""Reproducible, small, manually labelled retrieval fixture.

This measures the local lexical retriever, not the live LLM or clinical safety.
Fixture passages are fictional, fixed, and intentionally short. Results are
recomputed on request so that displayed measurements are not invented.
"""
from __future__ import annotations
from .evaluation import evaluate_golden_case
from .retrieval import lexical_retrieve

PASSAGES = [
    {'id': 'allergy', 'text': 'Patient reports hives and lip swelling after eating prawns. Shellfish allergy assessment is pending.'},
    {'id': 'medication', 'text': 'Current medication is metformin XR 1000 mg daily. Historical gliclazide was discontinued.'},
    {'id': 'laboratory', 'text': 'HbA1c increased from 7.5 percent in March to 8.1 percent in September.'},
    {'id': 'beverages', 'text': 'The patient drinks regular soda with lunch and adds sugar to tea twice daily.'},
    {'id': 'food', 'text': 'Meals usually include rice beans yam and vegetables. Patient requests practical family meal changes.'},
    {'id': 'activity', 'text': 'The patient sits at work and walks for approximately 15 minutes on weekdays.'},
]
CASES = [
    {'question': 'What shellfish allergy reaction was reported after prawns?', 'relevant': {'allergy'}},
    {'question': 'What happened to HbA1c between March and September?', 'relevant': {'laboratory'}},
    {'question': 'What current and discontinued diabetes medications are recorded?', 'relevant': {'medication'}},
    {'question': 'What sugar sweetened beverages does the patient drink?', 'relevant': {'beverages'}},
    {'question': 'Which usual meals and family food choices were recorded?', 'relevant': {'food'}},
]


def run_benchmark(k: int = 3) -> dict:
    rows = []
    for item in CASES:
        ranked = lexical_retrieve(item['question'], PASSAGES, k=k)
        ids = [passage['id'] for passage in ranked]
        metrics = evaluate_golden_case(retrieved_ids=ids, relevant_ids=item['relevant'],
                                        cited_ids=[], supported_ids=set(), k=k)
        rows.append({'query': item['question'], 'expected_source_ids': sorted(item['relevant']),
                     'retrieved_source_ids': ids, 'precision_at_k': metrics['precision_at_k'],
                     'recall_at_k': metrics['recall_at_k'], 'mrr': metrics['mrr']})
    return {'scope': 'Fixed fictional retrieval fixture, NOT an AI answer or clinical accuracy benchmark',
            'retriever': 'lexical', 'cases': len(rows), 'k': k,
            'precision_at_k': round(sum(r['precision_at_k'] for r in rows) / len(rows), 3),
            'recall_at_k': round(sum(r['recall_at_k'] for r in rows) / len(rows), 3),
            'mrr': round(sum(r['mrr'] for r in rows) / len(rows), 3),
            'results': rows,
            'answer_relevance': None, 'groundedness': None,
            'note': 'Answer relevance, citation support, and clinical safety require separately labelled real model outputs and qualified human review.'}
