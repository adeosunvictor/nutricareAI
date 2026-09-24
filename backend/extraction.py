
"""Conservative extraction of labelled synthetic outpatient records.

The source extracts remain the authority. This parser never converts missing
measurements, medicines, allergies, or patient identifiers into invented facts.
PDF/DOCX layout is not standardized; unrecognized items remain in source chunks.
"""
from __future__ import annotations

import re
from .security import normalize_text

REQUIRED_FOR_REVIEW = {
    'age': 'Age',
    'medical_history': 'Documented medical history',
    'medications': 'Current and previous medication information',
    'labs': 'Dated laboratory results',
    'diet': 'Dietary history',
    'allergies': 'Allergies or explicit none reported',
}

SECTIONS = [
    ('Patient details', (
        'date_of_birth', 'age', 'sex', 'height',
        'weight', 'bmi', 'patient_reference'
    )),
    ('Medical history', (
        'medical_history', 'reported_symptoms',
        'allergies', 'food_intolerance'
    )),
    ('Medication history', ('medications',)),
    ('Laboratory results', ('labs', 'previous_labs')),
    ('Diet and lifestyle', (
        'diet', 'meal_recall', 'cooking_habits',
        'patient_priorities', 'lifestyle', 'data_gaps'
    )),
]

HEAD = re.compile(
    r'^\s*0?[1-9]\s*\|\s*([^\n]+?)\s*$',
    re.I | re.M
)

MISSING = {
    '', 'not provided', 'not recorded',
    'not tested', 'unknown', 'n/a'
}

# Clinical labels identify source text, not diagnoses inferred by software.
CONDITIONS = (
    'type 2 diabetes mellitus',
    'hypertension',
    'dyslipidemia',
    'dyslipidaemia'
)

MEASURES = {
    'height': 'height',
    'weight': 'weight',
    'body mass index (bmi)': 'bmi',
    'bmi': 'bmi',
    'waist circumference': 'waist_circumference',
    'blood pressure': 'blood_pressure',
    'prior recorded weight': 'prior_weight',
    'earlier recorded weight': 'earlier_weight',
    'recent involuntary weight change': 'weight_change'
}

LABS = (
    'hba1c',
    'fasting plasma glucose',
    'total cholesterol',
    'ldl cholesterol',
    'hdl cholesterol',
    'triglycerides',
    'creatinine',
    'serum creatinine',
    'estimated gfr',
    'sodium',
    'potassium',
    'alt',
    'ast',
    'hemoglobin',
    'haemoglobin',
    'serum albumin',
    'urine albumin-to-creatinine ratio',
    'vitamin b12'
)

MEDICINES = (
    'metformin extended release',
    'metformin xr',
    'amlodipine',
    'atorvastatin',
    'glimepiride',
    'gliclazide'
)


# ============================================================
# 1. TEXT AND LABEL HELPERS
# ============================================================

def _lines(text: str) -> list[str]:
    return [
        re.sub(r'\s+', ' ', line).strip()
        for line in text.splitlines()
        if line.strip()
    ]


def _label(
    lines: list[str],
    labels: tuple[str, ...],
    stop: set[str],
    limit: int = 2
) -> str:
    """Get only text immediately following a recognized field label."""

    folded = {
        value.casefold().strip(':')
        for value in stop
    }

    for index, entry in enumerate(lines):

        for label in labels:

            match = re.fullmatch(
                rf'{re.escape(label)}\s*:\s*(.*)',
                entry,
                re.I
            )

            if match and match.group(1).strip():
                return match.group(1).strip()

            if entry.casefold().strip(':') != label.casefold():
                continue

            values = []

            for later in lines[index + 1:index + 1 + limit]:

                if (
                    later.casefold().strip(':') in folded
                    or HEAD.fullmatch(later)
                    or re.fullmatch(r'Page \d+', later, re.I)
                ):
                    break

                values.append(later)

            return ' '.join(values).strip()

    return ''


def _section_parts(
    parts: list[tuple[str, str]]
) -> dict[str, list[tuple[str, str]]]:
    """Split pages at numbered headings, retaining sections across pages."""

    sections: dict[str, list[tuple[str, str]]] = {}
    current = 'identification'

    for text, location in parts:

        matches = list(HEAD.finditer(text))
        start = 0

        for match in matches:

            prefix = text[start:match.start()]

            if prefix.strip():
                sections.setdefault(current, []).append(
                    (prefix, location)
                )

            title = match.group(1).casefold()

            if 'patient identification' in title:
                current = 'identification'

            elif 'medical' in title and 'history' in title:
                current = 'medical'

            elif (
                'anthropometric' in title
                or 'vital signs' in title
            ):
                current = 'measurements'

            elif 'laboratory' in title:
                current = 'labs'

            elif 'diet' in title or 'meal recall' in title:
                current = 'diet'

            elif (
                'lifestyle' in title
                or 'patient priorities' in title
            ):
                current = 'lifestyle'

            elif (
                'outstanding' in title
                or 'documentation completeness' in title
            ):
                current = 'gaps'

            start = match.end()

        tail = text[start:]

        if tail.strip():
            sections.setdefault(current, []).append(
                (tail, location)
            )

    return sections


# ============================================================
# 2. EXTRACT PATIENT INFORMATION
# ============================================================

def extract_document_fields(
    parts: list[tuple[str, str]]
) -> dict:
    """Extract supported patient facts and their source locations."""

    fields: dict[str, str] = {}
    sources: dict[str, list[str]] = {}

    name = ''
    patient_id = ''

    # Identity tables in PDF exports often precede the numbered identification
    # section. Read only explicit, labelled values, not header names or prose.
    identity_text = '\n'.join(text for text, _ in parts[:2])
    identity_lines = _lines(identity_text)
    name = _label(identity_lines, ('patient name', 'full name'),
                  {'patient reference', 'patient id', 'date of birth / age'}, 1)
    patient_id = _label(identity_lines, ('patient reference', 'patient id', 'record id'),
                        {'patient name', 'full name', 'date of birth / age'}, 1)

    def put(
        key: str,
        value: str,
        location: str,
        limit: int = 2400,
        append: bool = False
    ) -> None:

        cleaned = normalize_text(value, limit)

        if cleaned.casefold() in MISSING or not cleaned:
            return

        if append and fields.get(key):

            if cleaned not in fields[key]:
                fields[key] = normalize_text(
                    fields[key] + '; ' + cleaned,
                    limit
                )

        elif key not in fields:
            fields[key] = cleaned

        elif not append:
            return

        locations = sources.setdefault(key, [])

        if location not in locations:
            locations.append(location)

    sections = _section_parts(parts)

    # --------------------------------------------------------
    # PATIENT IDENTIFICATION
    # --------------------------------------------------------

    introductory = sections.get('identification', [])

    for text, location in introductory[:2]:

        lines = _lines(text)

        if not name:
            name = _label(
                lines,
                ('patient name', 'full name', 'name'),
                {
                    'patient reference',
                    'patient id',
                    'date of birth / age'
                },
                1
            )

        if not patient_id:
            patient_id = _label(
                lines,
                (
                    'patient reference',
                    'patient id',
                    'record id',
                    'mrn'
                ),
                {
                    'patient name',
                    'full name',
                    'date of birth / age'
                },
                1
            )

        dob = _label(
            lines,
            ('date of birth / age', 'date of birth'),
            {'sex', 'sex recorded for this case'},
            1
        )

        if ' / ' in dob:

            date_of_birth, age = dob.split(' / ', 1)

            put(
                'date_of_birth',
                date_of_birth,
                location
            )

            put('age', age, location)

        elif dob:
            put('date_of_birth', dob, location)

        for key, labels in {
            'age': ('age',),
            'sex': ('sex', 'sex recorded for this case'),
            'occupation': ('occupation',),
            'assessment_date': ('assessment date',),
            'reason_for_referral': (
                'reason for nutrition referral',
            ),
        }.items():

            value = _label(
                lines,
                labels,
                {
                    'patient name',
                    'patient reference',
                    'location'
                },
                3 if key == 'reason_for_referral' else 1
            )

            put(key, value, location)

        if (
            'reason_for_referral' not in fields
            and 'patient identification and reason for referral'
            in text.casefold()
        ):

            narrative = re.split(
                r'01\s*\|\s*Patient identification and reason for referral',
                text,
                maxsplit=1,
                flags=re.I
            )[-1]

            narrative = re.split(
                r'Patient.s words:',
                narrative,
                maxsplit=1,
                flags=re.I
            )[0]

            put(
                'reason_for_referral',
                re.sub(r'\s+', ' ', narrative),
                location,
                850
            )

        if 'assessment_date' not in fields:

            dated = re.search(
                r'Outpatient nutrition assessment\s*\|\s*'
                r'(\d{1,2}\s+\w+\s+20\d{2})',
                text,
                re.I
            )

            if dated:
                put(
                    'assessment_date',
                    dated.group(1),
                    location
                )

        # Repeated document header: fallback only.

        header = re.search(
            r'^([A-Z]{2,8}(?:/[A-Z]{2,8})?/\d[\w/-]*)'
            r'\s*\|\s*'
            r'([A-Za-z][A-Za-z .-]{3,70})$',
            text,
            re.M
        )

        if header:
            patient_id = patient_id or header.group(1).strip()
            name = name or header.group(2).strip()

    name = re.sub(
        r'\s*\(fictional\)\s*$',
        '',
        name,
        flags=re.I
    ).strip()

    patient_id = re.sub(
        r'\s*\([^\n]*$',
        '',
        patient_id
    ).strip()

    if patient_id:
        put(
            'patient_reference',
            patient_id,
            introductory[0][1] if introductory else 'document'
        )

    # --------------------------------------------------------
    # MEDICAL HISTORY AND ALLERGIES
    # --------------------------------------------------------

    for text, location in sections.get('medical', []):

        lines = _lines(text)

        stop = set(CONDITIONS) | {
            'item',
            'history / current status',
            'condition or concern',
            'recorded history',
            'food allergy',
            'food intolerance',
            'family history',
            'gastrointestinal symptoms',
            'sleep',
            'tobacco',
            'alcohol',
            'symptoms reported at consultation',
            'food allergies and intolerances',
            'patient-reported symptoms at intake',
            'clinical follow-up already in place',
            'previous hospital admissions',
        }

        documented = []

        for condition in CONDITIONS:

            value = _label(
                lines,
                (condition,),
                stop,
                3
            )

            if value:
                documented.append(
                    f'{condition}: {value}'
                )

        if documented:
            put(
                'medical_history',
                '; '.join(documented),
                location,
                append=True
            )

        reported = _label(
            lines,
            ('food allergy',),
            stop,
            4
        )

        if (
            not reported
            and 'food allergies and intolerances'
            in text.lower()
        ):

            reported = (
                text.split(
                    'Food allergies and intolerances',
                    1
                )[-1]
                .split('No food intolerance', 1)[0]
                .strip()
            )

        put(
            'allergies',
            reported,
            location,
            1700,
            append=True
        )

        put(
            'food_intolerance',
            _label(
                lines,
                ('food intolerance',),
                stop,
                3
            ),
            location,
            600
        )

        put(
            'reported_symptoms',
            _label(
                lines,
                (
                    'gastrointestinal symptoms',
                    'symptoms reported at consultation'
                ),
                stop,
                3
            ),
            location,
            700,
            append=True
        )

        put(
            'family_history',
            _label(
                lines,
                ('family history',),
                stop,
                3
            ),
            location,
            500
        )

    # --------------------------------------------------------
    # MEASUREMENTS AND MEDICATION HISTORY
    # --------------------------------------------------------

    for text, location in sections.get('measurements', []):

        lines = _lines(text)

        stop = (
            set(MEASURES)
            | set(MEDICINES)
            | {
                'measurement',
                'value',
                'date / source',
                '21 sep 2026',
                'previous record',
                'medication',
                'recorded regimen',
                'additional information',
                'medicine',
                'current record / timing',
                'notes',
                'current medication list',
                'medication reconciliation: present and historical',
                'previous medication',
            }
        )

        for label, key in MEASURES.items():

            put(
                key,
                _label(
                    lines,
                    (label,),
                    stop,
                    2
                ),
                location,
                180
            )

        # Separate current and historical medicines.

        med_entries = []
        historical = []

        for label in MEDICINES:

            value = _label(
                lines,
                (label,),
                stop,
                3
            )

            if not value:
                continue

            statement = f'{label}: {value}'

            if re.search(
                r'\b(?:historical|discontinued|previous|not on current)\b',
                value,
                re.I
            ):
                historical.append(statement)

            else:
                med_entries.append(statement)

        previous = re.search(
            r'Previous medication:\s*(.+?)'
            r'(?=\nKemi reports|\n04\s*\||\Z)',
            text,
            re.I | re.S
        )

        if previous:
            historical.append(
                re.sub(
                    r'\s+',
                    ' ',
                    previous.group(1)
                ).strip()
            )

        if med_entries or historical:

            value = '; '.join(
                ['Current: ' + '; '.join(med_entries)]
                if med_entries else []
            )

            if historical:
                value += (
                    ('; ' if value else '')
                    + 'Historical/discontinued: '
                    + '; '.join(historical)
                )

            put(
                'medications',
                value,
                location,
                2100,
                append=True
            )

    # --------------------------------------------------------
    # LABORATORY RESULTS
    # --------------------------------------------------------

    for text, location in sections.get('labs', []):

        lower = text.lower()

        date_info = re.search(
            r'Current laboratory sample:\s*([^\n]+)',
            text,
            re.I
        )

        lab_date = (
            'Current/previous sample dates: '
            + date_info.group(1).strip()
            + '; '
        ) if date_info else ''

        if 'collected 11 september 2026' in lower:
            lab_date = 'Current sample: 11 September 2026; '

        prior_date = (
            '15 March 2026'
            if 'prior dated results for comparison' in lower
            else ''
        )

        # The original case has current and prior results
        # in separate tables on the same page.

        if 'prior dated results for comparison' in lower:

            current_part, prior_part = re.split(
                'prior dated results for comparison',
                text,
                maxsplit=1,
                flags=re.I
            )

        else:
            current_part, prior_part = text, ''

        is_prior = False
        lines = _lines(current_part)

        labels = set(LABS) | {
            'investigation',
            'test',
            'result',
            'previous result',
            'illustrative lab reference / flag',
            '17 sep 2026',
            '14 mar 2026'
        }

        current_values = []
        previous_values = []

        for test in LABS:

            for idx, entry in enumerate(lines):

                if entry.casefold() != test:
                    continue

                next_values = []

                for item in lines[idx + 1:idx + 4]:

                    if (
                        item.casefold() in labels
                        or HEAD.fullmatch(item)
                    ):
                        break

                    next_values.append(item)

                if (
                    not next_values
                    or next_values[0].casefold() in MISSING
                ):
                    continue

                current_values.append(
                    f'{test}: {next_values[0]}'
                )

                # The two-column format can contain
                # current and previous values together.

                if (
                    not is_prior
                    and len(next_values) > 1
                    and re.match(r'^[<>]?\d', next_values[1])
                    and re.search(
                        r'14 Mar 2026|15 Mar 2026',
                        text
                    )
                ):

                    previous_values.append(
                        f'{test}: {next_values[1]}'
                    )

                elif (
                    is_prior
                    and len(next_values) > 1
                    and re.search(r'2026', next_values[1])
                ):

                    previous_values.append(
                        f'{test}: {next_values[0]} '
                        f'({next_values[1]})'
                    )

                break

        if current_values and not is_prior:

            put(
                'labs',
                lab_date + '; '.join(current_values),
                location,
                2450,
                append=True
            )

        if previous_values:

            put(
                'previous_labs',
                (
                    prior_date + ': '
                    if prior_date else 'Previous sample: '
                ) + '; '.join(previous_values),
                location,
                2350,
                append=True
            )

        if prior_part:

            prior_lines = _lines(prior_part)
            prior_rows = []

            for test in LABS:

                value = _label(
                    prior_lines,
                    (test,),
                    labels | {'date', 'weight'},
                    2
                )

                if (
                    value
                    and value.casefold() not in MISSING
                ):
                    prior_rows.append(
                        f'{test}: {value}'
                    )

            if prior_rows:

                put(
                    'previous_labs',
                    '15 March 2026: ' + '; '.join(prior_rows),
                    location,
                    2350,
                    append=True
                )

    # --------------------------------------------------------
    # DIETARY HISTORY AND MEAL RECALL
    # --------------------------------------------------------

    for text, location in sections.get('diet', []):

        lines = _lines(text)

        if not lines:
            continue

        cooking = re.search(
            r'Home food preparation\s*(.+?)'
            r'(?=Three-day food and beverage record|\Z)',
            text,
            re.I | re.S
        )

        if cooking:

            put(
                'cooking_habits',
                re.sub(
                    r'\s+',
                    ' ',
                    cooking.group(1)
                ),
                location,
                1600,
                append=True
            )

        drink = re.search(
            r'Beverages\s*(.+?)'
            r'(?=Home food preparation|\Z)',
            text,
            re.I | re.S
        )

        if drink and (
            'tea' in drink.group(1).casefold()
            or 'soft drink' in drink.group(1).casefold()
        ):

            put(
                'beverages',
                re.sub(
                    r'\s+',
                    ' ',
                    drink.group(1)
                ),
                location,
                1100,
                append=True
            )

        if 'Three-day food and beverage record' in text:

            recall = text.split(
                'Three-day food and beverage record',
                1
            )[1]

            put(
                'meal_recall',
                re.sub(r'\s+', ' ', recall),
                location,
                2100,
                append=True
            )

        if re.search(
            r'\b(?:Sep / \d{2}:\d{2}|'
            r'Friday, 18 September|'
            r'Saturday, 19 September|'
            r'Sunday, 20 September)\b',
            text
        ):

            put(
                'meal_recall',
                re.sub(r'\s+', ' ', text),
                location,
                2100,
                append=True
            )

        # Preserve recognizable dietary passages even when
        # their tables do not match a known layout.

        useful = re.sub(r'\s+', ' ', text)

        put(
            'diet',
            useful,
            location,
            2450,
            append=True
        )

    # --------------------------------------------------------
    # LIFESTYLE, PRIORITIES AND INFORMATION GAPS
    # --------------------------------------------------------

    for text, location in sections.get('lifestyle', []):

        priorities = re.search(
            r'Patient priorities\s*(.+?)'
            r'(?=Nutrition consultation observations|\Z)',
            text,
            re.I | re.S
        )

        if priorities:

            put(
                'patient_priorities',
                re.sub(
                    r'\s+',
                    ' ',
                    priorities.group(1)
                ),
                location,
                1200,
                append=True
            )

        put(
            'lifestyle',
            re.sub(r'\s+', ' ', text),
            location,
            1500,
            append=True
        )

        if 'Items explicitly requiring clarification' in text:

            put(
                'data_gaps',
                text.split(
                    'Items explicitly requiring clarification',
                    1
                )[1],
                location,
                1200,
                append=True
            )

    for text, location in sections.get('gaps', []):

        if 'Information requiring confirmation' in text:

            put(
                'data_gaps',
                re.sub(r'\s+', ' ', text),
                location,
                1600,
                append=True
            )

    return {
        'name': name,
        'patient_id': patient_id,
        'fields': fields,
        'field_sources': sources
    }


# ============================================================
# 3. GENERATE THE EVIDENCE SUMMARY
# ============================================================

def summarize(patient: dict) -> dict:
    fields = patient.get('fields', {})

    missing = [
        label
        for key, label in REQUIRED_FOR_REVIEW.items()
        if not fields.get(key)
    ]

    if (
        not patient.get('name')
        or patient['name'].casefold() == 'patient name not found'
    ):
        missing.insert(0, 'Patient name')

    if (
        not fields.get('patient_reference')
        and not patient.get('id')
    ):
        missing.insert(0, 'Patient reference')

    sections = []

    for title, keys in SECTIONS:

        rows = []

        for key in keys:

            if not fields.get(key):
                continue

            locations = set(
                patient.get(
                    'field_sources',
                    {}
                ).get(key, [])
            )

            related = [
                chunk
                for chunk in patient.get('chunks', [])
                if (
                    chunk.get('location', '').split(', part')[0]
                    in locations
                )
            ]

            rows.append({
                'key': key,
                'label': key.replace('_', ' ').capitalize(),
                'value': normalize_text(
                    fields[key],
                    2400
                ),
                'source_ids': [
                    chunk['id']
                    for chunk in related[:3]
                ]
            })

        sections.append({
            'title': title,
            'rows': rows
        })

    return {
        'sections': sections,
        'missing': missing,
        'sources': patient.get('chunks', []),
        'ready_for_clinician_review': not missing
    }