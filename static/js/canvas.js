/**
 * TIGER AI • FLOW STUDIO - CANVAS ENGINE
 * Quản lý vẽ Nodes, kéo thả vị trí, đường nối SVG Bézier curves phát sáng và tương tác.
 */

class FlowCanvas {
  constructor(viewportEl, containerEl, svgEl) {
    this.viewport = viewportEl;
    this.container = containerEl;
    this.svg = svgEl;

    this.nodes = [];
    this.edges = [];
    this.activeNodeId = null;

    // Viewport transforms (Pan & Zoom)
    this.scale = 1;
    this.panX = 40;
    this.panY = 40;
    this.isPanning = false;
    this.startX = 0;
    this.startY = 0;

    // Node dragging
    this.draggingNode = null;
    this.dragOffsetX = 0;
    this.dragOffsetY = 0;

    // Callbacks
    this.onNodeSelected = null;

    this.initEvents();
  }

  initEvents() {
    // Canvas Panning (Mouse)
    this.viewport.addEventListener("mousedown", (e) => {
      if (e.target === this.viewport || e.target.classList.contains("canvas-grid-bg") || e.target === this.svg) {
        this.isPanning = true;
        this.startX = e.clientX - this.panX;
        this.startY = e.clientY - this.panY;
        this.viewport.classList.add("panning");
      }
    });

    // Canvas Panning (Touch for Mobile)
    this.viewport.addEventListener("touchstart", (e) => {
      if (e.touches.length === 1) {
        const touch = e.touches[0];
        if (e.target === this.viewport || e.target.classList.contains("canvas-grid-bg") || e.target === this.svg) {
          this.isPanning = true;
          this.startX = touch.clientX - this.panX;
          this.startY = touch.clientY - this.panY;
        }
      }
    }, { passive: true });

    window.addEventListener("mousemove", (e) => {
      // Pan viewport
      if (this.isPanning) {
        this.panX = e.clientX - this.startX;
        this.panY = e.clientY - this.startY;
        this.updateTransform();
      }

      // Drag node
      if (this.draggingNode) {
        const rect = this.viewport.getBoundingClientRect();
        const mouseX = (e.clientX - rect.left - this.panX) / this.scale;
        const mouseY = (e.clientY - rect.top - this.panY) / this.scale;

        this.draggingNode.x = mouseX - this.dragOffsetX;
        this.draggingNode.y = mouseY - this.dragOffsetY;

        const nodeEl = document.getElementById(this.draggingNode.id);
        if (nodeEl) {
          nodeEl.style.left = `${this.draggingNode.x}px`;
          nodeEl.style.top = `${this.draggingNode.y}px`;
        }

        this.renderEdges();
      }
    });

    window.addEventListener("touchmove", (e) => {
      if (this.isPanning && e.touches.length === 1) {
        const touch = e.touches[0];
        this.panX = touch.clientX - this.startX;
        this.panY = touch.clientY - this.startY;
        this.updateTransform();
      }

      if (this.draggingNode && e.touches.length === 1) {
        const touch = e.touches[0];
        const rect = this.viewport.getBoundingClientRect();
        const mouseX = (touch.clientX - rect.left - this.panX) / this.scale;
        const mouseY = (touch.clientY - rect.top - this.panY) / this.scale;

        this.draggingNode.x = mouseX - this.dragOffsetX;
        this.draggingNode.y = mouseY - this.dragOffsetY;

        const nodeEl = document.getElementById(this.draggingNode.id);
        if (nodeEl) {
          nodeEl.style.left = `${this.draggingNode.x}px`;
          nodeEl.style.top = `${this.draggingNode.y}px`;
        }

        this.renderEdges();
      }
    }, { passive: true });

    window.addEventListener("mouseup", () => {
      if (this.isPanning) {
        this.isPanning = false;
        this.viewport.classList.remove("panning");
      }
      if (this.draggingNode) {
        this.draggingNode = null;
      }
    });

    window.addEventListener("touchend", () => {
      if (this.isPanning) {
        this.isPanning = false;
      }
      if (this.draggingNode) {
        this.draggingNode = null;
      }
    });

    // Zoom on wheel
    this.viewport.addEventListener("wheel", (e) => {
      e.preventDefault();
      const zoomFactor = 1.08;
      if (e.deltaY < 0) {
        this.zoom(this.scale * zoomFactor, e.clientX, e.clientY);
      } else {
        this.zoom(this.scale / zoomFactor, e.clientX, e.clientY);
      }
    }, { passive: false });
  }

  zoom(newScale, clientX, clientY) {
    newScale = Math.max(0.4, Math.min(2.5, newScale));
    const rect = this.viewport.getBoundingClientRect();
    const cx = clientX !== undefined ? clientX - rect.left : rect.width / 2;
    const cy = clientY !== undefined ? clientY - rect.top : rect.height / 2;

    this.panX = cx - (cx - this.panX) * (newScale / this.scale);
    this.panY = cy - (cy - this.panY) * (newScale / this.scale);
    this.scale = newScale;
    this.updateTransform();
  }

  updateTransform() {
    this.container.style.transform = `translate(${this.panX}px, ${this.panY}px) scale(${this.scale})`;
    this.renderEdges();
  }

  loadWorkflow(workflowData) {
    this.workflowId = workflowData.id || "kpi_gtc";
    this.workflowName = workflowData.name || "";
    const rawNodes = JSON.parse(JSON.stringify(workflowData.nodes || []));
    // Giãn khoảng cách tọa độ hợp lý cho thẻ Node 3D đa tầng không bị sít nhau
    this.nodes = rawNodes.map((n) => {
      const copy = { ...n };
      if (copy.x > 100) copy.x = Math.round(copy.x * 1.12);
      if (copy.y >= 240) copy.y = copy.y + 42;
      else if (copy.y <= 120) copy.y = Math.max(60, copy.y - 12);
      return copy;
    });
    this.edges = JSON.parse(JSON.stringify(workflowData.edges || []));
    this.activeNodeId = null;

    // Tự động căn chỉnh kích thước & vị trí cho màn hình điện thoại
    if (window.innerWidth <= 992) {
      this.scale = 0.68;
      this.panX = 16;
      this.panY = 16;
    } else {
      this.scale = 0.96;
      this.panX = 36;
      this.panY = 32;
    }
    this.updateTransform();

    this.renderNodes();
    requestAnimationFrame(() => this.renderEdges());
  }

  getWorkflowMeta(wfId) {
    const map = {
      kpi_gtc: { code: "KPI•07H", label: "Đánh Giá Tỉ Lệ GTC", accent: "emerald", meter: "🎯 Chuẩn ≥ 85% • Cảnh báo < 80%" },
      checkin: { code: "SOP•07:35", label: "Kiểm Soát Chuyên Cần", accent: "cyan", meter: "⏱ Mốc 07:30 • Lọc Trễ & OFF" },
      assigned: { code: "FLEET•09H", label: "Điều Phối Xuất Bến", accent: "amber", meter: "🚚 ON_TRIP • 4 Kho MT01" },
      unassigned: { code: "BKLG•10H", label: "Rà Soát Tồn & Hẹn SMS", accent: "rose", meter: "⏳ 10 Khung Giờ • Regex DD/MM" },
      pda: { code: "PDA•LIVE", label: "Giám Sát Hành Trình PDA", accent: "blue", meter: "📡 3 Ca (12h•15h•19h) • Tốc Độ NV" },
      b2b_looker: { code: "B2B•12/18H", label: "Xuất Đơn B2B Looker", accent: "indigo", meter: "📊 Looker CSV ➔ Sheets ➔ 4 Ảnh" },
      evening_cod: { code: "COD•21H", label: "Chốt Ca & Đối Soát COD", accent: "gold", meter: "💰 Quét Chuyến Treo & Công Nợ" },
      truck_odo_365: { code: "ODO•365", label: "Đồng Bộ Xe Tải 21 Kho", accent: "teal", meter: "🚛 21 Kho Miền Tây ➔ Radar 365" },
      lastmile_trips: { code: "SYNC•05H", label: "Đồng Bộ 36 Cột Chuyến", accent: "violet", meter: "⚡ Chuẩn Hóa 36 Cột ➔ Sheets" }
    };
    return map[wfId] || { code: "MT01•FLOW", label: "Quy Trình Tự Động", accent: "amber", meter: "⚡ Tự Động Hóa Vận Hành" };
  }

  buildNodeTelemetryChip(n, wfMeta) {
    const desc = n.description || "";
    if (n.category === "trigger") {
      const timeMatch = (n.title + " " + desc).match(/(\d{1,2}:\d{2}\s*(?:AM|PM)?|\d{1,2}h(?:\s*\/\s*\d{1,2}h)+)/i);
      const timeBadge = timeMatch ? timeMatch[1] : "AUTO CRON";
      return `
        <div class="node-3d-spec spec-trigger">
          <span class="spec-pill pill-trigger">⏱ CRON</span>
          <code class="spec-code">${timeBadge}</code>
          <span class="spec-wave"><i></i><i></i><i></i><i></i></span>
        </div>
      `;
    }
    if (n.category === "api") {
      const methodMatch = desc.match(/\b(POST|GET|PUT)\b/i);
      const pathMatch = desc.match(/(\/api\/[a-zA-Z0-9_\-\/]+)/);
      const method = methodMatch ? methodMatch[1].toUpperCase() : "API";
      const apiPath = pathMatch ? pathMatch[1].replace("/api/", "/") : "GHN Internal Stream";
      return `
        <div class="node-3d-spec spec-api">
          <span class="spec-pill pill-api">${method}</span>
          <code class="spec-code" title="${pathMatch ? pathMatch[1] : ''}">${apiPath}</code>
        </div>
      `;
    }
    if (n.category === "brain") {
      return `
        <div class="node-3d-spec spec-brain">
          <span class="spec-pill pill-brain">🧠 AI CORE</span>
          <span class="spec-text">${wfMeta.meter}</span>
        </div>
      `;
    }
    // output
    const isSheets = (n.title + desc).toLowerCase().includes("sheet") || (n.title + desc).toLowerCase().includes("looker");
    const topicMatch = desc.match(/Topic:\s*(\d+\s*[^,)]+)/i) || desc.match(/Topic\s*(\d+)/i);
    const outLabel = isSheets ? "GOOGLE SHEETS SYNC" : (topicMatch ? `TOPIC ${topicMatch[1].trim()}` : "GROUP MIỀN TÂY 01");
    return `
      <div class="node-3d-spec spec-output">
        <span class="spec-pill pill-output">${isSheets ? "📊 SHEETS" : "📡 TELE BOT"}</span>
        <code class="spec-code">${outLabel}</code>
      </div>
    `;
  }

  renderNodes() {
    this.container.innerHTML = "";
    const wfMeta = this.getWorkflowMeta(this.workflowId);

    this.nodes.forEach((n, idx) => {
      const el = document.createElement("div");
      el.id = n.id;
      el.className = `flow-node node-3d node-${n.category} wf-accent-${wfMeta.accent}`;
      el.style.left = `${n.x}px`;
      el.style.top = `${n.y}px`;

      const categoryLabels = {
        trigger: "Kích Hoạt",
        api: "GHN API",
        brain: "Đầu Não AI",
        output: "Đích Xuất"
      };

      const stepNum = String(idx + 1).padStart(2, "0");
      const telemetryHtml = this.buildNodeTelemetryChip(n, wfMeta);

      el.innerHTML = `
        <div class="node-3d-top-glow"></div>
        <div class="node-port port-in"><span class="port-core"></span></div>
        <div class="node-header">
          <div class="node-title-group">
            <div class="node-icon-box">
              <span class="icon-3d-glare"></span>
              <span class="icon-3d-symbol">${n.icon || "⚡"}</span>
            </div>
            <div class="node-title-stack">
              <div class="node-step-meta">
                <span class="node-step-tag">STEP ${stepNum}</span>
                <span class="node-wf-chip">${wfMeta.code}</span>
              </div>
              <div class="node-title-text">${n.title}</div>
            </div>
          </div>
          <span class="node-badge-cat cat-${n.category}">${categoryLabels[n.category] || n.category}</span>
        </div>
        <div class="node-body">
          ${telemetryHtml}
          <div class="node-desc">${n.description}</div>
        </div>
        <div class="node-footer">
          <span class="node-status-text" id="status_${n.id}">● SẴN SÀNG</span>
          <span class="node-wf-signature">${wfMeta.label}</span>
        </div>
        <div class="node-3d-bottom-lip"></div>
        <div class="node-port port-out"><span class="port-core"></span></div>
      `;

      // Drag event on node (Mouse)
      el.addEventListener("mousedown", (e) => {
        e.stopPropagation();
        this.selectNode(n.id);

        const rect = this.viewport.getBoundingClientRect();
        const mouseX = (e.clientX - rect.left - this.panX) / this.scale;
        const mouseY = (e.clientY - rect.top - this.panY) / this.scale;

        this.draggingNode = n;
        this.dragOffsetX = mouseX - n.x;
        this.dragOffsetY = mouseY - n.y;
      });

      // Touch drag on node (Mobile)
      el.addEventListener("touchstart", (e) => {
        e.stopPropagation();
        this.selectNode(n.id);

        if (e.touches.length === 1) {
          const touch = e.touches[0];
          const rect = this.viewport.getBoundingClientRect();
          const mouseX = (touch.clientX - rect.left - this.panX) / this.scale;
          const mouseY = (touch.clientY - rect.top - this.panY) / this.scale;

          this.draggingNode = n;
          this.dragOffsetX = mouseX - n.x;
          this.dragOffsetY = mouseY - n.y;
        }
      }, { passive: true });

      this.container.appendChild(el);
    });
  }

  selectNode(nodeId) {
    this.activeNodeId = nodeId;
    document.querySelectorAll(".flow-node").forEach((el) => {
      el.classList.toggle("active-node", el.id === nodeId);
    });

    const nodeData = this.nodes.find((n) => n.id === nodeId);
    if (this.onNodeSelected && nodeData) {
      this.onNodeSelected(nodeData);
    }
  }

  renderEdges() {
    this.svg.innerHTML = "";

    this.edges.forEach((edge) => {
      const fromNode = this.nodes.find((n) => n.id === edge.from);
      const toNode = this.nodes.find((n) => n.id === edge.to);

      if (!fromNode || !toNode) return;

      const fromEl = document.getElementById(fromNode.id);
      const toEl = document.getElementById(toNode.id);

      const fromW = fromEl ? fromEl.offsetWidth : 268;
      const fromH = fromEl ? fromEl.offsetHeight : 164;
      const toH = toEl ? toEl.offsetHeight : 164;

      // Tọa độ port out của fromNode
      const x1 = this.panX + (fromNode.x + fromW) * this.scale;
      const y1 = this.panY + (fromNode.y + fromH / 2) * this.scale;

      // Tọa độ port in của toNode
      const x2 = this.panX + toNode.x * this.scale;
      const y2 = this.panY + (toNode.y + toH / 2) * this.scale;

      // Tính điểm điều khiển đường cong Bézier mượt mà
      const deltaX = Math.max(45, Math.abs(x2 - x1) * 0.52);
      const pathData = `M ${x1} ${y1} C ${x1 + deltaX} ${y1}, ${x2 - deltaX} ${y2}, ${x2} ${y2}`;

      // Đường ống 3D đổ bóng (Outer 3D Cable Shadow)
      const shadowPath = document.createElementNS("http://www.w3.org/2000/svg", "path");
      shadowPath.setAttribute("d", pathData);
      shadowPath.setAttribute("class", "flow-edge-shadow");

      // Đường dây nền 3D
      const bgPath = document.createElementNS("http://www.w3.org/2000/svg", "path");
      bgPath.setAttribute("d", pathData);
      bgPath.setAttribute("class", `flow-edge-path edge-from-${fromNode.category}`);

      // Đường dây phát sáng động (pulse)
      const pulsePath = document.createElementNS("http://www.w3.org/2000/svg", "path");
      pulsePath.setAttribute("d", pathData);
      pulsePath.setAttribute("class", `flow-edge-pulse pulse-from-${fromNode.category}`);

      this.svg.appendChild(shadowPath);
      this.svg.appendChild(bgPath);
      this.svg.appendChild(pulsePath);
    });
  }

  highlightExecution(stepIndex, totalSteps) {
    if (stepIndex < this.nodes.length) {
      const activeNode = this.nodes[stepIndex];
      document.querySelectorAll(".flow-node").forEach((el) => {
        el.classList.remove("running-node");
      });
      const el = document.getElementById(activeNode.id);
      if (el) {
        el.classList.add("running-node");
        const statusEl = document.getElementById(`status_${activeNode.id}`);
        if (statusEl) statusEl.textContent = "● ĐANG XỬ LÝ...";
      }
    }
  }

  markAllSuccess() {
    this.nodes.forEach((n) => {
      const el = document.getElementById(n.id);
      if (el) {
        el.classList.remove("running-node");
        el.classList.add("success-node");
        const statusEl = document.getElementById(`status_${n.id}`);
        if (statusEl) statusEl.textContent = "✔ HOÀN TẤT";
      }
    });
  }

  resetNodeStatus() {
    this.nodes.forEach((n) => {
      const el = document.getElementById(n.id);
      if (el) {
        el.classList.remove("running-node", "success-node");
        const statusEl = document.getElementById(`status_${n.id}`);
        if (statusEl) statusEl.textContent = "● SẴN SÀNG";
      }
    });
  }
}
