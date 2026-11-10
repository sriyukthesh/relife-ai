import '@bryntum/gantt/fontawesome/css/fontawesome.css';
import '@bryntum/gantt/fontawesome/css/solid.css';
import '@bryntum/gantt/gantt.css';
import '@bryntum/gantt/svalbard-light.css';
import { Gantt } from '@bryntum/gantt';

const app = document.getElementById('app');
let gantt = null;

const d = (s) => new Date(s);
function mapTask(t) {
  if (t.children) {
    return { id: t.id, name: t.name, expanded: true, children: t.children.map(mapTask) };
  }
  return {
    id: t.id, name: t.name, startDate: d(t.startDate), endDate: d(t.endDate),
    manuallyScheduled: true, percentDone: 0, eventColor: t.eventColor,
  };
}

function build(state) {
  if (gantt) { gantt.destroy(); gantt = null; }
  app.innerHTML = '';
  if (!state.exists) { app.innerHTML = '<p style="font:14px system-ui;padding:1rem">Build a plan to see the project timeline.</p>'; return; }
  const sc = state.schedule;
  try {
    gantt = new Gantt({
      appendTo: 'app',
      startDate: d(sc.axis.start),
      endDate: d(sc.axis.end),
      viewPreset: 'hourAndDay',
      workingTime: { fromHour: sc.axis.fromHour, toHour: sc.axis.toHour },
      barMargin: 4,
      columns: [
        { type: 'name', field: 'name', text: 'Project / step', width: 300 },
        { type: 'startdate', text: 'Start' },
        { type: 'enddate', text: 'End' },
      ],
      tasks: sc.tasks.map(mapTask),
      dependencies: sc.dependencies,
    });
  } catch (e) {
    app.innerHTML = '<div id="err">Bryntum Gantt failed to start: ' + String(e.message || e) + '</div>';
    console.error(e);
  }
}

async function load() {
  try {
    const r = await fetch('/api/timeline/state', { headers: authHeaders() });
    if (!r.ok) throw new Error((await r.json()).detail || `HTTP ${r.status}`);
    build(await r.json());
  } catch (e) { app.innerHTML = '<div id="err">Could not load timeline: ' + String(e.message || e) + '</div>'; }
}

function authHeaders() {
  const token = localStorage.getItem('sl_token');
  return token ? { Authorization: `Bearer ${token}` } : {};
}

window.addEventListener('message', (e) => {
  if (e.origin === location.origin && e.data && e.data.type === 'reload') load();
});
load();
