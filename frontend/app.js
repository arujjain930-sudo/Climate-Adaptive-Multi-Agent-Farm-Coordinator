/* ============================================================
   Climate-Adaptive Multi-Agent Farm Coordinator — App Logic
   ============================================================ */

(function () {
  'use strict';

  // ── Constants ──────────────────────────────────────────────
  const API_BASE = window.location.hostname === '' || window.location.protocol === 'file:'
    ? 'http://localhost:8000'
    : '';
  const ANALYZE_URL = `${API_BASE}/api/analyze`;
  const SAMPLE_URL  = `${API_BASE}/api/sample`;

  // ── DOM References ─────────────────────────────────────────
  const $ = (sel) => document.querySelector(sel);
  const $$ = (sel) => document.querySelectorAll(sel);

  const form             = $('#analysis-form');
  const locationInput    = $('#location-input');
  const cropSelect       = $('#crop-select');
  const goalSelect       = $('#goal-select');
  const notesInput       = $('#notes-input');
  const sampleBtn        = $('#sample-btn');
  const runBtn           = $('#run-btn');
  const runSpinner       = $('#run-spinner');
  const errorAlert       = $('#error-alert');
  const errorMessage     = $('#error-message');
  const errorDismissBtn  = $('#error-dismiss-btn');

  const progressSection  = $('#progress-section');
  const resultsSection   = $('#results-section');
  const pipelineProgressBar = $('#pipeline-progress-bar');

  // Agent step elements
  const agentWeather     = $('#agent-weather');
  const agentSoil        = $('#agent-soil');
  const agentCrop        = $('#agent-crop');
  const weatherStatusTxt = $('#weather-status-text');
  const soilStatusTxt    = $('#soil-status-text');
  const cropStatusTxt    = $('#crop-status-text');
  const connector1       = $('#connector-1');
  const connector2       = $('#connector-2');

  // Result elements
  const summaryCard       = $('#summary-card');
  const summaryHeadline   = $('#summary-headline');
  const riskBadge         = $('#risk-badge');
  const urgencyIndicator  = $('#urgency-indicator');
  const confidenceFill    = $('#confidence-fill');
  const confidenceValue   = $('#confidence-value');
  const recommendationTxt = $('#recommendation-text');
  const detailCards       = $('#detail-cards');
  const weatherBody       = $('#weather-body');
  const soilBody          = $('#soil-body');
  const actionBody        = $('#action-body');
  const scheduleSection   = $('#schedule-section');
  const scheduleTimeline  = $('#schedule-timeline');
  const runAgainBtn       = $('#run-again-btn');

  // ── Utility: sanitize text ─────────────────────────────────
  function sanitize(str) {
    if (typeof str !== 'string') return '';
    const div = document.createElement('div');
    div.textContent = str;
    return div.innerHTML;
  }

  // ── Utility: set text safely ───────────────────────────────
  function setText(el, text) {
    if (el) el.textContent = text != null ? String(text) : '';
  }

  // ── Utility: smooth scroll ─────────────────────────────────
  function scrollTo(el) {
    if (el) el.scrollIntoView({ behavior: 'smooth', block: 'start' });
  }

  // ── Utility: sleep ─────────────────────────────────────────
  function sleep(ms) {
    return new Promise((resolve) => setTimeout(resolve, ms));
  }

  // ── Utility: trigger fade-in-up animation ──────────────────
  function animateIn(el) {
    if (el) {
      el.classList.remove('visible');
      // Force reflow
      void el.offsetWidth;
      el.classList.add('visible');
    }
  }

  // ── Validation ─────────────────────────────────────────────
  function validateForm() {
    let valid = true;

    // Location
    const locGroup = $('#location-group');
    const locError = $('#location-error');
    const locVal = locationInput.value.trim();

    if (!locVal) {
      locGroup.classList.add('has-error');
      locationInput.classList.add('has-error');
      setText(locError, 'Location is required for weather analysis');
      valid = false;
    } else if (locVal.length < 2) {
      locGroup.classList.add('has-error');
      locationInput.classList.add('has-error');
      setText(locError, 'Please enter a valid location (at least 2 characters)');
      valid = false;
    } else {
      locGroup.classList.remove('has-error');
      locationInput.classList.remove('has-error');
      setText(locError, '');
    }

    // Crop
    const cropGroup = $('#crop-group');
    const cropError = $('#crop-error');
    const cropVal = cropSelect.value;

    if (!cropVal) {
      cropGroup.classList.add('has-error');
      cropSelect.classList.add('has-error');
      setText(cropError, 'Please select a crop type');
      valid = false;
    } else {
      cropGroup.classList.remove('has-error');
      cropSelect.classList.remove('has-error');
      setText(cropError, '');
    }

    return valid;
  }

  // ── Clear validation errors ────────────────────────────────
  function clearValidation() {
    $$('.form-group').forEach((g) => g.classList.remove('has-error'));
    $$('.form-control').forEach((c) => c.classList.remove('has-error'));
    $$('.form-error').forEach((e) => setText(e, ''));
  }

  // ── Show / Hide Error Alert ────────────────────────────────
  function showError(msg) {
    setText(errorMessage, msg || 'An unexpected error occurred. Please check your connection and try again.');
    errorAlert.hidden = false;
    scrollTo(errorAlert);
  }

  function hideError() {
    errorAlert.hidden = true;
  }

  // ── Loading State ──────────────────────────────────────────
  function setLoading(on) {
    if (on) {
      runBtn.disabled = true;
      runBtn.classList.add('btn--loading');
      sampleBtn.disabled = true;
    } else {
      runBtn.disabled = false;
      runBtn.classList.remove('btn--loading');
      sampleBtn.disabled = false;
    }
  }

  // ── Agent Progress ─────────────────────────────────────────
  function setAgentStatus(agentEl, statusTextEl, status, text) {
    agentEl.setAttribute('data-status', status);
    setText(statusTextEl, text);
  }

  function setPipelineProgress(pct) {
    if (pipelineProgressBar) {
      pipelineProgressBar.style.width = `${pct}%`;
    }
  }

  function resetAgents() {
    setAgentStatus(agentWeather, weatherStatusTxt, 'pending', 'Pending');
    setAgentStatus(agentSoil, soilStatusTxt, 'pending', 'Pending');
    setAgentStatus(agentCrop, cropStatusTxt, 'pending', 'Pending');
    connector1.classList.remove('active');
    connector2.classList.remove('active');
    if (pipelineProgressBar) {
      pipelineProgressBar.style.width = '0%';
      pipelineProgressBar.classList.remove('error');
    }
  }

  async function simulateAgentProgress() {
    setPipelineProgress(15);
    // Step 1: Weather & Soil start simultaneously
    setAgentStatus(agentWeather, weatherStatusTxt, 'running', 'Analyzing weather...');
    setAgentStatus(agentSoil, soilStatusTxt, 'running', 'Analyzing soil...');

    await sleep(1200);

    // Weather completes first
    setAgentStatus(agentWeather, weatherStatusTxt, 'complete', 'Complete');
    connector1.classList.add('active');
    setPipelineProgress(50);

    await sleep(800);

    // Soil completes
    setAgentStatus(agentSoil, soilStatusTxt, 'complete', 'Complete');
    setPipelineProgress(75);

    await sleep(400);

    // Step 2: Crop Action Agent starts
    connector2.classList.add('active');
    setAgentStatus(agentCrop, cropStatusTxt, 'running', 'Generating plan...');
    setPipelineProgress(85);

    await sleep(1000);

    // Crop completes
    setAgentStatus(agentCrop, cropStatusTxt, 'complete', 'Complete');
    setPipelineProgress(100);

    await sleep(300);
  }

  function setAgentsError() {
    ['agent-weather', 'agent-soil', 'agent-crop'].forEach((id) => {
      const el = $(`#${id}`);
      const status = el.getAttribute('data-status');
      if (status === 'running' || status === 'pending') {
        const textEl = el.querySelector('.agent-status-text');
        setAgentStatus(el, textEl, 'error', 'Error');
      }
    });
    if (pipelineProgressBar) {
      pipelineProgressBar.classList.add('error');
    }
  }

  // ── Render Results ─────────────────────────────────────────

  function renderSummary(data) {
    // Headline
    const headline = data.summary || data.headline || data.overall_summary || 'Analysis complete. Review detailed results below.';
    setText(summaryHeadline, headline);
    // Add shimmer reveal class to headline
    summaryHeadline.classList.remove('text-reveal');
    void summaryHeadline.offsetWidth;
    summaryHeadline.classList.add('text-reveal');

    // Risk level — dynamic color class based on data
    const risk = (data.risk_level || data.overall_risk_level || 'MODERATE').toUpperCase();
    setText(riskBadge, risk);
    riskBadge.className = 'risk-badge';
    if (risk === 'LOW')            riskBadge.classList.add('risk-low');
    else if (risk === 'MODERATE')  riskBadge.classList.add('risk-moderate');
    else if (risk === 'HIGH')      riskBadge.classList.add('risk-high');
    else if (risk === 'CRITICAL')  riskBadge.classList.add('risk-critical');
    else                           riskBadge.classList.add('risk-moderate');
    // Trigger bounce-in animation for the badge
    riskBadge.classList.add('risk-badge-bounce');

    // Urgency
    const urgency = data.urgency || data.urgency_level || 'Normal';
    setText(urgencyIndicator, urgency);

    // Confidence — animate fill with CSS transition (starts from 0)
    const confidence = data.confidence_score ?? data.confidence ?? 75;
    const confPct = Math.min(100, Math.max(0, Number(confidence)));
    confidenceFill.style.width = '0%';
    // Force reflow so the browser registers the 0% width before animating
    void confidenceFill.offsetWidth;
    confidenceFill.classList.add('confidence-fill-animate');
    confidenceFill.style.width = `${confPct}%`;
    setText(confidenceValue, `${confPct}%`);

    // Recommendation
    const rec = data.key_recommendation || data.recommendation || data.primary_recommendation || 'Follow the detailed action plan below.';
    setText(recommendationTxt, rec);
  }

  function buildDetailItems(obj) {
    const frag = document.createDocumentFragment();

    if (typeof obj === 'string') {
      // Plain text — split by line
      const lines = obj.split('\n').filter((l) => l.trim());
      lines.forEach((line) => {
        const p = document.createElement('p');
        p.className = 'detail-item-value';
        p.textContent = line;
        p.style.marginBottom = '8px';
        frag.appendChild(p);
      });
      return frag;
    }

    if (typeof obj === 'object' && obj !== null) {
      const entries = Array.isArray(obj)
        ? obj.map((v, i) => [`Item ${i + 1}`, v])
        : Object.entries(obj);

      entries.forEach(([key, val]) => {
        const div = document.createElement('div');
        div.className = 'detail-item';

        const label = document.createElement('div');
        label.className = 'detail-item-label';
        label.textContent = formatLabel(key);
        div.appendChild(label);

        const value = document.createElement('div');
        value.className = 'detail-item-value';

        if (typeof val === 'object' && val !== null) {
          value.textContent = Array.isArray(val)
            ? val.map((v) => (typeof v === 'string' ? v : JSON.stringify(v))).join(', ')
            : JSON.stringify(val, null, 2);
        } else {
          value.textContent = String(val);
        }

        div.appendChild(value);
        frag.appendChild(div);
      });
    }

    return frag;
  }

  function formatLabel(key) {
    return String(key)
      .replace(/[_-]/g, ' ')
      .replace(/\b\w/g, (c) => c.toUpperCase());
  }

  function renderWeather(data) {
    weatherBody.innerHTML = '';
    const weather = data.weather_analysis || data.weather || data.weather_data || null;

    if (!weather) {
      const p = document.createElement('p');
      p.className = 'detail-placeholder';
      p.textContent = 'No weather data available.';
      weatherBody.appendChild(p);
      return;
    }

    weatherBody.appendChild(buildDetailItems(weather));
  }

  function renderSoil(data) {
    soilBody.innerHTML = '';
    const soil = data.soil_analysis || data.soil || data.soil_data || null;

    if (!soil) {
      const p = document.createElement('p');
      p.className = 'detail-placeholder';
      p.textContent = 'No soil data available.';
      soilBody.appendChild(p);
      return;
    }

    soilBody.appendChild(buildDetailItems(soil));
  }

  function renderActions(data) {
    actionBody.innerHTML = '';
    const actions = data.crop_action_plan || data.action_plan || data.crop_actions || data.actions || null;

    if (!actions) {
      const p = document.createElement('p');
      p.className = 'detail-placeholder';
      p.textContent = 'No action plan available.';
      actionBody.appendChild(p);
      return;
    }

    actionBody.appendChild(buildDetailItems(actions));
  }

  function renderSchedule(data) {
    scheduleTimeline.innerHTML = '';

    // Check for weekly_schedule inside crop_action_plan first
    const actionPlan = data.crop_action_plan || data.action_plan || null;
    const weeklySchedule = actionPlan && typeof actionPlan === 'object'
      ? (actionPlan.weekly_schedule || null)
      : null;

    const schedule = weeklySchedule || data.schedule || data.action_schedule || data.daily_schedule || null;

    if (!schedule) {
      // Build a default 3-day schedule from action plan
      renderDefaultSchedule(data);
      applyScheduleStagger();
      return;
    }

    if (Array.isArray(schedule)) {
      schedule.forEach((day, idx) => {
        const dayEl = buildScheduleDay(day, idx);
        scheduleTimeline.appendChild(dayEl);
      });
    } else if (typeof schedule === 'object') {
      const entries = Object.entries(schedule);
      entries.forEach(([dayLabel, tasks], idx) => {
        const dayEl = buildScheduleDayFromEntry(dayLabel, tasks, idx);
        scheduleTimeline.appendChild(dayEl);
      });
    } else if (typeof schedule === 'string') {
      renderDefaultScheduleFromText(schedule);
    }

    applyScheduleStagger();
  }

  // Apply staggered slide-in animation to each schedule day card
  function applyScheduleStagger() {
    const dayCards = scheduleTimeline.querySelectorAll('.schedule-day');
    dayCards.forEach((card, idx) => {
      card.classList.add('schedule-day-stagger');
      card.style.animationDelay = `${idx * 0.15}s`;
    });
  }

  function buildScheduleDay(day, idx) {
    const el = document.createElement('div');
    el.className = 'schedule-day fade-in-up';

    const header = document.createElement('div');
    header.className = 'schedule-day-header';
    header.textContent = day.day || day.label || day.title || `Day ${idx + 1}`;
    el.appendChild(header);

    const body = document.createElement('div');
    body.className = 'schedule-day-body';

    const tasks = day.tasks || day.actions || day.activities || [];
    if (Array.isArray(tasks)) {
      tasks.forEach((task) => {
        const taskEl = document.createElement('div');
        taskEl.className = 'schedule-task';

        const timeEl = document.createElement('span');
        timeEl.className = 'schedule-time';
        timeEl.textContent = task.time || task.period || '';

        const textEl = document.createElement('span');
        textEl.className = 'schedule-task-text';
        textEl.textContent = typeof task === 'string' ? task : (task.action || task.description || task.task || JSON.stringify(task));

        taskEl.appendChild(timeEl);
        taskEl.appendChild(textEl);
        body.appendChild(taskEl);
      });
    } else if (typeof tasks === 'string') {
      const taskEl = document.createElement('div');
      taskEl.className = 'schedule-task';
      const textEl = document.createElement('span');
      textEl.className = 'schedule-task-text';
      textEl.textContent = tasks;
      taskEl.appendChild(textEl);
      body.appendChild(taskEl);
    }

    el.appendChild(body);
    return el;
  }

  function buildScheduleDayFromEntry(dayLabel, tasks, idx) {
    let tasksArray = [];
    let focusLabel = '';
    
    if (tasks && typeof tasks === 'object' && !Array.isArray(tasks)) {
      if (tasks.focus) {
        focusLabel = ` (${tasks.focus})`;
      }
      const potentialTasks = tasks.tasks || tasks.actions || tasks.activities;
      if (Array.isArray(potentialTasks)) {
        tasksArray = potentialTasks;
      } else if (typeof potentialTasks === 'string') {
        tasksArray = [potentialTasks];
      }
    } else if (Array.isArray(tasks)) {
      tasksArray = tasks;
    } else if (typeof tasks === 'string') {
      tasksArray = [tasks];
    }

    const day = {
      day: formatLabel(dayLabel) + focusLabel,
      tasks: tasksArray,
    };
    return buildScheduleDay(day, idx);
  }

  function renderDefaultSchedule(data) {
    const actions = data.crop_action_plan || data.action_plan || data.actions || {};
    const rec = data.key_recommendation || data.recommendation || '';

    const days = [
      {
        day: 'Day 1 — Immediate',
        tasks: [
          { time: 'Morning', action: rec || 'Review analysis results and prepare materials' },
          { time: 'Afternoon', action: 'Begin implementing primary recommendations' },
          { time: 'Evening', action: 'Monitor weather conditions and adjust plans' },
        ],
      },
      {
        day: 'Day 2 — Implementation',
        tasks: [
          { time: 'Morning', action: 'Continue field preparation and treatment application' },
          { time: 'Afternoon', action: 'Check soil moisture levels and irrigation needs' },
          { time: 'Evening', action: 'Record observations and update action plan' },
        ],
      },
      {
        day: 'Day 3 — Monitoring',
        tasks: [
          { time: 'Morning', action: 'Inspect crops for changes and response to actions' },
          { time: 'Afternoon', action: 'Adjust irrigation and nutrient management as needed' },
          { time: 'Evening', action: 'Plan next analysis cycle based on observations' },
        ],
      },
    ];

    days.forEach((d, i) => {
      scheduleTimeline.appendChild(buildScheduleDay(d, i));
    });
  }

  function renderDefaultScheduleFromText(text) {
    const lines = text.split('\n').filter((l) => l.trim());
    const chunkSize = Math.ceil(lines.length / 3);

    for (let i = 0; i < 3; i++) {
      const chunk = lines.slice(i * chunkSize, (i + 1) * chunkSize);
      const day = {
        day: `Day ${i + 1}`,
        tasks: chunk.map((l) => ({ time: '', action: l.trim() })),
      };
      scheduleTimeline.appendChild(buildScheduleDay(day, i));
    }
  }

  function showResults(data) {
    renderSummary(data);
    renderWeather(data);
    renderSoil(data);
    renderActions(data);
    renderSchedule(data);

    resultsSection.hidden = false;

    // Animate cards
    requestAnimationFrame(() => {
      animateIn(summaryCard);

      setTimeout(() => {
        $$('#detail-cards .fade-in-up').forEach((el) => animateIn(el));
      }, 300);

      setTimeout(() => {
        animateIn($('#schedule-section'));
        $$('#schedule-timeline .schedule-day').forEach((el) => animateIn(el));
      }, 600);

      setTimeout(() => {
        scrollTo(summaryCard);
      }, 100);
    });
  }

  function hideResults() {
    resultsSection.hidden = true;
    // Reset animations
    $$('.fade-in-up').forEach((el) => el.classList.remove('visible'));
  }

  // ── API Call ───────────────────────────────────────────────

  async function runAnalysis() {
    clearValidation();
    hideError();

    if (!validateForm()) return;

    const payload = {
      location: locationInput.value.trim(),
      crop_type: cropSelect.value,
      farming_goal: goalSelect.value || 'General Guidance',
      notes: notesInput.value.trim(),
    };

    setLoading(true);
    hideResults();
    resetAgents();
    setPipelineProgress(5);
    progressSection.hidden = false;
    scrollTo(progressSection);

    // Start agent animation & API call in parallel
    const [_, response] = await Promise.allSettled([
      simulateAgentProgress(),
      fetchAnalysis(payload),
    ]);

    setLoading(false);

    if (response.status === 'fulfilled' && response.value.ok) {
      const data = response.value.data;
      // Ensure all agents show complete
      setAgentStatus(agentWeather, weatherStatusTxt, 'complete', 'Complete');
      setAgentStatus(agentSoil, soilStatusTxt, 'complete', 'Complete');
      setAgentStatus(agentCrop, cropStatusTxt, 'complete', 'Complete');
      connector1.classList.add('active');
      connector2.classList.add('active');

      await sleep(400);
      showResults(data);
    } else {
      setAgentsError();
      const errMsg = response.status === 'fulfilled'
        ? response.value.error
        : 'Network error. Please check your connection and ensure the backend server is running on port 8000.';
      showError(errMsg);
    }
  }

  async function fetchAnalysis(payload) {
    try {
      const res = await fetch(ANALYZE_URL, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify(payload),
      });

      if (!res.ok) {
        let errText = `Server error (${res.status})`;
        try {
          const errData = await res.json();
          errText = errData.detail || errData.message || errData.error || errText;
        } catch {
          // ignore parse error
        }
        return { ok: false, error: errText };
      }

      const data = await res.json();
      return { ok: true, data };
    } catch (err) {
      return {
        ok: false,
        error: `Unable to connect to the analysis server. Please ensure the backend is running at ${API_BASE}. (${err.message})`,
      };
    }
  }

  // ── Sample Data ────────────────────────────────────────────

  async function loadSampleData() {
    try {
      const res = await fetch(SAMPLE_URL);
      if (res.ok) {
        const data = await res.json();
        // data could be {samples: [...]} or a direct object
        if (data.samples && Array.isArray(data.samples)) {
          const randomIdx = Math.floor(Math.random() * data.samples.length);
          fillSampleData(data.samples[randomIdx]);
        } else {
          fillSampleData(data);
        }
        return;
      }
    } catch {
      // API unavailable, use fallback
    }

    // Fallback sample data
    fillSampleData({
      location: 'Pune, Maharashtra, India',
      crop_type: 'Rice',
      farming_goal: 'Water Conservation',
      notes: 'Monsoon season approaching, clay-loam soil, limited irrigation infrastructure.',
    });
  }

  function fillSampleData(data) {
    clearValidation();

    if (data.location) locationInput.value = data.location;

    if (data.crop_type) {
      const option = Array.from(cropSelect.options).find(
        (o) => o.value.toLowerCase() === data.crop_type.toLowerCase()
      );
      if (option) cropSelect.value = option.value;
    }

    if (data.farming_goal) {
      const option = Array.from(goalSelect.options).find(
        (o) => o.value.toLowerCase() === data.farming_goal.toLowerCase()
      );
      if (option) goalSelect.value = option.value;
    }

    if (data.notes) notesInput.value = data.notes;

    // Visual feedback — briefly highlight form
    const formEl = form;
    formEl.style.transition = 'box-shadow 0.3s ease';
    formEl.style.boxShadow = '0 0 0 3px rgba(218,165,32,0.3), 0 4px 12px rgba(27,67,50,0.08)';
    setTimeout(() => {
      formEl.style.boxShadow = '';
    }, 1200);
  }

  // ── Event Handlers ─────────────────────────────────────────

  function triggerLandingAnimations() {
    const headerEl = $('#site-header');
    const inputEl = $('#input-section');
    if (headerEl) headerEl.classList.add('animate-header');
    if (inputEl) inputEl.classList.add('animate-form');

    const p1 = $('.particle--1');
    const p2 = $('.particle--2');
    const p3 = $('.particle--3');
    if (p1) p1.classList.add('animate-particle-1');
    if (p2) p2.classList.add('animate-particle-2');
    if (p3) p3.classList.add('animate-particle-3');
  }

  function init() {
    document.body.classList.add('js-loaded');
    triggerLandingAnimations();

    // Form submit
    form.addEventListener('submit', (e) => {
      e.preventDefault();
      runAnalysis();
    });

    // Sample data button
    sampleBtn.addEventListener('click', () => {
      loadSampleData();
    });

    // Dismiss error
    errorDismissBtn.addEventListener('click', () => {
      hideError();
    });

    // Run again button
    runAgainBtn.addEventListener('click', () => {
      hideResults();
      progressSection.hidden = true;
      resetAgents();
      scrollTo($('#input-section'));
    });

    // Clear validation on input
    locationInput.addEventListener('input', () => {
      const group = $('#location-group');
      if (group.classList.contains('has-error')) {
        group.classList.remove('has-error');
        locationInput.classList.remove('has-error');
        setText($('#location-error'), '');
      }
    });

    cropSelect.addEventListener('change', () => {
      const group = $('#crop-group');
      if (group.classList.contains('has-error')) {
        group.classList.remove('has-error');
        cropSelect.classList.remove('has-error');
        setText($('#crop-error'), '');
      }
    });

    // Intersection observer for architecture section animation
    if ('IntersectionObserver' in window) {
      const observer = new IntersectionObserver(
        (entries) => {
          entries.forEach((entry) => {
            if (entry.isIntersecting) {
              entry.target.style.opacity = '1';
              entry.target.style.transform = 'translateY(0)';
            }
          });
        },
        { threshold: 0.1 }
      );

      $$('.arch-node, .arch-parallel-group').forEach((node) => {
        node.style.opacity = '0';
        node.style.transform = 'translateY(16px)';
        node.style.transition = 'opacity 0.5s ease, transform 0.5s ease';
        observer.observe(node);
      });
    }
  }

  // ── Boot ───────────────────────────────────────────────────
  if (document.readyState === 'loading') {
    document.addEventListener('DOMContentLoaded', init);
  } else {
    init();
  }
})();
