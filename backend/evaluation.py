"""Private counters and offline, human-labelled evaluation helpers. Not clinical certification."""
from __future__ import annotations
import statistics
from collections import defaultdict, deque
from time import perf_counter

_TIMINGS: dict[str, deque] = defaultdict(lambda: deque(maxlen=250))
_COUNTS: dict[str, int] = defaultdict(int)


def record(operation: str, elapsed_ms: float, success: bool, usage: dict | None = None) -> None:
    _TIMINGS[operation].append(round(elapsed_ms, 2))
    _COUNTS[f"{operation}_{'success' if success else 'failure'}"] += 1
    if usage:
        _COUNTS['input_tokens'] += int(usage.get('prompt_tokens', 0) or 0)
        _COUNTS['output_tokens'] += int(usage.get('completion_tokens', 0) or 0)


def dashboard() -> dict:
    """No raw records, names, prompts or model outputs are logged."""
    return {'requests': dict(_COUNTS), 'operations': {
        key: {'samples': len(times), 'p50_ms': round(statistics.median(times), 1),
              'p95_ms': round(sorted(times)[min(len(times)-1, int(.95*(len(times)-1)))], 1)}
        for key, times in _TIMINGS.items() if times}}


def precision_recall_at_k(retrieved_ids: list[str], relevant_ids: set[str], k: int = 5) -> dict:
    top = retrieved_ids[:k]
    hits = sum(item in relevant_ids for item in top)
    return {'precision_at_k': hits / len(top) if top else 0.0,
            'recall_at_k': hits / len(relevant_ids) if relevant_ids else 1.0, 'k': k}


def reciprocal_rank(retrieved_ids: list[str], relevant_ids: set[str]) -> float:
    return next((1 / i for i, item in enumerate(retrieved_ids, 1) if item in relevant_ids), 0.0)


def citation_accuracy(cited_ids: list[str], supported_ids: set[str]) -> float:
    """Human-labelled semantic support, not merely existence of source identifiers."""
    return sum(item in supported_ids for item in cited_ids) / len(cited_ids) if cited_ids else 0.0


def patient_leakage(retrieved: list[dict], authorized_ids: set[str]) -> bool:
    return any(item.get('patient_id') not in authorized_ids for item in retrieved)


def evaluate_golden_case(*, retrieved_ids: list[str], relevant_ids: set[str],
                         cited_ids: list[str], supported_ids: set[str],
                         answer_relevant: bool | None = None,
                         claim_grounded_labels: list[bool] | None = None,
                         k: int = 5) -> dict:
    """Human-annotated synthetic case; missing labels are unknown, not passing."""
    metrics = precision_recall_at_k(retrieved_ids, relevant_ids, k)
    metrics.update({'mrr': reciprocal_rank(retrieved_ids, relevant_ids),
        'context_relevance': metrics['precision_at_k'],
        'citation_accuracy': citation_accuracy(cited_ids, supported_ids),
        'answer_relevance': float(answer_relevant) if answer_relevant is not None else None,
        'groundedness': sum(claim_grounded_labels) / len(claim_grounded_labels)
        if claim_grounded_labels else None})
    return metrics


def evaluate_care_plan(*, required_topics: set[str], documented_topics: set[str],
                       claim_support_labels: list[bool] | None = None,
                       recommendation_safety_labels: list[bool] | None = None,
                       actionable_instruction_labels: list[bool] | None = None,
                       unchanged_sections_preserved: bool | None = None) -> dict:
    """Evaluate against evaluator-supplied case annotations; does not self-judge."""
    def rate(labels):
        return sum(labels) / len(labels) if labels is not None and labels else None
    return {'evidence_coverage': len(required_topics & documented_topics) / len(required_topics)
            if required_topics else None,
            'claim_groundedness': rate(claim_support_labels),
            'recommendation_safety_review': rate(recommendation_safety_labels),
            'instruction_actionability': rate(actionable_instruction_labels),
            'targeted_edit_integrity': float(unchanged_sections_preserved)
            if unchanged_sections_preserved is not None else None}


def elapsed(start: float) -> float:
    return (perf_counter() - start) * 1000
