(async function () {
  const app = document.getElementById("review-app");
  if (!app) return;

  const jobId = app.dataset.jobId;
  const canEdit = app.dataset.canEdit === "1";
  const canGenerate = app.dataset.canGenerate === "1";
  const content = document.getElementById("review-content");
  const statusEl = document.getElementById("review-status");
  const pageSelect = document.getElementById("page-select");
  const overlayImage = document.getElementById("overlay-image");
  const editLayer = document.getElementById("edit-layer");
  const activeToolEl = document.getElementById("active-tool");
  const selectionStatus = document.getElementById("selection-status");
  const PAGE_KIND_OPTIONS = [
    "TES_ADMINISTRATIVO",
    "EQUIPES_EXECUCAO",
    "PLANO_MANOBRA",
    "PASSOS_MANOBRA",
    "CROQUI_RESUMIDO",
    "PROJETO_REDE",
    "DETALHE_TECNICO",
    "ANEXO_DESCONHECIDO",
    "UNKNOWN",
  ];
  let payload = await fetch(`/api/jobs/${jobId}/payload`).then((r) => r.json());
  let tab = "meta";
  let activeTool = "select";
  let selectedVisual = null;
  let pendingSpanNode = null;

  normalizePayload();

  if (pageSelect && overlayImage) {
    pageSelect.addEventListener("change", () => {
      overlayImage.src = pageSelect.value;
      renderEditLayer();
    });
  }

  document.querySelectorAll("[data-tool]").forEach((button) => {
    button.addEventListener("click", () => {
      document.querySelectorAll("[data-tool]").forEach((item) => item.classList.remove("active"));
      button.classList.add("active");
      activeTool = button.dataset.tool;
      pendingSpanNode = null;
      setSelectionStatus(null);
      if (activeToolEl) activeToolEl.textContent = button.title || button.textContent.trim();
    });
  });

  document.querySelectorAll("[data-filter]").forEach((input) => {
    input.addEventListener("change", renderEditLayer);
  });

  editLayer?.addEventListener("click", (event) => {
    if (!canEdit) return;
    const point = svgPoint(event);
    const target = event.target.closest?.("[data-visual]");
    if (activeTool === "node") {
      payload.nodes.push({
        id: nextNodeId(),
        type: "POSTE",
        x: Math.round(point.x),
        y: Math.round(point.y),
        confidence: 1,
        raw_text: "Incluido no editor visual",
        approved: true,
        deleted: false,
      });
      setSelectionStatus("Poste incluido");
      render();
      markDirty();
      return;
    }
    if (activeTool === "equipment") {
      const nearest = nearestNode(point);
      payload.equipment.push({
        code: "MANUAL",
        type: "EQUIPAMENTO",
        node_id: nearest?.id || "",
        status: "manual",
        confidence: 1,
        raw_text: "Incluido no editor visual",
        approved: true,
        deleted: false,
      });
      setSelectionStatus("Equipamento incluido");
      render();
      markDirty();
      return;
    }
    if (activeTool === "delete" && target) {
      removeVisual(target.dataset.collection, Number(target.dataset.index));
      render();
      markDirty();
      return;
    }
    if (activeTool === "span" && target?.dataset.collection === "nodes") {
      const node = payload.nodes[Number(target.dataset.index)];
      if (!node) return;
      if (!pendingSpanNode) {
        pendingSpanNode = node;
        setSelectionStatus(`Origem ${node.id}. Selecione o destino.`);
        selectedVisual = target.dataset.visual;
        renderEditLayer();
        return;
      }
      if (pendingSpanNode.id !== node.id) {
        payload.spans.push({
          id: nextSpanId(pendingSpanNode.id, node.id),
          from_node: pendingSpanNode.id,
          to_node: node.id,
          length_m: null,
          cable: "",
          network_type: "MT",
          status: "manual",
          confidence: 1,
          raw_text: "Incluido no editor visual",
          approved: true,
          deleted: false,
        });
        pendingSpanNode = null;
        setSelectionStatus("Vao incluido");
        render();
        markDirty();
      }
      return;
    }
    if (target) {
      selectedVisual = target.dataset.visual;
      setSelectionStatus(target.dataset.label || "Item selecionado");
      renderEditLayer();
    } else {
      selectedVisual = null;
      setSelectionStatus(null);
      renderEditLayer();
    }
  });

  document.querySelectorAll(".tabs button").forEach((button) => {
    button.addEventListener("click", () => {
      document.querySelectorAll(".tabs button").forEach((b) => b.classList.remove("active"));
      button.classList.add("active");
      tab = button.dataset.tab;
      render();
    });
  });

  document.getElementById("save-review")?.addEventListener("click", savePayload);
  document.getElementById("approve-review")?.addEventListener("click", async () => {
    const saved = await savePayload();
    if (!saved) return;
    await fetch(`/api/jobs/${jobId}/approve`, { method: "POST" });
    window.location.href = `/jobs/${jobId}`;
  });
  document.getElementById("generate-review")?.addEventListener("click", async () => {
    const saved = await savePayload();
    if (!saved || !canGenerate) return;
    setStatus("Gerando saidas...");
    const res = await fetch(`/api/jobs/${jobId}/generate`, { method: "POST" });
    if (res.ok) window.location.href = `/jobs/${jobId}`;
    else setStatus("Falha ao gerar saidas.", true);
  });

  function normalizePayload() {
    payload.meta = payload.meta || {};
    payload.pages = payload.pages || [];
    payload.nodes = payload.nodes || [];
    payload.spans = payload.spans || [];
    payload.equipment = payload.equipment || [];
    payload.work_areas = payload.work_areas || [];
    payload.materials = payload.materials || [];
    payload.validations = payload.validations || [];
  }

  function render() {
    normalizePayload();
    if (tab === "meta") renderMeta();
    if (tab === "pages") renderPages();
    if (tab === "nodes") renderNodes();
    if (tab === "equipment") renderEquipment();
    if (tab === "spans") renderSpans();
    if (tab === "validations") renderValidations();
    if (tab === "json") renderJson();
    renderEditLayer();
  }

  function renderMeta() {
    const fields = [
      ["tes_number", "TES"],
      ["municipality", "Municipio"],
      ["state", "Estado"],
      ["service_classification", "Classificacao"],
      ["main_switching_equipment", "Equipamento principal"],
      ["service_description", "Descricao do servico"],
      ["execution_conditions", "Condicoes de execucao"],
    ];
    content.innerHTML = `<div class="meta-editor">${fields
      .map(([field, label]) => inputHtml("meta", 0, field, label, payload.meta[field] || "", field.includes("description") || field.includes("conditions")))
      .join("")}</div>`;
    bindInputs("meta");
  }

  function renderPages() {
    content.innerHTML = `
      ${payload.pages.map((item, index) => pageHtml(item, index)).join("") || emptyText("Nenhuma pagina classificada.")}
    `;
    bindInputs("pages");
  }

  function renderNodes() {
    content.innerHTML = `
      ${manualToolbar("add-node", "Adicionar poste/no")}
      ${payload.nodes.map((item, index) => nodeHtml(item, index)).join("") || emptyText("Nenhum poste/no cadastrado.")}
    `;
    bindInputs("nodes");
    bindRemoveButtons("nodes");
    document.getElementById("add-node")?.addEventListener("click", () => {
      payload.nodes.push({
        id: nextNodeId(),
        type: "POSTE",
        x: payload.nodes.length * 120,
        y: 0,
        confidence: 1,
        raw_text: "Incluido manualmente",
        approved: true,
        deleted: false,
      });
      render();
      markDirty();
    });
  }

  function renderEquipment() {
    content.innerHTML = `
      ${manualToolbar("add-equipment", "Adicionar equipamento")}
      ${payload.equipment.map((item, index) => equipmentHtml(item, index)).join("") || emptyText("Nenhum equipamento cadastrado.")}
    `;
    bindInputs("equipment");
    bindRemoveButtons("equipment");
    document.getElementById("add-equipment")?.addEventListener("click", () => {
      payload.equipment.push({
        code: "MANUAL",
        type: "EQUIPAMENTO",
        node_id: payload.nodes[0]?.id || "",
        status: "indeterminado",
        confidence: 1,
        raw_text: "Incluido manualmente",
        approved: true,
        deleted: false,
      });
      render();
      markDirty();
    });
  }

  function renderSpans() {
    content.innerHTML = `
      ${manualToolbar("add-span", "Adicionar vao/ligacao")}
      ${payload.spans.map((item, index) => spanHtml(item, index)).join("") || emptyText("Nenhum vao cadastrado.")}
    `;
    bindInputs("spans");
    bindRemoveButtons("spans");
    document.getElementById("add-span")?.addEventListener("click", () => {
      const fromNode = payload.nodes[0]?.id || "P1";
      const toNode = payload.nodes[1]?.id || "P2";
      payload.spans.push({
        id: nextSpanId(fromNode, toNode),
        from_node: fromNode,
        to_node: toNode,
        length_m: null,
        cable: "",
        network_type: "MT",
        status: "manual",
        confidence: 1,
        raw_text: "Incluido manualmente",
        approved: true,
        deleted: false,
      });
      render();
      markDirty();
    });
  }

  function renderValidations() {
    content.innerHTML = (payload.validations || [])
      .map(
        (item) => `
          <div class="validation ${escapeAttr(item.severity || "info")}">
            <strong>${escapeHtml(item.severity || "")} ${escapeHtml(item.code || "")}</strong>
            <span>${escapeHtml(item.message || "")}</span>
            ${item.suggested_action ? `<small>${escapeHtml(item.suggested_action)}</small>` : ""}
          </div>
        `
      )
      .join("") || emptyText("Sem validacoes registradas.");
  }

  function renderJson() {
    content.innerHTML = `
      <div class="manual-toolbar">
        ${canEdit ? '<button class="btn small" id="apply-json">Aplicar JSON</button>' : ""}
        <button class="btn small" id="format-json">Formatar</button>
      </div>
      <textarea class="json-editor" id="json-editor" ${canEdit ? "" : "readonly"}>${escapeHtml(JSON.stringify(payload, null, 2))}</textarea>
    `;
    document.getElementById("format-json")?.addEventListener("click", () => {
      const editor = document.getElementById("json-editor");
      try {
        editor.value = JSON.stringify(JSON.parse(editor.value), null, 2);
        setStatus("JSON formatado.");
      } catch (err) {
        setStatus(`JSON invalido: ${err.message}`, true);
      }
    });
    document.getElementById("apply-json")?.addEventListener("click", () => {
      const editor = document.getElementById("json-editor");
      try {
        payload = JSON.parse(editor.value);
        normalizePayload();
        setStatus("JSON aplicado. Clique em Salvar para persistir.");
        markDirty();
      } catch (err) {
        setStatus(`JSON invalido: ${err.message}`, true);
      }
    });
  }

  function pageHtml(item, index) {
    const dimensions = [item.width, item.height].every(Boolean)
      ? `${Math.round(item.width)} x ${Math.round(item.height)}`
      : "dimensoes indisponiveis";
    return `
      <div class="review-item">
        <header>
          <strong>Pagina ${(item.index ?? index) + 1}</strong>
          <span class="review-muted">${escapeHtml(item.orientation || "-")} - ${escapeHtml(dimensions)}</span>
        </header>
        <div class="row">
          ${selectHtml("pages", index, "kind", "Tipo da pagina", item.kind || "UNKNOWN", PAGE_KIND_OPTIONS)}
          ${inputHtml("pages", index, "confidence", "Confianca", item.confidence ?? 0, false, "number")}
        </div>
        ${inputHtml("pages", index, "signals", "Sinais de classificacao", (item.signals || []).join("\\n"), true)}
      </div>
    `;
  }

  function nodeHtml(item, index) {
    return `
      <div class="review-item">
        ${itemHeader(item.id || `No ${index + 1}`, "nodes", index)}
        <div class="row">
          ${inputHtml("nodes", index, "id", "ID", item.id || "")}
          ${inputHtml("nodes", index, "type", "Tipo", item.type || "POSTE")}
        </div>
        <div class="row">
          ${inputHtml("nodes", index, "x", "X", item.x ?? "", false, "number")}
          ${inputHtml("nodes", index, "y", "Y", item.y ?? "", false, "number")}
        </div>
        <div class="row">
          ${inputHtml("nodes", index, "confidence", "Confianca", item.confidence ?? 1, false, "number")}
          ${checkboxHtml("nodes", index, "approved", "Aprovado", item.approved)}
        </div>
        ${checkboxHtml("nodes", index, "deleted", "Excluir do croqui", item.deleted)}
      </div>
    `;
  }

  function equipmentHtml(item, index) {
    return `
      <div class="review-item">
        ${itemHeader(`${item.type || "Equipamento"} ${item.code || ""}`, "equipment", index)}
        <div class="row">
          ${inputHtml("equipment", index, "code", "Codigo", item.code || "")}
          ${inputHtml("equipment", index, "type", "Tipo", item.type || "")}
        </div>
        <div class="row">
          ${inputHtml("equipment", index, "node_id", "Poste/No", item.node_id || "")}
          ${inputHtml("equipment", index, "status", "Status", item.status || "")}
        </div>
        <div class="row">
          ${inputHtml("equipment", index, "confidence", "Confianca", item.confidence ?? 1, false, "number")}
          ${checkboxHtml("equipment", index, "approved", "Aprovado", item.approved)}
        </div>
        ${inputHtml("equipment", index, "raw_text", "Texto/fonte", item.raw_text || "", true)}
        ${checkboxHtml("equipment", index, "deleted", "Excluir falso positivo", item.deleted)}
      </div>
    `;
  }

  function spanHtml(item, index) {
    return `
      <div class="review-item">
        ${itemHeader(item.id || `Vao ${index + 1}`, "spans", index)}
        <div class="row">
          ${inputHtml("spans", index, "id", "ID", item.id || "")}
          ${inputHtml("spans", index, "network_type", "Tipo rede", item.network_type || "")}
        </div>
        <div class="row">
          ${inputHtml("spans", index, "from_node", "De", item.from_node || "")}
          ${inputHtml("spans", index, "to_node", "Para", item.to_node || "")}
        </div>
        <div class="row">
          ${inputHtml("spans", index, "length_m", "Comprimento m", item.length_m ?? "", false, "number")}
          ${inputHtml("spans", index, "cable", "Cabo", item.cable || "")}
        </div>
        <div class="row">
          ${inputHtml("spans", index, "status", "Status", item.status || "")}
          ${inputHtml("spans", index, "confidence", "Confianca", item.confidence ?? 1, false, "number")}
        </div>
        ${inputHtml("spans", index, "raw_text", "Texto/fonte", item.raw_text || "", true)}
        ${checkboxHtml("spans", index, "approved", "Aprovado", item.approved)}
        ${checkboxHtml("spans", index, "deleted", "Excluir falso positivo", item.deleted)}
      </div>
    `;
  }

  function itemHeader(title, collection, index) {
    return `
      <header>
        <strong>${escapeHtml(title)}</strong>
        ${canEdit ? `<button class="btn small danger" data-remove="${collection}" data-index="${index}">Remover</button>` : ""}
      </header>
    `;
  }

  function inputHtml(collection, index, field, label, value, multiline = false, type = "text") {
    const attrs = `data-collection="${collection}" data-field="${field}" data-index="${index}" ${canEdit ? "" : "readonly"}`;
    if (multiline) {
      return `<label>${escapeHtml(label)}<textarea rows="3" ${attrs}>${escapeHtml(value ?? "")}</textarea></label>`;
    }
    const step = type === "number" ? 'step="0.01"' : "";
    return `<label>${escapeHtml(label)}<input type="${type}" ${step} ${attrs} value="${escapeAttr(value ?? "")}"></label>`;
  }

  function selectHtml(collection, index, field, label, value, options) {
    const attrs = `data-collection="${collection}" data-field="${field}" data-index="${index}" ${canEdit ? "" : "disabled"}`;
    return `
      <label>${escapeHtml(label)}
        <select ${attrs}>
          ${options
            .map((option) => `<option value="${escapeAttr(option)}" ${option === value ? "selected" : ""}>${escapeHtml(option)}</option>`)
            .join("")}
        </select>
      </label>
    `;
  }

  function checkboxHtml(collection, index, field, label, checked) {
    return `<label><input type="checkbox" data-collection="${collection}" data-field="${field}" data-index="${index}" ${checked ? "checked" : ""} ${canEdit ? "" : "disabled"}> ${escapeHtml(label)}</label>`;
  }

  function manualToolbar(id, label) {
    if (!canEdit) return "";
    return `<div class="manual-toolbar"><button class="btn small" id="${id}">${label}</button><span class="review-muted">Alteracoes manuais entram no JSON revisado.</span></div>`;
  }

  function emptyText(text) {
    return `<div class="empty">${escapeHtml(text)}</div>`;
  }

  function bindInputs(collection) {
    content.querySelectorAll("[data-collection]").forEach((input) => {
      input.addEventListener("input", () => updateField(input));
      input.addEventListener("change", () => updateField(input));
    });
    if (collection === "meta") {
      content.querySelectorAll("[data-collection='meta']").forEach((input) => {
        input.addEventListener("input", () => {
          payload.meta[input.dataset.field] = input.value;
          markDirty();
        });
      });
    }
  }

  function updateField(input) {
    if (!canEdit || input.dataset.collection === "meta") return;
    const collection = input.dataset.collection;
    const item = payload[collection]?.[Number(input.dataset.index)];
    if (!item) return;
    const field = input.dataset.field;
    if (input.type === "checkbox") item[field] = input.checked;
    else if (input.type === "number") item[field] = input.value === "" ? null : Number(input.value);
    else if (field === "signals") item[field] = input.value.split(/\n|,/).map((value) => value.trim()).filter(Boolean);
    else item[field] = input.value;
    markDirty();
  }

  function bindRemoveButtons(collection) {
    content.querySelectorAll(`[data-remove='${collection}']`).forEach((button) => {
      button.addEventListener("click", () => {
        payload[collection].splice(Number(button.dataset.index), 1);
        render();
        markDirty();
      });
    });
  }

  function renderEditLayer() {
    if (!editLayer) return;
    const filters = activeFilters();
    const nodes = canvasNodes();
    const nodeMap = new Map(nodes.map((item) => [item.id, item]));
    const parts = [
      '<defs><filter id="glow"><feDropShadow dx="0" dy="0" stdDeviation="2" flood-color="#0ca2f8" flood-opacity="0.75"/></filter></defs>',
      '<rect x="0" y="0" width="1000" height="620" fill="transparent"/>',
    ];
    if (filters.spans) {
      (payload.spans || []).forEach((span, index) => {
        if (span.deleted) return;
        const from = nodeMap.get(span.from_node) || nodes[index % Math.max(nodes.length, 1)];
        const to = nodeMap.get(span.to_node) || nodes[(index + 1) % Math.max(nodes.length, 1)];
        if (!from || !to) return;
        const visual = `spans-${index}`;
        const selected = selectedVisual === visual;
        parts.push(
          `<line data-visual="${visual}" data-collection="spans" data-index="${index}" data-label="${escapeAttr(span.id || "Vao")}" x1="${from.x}" y1="${from.y}" x2="${to.x}" y2="${to.y}" class="edit-span${selected ? " selected" : ""}"/>`
        );
        if (span.id) {
          parts.push(
            `<text x="${(from.x + to.x) / 2}" y="${(from.y + to.y) / 2 - 8}" class="edit-label">${escapeHtml(span.id)}</text>`
          );
        }
      });
    }
    if (filters.nodes) {
      nodes.forEach((node) => {
        const visual = `nodes-${node.index}`;
        const selected = selectedVisual === visual || pendingSpanNode?.id === node.id;
        parts.push(
          `<g data-visual="${visual}" data-collection="nodes" data-index="${node.index}" data-label="${escapeAttr(node.id)}" class="edit-node${selected ? " selected" : ""}">
            <circle cx="${node.x}" cy="${node.y}" r="8"></circle>
            <text x="${node.x + 10}" y="${node.y + 4}" class="edit-label">${escapeHtml(node.id)}</text>
          </g>`
        );
      });
    }
    if (filters.equipment) {
      (payload.equipment || []).forEach((item, index) => {
        if (item.deleted) return;
        const anchor = nodeMap.get(item.node_id) || nodes[index % Math.max(nodes.length, 1)] || { x: 120 + index * 50, y: 120 };
        const x = anchor.x + 18;
        const y = anchor.y - 18;
        const visual = `equipment-${index}`;
        const selected = selectedVisual === visual;
        parts.push(
          `<g data-visual="${visual}" data-collection="equipment" data-index="${index}" data-label="${escapeAttr(`${item.type || "Equipamento"} ${item.code || ""}`)}" class="edit-equipment${selected ? " selected" : ""}">
            <rect x="${x - 8}" y="${y - 8}" width="16" height="16"></rect>
            <line x1="${x - 10}" y1="${y - 10}" x2="${x + 10}" y2="${y + 10}"></line>
            <line x1="${x + 10}" y1="${y - 10}" x2="${x - 10}" y2="${y + 10}"></line>
            <text x="${x + 13}" y="${y + 4}" class="edit-label red">${escapeHtml(item.code || item.type || "EQ")}</text>
          </g>`
        );
      });
    }
    if (filters.warnings) {
      parts.push('<rect x="54" y="386" width="328" height="74" class="edit-work-area"></rect>');
    }
    editLayer.innerHTML = parts.join("");
  }

  function canvasNodes() {
    const active = (payload.nodes || []).filter((node) => !node.deleted);
    const source = active.length ? active : fallbackNodesFromLabels();
    const raw = source.length ? source : [{ id: "P1", x: 120, y: 390, index: 0 }, { id: "P2", x: 300, y: 390, index: 1 }];
    const xs = raw.map((node, index) => Number(node.x ?? 120 + index * 80)).filter(Number.isFinite);
    const ys = raw.map((node, index) => Number(node.y ?? 320 + index * 8)).filter(Number.isFinite);
    const minX = Math.min(...xs);
    const maxX = Math.max(...xs);
    const minY = Math.min(...ys);
    const maxY = Math.max(...ys);
    const width = Math.max(maxX - minX, 1);
    const height = Math.max(maxY - minY, 1);
    return raw.map((node, index) => {
      const rawX = Number(node.x ?? 120 + index * 80);
      const rawY = Number(node.y ?? 320 + index * 8);
      const normalizedX = width > 900 ? 70 + ((rawX - minX) / width) * 860 : rawX;
      const normalizedY = height > 540 ? 70 + ((rawY - minY) / height) * 480 : rawY;
      return {
        id: String(node.id || `P${index + 1}`),
        x: clamp(normalizedX, 40, 960),
        y: clamp(normalizedY, 60, 560),
        index,
      };
    });
  }

  function fallbackNodesFromLabels() {
    const labels = payload.meta?.project_numeric_label_positions || [];
    return labels.slice(0, 26).map((item, index) => ({
      id: `P${item.text || index + 1}`,
      x: Number(item.x ?? 90 + index * 34),
      y: Number(item.y ?? 390),
      index,
    }));
  }

  function nearestNode(point) {
    return canvasNodes()
      .map((node) => ({ ...node, distance: Math.hypot(node.x - point.x, node.y - point.y) }))
      .sort((a, b) => a.distance - b.distance)[0];
  }

  function removeVisual(collection, index) {
    if (!payload[collection]?.[index]) return;
    if (collection === "nodes" || collection === "equipment" || collection === "spans") {
      payload[collection][index].deleted = true;
    } else {
      payload[collection].splice(index, 1);
    }
    setSelectionStatus("Item removido do croqui");
  }

  function svgPoint(event) {
    const rect = editLayer.getBoundingClientRect();
    const x = ((event.clientX - rect.left) / rect.width) * 1000;
    const y = ((event.clientY - rect.top) / rect.height) * 620;
    return { x: clamp(x, 0, 1000), y: clamp(y, 0, 620) };
  }

  function activeFilters() {
    const values = {};
    document.querySelectorAll("[data-filter]").forEach((input) => {
      values[input.dataset.filter] = input.checked;
    });
    return { nodes: true, spans: true, equipment: true, warnings: true, ...values };
  }

  function setSelectionStatus(message) {
    if (!selectionStatus) return;
    selectionStatus.textContent = message || "Nenhum item selecionado";
  }

  function clamp(value, min, max) {
    return Math.min(max, Math.max(min, Number(value) || 0));
  }

  async function savePayload() {
    if (!canEdit) {
      setStatus("Seu perfil nao permite salvar alteracoes.", true);
      return false;
    }
    setStatus("Salvando revisao...");
    const res = await fetch(`/api/jobs/${jobId}/payload/update`, {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify(payload),
    });
    if (res.ok) {
      const result = await res.json();
      payload.confidence_global = result.confidence;
      setStatus(`Revisao salva. Confianca recalculada: ${Number(result.confidence).toFixed(2)}.`);
      return true;
    }
    const text = await res.text();
    setStatus(`Erro ao salvar revisao: ${text.slice(0, 160)}`, true);
    return false;
  }

  function nextNodeId() {
    const numbers = payload.nodes
      .map((node) => String(node.id || "").match(/^P(\d+)$/))
      .filter(Boolean)
      .map((match) => Number(match[1]));
    return `P${(numbers.length ? Math.max(...numbers) : 0) + 1}`;
  }

  function nextSpanId(fromNode, toNode) {
    const a = String(fromNode).replace(/\D+/g, "") || "1";
    const b = String(toNode).replace(/\D+/g, "") || "2";
    return `V${a}-${b}`;
  }

  function markDirty() {
    setStatus("Alteracoes pendentes. Clique em Salvar.");
  }

  function setStatus(message, isError = false) {
    if (!statusEl) return;
    statusEl.textContent = message;
    statusEl.style.color = isError ? "#b74134" : "#66737b";
  }

  function escapeHtml(value) {
    return String(value ?? "")
      .replaceAll("&", "&amp;")
      .replaceAll("<", "&lt;")
      .replaceAll(">", "&gt;")
      .replaceAll('"', "&quot;")
      .replaceAll("'", "&#039;");
  }

  function escapeAttr(value) {
    return escapeHtml(value);
  }

  render();
})();
