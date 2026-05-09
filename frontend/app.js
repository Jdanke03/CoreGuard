const state = {
  apiBase: localStorage.getItem("coreguard.apiBase") || "http://127.0.0.1:8000",
  token: localStorage.getItem("coreguard.token") || "",
  user: JSON.parse(localStorage.getItem("coreguard.user") || "null"),
  dashboard: null,
  actions: null,
  plans: [],
  sessions: [],
  exercises: [],
  demo: false,
};

const $ = (selector) => document.querySelector(selector);
const els = {
  apiStatus: $("#apiStatus"), apiBaseLabel: $("#apiBaseLabel"), loginPanel: $("#loginPanel"), loginForm: $("#loginForm"), loginError: $("#loginError"), appContent: $("#appContent"), logoutButton: $("#logoutButton"), demoModeButton: $("#demoModeButton"), pageTitle: $("#pageTitle"), roleLabel: $("#roleLabel"), heroTitle: $("#heroTitle"), heroText: $("#heroText"), metricsGrid: $("#metricsGrid"), actionList: $("#actionList"), actionCount: $("#actionCount"), feedbackDonut: $("#feedbackDonut"), feedbackLegend: $("#feedbackLegend"), plansList: $("#plansList"), analysisList: $("#analysisList"), ruleBars: $("#ruleBars"), exerciseGrid: $("#exerciseGrid"), refreshButton: $("#refreshButton"),
};

const demoData = {
  user: { username: "demo_physio", role: "physio", email: "physio@coreguard.local" },
  dashboard: { role: "physio", metrics: { clients: 8, active_plans: 21, awaiting_review: 6, feedback_sent: 34 } },
  actions: { role: "physio", actions: [
    { type: "review_analysis", title: "Review Amy's squat session", description: "15 flagged frames are waiting for clinical feedback.", priority: "high", object_type: "analysis_session", object_id: 42 },
    { type: "review_analysis", title: "Review Ben's knee control check", description: "The client completed live analysis this morning.", priority: "medium", object_type: "analysis_session", object_id: 43 },
  ], summary: { clients: 8, active_plans: 21, awaiting_review: 6, feedback_sent: 34 } },
  plans: [
    { id: 1, name: "Knee Control Programme", description: "Build squat control, quad endurance, and confidence with loaded movement.", duration_weeks: 6, requires_analysis: true, client_username: "amy_client", prescriptions: [{ id: 1, sets: 3, reps: 10, exercise: { name: "Squat", body_area: "Legs" } }, { id: 2, sets: 3, reps: 30, exercise: { name: "Wall Sit", body_area: "Legs" } }] },
    { id: 2, name: "Shoulder Stability Programme", description: "Improve shoulder control, upper-back strength, and daily movement tolerance.", duration_weeks: 8, requires_analysis: false, client_username: "ben_client", prescriptions: [{ id: 3, sets: 3, reps: 8, exercise: { name: "Shoulder Press", body_area: "Shoulder" } }] },
  ],
  sessions: [
    { id: 1, client_username: "amy_client", plan_name: "Knee Control Programme", exercise_name: "Squat", total_frames: 240, flagged_frames: 15, feedback_shared: true, summary_metrics: { rules: { knee_valgus: 3, shallow_depth: 8, forward_lean: 4 }, angles: { knee_avg: 96.4, hip_avg: 72.1 } } },
    { id: 2, client_username: "ben_client", plan_name: "Shoulder Stability Programme", exercise_name: "Shoulder Press", total_frames: 180, flagged_frames: 4, feedback_shared: false, summary_metrics: { rules: { control: 4 }, angles: { shoulder_avg: 82.3 } } },
  ],
  exercises: [
    { id: 1, name: "Squat", body_area: "Legs", difficulty: "Easy", description: "Controlled lower-body movement for knee and hip strength." },
    { id: 2, name: "Wall Sit", body_area: "Legs", difficulty: "Medium", description: "Hold a seated position against a wall to build quad endurance." },
    { id: 3, name: "Resistance Band Row", body_area: "Back", difficulty: "Medium", description: "Pull the band towards the body while keeping shoulders controlled." },
    { id: 4, name: "Calf Raise", body_area: "Ankle", difficulty: "Easy", description: "Rise onto the toes and lower with control." },
    { id: 5, name: "Shoulder Press", body_area: "Shoulder", difficulty: "Medium", description: "Press upward while keeping the trunk stable." },
  ],
};

function normaliseList(payload) { return Array.isArray(payload) ? payload : payload?.results || []; }
function formatNumber(value) { return new Intl.NumberFormat("en-GB").format(value || 0); }
function emptyState(message) { return `<div class="empty-state"><span></span><strong>No data yet</strong><p>${message}</p></div>`; }
function setApiStatus(text, online) { els.apiStatus.textContent = text; els.apiStatus.style.color = online ? "#c9f36f" : "#ffb29f"; els.apiBaseLabel.textContent = state.apiBase; }

async function apiFetch(path, options = {}) {
  const headers = new Headers(options.headers || {});
  headers.set("Accept", "application/json");
  if (!(options.body instanceof FormData)) headers.set("Content-Type", "application/json");
  if (state.token) headers.set("Authorization", `Token ${state.token}`);
  const response = await fetch(`${state.apiBase}${path}`, { ...options, headers });
  if (!response.ok) throw new Error(await response.text() || `Request failed with ${response.status}`);
  return response.status === 204 ? null : response.json();
}

async function login(event) {
  event.preventDefault();
  els.loginError.textContent = "";
  const form = new FormData(event.currentTarget);
  state.apiBase = form.get("apiBase").replace(/\/$/, "");
  try {
    const payload = await apiFetch("/api/auth/login/", { method: "POST", body: JSON.stringify({ username: form.get("username"), password: form.get("password") }) });
    state.token = payload.token; state.user = payload.user; state.demo = false;
    localStorage.setItem("coreguard.apiBase", state.apiBase); localStorage.setItem("coreguard.token", state.token); localStorage.setItem("coreguard.user", JSON.stringify(state.user));
    await loadData();
  } catch (error) {
    els.loginError.textContent = "Could not sign in. Check Django is running and CORS is configured.";
    setApiStatus("Offline", false); console.error(error);
  }
}

async function logout() {
  try { if (state.token && !state.demo) await apiFetch("/api/auth/logout/", { method: "POST" }); } catch (error) { console.warn(error); }
  state.token = ""; state.user = null; state.demo = false;
  localStorage.removeItem("coreguard.token"); localStorage.removeItem("coreguard.user"); renderLoggedOut();
}

async function loadData() {
  setApiStatus("Loading", true);
  const [dashboard, actions, plans, sessions, exercises] = await Promise.all([
    apiFetch("/api/dashboard/"), apiFetch("/api/actions/"), apiFetch("/api/plans/"), apiFetch("/api/analysis-sessions/"), apiFetch("/api/exercises/"),
  ]);
  Object.assign(state, { dashboard, actions, plans: normaliseList(plans), sessions: normaliseList(sessions), exercises: normaliseList(exercises), demo: false });
  setApiStatus("Connected", true); renderApp();
}

function useDemoMode() { Object.assign(state, demoData, { demo: true }); setApiStatus("Demo mode", true); renderApp(); }
function renderLoggedOut() { els.loginPanel.hidden = false; els.appContent.hidden = true; els.logoutButton.hidden = true; els.pageTitle.textContent = "Your rehab command centre"; setApiStatus("Waiting", false); }

function renderApp() {
  els.loginPanel.hidden = true; els.appContent.hidden = false; els.logoutButton.hidden = state.demo;
  const role = state.dashboard?.role || state.user?.role || "client"; const username = state.user?.username || "there";
  els.pageTitle.textContent = role === "physio" ? "Clinical review workspace" : "Your rehab command centre";
  els.roleLabel.textContent = role === "physio" ? "Physiotherapist workspace" : "Client workspace";
  els.heroTitle.textContent = role === "physio" ? `Welcome back, ${username}` : `Ready when you are, ${username}`;
  els.heroText.textContent = role === "physio" ? "Review movement sessions, prioritise client feedback, and keep rehabilitation plans moving without digging through raw tables." : "See your latest plan, understand the next step, and keep your physiotherapist updated from one calm workspace.";
  renderMetrics(role); renderActions(); renderFeedbackChart(role); renderPlans(); renderAnalysis(); renderExercises(); updateActiveNav();
}

function renderMetrics(role) {
  const metrics = state.dashboard?.metrics || state.actions?.summary || {};
  const items = role === "physio" ? [["Clients", metrics.clients, "Distinct clients under your care."], ["Active plans", metrics.active_plans, "Current programmes being followed."], ["Awaiting review", metrics.awaiting_review, "Analysis sessions needing feedback."], ["Feedback sent", metrics.feedback_sent, "Completed review loops."]] : [["Active plans", metrics.active_plans, "Plans assigned by your physio."], ["Sessions logged", metrics.sessions_logged, "Progress updates recorded."], ["Analyses", metrics.analyses_completed, "Movement checks completed."], ["Feedback ready", metrics.feedback_ready, "Reviews shared by your physio."]];
  els.metricsGrid.innerHTML = items.map(([label, value, description]) => `<article class="metric-card"><span>${label}</span><strong>${formatNumber(value)}</strong><p>${description}</p></article>`).join("");
}

function renderActions() {
  const actions = state.actions?.actions || [];
  els.actionCount.textContent = `${actions.length} action${actions.length === 1 ? "" : "s"}`;
  els.actionList.innerHTML = actions.length ? actions.map((action, index) => `<article class="action-card"><div class="action-icon">${index + 1}</div><div><h4>${action.title}</h4><p>${action.description}</p></div><span class="priority ${action.priority}">${action.priority}</span></article>`).join("") : emptyState("Nothing needs urgent attention right now.");
}

function renderFeedbackChart(role) {
  const metrics = state.dashboard?.metrics || state.actions?.summary || {};
  const ready = role === "physio" ? metrics.feedback_sent || 0 : metrics.feedback_ready || 0;
  const waiting = role === "physio" ? metrics.awaiting_review || 0 : state.actions?.pending_feedback_count || Math.max((metrics.analyses_completed || 0) - ready, 0);
  const readyDeg = Math.round((ready / Math.max(ready + waiting, 1)) * 360);
  els.feedbackDonut.style.background = `conic-gradient(var(--teal) 0deg ${readyDeg}deg, var(--navy) ${readyDeg}deg 360deg)`;
  els.feedbackLegend.innerHTML = `<span class="legend-item"><span class="legend-dot" style="background: var(--teal)"></span>${ready} complete</span><span class="legend-item"><span class="legend-dot" style="background: var(--navy)"></span>${waiting} waiting</span>`;
}

function renderPlans() {
  els.plansList.innerHTML = state.plans.length ? state.plans.map(plan => `<article class="item-card"><h4>${plan.name}</h4><p>${plan.description || "No description provided."}</p><div class="item-meta"><span class="tag">${plan.duration_weeks || "-"} weeks</span><span class="tag">${plan.requires_analysis ? "Live analysis required" : "Standard plan"}</span>${plan.client_username ? `<span class="tag">Client: ${plan.client_username}</span>` : ""}</div><div class="prescription-list">${(plan.prescriptions || []).map(item => `<span class="prescription">${item.exercise?.name || "Exercise"}: ${item.sets} x ${item.reps}</span>`).join("")}</div></article>`).join("") : emptyState("Plans from Django will appear here once assigned.");
}

function renderAnalysis() {
  if (!state.sessions.length) { els.analysisList.innerHTML = emptyState("Movement analysis sessions will appear after clients complete checks."); els.ruleBars.innerHTML = emptyState("No rule alerts yet."); return; }
  els.analysisList.innerHTML = state.sessions.map(session => `<article class="session-card"><h4>${session.exercise_name || "Analysis session"}</h4><p>${session.client_username ? `${session.client_username} · ` : ""}${session.plan_name || "No linked plan"}</p><div class="session-meta"><span class="tag">${formatNumber(session.total_frames)} frames</span><span class="tag">${formatNumber(session.flagged_frames)} flagged</span><span class="tag">${session.feedback_shared ? "Feedback shared" : "Awaiting review"}</span></div></article>`).join("");
  const ruleTotals = state.sessions.reduce((acc, session) => { Object.entries(session.summary_metrics?.rules || {}).forEach(([name, value]) => { acc[name] = (acc[name] || 0) + Number(value || 0); }); return acc; }, {});
  const max = Math.max(...Object.values(ruleTotals), 1);
  els.ruleBars.innerHTML = Object.entries(ruleTotals).length ? Object.entries(ruleTotals).map(([name, value]) => `<div class="bar-row"><span><strong>${name.replaceAll("_", " ")}</strong><em>${value}</em></span><div class="bar-track"><div class="bar-fill" style="width:${(value / max) * 100}%"></div></div></div>`).join("") : emptyState("No rule alerts were detected in the loaded sessions.");
}

function renderExercises() {
  els.exerciseGrid.innerHTML = state.exercises.length ? state.exercises.slice(0, 9).map(exercise => `<article class="exercise-card"><div class="exercise-image">${exercise.name?.slice(0, 2).toUpperCase() || "CG"}</div><div class="exercise-card-body"><h4>${exercise.name}</h4><p>${exercise.description || "No description provided."}</p><div class="item-meta"><span class="tag">${exercise.body_area}</span><span class="tag">${exercise.difficulty}</span></div></div></article>`).join("") : emptyState("Exercises from the API will appear here.");
}

function updateActiveNav() { const route = window.location.hash.replace("#", "") || "overview"; document.querySelectorAll(".nav-link").forEach(link => link.classList.toggle("active", link.dataset.route === route)); }

els.loginForm.addEventListener("submit", login);
els.logoutButton.addEventListener("click", logout);
els.demoModeButton.addEventListener("click", useDemoMode);
els.refreshButton.addEventListener("click", () => state.demo ? useDemoMode() : loadData().catch(console.error));
window.addEventListener("hashchange", updateActiveNav);

if (state.token && state.user) loadData().catch(error => { console.warn(error); renderLoggedOut(); els.loginError.textContent = "Saved session could not connect. Please sign in again."; });
else renderLoggedOut();
