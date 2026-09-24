
"""Readable PDF export of a reviewed *synthetic* patient-language report.

This interface does not authenticate reviewers or authorize clinical release.
"""
from __future__ import annotations

import io
import re
from datetime import datetime, timezone
from html import escape
from reportlab.lib import colors
from reportlab.lib.pagesizes import A4
from reportlab.lib.styles import ParagraphStyle, getSampleStyleSheet
from reportlab.lib.units import mm
from reportlab.platypus import HRFlowable, Paragraph, SimpleDocTemplate, Spacer


HEADINGS = {
    'WELCOME', 'UNDERSTANDING YOUR RESULTS', 'YOUR PRACTICAL NUTRITION STEPS',
    'MEAL IDEAS', 'MEAL OPTIONS', 'IMPORTANT PRECAUTIONS',
    'MONITORING AND FOLLOW-UP', 'TO CONFIRM WITH YOUR NUTRITION PROFESSIONAL',
}

REMOVABLE_DRAFT_LINES = {
    'YOUR PERSONAL NUTRITION CARE PLAN',
    'DRAFT: Professional review required before patient release.',
    'This is an unapproved fictional demonstration draft.',
    'Prepared for professional review. This document is not a verified medical treatment order.',
}


def build_pdf(patient: dict, text: str, reviewer: str) -> bytes:
    """Use the reviewed report body; remove only boilerplate that contradicts status."""
    name = (patient.get('name') or '').strip()
    if not name or name.casefold() in {'patient name not found', 'unknown', 'not provided'}:
        raise ValueError('Patient name must be resolved before export.')

    fields = patient.get('fields') or {}
    reference = str(fields.get('patient_reference') or patient.get('id') or '').strip()

    if not reference:
        raise ValueError('Patient reference must be resolved before export.')

    if not reviewer.strip():
        raise ValueError('Reviewer name is required for this demonstration.')

    stream = io.BytesIO()

    doc = SimpleDocTemplate(
        stream,
        pagesize=A4,
        leftMargin=19 * mm,
        rightMargin=19 * mm,
        topMargin=19 * mm,
        bottomMargin=19 * mm
    )

    styles = getSampleStyleSheet()
    navy = colors.HexColor('#18372F')
    muted = colors.HexColor('#50645B')

    styles.add(ParagraphStyle(
        name='CareTitle',
        parent=styles['Title'],
        fontName='Helvetica-Bold',
        fontSize=18,
        leading=23,
        textColor=navy,
        spaceAfter=12
    ))

    styles.add(ParagraphStyle(
        name='CareSection',
        parent=styles['Heading2'],
        fontName='Helvetica-Bold',
        fontSize=12.5,
        leading=17,
        textColor=navy,
        spaceBefore=14,
        spaceAfter=7,
        keepWithNext=True
    ))

    styles.add(ParagraphStyle(
        name='CareSub',
        parent=styles['Heading3'],
        fontName='Helvetica-Bold',
        fontSize=10.5,
        leading=15,
        textColor=navy,
        spaceBefore=10,
        spaceAfter=5,
        keepWithNext=True
    ))

    styles.add(ParagraphStyle(
        name='CareBody',
        parent=styles['BodyText'],
        fontSize=10.2,
        leading=15.7,
        spaceAfter=8,
        splitLongWords=True
    ))

    styles.add(ParagraphStyle(
        name='CareMeta',
        parent=styles['BodyText'],
        fontSize=9,
        leading=13,
        textColor=muted,
        spaceAfter=4
    ))

    story = [
        Paragraph('Personal Nutrition Care Plan', styles['CareTitle']),
        Paragraph(f'Patient: {escape(name)}', styles['CareBody']),
        Paragraph(f'Patient reference: {escape(reference)}', styles['CareMeta']),
        Paragraph(
            'Status: Review recorded. '
            'Reviewer identity and qualifications are not verified.',
            styles['CareMeta']
        ),
        Paragraph(
            f'Reviewer entered: {escape(reviewer.strip())}  |  '
            f'Generated: {datetime.now(timezone.utc).strftime("%d %b %Y %H:%M UTC")}',
            styles['CareMeta']
        ),
        Spacer(1, 8),
        HRFlowable(
            width='100%',
            thickness=1,
            color=colors.HexColor('#DBE5E1')
        ),
        Spacer(1, 10)
    ]

    for raw in text.splitlines():
        line = raw.strip()

        if not line:
            story.append(Spacer(1, 4))
            continue

        if (
            line in REMOVABLE_DRAFT_LINES
            or re.fullmatch(r'Prepared for\s+' + re.escape(name), line, re.I)
        ):
            continue

        if line == 'MEAL OPTIONS TO REVIEW':
            line = 'MEAL IDEAS'

        if line in HEADINGS:
            story.append(
                Paragraph(escape(line.title()), styles['CareSection'])
            )

        elif re.match(r'^\d+\.\s+\S', line) and len(line) < 145:
            story.append(
                Paragraph(escape(line), styles['CareSub'])
            )

        elif re.match(
            r'^(?:What to do:|Why it matters:|How to put this into practice:)',
            line
        ):
            marker, content = line.split(':', 1)

            story.append(
                Paragraph(
                    f'<b>{escape(marker)}:</b>{escape(content)}',
                    styles['CareBody']
                )
            )

        elif (
            len(line) <= 95
            and not line.endswith(('.', '!', '?', ':', ';'))
            and not line.startswith(('•', '-'))
        ):
            story.append(
                Paragraph(escape(line), styles['CareSub'])
            )

        else:
            story.append(
                Paragraph(escape(line), styles['CareBody'])
            )

    story.extend([
        Spacer(1, 16),
        HRFlowable(
            width='100%',
            thickness=1,
            color=colors.HexColor('#DBE5E1')
        ),
        Spacer(1, 8),
        Paragraph(
            'This interface does not verify clinical '
            'credentials, assess the accuracy of recommendations, or authorize '
            'use for real patient care.',
            styles['CareMeta']
        )
    ])

    doc.build(story)
    return stream.getvalue()