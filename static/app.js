const CATEGORY_COLORS = {
  program: "#3b82f6",
  declaration: "#06b6d4",
  control: "#f59e0b",
  expression: "#a855f7",
  literal: "#10b981",
};

const state = {
  presets: [],
  tokens: [],
  lastResult: null,
  astHierarchyRoot: null,
  orientation: "vertical",
  selectedNodeId: null,
  highlightedLine: null,
  highlightedIsError: false,
  nodeIdCounter: 0,
};

const elPresetSelect = document.getElementById("presetSelect");
const elPresetDesc = document.getElementById("presetDesc");
const elCompileBtn = document.getElementById("compileBtn");
const elCodeEditor = document.getElementById("codeEditor");
const elLineNumbers = document.getElementById("lineNumbers");
const elLineHighlight = document.getElementById("lineHighlight");

const elStatusPill = document.getElementById("statusPill");
const elStatusText = document.getElementById("statusText");
const elMetricTokens = document.getElementById("metricTokens");
const elMetricNodes = document.getElementById("metricNodes");
const elMetricSymbols = document.getElementById("metricSymbols");
const elMetricStates = document.getElementById("metricStates");
const elMetricConflicts = document.getElementById("metricConflicts");

const elDiagCount = document.getElementById("diagCount");
const elDiagnosticsList = document.getElementById("diagnosticsList");

const elAstEmptyBanner = document.getElementById("astEmptyBanner");
const elInspectorBody = document.getElementById("inspectorBody");

const elPythonCodeOutput = document.getElementById("pythonCodeOutput");
const elPythonStdoutOutput = document.getElementById("pythonStdoutOutput");
const elAstStepsBadge = document.getElementById("astStepsBadge");
const elAstStdoutOutput = document.getElementById("astStdoutOutput");
const elAstVarsOutput = document.getElementById("astVarsOutput");
const elSymbolsTableBody = document.getElementById("symbolsTableBody");
const elTokensTableBody = document.getElementById("tokensTableBody");
const elTokenSearch = document.getElementById("tokenSearch");
const elPreprocessorInfo = document.getElementById("preprocessorInfo");
const elLalrStatesOutput = document.getElementById("lalrStatesOutput");

const NODE_W = 158;
const NODE_H = 44;

const svg = d3.select("#astSvg");
const gViewport = svg.append("g").attr("class", "ast-viewport");
const gLinks = gViewport.append("g").attr("class", "ast-links-layer");
const gNodes = gViewport.append("g").attr("class", "ast-nodes-layer");

const zoomBehavior = d3
  .zoom()
  .scaleExtent([0.12, 2.8])
  .on("zoom", (event) => {
    gViewport.attr("transform", event.transform);
  });

svg.call(zoomBehavior).on("dblclick.zoom", null);

function updateLineNumbers() {
  const linesCount = elCodeEditor.value.split("\n").length;
  const nums = [];
  for (let i = 1; i <= linesCount; i++) {
    nums.push(i);
  }
  elLineNumbers.textContent = nums.join("\n");
  syncHighlightPosition();
}

function highlightEditorLine(lineNumber, isError = false, scrollIntoView = false) {
  state.highlightedLine = lineNumber;
  state.highlightedIsError = isError;
  if (!lineNumber || lineNumber < 1) {
    elLineHighlight.style.display = "none";
    return;
  }
  const lineHeight = 21;
  if (scrollIntoView) {
    const targetScroll = Math.max(0, (lineNumber - 4) * lineHeight);
    elCodeEditor.scrollTop = targetScroll;
    elLineNumbers.scrollTop = elCodeEditor.scrollTop;
  }
  syncHighlightPosition();
}

function syncHighlightPosition() {
  if (!state.highlightedLine) {
    elLineHighlight.style.display = "none";
    return;
  }
  const lineHeight = 21;
  const paddingTop = 12;
  const topPx = paddingTop + (state.highlightedLine - 1) * lineHeight - elCodeEditor.scrollTop;
  elLineHighlight.style.display = "block";
  elLineHighlight.style.top = `${topPx}px`;
  elLineHighlight.classList.toggle("is-error", state.highlightedIsError);
}

elCodeEditor.addEventListener("scroll", () => {
  elLineNumbers.scrollTop = elCodeEditor.scrollTop;
  syncHighlightPosition();
});

elCodeEditor.addEventListener("input", () => {
  updateLineNumbers();
});

elCodeEditor.addEventListener("keydown", (e) => {
  if (e.key === "Tab") {
    e.preventDefault();
    const start = elCodeEditor.selectionStart;
    const end = elCodeEditor.selectionEnd;
    elCodeEditor.value =
      elCodeEditor.value.substring(0, start) + "    " + elCodeEditor.value.substring(end);
    elCodeEditor.selectionStart = elCodeEditor.selectionEnd = start + 4;
    updateLineNumbers();
  } else if ((e.ctrlKey || e.metaKey) && e.key === "Enter") {
    e.preventDefault();
    compileCurrentCode();
  }
});

document.querySelectorAll(".tab-btn").forEach((btn) => {
  btn.addEventListener("click", () => {
    document.querySelectorAll(".tab-btn").forEach((b) => b.classList.remove("active"));
    document.querySelectorAll(".tab-panel").forEach((p) => p.classList.remove("active"));
    btn.classList.add("active");
    const panel = document.getElementById(btn.dataset.tab);
    panel.classList.add("active");
    if (btn.dataset.tab === "tab-ast" && state.astHierarchyRoot) {
      requestAnimationFrame(() => fitAstToViewport(250));
    }
  });
});

async function loadPresets() {
  const resp = await fetch("/api/presets");
  const data = await resp.json();
  state.presets = data.presets || [];

  elPresetSelect.innerHTML = "";
  state.presets.forEach((p, idx) => {
    const opt = document.createElement("option");
    opt.value = String(idx);
    opt.textContent = p.title;
    elPresetSelect.appendChild(opt);
  });

  if (state.presets.length > 0) {
    selectPreset(0);
  }
}

function selectPreset(index) {
  const preset = state.presets[index];
  if (!preset) return;
  elCodeEditor.value = preset.code;
  elPresetDesc.textContent = preset.filename || "";
  highlightEditorLine(null);
  updateLineNumbers();
  compileCurrentCode();
}

elPresetSelect.addEventListener("change", () => {
  selectPreset(Number(elPresetSelect.value));
});

elCompileBtn.addEventListener("click", () => compileCurrentCode());

async function compileCurrentCode() {
  elCompileBtn.disabled = true;
  elStatusText.textContent = "Виконується розбір...";

  try {
    const resp = await fetch("/api/compile", {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({
        code: elCodeEditor.value,
        runAst: true,
        runPython: true,
      }),
    });
    const result = await resp.json();
    state.lastResult = result;
    renderAllResults(result);
  } catch (err) {
    elStatusPill.classList.add("error");
    elStatusText.textContent = "Помилка з'єднання із сервером";
    console.error(err);
  } finally {
    elCompileBtn.disabled = false;
  }
}

function renderAllResults(result) {
  state.tokens = result.tokens || [];
  elMetricTokens.textContent = String(state.tokens.length);
  elMetricNodes.textContent = String(result.astNodeCount || 0);
  elMetricSymbols.textContent = String((result.symbols || []).length);

  if (result.lalrStats) {
    elMetricStates.textContent = `${result.lalrStats.statesCount} (${result.lalrStats.rulesCount} правил)`;
    elMetricConflicts.textContent = `${result.lalrStats.shiftReduceConflicts} | ${result.lalrStats.reduceReduceConflicts}`;
    const lalrLabel = document.getElementById("lalrSummaryLabel");
    if (lalrLabel) {
      lalrLabel.textContent = `Метод: ${result.lalrStats.method} • Правил: ${result.lalrStats.rulesCount} • Станів: ${result.lalrStats.statesCount} • S/R: ${result.lalrStats.shiftReduceConflicts} • R/R: ${result.lalrStats.reduceReduceConflicts}`;
    }
    elLalrStatesOutput.textContent = (result.lalrStats.sampleStates || []).join("\n\n" + "─".repeat(64) + "\n\n");
  }

  if (result.success) {
    elStatusPill.classList.remove("error");
    elStatusText.textContent = "Успішно";
  } else {
    elStatusPill.classList.add("error");
    elStatusText.textContent = "Помилки";
  }

  renderDiagnostics(result.diagnostics || []);

  if (result.ast) {
    elAstEmptyBanner.hidden = true;
    buildAndRenderAst(result.ast);
  } else {
    elAstEmptyBanner.hidden = false;
    gLinks.selectAll("*").remove();
    gNodes.selectAll("*").remove();
    state.astHierarchyRoot = null;
  }

  elPythonCodeOutput.textContent = result.pythonCode || "";
  if (result.pythonExecution) {
    const pyExec = result.pythonExecution;
    let out = pyExec.stdout || "";
    if (pyExec.stderr) {
      out += (out ? "\n" : "") + "[stderr]:\n" + pyExec.stderr;
    }
    elPythonStdoutOutput.textContent = out || `exit code = ${pyExec.exitCode}`;
  } else {
    elPythonStdoutOutput.textContent = "—";
  }

  if (result.astExecution) {
    const astExec = result.astExecution;
    elAstStepsBadge.textContent = `${astExec.steps} кроків`;
    elAstStdoutOutput.textContent = astExec.error
      ? `[Помилка]: ${astExec.error}`
      : astExec.stdout || "—";

    const varsLines = [`return: ${JSON.stringify(astExec.returnValue)}`];
    const entries = Object.entries(astExec.variables || {});
    if (entries.length > 0) {
      varsLines.push("─".repeat(34));
      for (const [k, v] of entries) {
        varsLines.push(`${k} = ${JSON.stringify(v)}`);
      }
    }
    elAstVarsOutput.textContent = varsLines.join("\n");
  } else {
    elAstStepsBadge.textContent = "0 кроків";
    elAstStdoutOutput.textContent = "—";
    elAstVarsOutput.textContent = "";
  }

  renderSymbolsTable(result.symbols || []);
  renderTokensTable();

  const dirs = result.preprocessor || [];
  elPreprocessorInfo.textContent =
    dirs.length > 0
      ? "Препроцесор: " + dirs.map((d) => `${d.directive} (ряд. ${d.line})`).join(", ")
      : "Препроцесор: —";
}

function renderDiagnostics(diagnostics) {
  elDiagCount.textContent = String(diagnostics.length);
  elDiagnosticsList.innerHTML = "";

  if (diagnostics.length === 0) {
    const ok = document.createElement("div");
    ok.className = "diag-ok";
    ok.textContent = "✓ Помилок немає";
    elDiagnosticsList.appendChild(ok);
    highlightEditorLine(null);
    return;
  }

  diagnostics.forEach((d, index) => {
    const item = document.createElement("div");
    const isWarn = d.severity === "warning" || d.type === "SemanticWarning";
    item.className = "diag-item" + (isWarn ? " warning" : "");

    const meta = document.createElement("div");
    meta.className = "diag-meta";
    meta.textContent = `${d.type} • Рядок ${d.line}`;

    const msg = document.createElement("div");
    msg.textContent = d.message;

    item.appendChild(meta);
    item.appendChild(msg);
    item.addEventListener("click", () => {
      highlightEditorLine(d.line, !isWarn, true);
    });
    elDiagnosticsList.appendChild(item);

    if (index === 0) {
      highlightEditorLine(d.line, !isWarn, true);
    }
  });
}

function renderSymbolsTable(symbols) {
  elSymbolsTableBody.innerHTML = "";
  if (symbols.length === 0) {
    const tr = document.createElement("tr");
    const td = document.createElement("td");
    td.colSpan = 6;
    td.style.color = "#94a3b8";
    td.textContent = "Таблиця символів порожня.";
    tr.appendChild(td);
    elSymbolsTableBody.appendChild(tr);
    return;
  }

  const kindMap = {
    function: "Функція",
    variable: "Змінна",
    array: "Масив",
    parameter: "Параметр",
  };

  symbols.forEach((s) => {
    const tr = document.createElement("tr");
    const signature =
      s.kind === "function" && Array.isArray(s.params)
        ? `${s.type} (${s.params.join(", ")})`
        : s.type;

    const cells = [
      s.name,
      kindMap[s.kind] || s.kind,
      signature,
      s.scope,
      s.isConst ? "так" : "—",
      String(s.line),
    ];
    cells.forEach((val, idx) => {
      const td = document.createElement("td");
      if (idx === 0 || idx === 2) {
        const span = document.createElement("span");
        span.className = "tok-badge";
        span.textContent = val;
        td.appendChild(span);
      } else {
        td.textContent = val;
      }
      tr.appendChild(td);
    });
    tr.style.cursor = "pointer";
    tr.addEventListener("click", () => highlightEditorLine(s.line, false, true));
    elSymbolsTableBody.appendChild(tr);
  });
}

function renderTokensTable() {
  const query = elTokenSearch.value.trim().toLowerCase();
  elTokensTableBody.innerHTML = "";

  const filtered = state.tokens.filter(
    (t) =>
      !query ||
      t.type.toLowerCase().includes(query) ||
      String(t.value).toLowerCase().includes(query)
  );

  filtered.forEach((tok, idx) => {
    const tr = document.createElement("tr");
    const vals = [String(idx + 1), tok.type, tok.value, String(tok.line), String(tok.column)];
    vals.forEach((v, colIdx) => {
      const td = document.createElement("td");
      if (colIdx === 1) {
        const badge = document.createElement("span");
        badge.className = "tok-badge";
        badge.textContent = v;
        td.appendChild(badge);
      } else {
        td.textContent = v;
      }
      tr.appendChild(td);
    });
    tr.style.cursor = "pointer";
    tr.addEventListener("click", () => highlightEditorLine(tok.line, false, true));
    elTokensTableBody.appendChild(tr);
  });
}

elTokenSearch.addEventListener("input", renderTokensTable);

function truncateLabel(text, maxChars = 19) {
  if (!text) return "";
  return text.length > maxChars ? text.slice(0, maxChars - 1) + "…" : text;
}

function countHiddenDescendants(d) {
  if (!d._children) return 0;
  let total = 0;
  function walk(arr) {
    for (const child of arr) {
      total += 1;
      if (child.children) walk(child.children);
      if (child._children) walk(child._children);
    }
  }
  walk(d._children);
  return total;
}

function buildAndRenderAst(astData) {
  state.nodeIdCounter = 0;
  const root = d3.hierarchy(astData, (d) => d.children);
  root.x0 = 0;
  root.y0 = 0;
  root.each((d) => {
    d.id = ++state.nodeIdCounter;
  });
  state.astHierarchyRoot = root;
  state.selectedNodeId = root.id;
  updateInspector(root.data);
  updateAstTree(root, true);
}

function updateAstTree(sourceNode, fitAfter = false) {
  const root = state.astHierarchyRoot;
  if (!root) return;

  const isVertical = state.orientation === "vertical";
  const treeLayout = isVertical
    ? d3.tree().nodeSize([NODE_W + 22, NODE_H + 54])
    : d3.tree().nodeSize([NODE_H + 16, NODE_W + 68]);

  treeLayout(root);

  const nodes = root.descendants();
  const links = root.links();

  const coordX = (d) => (isVertical ? d.x : d.y);
  const coordY = (d) => (isVertical ? d.y : d.x);

  const duration = 280;

  const linkGen = isVertical
    ? d3
        .linkVertical()
        .x((d) => d.x)
        .y((d) => d.y)
    : d3
        .linkHorizontal()
        .x((d) => d.y)
        .y((d) => d.x);

  const linkSel = gLinks.selectAll("path.ast-link").data(links, (d) => d.target.id);

  const linkEnter = linkSel
    .enter()
    .append("path")
    .attr("class", "ast-link")
    .attr("d", () => {
      const o = { x: sourceNode.x0 ?? 0, y: sourceNode.y0 ?? 0 };
      return linkGen({ source: o, target: o });
    });

  linkSel
    .merge(linkEnter)
    .transition()
    .duration(duration)
    .attr("d", (d) => linkGen(d));

  linkSel
    .exit()
    .transition()
    .duration(duration)
    .attr("d", () => {
      const o = { x: sourceNode.x, y: sourceNode.y };
      return linkGen({ source: o, target: o });
    })
    .remove();

  const nodeSel = gNodes.selectAll("g.ast-node").data(nodes, (d) => d.id);

  const nodeEnter = nodeSel
    .enter()
    .append("g")
    .attr("class", "ast-node")
    .attr("transform", () => {
      const sx = isVertical ? sourceNode.x0 ?? 0 : sourceNode.y0 ?? 0;
      const sy = isVertical ? sourceNode.y0 ?? 0 : sourceNode.x0 ?? 0;
      return `translate(${sx - NODE_W / 2},${sy - NODE_H / 2})`;
    })
    .on("click", (event, d) => {
      event.stopPropagation();
      state.selectedNodeId = d.id;
      gNodes.selectAll("g.ast-node").classed("selected", (n) => n.id === d.id);
      updateInspector(d.data);
      if (d.data.line) {
        highlightEditorLine(d.data.line, false, true);
      }
    })
    .on("dblclick", (event, d) => {
      event.stopPropagation();
      toggleNodeCollapse(d);
    });

  nodeEnter
    .append("rect")
    .attr("class", "node-card")
    .attr("width", NODE_W)
    .attr("height", NODE_H)
    .attr("rx", 8)
    .attr("ry", 8)
    .attr("stroke", (d) => CATEGORY_COLORS[d.data.category] || "#64748b");

  nodeEnter
    .append("rect")
    .attr("width", 5)
    .attr("height", NODE_H - 10)
    .attr("x", 4)
    .attr("y", 5)
    .attr("rx", 2.5)
    .attr("fill", (d) => CATEGORY_COLORS[d.data.category] || "#64748b");

  nodeEnter
    .append("text")
    .attr("class", "node-label")
    .attr("x", 15)
    .attr("y", 19)
    .text((d) => truncateLabel(d.data.name, 19));

  nodeEnter
    .append("text")
    .attr("class", "node-sub")
    .attr("x", 15)
    .attr("y", 34)
    .text((d) => {
      const parts = [];
      if (d.data.inferredType && d.data.inferredType !== "void") {
        parts.push(`тип: ${d.data.inferredType}`);
      } else {
        parts.push(d.data.nodeType);
      }
      if (d.data.line) {
        parts.push(`ряд. ${d.data.line}`);
      }
      return truncateLabel(parts.join(" • "), 24);
    });

  const toggleGroup = nodeEnter
    .append("g")
    .attr("class", "toggle-badge")
    .attr("transform", `translate(${NODE_W - 28}, 6)`)
    .on("click", (event, d) => {
      event.stopPropagation();
      toggleNodeCollapse(d);
    });

  toggleGroup
    .append("rect")
    .attr("class", "collapse-pill")
    .attr("width", 22)
    .attr("height", 15)
    .attr("rx", 4);

  toggleGroup
    .append("text")
    .attr("class", "collapse-text")
    .attr("x", 11)
    .attr("y", 11)
    .attr("text-anchor", "middle");

  const nodeMerge = nodeSel.merge(nodeEnter);

  nodeMerge.classed("selected", (d) => d.id === state.selectedNodeId);

  nodeMerge
    .select("g.toggle-badge")
    .style("display", (d) => (d.children || d._children ? "block" : "none"))
    .select("text.collapse-text")
    .text((d) => {
      if (d._children) {
        const hiddenCount = countHiddenDescendants(d);
        return `+${hiddenCount}`;
      }
      return "−";
    });

  nodeMerge
    .transition()
    .duration(duration)
    .attr("transform", (d) => `translate(${coordX(d) - NODE_W / 2},${coordY(d) - NODE_H / 2})`);

  nodeSel
    .exit()
    .transition()
    .duration(duration)
    .attr("transform", () => {
      const tx = isVertical ? sourceNode.x : sourceNode.y;
      const ty = isVertical ? sourceNode.y : sourceNode.x;
      return `translate(${tx - NODE_W / 2},${ty - NODE_H / 2})`;
    })
    .style("opacity", 0)
    .remove();

  nodes.forEach((d) => {
    d.x0 = d.x;
    d.y0 = d.y;
  });

  if (fitAfter) {
    setTimeout(() => fitAstToViewport(320), duration + 30);
  }
}

function toggleNodeCollapse(d) {
  if (d.children) {
    d._children = d.children;
    d.children = null;
  } else if (d._children) {
    d.children = d._children;
    d._children = null;
  } else {
    return;
  }
  updateAstTree(d, false);
}

function fitAstToViewport(durationMs = 300) {
  const svgNode = svg.node();
  const vpNode = gViewport.node();
  if (!svgNode || !vpNode || !state.astHierarchyRoot) return;

  const { width, height } = svgNode.getBoundingClientRect();
  if (width === 0 || height === 0) return;

  const bbox = vpNode.getBBox();
  if (bbox.width === 0 || bbox.height === 0) return;

  const pad = 52;
  const scale = Math.min(
    1.15,
    Math.max(0.16, Math.min((width - pad * 2) / bbox.width, (height - pad * 2) / bbox.height))
  );
  const tx = width / 2 - (bbox.x + bbox.width / 2) * scale;
  const ty = Math.max(pad, (height - bbox.height * scale) / 2 - bbox.y * scale);

  svg
    .transition()
    .duration(durationMs)
    .call(zoomBehavior.transform, d3.zoomIdentity.translate(tx, ty).scale(scale));
}

function updateInspector(nodeData) {
  if (!nodeData) return;
  const rows = [
    ["Вузол", nodeData.name],
    ["Клас AST", nodeData.nodeType],
    ["Категорія", nodeData.category],
    ["Виведений тип", nodeData.inferredType || "—"],
    ["Рядок у C", nodeData.line ? String(nodeData.line) : "—"],
  ];
  elInspectorBody.innerHTML = "";
  for (const [label, val] of rows) {
    const row = document.createElement("div");
    row.className = "insp-row";
    const spanL = document.createElement("span");
    spanL.textContent = label + ":";
    const strongR = document.createElement("strong");
    strongR.textContent = val;
    row.appendChild(spanL);
    row.appendChild(strongR);
    elInspectorBody.appendChild(row);
  }
  if (nodeData.details) {
    const det = document.createElement("div");
    det.style.marginTop = "6px";
    det.style.paddingTop = "5px";
    det.style.borderTop = "1px solid #1e293b";
    det.textContent = nodeData.details;
    elInspectorBody.appendChild(det);
  }
}

document.getElementById("btnToggleLayout").addEventListener("click", (e) => {
  state.orientation = state.orientation === "vertical" ? "horizontal" : "vertical";
  e.currentTarget.textContent =
    state.orientation === "vertical" ? "Орієнтація: Вертикальна" : "Орієнтація: Горизонтальна";
  if (state.astHierarchyRoot) {
    updateAstTree(state.astHierarchyRoot, true);
  }
});

document.getElementById("btnFitView").addEventListener("click", () => fitAstToViewport(300));

document.getElementById("btnExpandAll").addEventListener("click", () => {
  if (!state.astHierarchyRoot) return;
  state.astHierarchyRoot.each((d) => {
    if (d._children) {
      d.children = d._children;
      d._children = null;
    }
  });
  updateAstTree(state.astHierarchyRoot, true);
});

document.getElementById("btnCollapseDeep").addEventListener("click", () => {
  if (!state.astHierarchyRoot) return;
  state.astHierarchyRoot.each((d) => {
    if (d._children) {
      d.children = d._children;
      d._children = null;
    }
  });
  state.astHierarchyRoot.each((d) => {
    if (d.depth >= 3 && d.children) {
      d._children = d.children;
      d.children = null;
    }
  });
  updateAstTree(state.astHierarchyRoot, true);
});

document.getElementById("btnExportSvg").addEventListener("click", () => {
  const svgEl = document.getElementById("astSvg");
  if (!svgEl || !state.astHierarchyRoot) return;

  const clone = svgEl.cloneNode(true);
  clone.setAttribute("xmlns", "http://www.w3.org/2000/svg");

  const styleTag = document.createElementNS("http://www.w3.org/2000/svg", "style");
  styleTag.textContent = `
    svg { background: #090e1a; font-family: Segoe UI, sans-serif; }
    .ast-link { fill: none; stroke: #475569; stroke-width: 1.7px; }
    .node-card { fill: #151f32; stroke-width: 1.8px; }
    .node-label { fill: #f8fafc; font-size: 11.5px; font-weight: 600; font-family: Consolas, monospace; }
    .node-sub { fill: #94a3b8; font-size: 10px; }
    .collapse-pill { fill: #334155; stroke: #64748b; }
    .collapse-text { fill: #e2e8f0; font-size: 9.5px; font-weight: 700; }
  `;
  clone.insertBefore(styleTag, clone.firstChild);

  const serializer = new XMLSerializer();
  const svgBlob = new Blob([serializer.serializeToString(clone)], {
    type: "image/svg+xml;charset=utf-8",
  });
  const url = URL.createObjectURL(svgBlob);
  const link = document.createElement("a");
  link.href = url;
  link.download = "ast_tree.svg";
  link.click();
  URL.revokeObjectURL(url);
});

document.getElementById("btnCopyPython").addEventListener("click", async (e) => {
  const btn = e.currentTarget;
  const code = state.lastResult?.pythonCode || "";
  if (!code) return;
  await navigator.clipboard.writeText(code);
  const prev = btn.textContent;
  btn.textContent = "Скопійовано!";
  setTimeout(() => (btn.textContent = prev), 1400);
});

document.getElementById("btnDownloadPython").addEventListener("click", () => {
  const code = state.lastResult?.pythonCode || "";
  if (!code) return;
  const blob = new Blob([code], { type: "text/x-python;charset=utf-8" });
  const url = URL.createObjectURL(blob);
  const a = document.createElement("a");
  a.href = url;
  a.download = "translated_program.py";
  a.click();
  URL.revokeObjectURL(url);
});

window.addEventListener("resize", () => {
  if (state.astHierarchyRoot) {
    fitAstToViewport(150);
  }
});

loadPresets();
