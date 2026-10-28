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
      if (copy.x > 100) copy.x = Math.round(copy.x * 1.18);
      if (copy.y >= 240) copy.y = copy.y + 54;
      else if (copy.y <= 120) copy.y = Math.max(54, copy.y - 16);
      return copy;
    });
    this.edges = JSON.parse(JSON.stringify(workflowData.edges || []));
    this.activeNodeId = null;

    // Tự động căn chỉnh kích thước & vị trí cho màn hình điện thoại
    if (window.innerWidth <= 992) {
      this.scale = 0.66;
      this.panX = 16;
      this.panY = 16;
    } else {
      this.scale = 0.94;
      this.panX = 42;
      this.panY = 34;
    }
    this.updateTransform();

    this.renderNodes();
    requestAnimationFrame(() => this.renderEdges());
  }

  getWorkflowMeta(wfId) {
    const map = {
      kpi_gtc: { code: "KPI•07H", label: "Đánh Giá Tỉ Lệ GTC", accent: "emerald", meter: "Chuẩn ≥85% • Cảnh báo <80%" },
      checkin: { code: "SOP•07:35", label: "Kiểm Soát Chuyên Cần", accent: "cyan", meter: "Mốc 07:30 • Lọc Trễ & OFF" },
      assigned: { code: "FLEET•09H", label: "Điều Phối Xuất Bến", accent: "amber", meter: "ON_TRIP • 4 Kho MT01" },
      unassigned: { code: "BKLG•10H", label: "Rà Soát Tồn & Hẹn SMS", accent: "rose", meter: "10 Khung Giờ • Regex DD/MM" },
      pda: { code: "PDA•LIVE", label: "Giám Sát Hành Trình PDA", accent: "blue", meter: "3 Ca (12h•15h•19h) • Tốc Độ NV" },
      b2b_looker: { code: "B2B•12/18H", label: "Xuất Đơn B2B Looker", accent: "indigo", meter: "Looker CSV ➔ Sheets ➔ 4 Ảnh" },
      evening_cod: { code: "COD•21H", label: "Chốt Ca & Đối Soát COD", accent: "gold", meter: "Quét Chuyến Treo & Công Nợ" },
      truck_odo_365: { code: "ODO•365", label: "Đồng Bộ Xe Tải 21 Kho", accent: "teal", meter: "21 Kho Miền Tây ➔ Radar 365" },
      lastmile_trips: { code: "SYNC•05H", label: "Đồng Bộ 36 Cột Chuyến", accent: "violet", meter: "Chuẩn Hóa 36 Cột ➔ Sheets" }
    };
    return map[wfId] || { code: "MT01•FLOW", label: "Quy Trình Tự Động", accent: "amber", meter: "Tự Động Hóa Vận Hành" };
  }

  cleanNodeDescription(desc) {
    if (!desc) return "";
    let cleaned = desc.replace(/^(POST|GET|PUT)\s+\/api\/[a-zA-Z0-9_\-\/]+\s*/i, "").trim();
    if (cleaned.startsWith("(") && cleaned.endsWith(").")) {
      cleaned = cleaned.slice(1, -2).trim() + ".";
    } else if (cleaned.startsWith("(") && cleaned.endsWith(")")) {
      cleaned = cleaned.slice(1, -1).trim();
    }
    return cleaned || desc;
  }

  get3DNodeSvgIcon(n) {
    const text = ((n.title || "") + " " + (n.description || "")).toLowerCase();
    if (n.category === "trigger") {
      return `
        <svg class="svg-icon-3d" viewBox="0 0 36 36" fill="none" xmlns="http://www.w3.org/2000/svg">
          <defs>
            <linearGradient id="trigG_${n.id}" x1="0" y1="0" x2="36" y2="36" gradientUnits="userSpaceOnUse">
              <stop offset="0%" stop-color="#fde047"/>
              <stop offset="55%" stop-color="#f97316"/>
              <stop offset="100%" stop-color="#dc2626"/>
            </linearGradient>
          </defs>
          <circle cx="18" cy="19" r="12" fill="rgba(249,115,22,0.18)" stroke="url(#trigG_${n.id})" stroke-width="2.4"/>
          <path d="M14 4.5H22M18 4.5V7" stroke="#fde047" stroke-width="2.4" stroke-linecap="round"/>
          <path d="M27.5 9.5L29.5 7.5" stroke="#fb923c" stroke-width="2.2" stroke-linecap="round"/>
          <path d="M18 12.5V19L22.5 21.5" stroke="#ffffff" stroke-width="2.5" stroke-linecap="round" stroke-linejoin="round"/>
          <circle cx="18" cy="19" r="2.2" fill="#fde047"/>
        </svg>
      `;
    }
    if (n.category === "api") {
      const isParcel = text.includes("item") || text.includes("đơn") || text.includes("history") || text.includes("sms");
      if (isParcel) {
        return `
          <svg class="svg-icon-3d" viewBox="0 0 36 36" fill="none" xmlns="http://www.w3.org/2000/svg">
            <defs>
              <linearGradient id="boxTop_${n.id}" x1="6" y1="6" x2="30" y2="18" gradientUnits="userSpaceOnUse">
                <stop offset="0%" stop-color="#7dd3fc"/>
                <stop offset="100%" stop-color="#0284c7"/>
              </linearGradient>
              <linearGradient id="boxLeft_${n.id}" x1="6" y1="14" x2="18" y2="31" gradientUnits="userSpaceOnUse">
                <stop offset="0%" stop-color="#38bdf8"/>
                <stop offset="100%" stop-color="#0369a1"/>
              </linearGradient>
            </defs>
            <polygon points="18,5 30,11.5 18,18 6,11.5" fill="url(#boxTop_${n.id})" stroke="#bae6fd" stroke-width="1.2"/>
            <polygon points="6,11.5 18,18 18,30.5 6,24" fill="url(#boxLeft_${n.id})" stroke="#7dd3fc" stroke-width="1.2"/>
            <polygon points="30,11.5 18,18 18,30.5 30,24" fill="rgba(2,132,199,0.75)" stroke="#38bdf8" stroke-width="1.2"/>
            <line x1="12" y1="8.2" x2="24" y2="14.8" stroke="#fef08a" stroke-width="2" stroke-linecap="round"/>
          </svg>
        `;
      }
      return `
        <svg class="svg-icon-3d" viewBox="0 0 36 36" fill="none" xmlns="http://www.w3.org/2000/svg">
          <defs>
            <linearGradient id="apiG_${n.id}" x1="4" y1="4" x2="32" y2="32" gradientUnits="userSpaceOnUse">
              <stop offset="0%" stop-color="#67e8f9"/>
              <stop offset="50%" stop-color="#0ea5e9"/>
              <stop offset="100%" stop-color="#2563eb"/>
            </linearGradient>
          </defs>
          <rect x="6" y="7" width="24" height="8" rx="3" fill="rgba(14,165,233,0.25)" stroke="url(#apiG_${n.id})" stroke-width="2"/>
          <rect x="6" y="20" width="24" height="8" rx="3" fill="rgba(14,165,233,0.25)" stroke="url(#apiG_${n.id})" stroke-width="2"/>
          <circle cx="11" cy="11" r="1.8" fill="#fde047"/>
          <circle cx="15.5" cy="11" r="1.8" fill="#34d399"/>
          <circle cx="11" cy="24" r="1.8" fill="#67e8f9"/>
          <circle cx="15.5" cy="24" r="1.8" fill="#38bdf8"/>
          <path d="M24 15V20M18 15V20" stroke="#7dd3fc" stroke-width="2" stroke-linecap="round"/>
        </svg>
      `;
    }
    if (n.category === "brain") {
      return `
        <svg class="svg-icon-3d" viewBox="0 0 36 36" fill="none" xmlns="http://www.w3.org/2000/svg">
          <defs>
            <linearGradient id="brainG_${n.id}" x1="4" y1="4" x2="32" y2="32" gradientUnits="userSpaceOnUse">
              <stop offset="0%" stop-color="#fef08a"/>
              <stop offset="50%" stop-color="#f59e0b"/>
              <stop offset="100%" stop-color="#a855f7"/>
            </linearGradient>
          </defs>
          <polygon points="18,4.5 29.5,11 29.5,25 18,31.5 6.5,25 6.5,11" fill="rgba(245,158,11,0.2)" stroke="url(#brainG_${n.id})" stroke-width="2.2"/>
          <polygon points="18,10 24.5,14 24.5,22 18,26 11.5,22 11.5,14" fill="rgba(168,85,247,0.28)" stroke="#fef08a" stroke-width="1.6"/>
          <circle cx="18" cy="18" r="3.2" fill="#ffffff"/>
          <path d="M18 4.5V10M29.5 11L24.5 14M29.5 25L24.5 22M18 31.5V26M6.5 25L11.5 22M6.5 11L11.5 14" stroke="#fde047" stroke-width="1.5"/>
        </svg>
      `;
    }
    // output
    const isSheets = text.includes("sheet") || text.includes("looker");
    if (isSheets) {
      return `
        <svg class="svg-icon-3d" viewBox="0 0 36 36" fill="none" xmlns="http://www.w3.org/2000/svg">
          <rect x="6" y="5" width="24" height="26" rx="4" fill="rgba(16,185,129,0.24)" stroke="#34d399" stroke-width="2.2"/>
          <line x1="6" y1="13" x2="30" y2="13" stroke="#6ee7b7" stroke-width="1.8"/>
          <line x1="6" y1="21" x2="30" y2="21" stroke="#6ee7b7" stroke-width="1.8"/>
          <line x1="15" y1="13" x2="15" y2="31" stroke="#6ee7b7" stroke-width="1.8"/>
          <circle cx="10.5" cy="9" r="1.6" fill="#fde047"/>
          <circle cx="15.5" cy="9" r="1.6" fill="#34d399"/>
        </svg>
      `;
    }
    return `
      <svg class="svg-icon-3d" viewBox="0 0 36 36" fill="none" xmlns="http://www.w3.org/2000/svg">
        <defs>
          <linearGradient id="outG_${n.id}" x1="4" y1="6" x2="32" y2="30" gradientUnits="userSpaceOnUse">
            <stop offset="0%" stop-color="#6ee7b7"/>
            <stop offset="55%" stop-color="#10b981"/>
            <stop offset="100%" stop-color="#0ea5e9"/>
          </linearGradient>
        </defs>
        <path d="M30.5 6.5L5.5 16.5L14.5 20.5L26 11L17.5 22.5L22.5 29.5L30.5 6.5Z" fill="rgba(16,185,129,0.28)" stroke="url(#outG_${n.id})" stroke-width="2.2" stroke-linejoin="round"/>
        <circle cx="28" cy="8" r="2" fill="#ffffff"/>
      </svg>
    `;
  }

  buildNodeTelemetryChip(n, wfMeta) {
    const desc = n.description || "";
    if (n.category === "trigger") {
      const timeMatch = (n.title + " " + desc).match(/(\d{1,2}:\d{2}\s*(?:AM|PM)?|\d{1,2}h(?:\s*\/\s*\d{1,2}h)+)/i);
      const timeBadge = timeMatch ? timeMatch[1] : "AUTO CRON";
      return `
        <div class="node-3d-telemetry">
          <div class="node-3d-spec spec-trigger">
            <span class="spec-pill pill-trigger">⏱ CRON</span>
            <code class="spec-code">${timeBadge}</code>
            <span class="spec-wave"><i></i><i></i><i></i><i></i></span>
          </div>
          <div class="node-mini-subbar">
            <span class="hub-led-tag"><i></i>CR</span>
            <span class="hub-led-tag"><i></i>BT</span>
            <span class="hub-led-tag"><i></i>VT</span>
            <span class="hub-led-tag"><i></i>ÔM</span>
            <span class="mini-subbar-right">GMT+7</span>
          </div>
        </div>
      `;
    }
    if (n.category === "api") {
      const methodMatch = desc.match(/\b(POST|GET|PUT)\b/i);
      const pathMatch = desc.match(/(\/api\/[a-zA-Z0-9_\-\/]+)/);
      const method = methodMatch ? methodMatch[1].toUpperCase() : "POST";
      const apiPath = pathMatch ? pathMatch[1].replace("/api/", "/") : "/lastmile/internal-stream";
      return `
        <div class="node-3d-telemetry">
          <div class="node-3d-spec spec-api">
            <span class="spec-pill pill-api">${method}</span>
            <code class="spec-code" title="${pathMatch ? pathMatch[1] : apiPath}">${apiPath}</code>
          </div>
          <div class="node-mini-subbar">
            <span class="api-stream-pill">⚡ 4 HUB MT01</span>
            <div class="api-stream-bar"><span class="api-stream-fill"></span></div>
            <span class="mini-subbar-right">200 OK</span>
          </div>
        </div>
      `;
    }
    if (n.category === "brain") {
      return `
        <div class="node-3d-telemetry">
          <div class="node-3d-spec spec-brain">
            <span class="spec-pill pill-brain">🧠 AI CORE</span>
            <span class="spec-text">${wfMeta.meter}</span>
          </div>
          <div class="brain-tier-bar">
            <span class="tier-seg seg-pass">≥85% Đạt</span>
            <span class="tier-seg seg-warn">80-84%</span>
            <span class="tier-seg seg-fail">&lt;80% Báo động</span>
          </div>
        </div>
      `;
    }
    // output
    const isSheets = (n.title + desc).toLowerCase().includes("sheet") || (n.title + desc).toLowerCase().includes("looker");
    const topicMatch = desc.match(/Topic:\s*(\d+\s*[^,)]+)/i) || desc.match(/Topic\s*(\d+)/i);
    const outLabel = isSheets ? "GOOGLE SHEETS SYNC" : (topicMatch ? `TOPIC ${topicMatch[1].trim()}` : "GROUP MIỀN TÂY 01");
    return `
      <div class="node-3d-telemetry">
        <div class="node-3d-spec spec-output">
          <span class="spec-pill pill-output">${isSheets ? "📊 SHEETS" : "📡 TELE BOT"}</span>
          <code class="spec-code">${outLabel}</code>
        </div>
        <div class="node-mini-subbar">
          <span class="out-tag-pill">${isSheets ? "📑 Auto Grid" : "🏷️ @Tag 4 NVXL"}</span>
          <span class="out-tag-pill">${isSheets ? "📸 4 Ảnh Kho" : "💬 HTML Live"}</span>
          <span class="mini-subbar-right">SYNC</span>
        </div>
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
      const svgIconHtml = this.get3DNodeSvgIcon(n);
      const cleanDesc = this.cleanNodeDescription(n.description);

      el.innerHTML = `
        <div class="node-3d-spine"></div>
        <div class="node-3d-top-glow"></div>
        <div class="node-port port-in"><span class="port-core"></span></div>
        <div class="node-header">
          <div class="node-title-group">
            <div class="node-icon-box">
              <span class="icon-3d-glare"></span>
              ${svgIconHtml}
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
          <div class="node-desc">${cleanDesc}</div>
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
    this.svg.innerHTML = `
      <defs>
        <linearGradient id="edgeGrad_trigger" x1="0%" y1="0%" x2="100%" y2="0%">
          <stop offset="0%" stop-color="#f97316"/>
          <stop offset="100%" stop-color="#38bdf8"/>
        </linearGradient>
        <linearGradient id="edgeGrad_api" x1="0%" y1="0%" x2="100%" y2="0%">
          <stop offset="0%" stop-color="#38bdf8"/>
          <stop offset="100%" stop-color="#fbbf24"/>
        </linearGradient>
        <linearGradient id="edgeGrad_brain" x1="0%" y1="0%" x2="100%" y2="0%">
          <stop offset="0%" stop-color="#fbbf24"/>
          <stop offset="100%" stop-color="#10b981"/>
        </linearGradient>
      </defs>
    `;

    this.edges.forEach((edge, idx) => {
      const fromNode = this.nodes.find((n) => n.id === edge.from);
      const toNode = this.nodes.find((n) => n.id === edge.to);

      if (!fromNode || !toNode) return;

      const fromEl = document.getElementById(fromNode.id);
      const toEl = document.getElementById(toNode.id);

      const fromW = fromEl ? fromEl.offsetWidth : 284;
      const fromH = fromEl ? fromEl.offsetHeight : 178;
      const toH = toEl ? toEl.offsetHeight : 178;

      // Tọa độ port out của fromNode
      const x1 = this.panX + (fromNode.x + fromW) * this.scale;
      const y1 = this.panY + (fromNode.y + fromH / 2) * this.scale;

      // Tọa độ port in của toNode
      const x2 = this.panX + toNode.x * this.scale;
      const y2 = this.panY + (toNode.y + toH / 2) * this.scale;

      // Tính điểm điều khiển đường cong Bézier mượt mà
      const deltaX = Math.max(50, Math.abs(x2 - x1) * 0.52);
      const pathData = `M ${x1} ${y1} C ${x1 + deltaX} ${y1}, ${x2 - deltaX} ${y2}, ${x2} ${y2}`;
      const pathId = `flowEdgePath_${idx}`;

      // 1. Đường ống 3D đổ bóng (Outer 3D Cable Shadow)
      const shadowPath = document.createElementNS("http://www.w3.org/2000/svg", "path");
      shadowPath.setAttribute("d", pathData);
      shadowPath.setAttribute("class", "flow-edge-shadow");

      // 2. Lớp vỏ cáp 3D (Metallic Tube Casing)
      const casingPath = document.createElementNS("http://www.w3.org/2000/svg", "path");
      casingPath.setAttribute("d", pathData);
      casingPath.setAttribute("class", "flow-edge-casing");

      // 3. Đường dây lõi Gradient 3D
      const bgPath = document.createElementNS("http://www.w3.org/2000/svg", "path");
      bgPath.setAttribute("id", pathId);
      bgPath.setAttribute("d", pathData);
      bgPath.setAttribute("class", `flow-edge-path edge-from-${fromNode.category}`);

      // 4. Đường dây xung năng lượng (pulse)
      const pulsePath = document.createElementNS("http://www.w3.org/2000/svg", "path");
      pulsePath.setAttribute("d", pathData);
      pulsePath.setAttribute("class", `flow-edge-pulse pulse-from-${fromNode.category}`);

      // 5. Hạt photon năng lượng 3D chạy dọc dây cáp
      const orb = document.createElementNS("http://www.w3.org/2000/svg", "circle");
      orb.setAttribute("r", "4.2");
      orb.setAttribute("class", `edge-energy-orb orb-from-${fromNode.category}`);
      const anim = document.createElementNS("http://www.w3.org/2000/svg", "animateMotion");
      anim.setAttribute("dur", `${2.1 + (idx % 3) * 0.35}s`);
      anim.setAttribute("repeatCount", "indefinite");
      anim.setAttribute("path", pathData);
      orb.appendChild(anim);

      this.svg.appendChild(shadowPath);
      this.svg.appendChild(casingPath);
      this.svg.appendChild(bgPath);
      this.svg.appendChild(pulsePath);
      this.svg.appendChild(orb);
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
