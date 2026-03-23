function safeParse(v, fallback) {
  try { return JSON.parse(v); } catch { return fallback; }
}

let areaRows = [];
let documentRows = [];

function areaSubtypeOptions(model, current) {
  const sets = {
    woflv: [
      { value: 'a', label: 'Wohnfläche (a)' },
      { value: 'b', label: 'Nicht-Wohnfläche (b)' }
    ],
    nutz: [
      { value: 'a', label: 'Nutzfläche (a)' },
      { value: 'b', label: 'Verkehrsfläche (b)' },
      { value: 'c', label: 'Technikfläche (c)' }
    ]
  };
  return (sets[model] || []).map(opt => `<option value="${opt.value}" ${opt.value===current?'selected':''}>${opt.label}</option>`).join('');
}

function renderAreaRows() {
  const tbody = document.querySelector('#area-table tbody');
  if (!tbody) return;
  tbody.innerHTML = areaRows.map((row, i) => `
    <tr>
      <td><input value="${row.level || ''}" onchange="updateAreaField(${i}, 'level', this.value)" placeholder="EG / OG / DG"></td>
      <td><input value="${row.name || ''}" onchange="updateAreaField(${i}, 'name', this.value)" placeholder="Raum / Einheit"></td>
      <td><input type="number" step="0.01" value="${row.area || ''}" onchange="updateAreaField(${i}, 'area', this.value)"></td>
      <td>
        <select onchange="changeAreaModel(${i}, this.value)">
          <option value="woflv" ${row.model==='woflv'?'selected':''}>Wohnfläche WoFlV</option>
          <option value="nutz" ${row.model==='nutz'?'selected':''}>Nutzfläche</option>
        </select>
      </td>
      <td>
        <select onchange="updateAreaField(${i}, 'subtype', this.value)">
          ${areaSubtypeOptions(row.model || 'woflv', row.subtype || 'a')}
        </select>
      </td>
      <td><button class="button button-secondary" type="button" onclick="removeAreaRow(${i})">Entfernen</button></td>
    </tr>
  `).join('');
  renderSummary();
}

function renderSummary() {
  const el = document.getElementById('area-summary');
  if (!el) return;
  const sum = { gesamt:0, wa:0, wb:0, na:0, nb:0, nc:0 };
  areaRows.forEach(r => {
    const a = parseFloat(r.area || 0) || 0;
    sum.gesamt += a;
    if (r.model === 'woflv') {
      if (r.subtype === 'a') sum.wa += a;
      if (r.subtype === 'b') sum.wb += a;
    }
    if (r.model === 'nutz') {
      if (r.subtype === 'a') sum.na += a;
      if (r.subtype === 'b') sum.nb += a;
      if (r.subtype === 'c') sum.nc += a;
    }
  });
  const cards = [
    ['Gesamtfläche', sum.gesamt],
    ['Wohnfläche (a)', sum.wa],
    ['Nicht-Wohnfläche (b)', sum.wb],
    ['Nutzfläche (a)', sum.na],
    ['Verkehrsfläche (b)', sum.nb],
    ['Technikfläche (c)', sum.nc],
  ];
  el.innerHTML = cards.map(([label, value]) => `
    <div class="summary-card"><div class="summary-label">${label}</div><div class="summary-value">${value.toFixed(2)} m²</div></div>
  `).join('');
}

function updateAreaField(index, field, value) {
  areaRows[index][field] = value;
  renderAreaRows();
}

function changeAreaModel(index, value) {
  areaRows[index].model = value;
  areaRows[index].subtype = 'a';
  renderAreaRows();
}

function addAreaRow() {
  areaRows.push({ level:'', name:'', area:'', model:'woflv', subtype:'a' });
  renderAreaRows();
}

function removeAreaRow(index) {
  areaRows.splice(index, 1);
  renderAreaRows();
}

function renderDocumentRows() {
  const tbody = document.querySelector('#document-table tbody');
  if (!tbody) return;
  tbody.innerHTML = documentRows.map((row, i) => `
    <tr>
      <td><input value="${row.name || ''}" onchange="updateDocumentField(${i}, 'name', this.value)"></td>
      <td>
        <select onchange="updateDocumentField(${i}, 'status', this.value)">
          ${['offen', 'prüfen', 'optional', 'erledigt'].map(v => `<option value="${v}" ${row.status===v?'selected':''}>${v}</option>`).join('')}
        </select>
      </td>
      <td><button class="button button-secondary" type="button" onclick="removeDocumentRow(${i})">Entfernen</button></td>
    </tr>
  `).join('');
}

function updateDocumentField(index, field, value) {
  documentRows[index][field] = value;
}

function addDocumentRow() {
  documentRows.push({ name:'Neue Unterlage', status:'offen' });
  renderDocumentRows();
}

function removeDocumentRow(index) {
  documentRows.splice(index, 1);
  renderDocumentRows();
}

window.addEventListener('DOMContentLoaded', () => {
  areaRows = Array.isArray(window.initialAreaRows) ? window.initialAreaRows : [];
  documentRows = Array.isArray(window.initialDocuments) ? window.initialDocuments : [];
  if (document.getElementById('project-form')) {
    renderAreaRows();
    renderDocumentRows();
    document.getElementById('project-form').addEventListener('submit', () => {
      document.getElementById('area_rows_json').value = JSON.stringify(areaRows);
      document.getElementById('documents_json').value = JSON.stringify(documentRows);
    });
  }
});
