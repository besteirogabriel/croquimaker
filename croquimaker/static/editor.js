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
  const exportResult = document.querySelector("#exportResult");
  const revisionDownload = document.querySelector("#revisionDownload");
  let scene;
  let selectedId = null;
  let mode = "select";
  let drag = null;
  let history = [];
  let future = [];
  let newLineStart = null;

  const clone = value => JSON.parse(JSON.stringify(value));
  const selected = () => scene?.elements.find(item => item.id === selectedId);
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

  function symbolMarkup(item) {
    const selectedClass = item.id === selectedId ? " selected" : "";
    const label = item.symbol.replaceAll("_", " ");
    const code = item.code ? `<text class="symbol-code" x="${item.x + 9}" y="${item.y - 7}">${escapeText(item.code)}</text>` : "";
    if (item.symbol.startsWith("POSTE_")) {
      const extra = item.symbol === "POSTE_CONCRETO"
        ? `<circle cx="${item.x}" cy="${item.y}" r="4"></circle>`
        : item.symbol === "POSTE_DUPLO_T"
          ? `<path d="M${item.x - 5} ${item.y - 5}h10M${item.x} ${item.y - 5}v10M${item.x - 5} ${item.y + 5}h10"></path>`
          : "";
      return `<g class="scene-symbol${selectedClass}" data-id="${item.id}">
        <circle cx="${item.x}" cy="${item.y}" r="7"></circle>${extra}${code}
        <title>${escapeText(label)}</title>
      </g>`;
    }
    return `<g class="scene-symbol equipment-symbol${selectedClass}" data-id="${item.id}">
      <rect x="${item.x - 7}" y="${item.y - 7}" width="14" height="14" rx="2"></rect>
      <text x="${item.x}" y="${item.y + 2.2}">${escapeText(label.slice(0, 2))}</text>${code}
      <title>${escapeText(label)}</title>
    </g>`;
  }

  function lineMarkup(item) {
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

  function updateProperties() {
    const item = selected();
    form.hidden = !item;
    hint.textContent = item ? "Edite o elemento selecionado." : "Selecione um elemento.";
    lineProperties.hidden = !item || item.kind !== "line";
    symbolProperties.hidden = !item || item.kind !== "symbol";
    if (!item) return;
    idField.value = item.id;
    if (item.kind === "line") tensionField.value = item.tension;
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
  }

  function addSymbol(point) {
    remember();
    const id = `manual-symbol-${Date.now()}`;
    scene.elements.push({
      id, kind: "symbol", category: "equipment",
      symbol: symbolField.value || "POSTE_CONCRETO",
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
    const id = `manual-line-${Date.now()}`;
    scene.elements.push({
      id, kind: "line",
      x1: newLineStart.x, y1: newLineStart.y,
      x2: point.x, y2: point.y, tension: "BT"
    });
    selectedId = id;
    setMode("select");
    render();
  }

  canvas.addEventListener("dblclick", event => {
    const point = svgPoint(event);
    if (mode === "add-symbol") addSymbol(point);
    if (mode === "add-line") addLine(point);
  });

  canvas.addEventListener("pointerdown", event => {
    const target = event.target.closest("[data-id]");
    if (!target || mode !== "select") {
      if (!target) { selectedId = null; render(); }
      return;
    }
    selectedId = target.dataset.id;
    const item = selected();
    if (!item) return;
    remember();
    const point = svgPoint(event);
    drag = {
      id: item.id,
      end: event.target.dataset.end || null,
      point,
      original: clone(item)
    };
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
    } else if (drag.end === "start") {
      item.x1 = drag.original.x1 + dx; item.y1 = drag.original.y1 + dy;
    } else if (drag.end === "end") {
      item.x2 = drag.original.x2 + dx; item.y2 = drag.original.y2 + dy;
    } else {
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
    render();
  }
  tensionField.addEventListener("change", () => changeProperty("tension", tensionField.value));
  symbolField.addEventListener("change", () => changeProperty("symbol", symbolField.value));
  codeField.addEventListener("change", () => changeProperty("code", codeField.value.trim()));

  document.querySelector(".editor-toolbar").addEventListener("click", async event => {
    const button = event.target.closest("[data-action]");
    if (!button) return;
    const action = button.dataset.action;
    if (["select", "add-line", "add-symbol"].includes(action)) return setMode(action);
    if (action === "delete" && selected()) {
      remember();
      scene.elements = scene.elements.filter(item => item.id !== selectedId);
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

  fetch(`${api}/cena`)
    .then(response => {
      if (!response.ok) throw new Error();
      return response.json();
    })
    .then(payload => {
      scene = payload;
      loading.hidden = true;
      viewport.hidden = false;
      render();
    })
    .catch(() => { loading.textContent = "Não foi possível carregar a cena deste projeto."; });
})();
