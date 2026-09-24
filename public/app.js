
/*
 * NutriCare AI
 * Frontend controller for the synthetic-data demonstration.
 * Patient information remains in the current browser session.
 */

'use strict';

// ============================================================
// 1. APPLICATION STATE AND HELPERS
// ============================================================

const byId = id => document.getElementById(id);

const state = {
  patients: [],
  active: 0,
  sidebarCollapsed: false,
  assessmentName: '',
  mode: 'single',
  evidenceTab: 'overview',
  planTab: 'draft',
  aiConfigured: false,
  busy: false,
  exports: [],
  view: 'workspace',
  toastTimer: null
};

const patient = () => state.patients[state.active] || null;

function node(tag, className = '', content) {
  const element = document.createElement(tag);
  if (className) element.className = className;

  if (content !== undefined && content !== null) {
    element.textContent = String(content);
  }

  return element;
}

function required(condition, message) {
  if (!condition) throw new Error(message);
}

function toast(message, error = false) {
  const element = byId('toast');
  element.textContent = message;
  element.className = error ? 'toast error' : 'toast';

  clearTimeout(state.toastTimer);
  state.toastTimer = setTimeout(
    () => element.classList.add('hidden'),
    5500
  );
}

async function api(path, options = {}) {
  const response = await fetch(path, {
    cache: 'no-store',
    ...options
  });

  if (!response.ok) {
    let message = `Request failed (${response.status}).`;

    try {
      const data = await response.json();
      if (typeof data.detail === 'string') {
        message = data.detail;
      }
    } catch (_) {
      // Retain the HTTP error message.
    }

    throw new Error(message);
  }

  return response;
}

async function jsonPost(path, payload) {
  const response = await api(path, {
    method: 'POST',
    headers: {
      'Content-Type': 'application/json'
    },
    body: JSON.stringify({
      ...payload,
      demo_confirmed: true
    })
  });

  return response.json();
}

function busy(value) {
  state.busy = Boolean(value);

  for (const id of [
    'sendBtn',
    'generateBtn',
    'exportBtn',
    'uploadSubmit'
  ]) {
    const button = byId(id);
    if (button) button.disabled = state.busy;
  }

  if (!state.busy && state.patients.length) {
    render();
  }
}

function showDialog(id) {
  byId(id).showModal();
}

function closeDialog(id) {
  byId(id).close();
}

// ============================================================
// 2. UPLOAD AND PATIENT MANAGEMENT
// ============================================================

function confirmReplace() {
  return !state.patients.length || window.confirm(
    'Start a new assessment? Current records ' +
    'and unsaved drafts will be cleared.'
  );
}

function selectUploadMode(mode) {
  byId('singleChoice').classList.toggle(
    'selected',
    mode === 'single'
  );

  byId('groupChoice').classList.toggle(
    'selected',
    mode === 'group'
  );
}

function openUpload() {
  if (state.busy || !confirmReplace()) return;

  byId('uploadForm').reset();

  byId('fileLabel').textContent =
    'Click to choose a file or drop it here';

  byId('uploadError').classList.add('hidden');

  selectUploadMode('single');
  showDialog('uploadDialog');
}

async function parseUpload(file, mode, confirmed) {
  required(file, 'Choose a file.');

  required(
    confirmed,
    'Confirm that the record is fictional or synthetic.'
  );

  required(
    file.size <= 3 * 1024 * 1024,
    'Maximum file size is 3 MB.'
  );

  const form = new FormData();

  form.set('file', file);
  form.set('mode', mode);
  form.set('demo_confirmed', 'true');

  return (
    await api('/api/upload', {
      method: 'POST',
      body: form
    })
  ).json();
}

function initializeAssessment(result, mode, filename) {
  required(
    Array.isArray(result.patients) && result.patients.length,
    'No patient records were extracted.'
  );

  state.patients = result.patients.map(p => ({
    ...p,
    verified: false,
    approved: false,
    draft: null,
    plan: '',
    reviewer: '',
    history: [],
    suggestion: null,
    edits: [],
    updatedAt: null
  }));

  state.active = 0;

  state.assessmentName = filename
    .replace(/\.[^.]+$/, '')
    .replace(/[_-]+/g, ' ');

  state.mode = mode;
  state.view = 'workspace';
  state.evidenceTab = 'overview';
  state.planTab = 'draft';

  render();

  toast(
    `${state.patients.length} record(s) ready. ` +
    'Verify the extracted facts before drafting.'
  );
}

async function loadDemo() {
  if (state.busy || !confirmReplace()) return;

  try {
    busy(true);

    const response = await api('/demo-patients.csv');

    const file = new File(
      [await response.blob()],
      'demo-patients.csv',
      { type: 'text/csv' }
    );

    const result = await parseUpload(file, 'group', true);

    initializeAssessment(
      result,
      'group',
      'Sample assessment'
    );

  } catch (error) {
    toast(error.message, true);
  } finally {
    busy(false);
  }
}

function switchPatient(index) {
  if (
    state.busy ||
    index === state.active ||
    !state.patients[index]
  ) {
    return;
  }

  state.active = index;
  state.evidenceTab = 'overview';
  state.planTab = 'draft';

  render();
}

// ============================================================
// 3. DISPLAY HELPERS
// ============================================================

function heading(title, aside = '') {
  const element = node('div', 'section-heading');

  element.append(
    node('h3', '', title),
    node('span', '', aside)
  );

  return element;
}

function row(label, value) {
  const element = node('div', 'evidence-row');

  element.append(
    node('span', '', label),
    node('strong', '', value)
  );

  return element;
}

function warning(message) {
  return node('div', 'review-warning', message);
}

function paragraph(container, text, className = 'plan-paragraph') {
  container.append(node('p', className, text));
}

function listSection(container, title, items, numbered = false) {
  if (!Array.isArray(items) || !items.length) return;

  container.append(node('h3', 'plan-title', title));

  const list = node('div', 'plan-list');

  items.forEach((value, index) => {
    const item = node('div', 'plan-list-row');

    item.append(
      node(
        'span',
        'list-index',
        numbered ? String(index + 1) : '•'
      ),
      node('span', '', value)
    );

    list.append(item);
  });

  container.append(list);
}

// ============================================================
// 4. PATIENT-FACING REPORT TEXT
// ============================================================

/*
 * The same text is used for:
 * - Manual editing
 * - Conversational revisions
 * - The exported PDF
 *
 * Clinical ADIME information remains separate.
 */

function patientText(plan, name) {
  if (!plan) return '';

  const lines = [
    'YOUR PERSONAL NUTRITION CARE PLAN',
    `Prepared for ${name}`,
    'DRAFT: Professional review required before patient release.',
    '',
    'WELCOME',
    plan.opening,
    '',
    'UNDERSTANDING YOUR RESULTS'
  ];

  (plan.result_explanations || []).forEach(item => {
    lines.push(
      '',
      item.title,
      item.explanation
    );
  });

  lines.push('', 'YOUR PRACTICAL NUTRITION STEPS');

  (plan.action_steps || []).forEach((item, index) => {
    lines.push(
      '',
      `${index + 1}. ${item.title}`,
      `What to do: ${item.what}`,
      `Why it matters: ${item.why}`,
      `How to put this into practice: ${item.how}`
    );
  });

  lines.push('', 'MEAL OPTIONS TO REVIEW');

  (plan.meal_options || []).forEach(item => {
    lines.push(
      '',
      item.title,
      item.details
    );
  });

  if (!(plan.meal_options || []).length) {
    lines.push(
      'Individual meal selections require additional ' +
      'information and professional review.'
    );
  }

  lines.push('', 'IMPORTANT PRECAUTIONS');

  (plan.precautions || []).forEach(item => {
    lines.push(
      '',
      item.title,
      item.details
    );
  });

  lines.push('', 'MONITORING AND FOLLOW-UP');

  (plan.monitoring || []).forEach((item, index) => {
    lines.push(`${index + 1}. ${item}`);
  });

  lines.push(
    '',
    'TO CONFIRM WITH YOUR NUTRITION PROFESSIONAL'
  );

  (plan.pending_review || []).forEach((item, index) => {
    lines.push(`${index + 1}. ${item}`);
  });

  lines.push(
    '',
    'This plan is pending professional review.'
  );

  return lines.join('\n').trim();
}

// ============================================================
// 5. PATIENT EVIDENCE AND SOURCE REFERENCES
// ============================================================

function appendSourceLinks(container, ids) {
  if (!Array.isArray(ids) || !ids.length || !patient()) {
    return;
  }

  const line = node(
    'div',
    'citation-line',
    'Record evidence: '
  );

  ids.forEach(id => {
    const source = (patient().chunks || []).find(
      chunk => chunk.id === id
    );

    if (!source) return;

    const button = node(
      'button',
      'source-pill',
      `${id} · ${source.location}`
    );

    button.type = 'button';

    button.title =
      `Open ${source.source}, ${source.location}`;

    button.addEventListener('click', () => {
      state.evidenceTab = 'sources';
      renderEvidence();

      const area = byId('evidenceContent');

      const target = [
        ...area.querySelectorAll('.source-item')
      ].find(element => element.dataset.sourceId === id);

      if (target) {
        area.scrollTop +=
          target.getBoundingClientRect().top -
          area.getBoundingClientRect().top - 8;
      }
    });

    line.append(button);
  });

  container.append(line);
}

function renderEvidence() {
  const p = patient();
  if (!p) return;

  document.querySelectorAll('#evidenceTabs .tab').forEach(tab => {
    const active = tab.dataset.tab === state.evidenceTab;

    tab.classList.toggle('active', active);
    tab.setAttribute('aria-selected', String(active));
  });

  const box = byId('evidenceContent');
  box.replaceChildren();

  const fields = p.fields || {};

  if (state.evidenceTab === 'overview') {
    box.append(heading('PATIENT PROFILE'));

    const grid = node('div', 'evidence-grid');

    for (const [key, label] of [
      ['age', 'Age'],
      ['sex', 'Sex / gender'],
      ['height', 'Height'],
      ['weight', 'Weight']
    ]) {
      const card = node('div', 'fact-card');

      card.append(
        node('label', '', label),
        node('strong', '', fields[key] || 'Not provided')
      );

      grid.append(card);
    }

    box.append(grid);

    if (fields.bmi) {
      box.append(row('Recorded BMI', fields.bmi));
    }

    if (fields.blood_pressure) {
      box.append(
        row('Recorded blood pressure', fields.blood_pressure)
      );
    }

    box.append(heading('CLINICAL SNAPSHOT'));

    for (const [key, label] of [
      ['medical_history', 'Medical history'],
      ['medications', 'Medications'],
      ['diet', 'Dietary history'],
      ['allergies', 'Allergies'],
      ['food_intolerance', 'Food intolerance'],
      ['lifestyle', 'Lifestyle and priorities']
    ]) {
      box.append(
        row(label, fields[key] || 'Not provided')
      );
    }

    if (p.evidence?.missing?.length) {
      box.append(
        warning(
          'Missing or unverified: ' +
          p.evidence.missing.join(', ')
        )
      );
    }

    if (fields.data_gaps) {
      box.append(
        warning(
          'Information to clarify: ' +
          fields.data_gaps
        )
      );
    }

  } else if (state.evidenceTab === 'labs') {
    box.append(heading('LABORATORY EVIDENCE'));

    box.append(
      row(
        'Current results',
        fields.labs || 'Not provided'
      )
    );

    if (fields.previous_labs) {
      box.append(
        row('Previous results', fields.previous_labs)
      );
    }

    box.append(
      warning(
        'Recorded observations only; clinical interpretation ' +
        'requires professional review.'
      )
    );

  } else if (state.evidenceTab === 'history') {
    box.append(
      heading('HISTORY AND DIETARY INFORMATION')
    );

    for (const [key, label] of [
      ['medical_history', 'Medical history'],
      ['medications', 'Medications'],
      ['diet', 'Dietary history'],
      ['allergies', 'Allergies'],
      ['meal_recall', 'Three-day meal recall'],
      ['food_intolerance', 'Food intolerance'],
      ['lifestyle', 'Lifestyle'],
      ['family_history', 'Family history'],
      ['data_gaps', 'Information to clarify']
    ]) {
      box.append(
        row(label, fields[key] || 'Not provided')
      );
    }

  } else {
    box.append(
      heading(
        'SOURCE RECORDS',
        `${(p.chunks || []).length} extracts`
      )
    );

    (p.chunks || []).forEach(item => {
      const card = node('div', 'source-item');

      card.dataset.sourceId = item.id;

      card.append(
        node('strong', '', `${item.id} · ${item.source}`),
        node('span', '', item.location),
        node('p', '', item.text)
      );

      box.append(card);
    });
  }
}

// ============================================================
// 6. PATIENT-FACING NUTRITION PLAN
// ============================================================

function renderPatientPlan(box, plan) {
  box.append(
    heading('YOUR PERSONAL NUTRITION CARE PLAN')
  );

  box.append(
    warning(
      'Patient-language draft, not approved for patient release.'
    )
  );

  paragraph(box, plan.opening, 'plan-summary');

  box.append(heading('UNDERSTANDING YOUR RESULTS'));

  plan.result_explanations.forEach(item => {
    box.append(
      node('h3', 'plan-title', item.title)
    );

    paragraph(box, item.explanation);
    appendSourceLinks(box, item.source_ids);
  });

  box.append(
    heading('YOUR PRACTICAL NUTRITION STEPS')
  );

  plan.action_steps.forEach((item, index) => {
    box.append(
      node(
        'h3',
        'plan-title',
        `${index + 1}. ${item.title}`
      )
    );

    paragraph(
      box,
      `What to do: ${item.what}\n\n` +
      `Why it matters: ${item.why}\n\n` +
      `How to put this into practice: ${item.how}`
    );

    appendSourceLinks(box, item.source_ids);
  });

  box.append(heading('MEAL OPTIONS TO REVIEW'));

  if (!plan.meal_options.length) {
    box.append(
      warning(
        'Meal choices need additional professional assessment.'
      )
    );
  }

  plan.meal_options.forEach(item => {
    box.append(
      node('h3', 'plan-title', item.title)
    );

    paragraph(box, item.details);
    appendSourceLinks(box, item.source_ids);
  });

  box.append(heading('IMPORTANT PRECAUTIONS'));

  plan.precautions.forEach(item => {
    box.append(
      node('h3', 'plan-title', item.title)
    );

    paragraph(box, item.details);
    appendSourceLinks(box, item.source_ids);
  });

  listSection(
    box,
    'MONITORING AND FOLLOW-UP',
    plan.monitoring,
    true
  );

  listSection(
    box,
    'TO CONFIRM WITH YOUR NUTRITION PROFESSIONAL',
    plan.pending_review,
    true
  );
}

// ============================================================
// 7. CLINICAL ADIME ASSESSMENT
// ============================================================

function renderClinicalDraft(box, draft) {
  const a = draft.assessment;
  const d = draft.nutrition_diagnosis;
  const i = draft.intervention;
  const m = draft.monitoring;
  const r = draft.review;

  box.append(heading('A. NUTRITION ASSESSMENT'));

  paragraph(box, a.summary);

  a.key_findings.forEach(finding => {
    paragraph(box, finding.text);

    appendSourceLinks(
      box,
      finding.source_ids
    );
  });

  listSection(
    box,
    'Missing / unconfirmed information',
    a.missing_information
  );

  box.append(
    heading('D. PROPOSED NUTRITION DIAGNOSIS')
  );

  paragraph(
    box,
    d.pes_statement ||
    'Insufficient evidence for a candidate PES statement.'
  );

  box.append(
    warning(
      'Candidate diagnosis only. A qualified professional ' +
      'must confirm its terminology and supporting evidence.'
    )
  );

  box.append(
    heading('I. PROPOSED NUTRITION INTERVENTION')
  );

  listSection(box, 'Objectives', i.objectives, true);

  listSection(
    box,
    'Meal options requiring review',
    i.meal_options
  );

  listSection(box, 'Education topics', i.education);

  paragraph(
    box,
    'Nutrition prescription: ' +
    i.nutrition_prescription
  );

  box.append(
    heading('M/E. MONITORING AND EVALUATION')
  );

  listSection(box, 'Indicators', m.indicators);

  paragraph(
    box,
    'Follow-up: ' + m.follow_up
  );

  box.append(heading('SAFETY AND REVIEW'));

  listSection(
    box,
    'Safety flags',
    r.safety_flags
  );

  listSection(
    box,
    'Clinician questions',
    r.questions
  );

  box.append(
    warning(
      draft.guideline_status +
      ' Source IDs have not been independently ' +
      'checked for claim support.'
    )
  );
}

// ============================================================
// 8. NUTRITION PLAN TABS
// ============================================================

function renderPlan() {
  const p = patient();
  if (!p) return;

  document.querySelectorAll('#planTabs .tab').forEach(tab => {
    const active =
      tab.dataset.tab === state.planTab;

    tab.classList.toggle('active', active);
    tab.setAttribute('aria-selected', String(active));

    if (tab.dataset.tab === 'draft') {
      tab.textContent = 'Patient plan';
    }

    if (tab.dataset.tab === 'considerations') {
      tab.textContent = 'Clinical ADIME';
    }

    if (tab.dataset.tab === 'questions') {
      tab.textContent = 'Review questions';
    }
  });

  const box = byId('planContent');
  box.replaceChildren();

  // Clinical assessment tab.

  if (state.planTab === 'considerations') {
    if (p.draft) {
      renderClinicalDraft(box, p.draft);
    } else {
      box.append(
        warning(
          'No structured clinical assessment is available.'
        )
      );
    }

    return;
  }

  // Questions and safety tab.

  if (state.planTab === 'questions') {
    box.append(
      heading('OUTSTANDING QUESTIONS AND SAFETY')
    );

    listSection(
      box,
      'Clinical questions',
      p.draft?.review?.questions || []
    );

    listSection(
      box,
      'Patient-facing decisions to confirm',
      p.draft?.patient_plan?.pending_review || []
    );

    listSection(
      box,
      'Reported safety restrictions',
      p.draft?.review?.safety_flags || []
    );

    listSection(
      box,
      'Missing extracted facts',
      p.evidence?.missing || []
    );

    return;
  }

  // Patient-facing plan tab.

  if (!p.plan) {
    box.append(
      warning(
        p.verified
          ? 'Generate a patient-language draft or write one manually.'
          : 'Verify the source record before generating a draft.'
      )
    );

    return;
  }

  if (p.approved) {
    box.append(
      warning(
        `Review recorded by ${p.reviewer}. ` +
        'Reviewer identity is not verified.'
      )
    );
  }

  // Display the original structured draft when unchanged.

  if (
    p.draft?.patient_plan &&
    p.plan === patientText(p.draft.patient_plan, p.name)
  ) {
    renderPatientPlan(
      box,
      p.draft.patient_plan
    );

  } else {
    // Keep edited reports intact, including targeted AI revisions.

    box.append(
      heading('EDITED PATIENT-FACING PLAN')
    );

    box.append(
      node('p', 'plan-paragraph', p.plan)
    );

    if (p.draft) {
      box.append(
        warning(
          'The patient-facing text was edited. Review the ' +
          'Clinical ADIME tab for consistency before approval.'
        )
      );
    }
  }
}

// ============================================================
// 9. CHAT AND PROPOSED REVISIONS
// ============================================================

function renderChat() {
  const p = patient();
  if (!p) return;

  const messages = byId('chatMessages');
  messages.replaceChildren();

  if (!p.history.length) {
    const greeting = !p.verified
      ? 'Verify the extracted patient information first.'
      : !state.aiConfigured
        ? 'Cloudflare AI is not connected. Manual editing is available.'
        : `Review ${p.name}'s patient plan here. Quote a passage ` +
          'and request a specific change.';

    messages.append(
      node('div', 'message', greeting)
    );
  }

  p.history.forEach(message => {
    messages.append(
      node(
        'div',
        `message ${message.role}`,
        message.content
      )
    );
  });

  messages.scrollTop = messages.scrollHeight;

  const canChat =
    p.verified &&
    state.aiConfigured &&
    !state.busy;

  byId('chatInput').disabled = !canChat;
  byId('sendBtn').disabled = !canChat;

  byId('chatInput').placeholder = !p.verified
    ? 'Verify the evidence to begin…'
    : !state.aiConfigured
      ? 'Configure Cloudflare to enable chat…'
      : 'Ask about the evidence or request a specific passage revision…';

  byId('chatSuggestion').classList.toggle(
    'hidden',
    !p.suggestion
  );

  byId('suggestionPreview').textContent = p.suggestion
    ? `REPLACE:\n${p.suggestion.old_text}\n\n` +
      `WITH:\n${p.suggestion.new_text}\n\n` +
      `REASON:\n${p.suggestion.reason}`
    : '';
}

// ============================================================
// 10. MAIN WORKSPACE RENDER
// ============================================================

function render() {
  const hasPatients = state.patients.length > 0;

  byId('welcomeView').classList.toggle(
    'hidden',
    hasPatients || state.view !== 'workspace'
  );

  byId('workspaceView').classList.toggle(
    'hidden',
    !hasPatients || state.view !== 'workspace'
  );

  byId('secondaryView').classList.toggle(
    'hidden',
    state.view === 'workspace'
  );

  byId('navCount').textContent = state.patients.length;

  document.querySelectorAll('.nav-item').forEach(item => {
    item.classList.toggle(
      'active',
      item.dataset.view === state.view
    );
  });

  const breadcrumbs = {
    workspace: 'Assessments',
    exports: 'Export history',
    metrics: 'Evaluation'
  };

  byId('breadcrumbCurrent').textContent =
    breadcrumbs[state.view];

  if (state.view !== 'workspace') {
    renderSecondary();
    return;
  }

  if (!hasPatients) return;

  const p = patient();

  byId('assessmentTitle').textContent =
    state.assessmentName || 'Patient assessment';

  byId('assessmentSubtitle').textContent =
    `Reviewing ${state.patients.length} record(s). ` +
    'Information is not saved.';

  byId('patientDisplay').textContent =
    `${p.name} · ${p.id}`;

  byId('chatPatientName').textContent = p.name;

  byId('modeBadge').textContent =
    state.mode === 'group'
      ? 'Multiple patients'
      : 'Single patient';

  byId('batchProgress').textContent =
    state.mode === 'group'
      ? `${state.patients.filter(
          item => item.approved
        ).length}/${state.patients.length} reviewed`
      : '';

  // Patient selector.

  const tabs = byId('patientTabs');
  tabs.replaceChildren();

  state.patients.forEach((item, index) => {
    const chip = node(
      'button',
      `patient-chip ${index === state.active ? 'active' : ''}`
    );

    chip.type = 'button';
    chip.role = 'tab';

    chip.setAttribute(
      'aria-selected',
      String(index === state.active)
    );

    chip.title = item.name;

    chip.append(
      node(
        'span',
        'patient-initial',
        item.name[0] || '?'
      )
    );

    const content = node('span');

    content.append(
      node('strong', '', item.name),
      node(
        'small',
        '',
        item.approved
          ? '✓ Reviewed'
          : item.verified
            ? '◌ In review'
            : '◌ Unverified'
      )
    );

    chip.append(content);

    chip.addEventListener(
      'click',
      () => switchPatient(index)
    );

    tabs.append(chip);
  });

  // Evidence and plan statuses.

  byId('evidenceBadge').textContent =
    p.verified ? 'Verified' : 'Unverified';

  byId('evidenceBadge').classList.toggle(
    'verified',
    p.verified
  );

  byId('planState').textContent = p.approved
    ? '✓ Reviewed'
    : p.plan
      ? 'Draft · review needed'
      : 'Not started';

  byId('planState').classList.toggle(
    'approved',
    p.approved
  );

  byId('verifyBtn').textContent =
    p.verified ? '✓ Verified' : 'Verify extracted facts';

  byId('verifyBtn').disabled =
    p.verified || state.busy;

  byId('evidenceFootnote').textContent =
    p.verified
      ? 'Verified in this browser tab.'
      : 'Compare all extracted facts against the source.';

  // Action buttons.

  byId('generateBtn').disabled =
    !p.verified ||
    !state.aiConfigured ||
    state.busy;

  byId('generateBtn').title =
    !state.aiConfigured
      ? 'Configure Cloudflare to generate a draft'
      : '';

  byId('editPlanBtn').disabled =
    !p.verified || state.busy;

  byId('approveBtn').disabled =
    !p.verified ||
    !p.plan.trim() ||
    p.approved ||
    state.busy;

  byId('exportBtn').disabled =
    !p.approved || state.busy;

  byId('planFooterText').textContent =
    !p.verified
      ? 'Verify patient evidence first'
      : p.approved
        ? `Reviewed by ${p.reviewer}`
        : p.plan
          ? 'Pending professional review'
          : state.aiConfigured
            ? 'Ready to generate a draft'
            : 'Manual editing is available';

  renderEvidence();
  renderPlan();
  renderChat();
}

// ============================================================
// 11. GENERATE CLINICAL AND PATIENT-FACING DRAFTS
// ============================================================

async function generateDraft() {
  const p = patient();

  if (
    !p ||
    !p.verified ||
    !state.aiConfigured ||
    state.busy
  ) {
    return;
  }

  if (
    p.plan &&
    !window.confirm(
      'Replace the current patient-facing draft ' +
      'with a newly generated draft?'
    )
  ) {
    return;
  }

  try {
    busy(true);

    byId('planFooterText').textContent =
      'Preparing clinical and patient-facing drafts…';

    const result = await jsonPost(
      '/api/assess',
      { patient: p }
    );

    required(
      result.draft?.patient_plan,
      'The server did not return a patient-facing plan.'
    );

    const text = patientText(
      result.draft.patient_plan,
      p.name
    );

    required(
      text.length <= 12000,
      'Generated report is too long for the current export limit.'
    );

    p.draft = result.draft;
    p.plan = text;
    p.suggestion = null;
    p.approved = false;
    p.reviewer = '';
    p.updatedAt = new Date().toISOString();

    state.planTab = 'draft';

    toast(
      'Detailed patient-facing and clinical drafts ' +
      'are ready for review.'
    );

  } catch (error) {
    toast(error.message, true);
  } finally {
    busy(false);
    render();
  }
}

// ============================================================
// 12. AI CHAT
// ============================================================

async function sendMessage(event) {
  event.preventDefault();

  const p = patient();
  const message = byId('chatInput').value.trim();

  if (
    !p ||
    !p.verified ||
    !state.aiConfigured ||
    state.busy ||
    !message
  ) {
    return;
  }

  const previous = p.history
    .filter(item =>
      item.role === 'user' ||
      item.role === 'assistant'
    )
    .slice(-6);

  p.history.push({
    role: 'user',
    content: message
  });

  byId('chatInput').value = '';

  try {
    busy(true);
    renderChat();

    const response = await jsonPost(
      '/api/chat',
      {
        patient: p,
        message,
        history: previous,
        current_plan: p.plan
      }
    );

    p.history.push({
      role: 'assistant',
      content: response.result.answer
    });

    // Save a proposed edit for review.
    // Do not apply it automatically.

    if (response.result.proposed_edit) {
      p.suggestion = response.result.proposed_edit;
    }

  } catch (error) {
    p.history.push({
      role: 'system',
      content: error.message
    });

    toast(error.message, true);

  } finally {
    busy(false);
    render();
  }
}

// ============================================================
// 13. MANUAL EDITING AND DEMO REVIEW
// ============================================================

function openEdit() {
  const p = patient();

  if (!p || !p.verified || state.busy) return;

  byId('planEditor').value = p.plan;

  showDialog('editDialog');
}

function savePlan(event) {
  event.preventDefault();

  const p = patient();

  if (!p || state.busy) return;

  const value = byId('planEditor').value.trim();

  if (!value || value.length > 12000) {
    toast(
      'The report must contain 1 to 12000 characters.',
      true
    );
    return;
  }

  p.plan = value;
  p.suggestion = null;
  p.approved = false;
  p.reviewer = '';

  p.edits.push({
    type: 'manual',
    at: new Date().toISOString()
  });

  p.updatedAt = new Date().toISOString();
  state.planTab = 'draft';

  closeDialog('editDialog');

  render();
  toast('Saved as an unapproved draft.');
}

function approvePlan(event) {
  event.preventDefault();

  const p = patient();

  if (
    !p ||
    !p.verified ||
    !p.plan.trim()
  ) {
    return;
  }

  const reviewer =
    byId('reviewerName').value.trim();

  if (reviewer.length < 2) {
    toast('Enter reviewer name.', true);
    return;
  }

  p.approved = true;
  p.reviewer = reviewer;

  closeDialog('approveDialog');

  render();

  toast(
    'Review recorded. ' +
    'This does not verify professional identity.'
  );
}

// ============================================================
// 14. PDF EXPORT
// ============================================================

async function exportPlan() {
  const p = patient();

  if (!p || !p.approved || state.busy) return;

  try {
    busy(true);

    const response = await api('/api/report', {
      method: 'POST',
      headers: {
        'Content-Type': 'application/json'
      },
      body: JSON.stringify({
        patient: p,
        plan: p.plan,
        reviewer: p.reviewer,
        approved: p.approved,
        demo_confirmed: true
      })
    });

    const objectUrl = URL.createObjectURL(
      await response.blob()
    );

    const safeName = p.name
      .replace(/[^A-Za-z0-9]+/g, '_')
      .slice(0, 46)
      .replace(/^_+|_+$/g, '') || 'Patient';

    const link = node('a');

    link.href = objectUrl;

    link.download =
      `${safeName}_Recommendation.pdf`;

    document.body.append(link);
    link.click();
    link.remove();

    setTimeout(
      () => URL.revokeObjectURL(objectUrl),
      1500
    );

    state.exports.unshift({
      file: link.download,
      date: new Date().toLocaleString()
    });

    toast('Report exported.');

  } catch (error) {
    toast(error.message, true);
  } finally {
    busy(false);
    render();
  }
}

// ============================================================
// 15. SECONDARY PAGES
// ============================================================

function createSecondary(title, intro) {
  const card = node('div', 'secondary-card');

  card.append(
    node('h1', '', title),
    node('p', '', intro)
  );

  byId('secondaryContent').replaceChildren(card);

  return card;
}

function renderSecondary() {
  if (state.view === 'exports') {
    const card = createSecondary(
      'Export history',
      'Exports recorded in this browser tab. ' +
      'Refreshing or closing the tab clears the list.'
    );

    if (!state.exports.length) {
      card.append(
        node(
          'div',
          'info-box',
          'No PDF exports yet.'
        )
      );
    }

    state.exports.forEach(item => {
      const entry = node('div', 'export-row');

      entry.append(
        node('span', '', item.file),
        node('small', '', item.date)
      );

      card.append(entry);
    });

  } else if (state.view === 'metrics') {
    const card = createSecondary(
      'AI evaluation',
      'Instance-local operational statistics, ' +
      'not measures of clinical correctness.'
    );

    const area = node('div', 'metric-grid');

    card.append(area);

    (async () => {
      try {
        const data = await (
          await api('/api/metrics')
        ).json();

        for (const [key, value] of Object.entries(
          data.requests || {}
        )) {
          const tile = node('div', 'metric-tile');

          tile.append(
            node('span', '', key.replace(/_/g, ' ')),
            node('strong', '', value)
          );

          area.append(tile);
        }

        for (const [key, value] of Object.entries(
          data.operations || {}
        )) {
          const tile = node('div', 'metric-tile');

          tile.append(
            node('span', '', `${key}: P95 latency`),
            node('strong', '', `${value.p95_ms} ms`)
          );

          area.append(tile);
        }

        if (!area.children.length) {
          area.append(
            node(
              'div',
              'info-box',
              'No requests measured yet.'
            )
          );
        }

      } catch (error) {
        area.textContent = error.message;
      }
    })();

    const benchmarkCard = createSecondary(
      'Retrieval benchmark',
      'Reproducible measurements on five fixed fictional questions. ' +
      'These scores measure source retrieval only, not clinical correctness or live AI responses.'
    );
    const benchmarkArea = node('div', 'metric-grid');
    benchmarkCard.append(benchmarkArea);
    (async () => {
      try {
        const benchmark = await (await api('/api/evaluation')).json();
        for (const [label, value] of [
          ['Precision@' + benchmark.k, benchmark.precision_at_k],
          ['Recall@' + benchmark.k, benchmark.recall_at_k],
          ['MRR', benchmark.mrr],
          ['Labelled questions', benchmark.cases]
        ]) {
          const tile = node('div', 'metric-tile');
          tile.append(node('span', '', label),
                      node('strong', '', String(value)));
          benchmarkArea.append(tile);
        }
        benchmarkCard.append(node('div', 'info-box',
          'Answer relevance and groundedness: not yet measured. ' +
          'See EVALUATION.md for the fixture, calculation and limitations.'));
      } catch (error) {
        benchmarkArea.textContent = error.message;
      }
    })();
    card.append(benchmarkCard);

    card.append(
      node(
        'div',
        'info-box',
        'Offline source-grounding and clinician-labelled ' +
        'evaluation are required. This workspace does not ' +
        'certify clinical safety.'
      )
    );
  }
}

function go(view) {
  state.view = view;
  render();
}

// ============================================================
// 16. CLOUDFLARE STATUS AND SIDEBAR
// ============================================================

async function checkHealth() {
  try {
    const response = await api('/api/health');
    const data = await response.json();

    state.aiConfigured = Boolean(
      data.ai_configured
    );

  } catch (error) {
    state.aiConfigured = false;
    toast(error.message, true);
  }

  render();
}

function toggleSidebar() {
  state.sidebarCollapsed = !state.sidebarCollapsed;

  document.body.classList.toggle(
    'sidebar-collapsed',
    state.sidebarCollapsed
  );

  const button = byId('sidebarToggle');

  button.textContent =
    state.sidebarCollapsed ? '›' : '‹';

  button.setAttribute(
    'aria-expanded',
    String(!state.sidebarCollapsed)
  );

  button.setAttribute(
    'aria-label',
    state.sidebarCollapsed
      ? 'Expand sidebar'
      : 'Collapse sidebar'
  );

  button.title = state.sidebarCollapsed
    ? 'Expand sidebar'
    : 'Collapse sidebar';
}

// ============================================================
// 17. EVENT LISTENERS
// ============================================================

function bindEvents() {

  // Sidebar and navigation.

  byId('sidebarToggle').addEventListener(
    'click',
    toggleSidebar
  );

  [
    'sidebarNew',
    'welcomeNew',
    'addMore'
  ].forEach(id => {
    byId(id).addEventListener('click', openUpload);
  });

  byId('loadDemo').addEventListener(
    'click',
    loadDemo
  );

  document.querySelectorAll('.nav-item').forEach(button => {
    button.title =
      button.querySelector('.nav-label')
        ?.textContent.trim() || '';

    button.addEventListener(
      'click',
      () => go(button.dataset.view)
    );
  });

  byId('backToWorkspace').addEventListener(
    'click',
    () => go('workspace')
  );

  // Dialog controls.

  ['closeUpload', 'cancelUpload'].forEach(id => {
    byId(id).addEventListener(
      'click',
      () => closeDialog('uploadDialog')
    );
  });

  ['closeEdit', 'cancelEdit'].forEach(id => {
    byId(id).addEventListener(
      'click',
      () => closeDialog('editDialog')
    );
  });

  ['closeApprove', 'cancelApprove'].forEach(id => {
    byId(id).addEventListener(
      'click',
      () => closeDialog('approveDialog')
    );
  });

  // Upload mode.

  document.querySelectorAll(
    'input[name="mode"]'
  ).forEach(input => {
    input.addEventListener('change', () => {
      selectUploadMode(input.value);
    });
  });

  // File selection.

  byId('fileInput').addEventListener(
    'change',
    event => {
      byId('fileLabel').textContent =
        event.target.files[0]?.name ||
        'Click to choose a file or drop it here';
    }
  );

  // Drag-and-drop upload.

  const dropzone = byId('dropzone');

  ['dragenter', 'dragover'].forEach(name => {
    dropzone.addEventListener(name, event => {
      event.preventDefault();
      dropzone.classList.add('dragging');
    });
  });

  ['dragleave', 'drop'].forEach(name => {
    dropzone.addEventListener(name, event => {
      event.preventDefault();
      dropzone.classList.remove('dragging');
    });
  });

  dropzone.addEventListener('drop', event => {
    if (!event.dataTransfer.files.length) return;

    byId('fileInput').files =
      event.dataTransfer.files;

    byId('fileLabel').textContent =
      event.dataTransfer.files[0].name;
  });

  // Upload submission.

  byId('uploadForm').addEventListener(
    'submit',
    async event => {
      event.preventDefault();

      const error = byId('uploadError');
      error.classList.add('hidden');

      const file = byId('fileInput').files[0];

      const mode = document.querySelector(
        'input[name="mode"]:checked'
      ).value;

      try {
        busy(true);

        const result = await parseUpload(
          file,
          mode,
          byId('syntheticConfirm').checked
        );

        closeDialog('uploadDialog');

        initializeAssessment(
          result,
          mode,
          file.name
        );

      } catch (exception) {
        error.textContent = exception.message;
        error.classList.remove('hidden');

      } finally {
        busy(false);
      }
    }
  );

  // Evidence tabs.

  document.querySelectorAll(
    '#evidenceTabs .tab'
  ).forEach(tab => {
    tab.addEventListener('click', () => {
      state.evidenceTab = tab.dataset.tab;
      renderEvidence();
    });
  });

  // Nutrition plan tabs.

  document.querySelectorAll(
    '#planTabs .tab'
  ).forEach(tab => {
    tab.addEventListener('click', () => {
      state.planTab = tab.dataset.tab;
      renderPlan();
    });
  });

  // Verify extracted facts.

  byId('verifyBtn').addEventListener(
    'click',
    () => {
      const p = patient();

      if (!p || state.busy) return;

      const confirmed = window.confirm(
        `Have you checked ${p.name}'s extracted facts ` +
        'against the original synthetic record?'
      );

      if (!confirmed) return;

      p.verified = true;

      render();

      toast(
        'Extracted facts marked verified.'
      );
    }
  );

  // Nutrition plan actions.

  byId('generateBtn').addEventListener(
    'click',
    generateDraft
  );

  byId('editPlanBtn').addEventListener(
    'click',
    openEdit
  );

  byId('planEditor').maxLength = 12000;

  byId('editForm').addEventListener(
    'submit',
    savePlan
  );

  byId('approveBtn').addEventListener(
    'click',
    () => {
      const p = patient();

      if (
        !p ||
        !p.verified ||
        !p.plan.trim()
      ) {
        return;
      }

      byId('approveForm').reset();
      showDialog('approveDialog');
    }
  );

  byId('approveForm').addEventListener(
    'submit',
    approvePlan
  );

  byId('exportBtn').addEventListener(
    'click',
    exportPlan
  );

  // AI copilot.

  byId('chatForm').addEventListener(
    'submit',
    sendMessage
  );

  // Discard proposed revision.

  byId('discardSuggestion').addEventListener(
    'click',
    () => {
      if (patient()) {
        patient().suggestion = null;
      }

      renderChat();
    }
  );

  // Apply only the proposed passage replacement.

  byId('applySuggestion').addEventListener(
    'click',
    () => {
      const p = patient();

      if (!p?.suggestion || state.busy) return;

      const {
        old_text: oldText,
        new_text: newText
      } = p.suggestion;

      // The original passage must still exist
      // exactly once in the current report.

      if (
        !oldText ||
        p.plan.split(oldText).length !== 2
      ) {
        p.suggestion = null;
        renderChat();

        toast(
          'The original passage changed. ' +
          'Request a new revision.',
          true
        );

        return;
      }

      const updated = p.plan.replace(
        oldText,
        newText
      );

      if (updated.length > 12000) {
        toast(
          'The revision exceeds the report length limit.',
          true
        );

        return;
      }

      p.plan = updated;

      p.edits.push({
        type: 'copilot',
        at: new Date().toISOString()
      });

      p.suggestion = null;

      // Any change requires a fresh review.

      p.approved = false;
      p.reviewer = '';
      p.updatedAt = new Date().toISOString();

      state.planTab = 'draft';

      render();

      toast(
        'Only the selected passage was replaced. ' +
        'The revised report needs fresh review.'
      );
    }
  );
}

// ============================================================
// 18. APPLICATION STARTUP
// ============================================================

bindEvents();
checkHealth();