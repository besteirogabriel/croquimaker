(() => {
  const app = document.querySelector("#editorApp");
  if (!app) return;

  const project = app.dataset.project;
  const job = app.dataset.job;
  const csrf = document.querySelector('meta[name="csrf-token"]').content;
  const api = `/api/unidades/${project}/projetos/${job}`;
  const canvas = document.querySelector("#croquiCanvas");
  const viewport = document.querySelector("#canvasViewport");
  const loading = document.querySelector("#editorLoading");
  const form = document.querySelector("#propertiesForm");
  const hint = document.querySelector("#selectionHint");
  const idField = document.querySelector("#propertyId");
  const tensionField = document.querySelector("#propertyTension");
  const symbolField = document.querySelector("#propertySymbol");
  const codeField = document.querySelector("#propertyCode");
  const lineProperties = document.querySelector("#lineProperties");
  const symbolProperties = document.querySelector("#symbolProperties");
  const startSymbolField = document.querySelector("#propertyStartSymbol");
  const startPortField = document.querySelector("#propertyStartPort");
  const endSymbolField = document.querySelector("#propertyEndSymbol");
  const endPortField = document.querySelector("#propertyEndPort");
  const exportResult = document.querySelector("#exportResult");
  const revisionDownload = document.querySelector("#revisionDownload");

  let scene;
  let selectedId = null;
  let mode = "select";
  let drag = null;
  let history = [];
  let future = [];
  let newLineStart = null;
  let symbolCatalog = {};
  let clipboardSymbol = null;

  const clone = value => JSON.parse(JSON.stringify(value));
  const selected = () => scene?.elements.find(item => item.id === selectedId);
  const symbols = () => scene?.elements.filter(item => item.kind === "symbol") || [];
  const svgPoint = event => {
    const point = canvas.createSVGPoint();
    point.x = event.clientX;
    point.y = event.clientY;
    return point.matrixTransform(canvas.getScreenCTM().inverse());
  };
  const escapeText = value => String(value || "").replace(/[&<>"']/g, char => ({
    "&": "&amp;", "<": "&lt;", ">": "&gt;", '"': "&quot;", "'": "&#39;"
  })[char]);

  function remember() {
    history.push(clone(scene));
    if (history.length > 80) history.shift();
    future = [];
  }

  function uniqueId(prefix) {
    return `${prefix}-${Date.now()}-${Math.random().toString(16).slice(2, 8)}`;
  }

  function pathData(commands) {
    return commands.map(command => {
      const op = command[0];
      if (op === "M" || op === "L") return `${op}${command[1]} ${command[2]}`;
      if (op === "C") return `C${command.slice(1).join(" ")}`;
      if (op === "Z") return "Z";
      return "";
    }).join(" ");
  }

  function rotationForSymbol(spec, direction) {
    const [dxRaw, dyRaw] = Array.isArray(direction) ? direction : [1, 0];
    const length = Math.hypot(dxRaw, dyRaw) || 1;
    const dx = dxRaw / length;
    const dy = dyRaw / length;
    const [hx, hy] = spec.heading || [1, 0];
    return (Math.atan2(dy, dx) - Math.atan2(hy, hx)) * 180 / Math.PI;
  }

  function symbolVectorMarkup(item) {
    const spec = symbolCatalog[item.symbol];
    if (!spec) return `<circle cx="${item.x}" cy="${item.y}" r="5" fill="none" stroke="#111"></circle>`;
    const scale = Number(spec.render_scale || 1);
    const rotation = rotationForSymbol(spec, item.direction);
    const paths = (spec.paths || []).map(path => {
      const stroke = path.stroke || "none";
      const fill = path.fill || "none";
      const width = Math.max(0.35 / Math.max(scale, 0.0001), Number(path.width || 0));
      return `<path d="${pathData(path.commands || [])}" fill="${escapeText(fill)}" stroke="${escapeText(stroke)}" stroke-width="${width}" vector-effect="non-scaling-stroke"></path>`;
    }).join("");
    return `<g transform="translate(${item.x} ${item.y}) rotate(${-rotation}) scale(${scale} ${-scale})">${paths}</g>`;
  }

  function symbolMarkup(item) {
    const selectedClass = item.id === selectedId ? " selected" : "";
    const label = item.symbol.replaceAll("_", " ");
    const code = item.code ? `<text class="symbol-code" x="${item.x + 9}" y="${item.y - 7}">${escapeText(item.code)}</text>` : "";
    return `<g class="scene-symbol${selectedClass}" data-id="${item.id}">
      ${symbolVectorMarkup(item)}${code}<title>${escapeText(label)}</title>
    </g>`;
  }

  function portPoint(symbolId, port) {
    const item = scene?.elements.find(element => element.kind === "symbol" && element.id === symbolId);
    if (!item) return null;
    if (!port || port === "CENTER") return {x: item.x, y: item.y};
    const spec = symbolCatalog[item.symbol];
    if (!spec || !Array.isArray(spec.bounds)) return {x: item.x, y: item.y};
    const [x0, y0, x1, y1] = spec.bounds.map(Number);
    let local;
    if (port === "LEFT") local = [x0, (y0 + y1) / 2];
    else if (port === "RIGHT") local = [x1, (y0 + y1) / 2];
    else if (port === "TOP") local = [(x0 + x1) / 2, y1];
    else if (port === "BOTTOM") local = [(x0 + x1) / 2, y0];
    else return {x: item.x, y: item.y};

    const scale = Number(spec.render_scale || 1);
    const angle = rotationForSymbol(spec, item.direction) * Math.PI / 180;
    const lx = local[0] * scale;
    const ly = -local[1] * scale;
    return {
      x: item.x + lx * Math.cos(-angle) - ly * Math.sin(-angle),
      y: item.y + lx * Math.sin(-angle) + ly * Math.cos(-angle),
    };
  }

  function syncLinePorts(item) {
    if (!item || item.kind !== "line") return;
    const start = portPoint(item.startSymbolId, item.startPort);
    const end = portPoint(item.endSymbolId, item.endPort);
    if (start) { item.x1 = start.x; item.y1 = start.y; }
    if (end) { item.x2 = end.x; item.y2 = end.y; }
  }

  function syncConnectedLines(symbolId) {
    if (!symbolId) return;
    scene.elements.forEach(item => {
      if (item.kind === "line" && (item.startSymbolId === symbolId || item.endSymbolId === symbolId)) syncLinePorts(item);
    });
  }

  function lineMarkup(item) {
    syncLinePorts(item);
    const selectedClass = item.id === selectedId ? " selected" : "";
    const dash = item.tension === "MT" ? ` stroke-dasharray="5 3"` : "";
    const handles = item.id === selectedId
      ? `<circle class="line-handle" data-id="${item.id}" data-end="start" cx="${item.x1}" cy="${item.y1}" r="5"></circle>
         <circle class="line-handle" data-id="${item.id}" data-end="end" cx="${item.x2}" cy="${item.y2}" r="5"></circle>`
      : "";
    return `<g class="scene-line${selectedClass}" data-id="${item.id}">
      <line x1="${item.x1}" y1="${item.y1}" x2="${item.x2}" y2="${item.y2}"${dash}></line>${handles}
    </g>`;
  }

  function render() {
    if (!scene) return;
    const {width, height} = scene.page;
    canvas.setAttribute("viewBox", `0 0 ${width} ${height}`);
    const drawing = scene.elements
      .filter(item => item.kind === "line").map(lineMarkup)
      .concat(scene.elements.filter(item => item.kind === "symbol").map(symbolMarkup))
      .join("");
    canvas.innerHTML = `
      <rect class="sheet" x="0" y="0" width="${width}" height="${height}"></rect>
      <rect class="drawing-frame" x="20" y="20" width="${width - 40}" height="${height - 40}"></rect>
      <rect class="header-mask" x="20" y="20" width="${width - 40}" height="62"></rect>
      <rect class="footer-mask" x="20" y="${height - 86}" width="${width - 40}" height="66"></rect>
      <text class="sheet-title" x="${width / 2}" y="38">Croqui</text>
      <g class="scene-elements">${drawing}</g>`;
    updateProperties();
  }

  function symbolOptionLabel(item) {
    return item.code ? `${item.code} — ${item.symbol}` : `${item.id} — ${item.symbol}`;
  }

  function fillSymbolReference(select, value) {
    const options = [`<option value="">Sem associação</option>`]
      .concat(symbols().map(item => `<option value="${escapeText(item.id)}">${escapeText(symbolOptionLabel(item))}</option>`));
    select.innerHTML = options.join("");
    select.value = value || "";
  }

  function updateProperties() {
    const item = selected();
    form.hidden = !item;
    hint.textContent = item ? "Edite o elemento selecionado." : "Selecione um elemento.";
    lineProperties.hidden = !item || item.kind !== "line";
    symbolProperties.hidden = !item || item.kind !== "symbol";
    if (!item) return;
    idField.value = item.id;
    if (item.kind === "line") {
      tensionField.value = item.tension;
      fillSymbolReference(startSymbolField, item.startSymbolId);
      fillSymbolReference(endSymbolField, item.endSymbolId);
      startPortField.value = item.startPort || "CENTER";
      endPortField.value = item.endPort || "CENTER";
    }
    if (item.kind === "symbol") {
      symbolField.value = item.symbol;
      codeField.value = item.code || "";
    }
  }

  function setMode(nextMode) {
    mode = nextMode;
    newLineStart = null;
    document.querySelectorAll("[data-action].tool").forEach(button => {
      button.classList.toggle("active", button.dataset.action === mode);
    });
    canvas.classList.toggle("crosshair", mode !== "select");
    if (mode === "add-symbol") hint.textContent = "Clique uma vez no croqui para inserir o símbolo selecionado.";
    if (mode === "add-line") hint.textContent = "Clique no ponto inicial e depois no ponto final da nova linha.";
  }

  function addSymbol(point) {
    remember();
    const id = uniqueId("manual-symbol");
    scene.elements.push({
      id, kind: "symbol", category: "equipment",
      symbol: symbolField.value || Object.keys(symbolCatalog)[0] || "POSTE_CONCRETO",
      x: point.x, y: point.y, code: "", direction: [1, 0]
    });
    selectedId = id;
    setMode("select");
    render();
  }

  function addLine(point) {
    if (!newLineStart) {
      newLineStart = point;
      hint.textContent = "Clique no ponto final da nova linha.";
      return;
    }
    remember();
    const id = uniqueId("manual-line");
    scene.elements.push({
      id, kind: "line",
      x1: newLineStart.x, y1: newLineStart.y,
      x2: point.x, y2: point.y, tension: "BT",
      startSymbolId: "", startPort: "CENTER", endSymbolId: "", endPort: "CENTER"
    });
    selectedId = id;
    setMode("select");
    render();
  }

  canvas.addEventListener("click", event => {
    if (mode === "select") return;
    const point = svgPoint(event);
    if (mode === "add-symbol") addSymbol(point);
    else if (mode === "add-line") addLine(point);
  });

  canvas.addEventListener("pointerdown", event => {
    const target = event.target.closest("[data-id]");
    if (mode !== "select") return;
    if (!target) {
      selectedId = null;
      render();
      return;
    }
    selectedId = target.dataset.id;
    const item = selected();
    if (!item) return;
    remember();
    const point = svgPoint(event);
    drag = {id: item.id, end: event.target.dataset.end || null, point, original: clone(item)};
    canvas.setPointerCapture(event.pointerId);
    render();
  });

  canvas.addEventListener("pointermove", event => {
    if (!drag) return;
    const item = selected();
    const point = svgPoint(event);
    const dx = point.x - drag.point.x;
    const dy = point.y - drag.point.y;
    if (item.kind === "symbol") {
      item.x = drag.original.x + dx;
      item.y = drag.original.y + dy;
      syncConnectedLines(item.id);
    } else if (drag.end === "start") {
      item.startSymbolId = "";
      item.x1 = drag.original.x1 + dx; item.y1 = drag.original.y1 + dy;
    } else if (drag.end === "end") {
      item.endSymbolId = "";
      item.x2 = drag.original.x2 + dx; item.y2 = drag.original.y2 + dy;
    } else {
      item.startSymbolId = ""; item.endSymbolId = "";
      item.x1 = drag.original.x1 + dx; item.y1 = drag.original.y1 + dy;
      item.x2 = drag.original.x2 + dx; item.y2 = drag.original.y2 + dy;
    }
    render();
  });
  canvas.addEventListener("pointerup", () => { drag = null; });

  function changeProperty(field, value) {
    const item = selected();
    if (!item) return;
    remember();
    item[field] = value;
    if (item.kind === "symbol") syncConnectedLines(item.id);
    if (item.kind === "line") syncLinePorts(item);
    render();
  }

  tensionField.addEventListener("change", () => changeProperty("tension", tensionField.value));
  symbolField.addEventListener("change", () => changeProperty("symbol", symbolField.value));
  codeField.addEventListener("change", () => changeProperty("code", codeField.value.trim()));
  startSymbolField.addEventListener("change", () => changeProperty("startSymbolId", startSymbolField.value));
  startPortField.addEventListener("change", () => changeProperty("startPort", startPortField.value));
  endSymbolField.addEventListener("change", () => changeProperty("endSymbolId", endSymbolField.value));
  endPortField.addEventListener("change", () => changeProperty("endPort", endPortField.value));

  document.addEventListener("keydown", event => {
    const target = event.target;
    const editingField = target && ["INPUT", "TEXTAREA", "SELECT"].includes(target.tagName);
    const modifier = event.ctrlKey || event.metaKey;
    if (!modifier || editingField) return;
    if (event.key.toLowerCase() === "c") {
      const item = selected();
      if (item?.kind === "symbol") {
        clipboardSymbol = clone(item);
        event.preventDefault();
      }
    }
    if (event.key.toLowerCase() === "v" && clipboardSymbol) {
      remember();
      const copy = clone(clipboardSymbol);
      copy.id = uniqueId("manual-symbol");
      copy.x += 12;
      copy.y += 12;
      scene.elements.push(copy);
      clipboardSymbol = clone(copy);
      selectedId = copy.id;
      event.preventDefault();
      render();
    }
  });

  document.querySelector(".editor-toolbar").addEventListener("click", async event => {
    const button = event.target.closest("[data-action]");
    if (!button) return;
    const action = button.dataset.action;
    if (["select", "add-line", "add-symbol"].includes(action)) return setMode(action);
    if (action === "delete" && selected()) {
      remember();
      const removedId = selectedId;
      scene.elements = scene.elements.filter(item => item.id !== removedId);
      scene.elements.forEach(item => {
        if (item.kind !== "line") return;
        if (item.startSymbolId === removedId) item.startSymbolId = "";
        if (item.endSymbolId === removedId) item.endSymbolId = "";
      });
      selectedId = null;
      render();
    }
    if (action === "undo" && history.length) {
      future.push(clone(scene)); scene = history.pop(); selectedId = null; render();
    }
    if (action === "redo" && future.length) {
      history.push(clone(scene)); scene = future.pop(); selectedId = null; render();
    }
    if (action === "fit") canvas.scrollIntoView({block: "center"});
    if (action === "export") await exportRevision(button);
  });

  async function exportRevision(button) {
    button.disabled = true;
    button.textContent = "Exportando...";
    exportResult.hidden = true;
    try {
      scene.elements.filter(item => item.kind === "line").forEach(syncLinePorts);
      const response = await fetch(`${api}/revisoes`, {
        method: "POST",
        headers: {"Content-Type": "application/json", "X-CSRF-Token": csrf},
        body: JSON.stringify(scene)
      });
      if (!response.ok) throw new Error();
      const body = await response.json();
      revisionDownload.href = body.download_url;
      revisionDownload.textContent = `Baixar ${body.filename}`;
      exportResult.hidden = false;
    } catch {
      window.alert("Não foi possível exportar esta revisão.");
    } finally {
      button.disabled = false;
      button.textContent = "Exportar PDF revisado";
    }
  }

  Promise.all([
    fetch(`${api}/cena`).then(response => { if (!response.ok) throw new Error(); return response.json(); }),
    fetch("/static/rge_symbol_catalog.json").then(response => { if (!response.ok) throw new Error(); return response.json(); })
  ])
    .then(([payload, catalog]) => {
      scene = payload;
      symbolCatalog = catalog.symbols || {};
      loading.hidden = true;
      viewport.hidden = false;
      render();
    })
    .catch(() => { loading.textContent = "Não foi possível carregar a cena ou a simbologia oficial deste projeto."; });
})();
