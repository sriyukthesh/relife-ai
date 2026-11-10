import '@bryntum/scheduler/fontawesome/css/fontawesome.css';
import '@bryntum/scheduler/fontawesome/css/solid.css';
import '@bryntum/scheduler/scheduler.css';
import '@bryntum/scheduler/svalbard-light.css';
import { Scheduler } from '@bryntum/scheduler';

const app = document.getElementById('app');
let scheduler = null;
const d = (s) => new Date(s);

function build(state) {
  if (scheduler) { scheduler.destroy(); scheduler = null; }
  app.innerHTML = '';
  if (!state.exists) { app.innerHTML = '<p style="font:14px system-ui;padding:1rem">Build a plan to see the resource lanes.</p>'; return; }
  const sc = state.schedule;
  try {
    scheduler = new Scheduler({
      appendTo: 'app',
      startDate: d(sc.axis.start),
      endDate: d(sc.axis.end),
      viewPreset: 'hourAndDay',
      workingTime: { fromHour: sc.axis.fromHour, toHour: sc.axis.toHour },
      rowHeight: 46,
      barMargin: 6,
      columns: [{ text: 'Resource', field: 'name', width: 190 }],
      resources: sc.resources.map((r) => ({ id: r.id, name: r.name })),
      events: sc.events.map((e) => ({
        id: e.id, resourceId: e.resourceId, name: e.name,
        startDate: d(e.startDate), endDate: d(e.endDate), eventColor: e.eventColor,
      })),
    });
  } catch (e) {
    app.innerHTML = '<div id="err">Bryntum Scheduler failed to start: ' + String(e.message || e) + '</div>';
    console.error(e);
  }
}

async function load() {
  try {
    const token = localStorage.getItem('sl_token');
    const r = await fetch('/api/timeline/state', { headers: token ? { Authorization: `Bearer ${token}` } : {} });
    if (!r.ok) throw new Error((await r.json()).detail || `HTTP ${r.status}`);
    build(await r.json());
  } catch (e) { app.innerHTML = '<div id="err">Could not load schedule: ' + String(e.message || e) + '</div>'; }
}

window.addEventListener('message', (e) => {
  if (e.origin === location.origin && e.data && e.data.type === 'reload') load();
});
load();
