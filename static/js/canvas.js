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
    this.nodes = JSON.parse(JSON.stringify(workflowData.nodes || []));
    this.edges = JSON.parse(JSON.stringify(workflowData.edges || []));
    this.activeNodeId = null;

    // Tự động căn chỉnh kích thước & vị trí cho màn hình điện thoại
    if (window.innerWidth <= 992) {
      this.scale = 0.72;
      this.panX = 16;
      this.panY = 16;
    } else {
      this.scale = 1;
      this.panX = 40;
      this.panY = 40;
    }
    this.updateTransform();

    this.renderNodes();
    this.renderEdges();
  }

  renderNodes() {
    this.container.innerHTML = "";

    this.nodes.forEach((n) => {
      const el = document.createElement("div");
      el.id = n.id;
      el.className = `flow-node node-${n.category}`;
      el.style.left = `${n.x}px`;
      el.style.top = `${n.y}px`;

      const categoryLabels = {
        trigger: "Kích Hoạt",
        api: "GHN API",
        brain: "Đầu Não AI",
        output: "Telegram"
      };

      el.innerHTML = `
        <div class="node-port port-in"></div>
        <div class="node-header">
          <div class="node-title-group">
            <div class="node-icon-box">${n.icon || "⚡"}</div>
            <div>
              <div class="node-title-text">${n.title}</div>
            </div>
          </div>
          <span class="node-badge-cat cat-${n.category}">${categoryLabels[n.category] || n.category}</span>
        </div>
        <div class="node-body">
          <div class="node-desc">${n.description}</div>
        </div>
        <div class="node-footer">
          <span class="node-status-text" id="status_${n.id}">● SẴN SÀNG</span>
        </div>
        <div class="node-port port-out"></div>
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

      const nodeWidth = 250;
      const nodeHeight = 120; // xấp xỉ

      // Tọa độ port out của fromNode
      const x1 = this.panX + (fromNode.x + nodeWidth) * this.scale;
      const y1 = this.panY + (fromNode.y + nodeHeight / 2) * this.scale;

      // Tọa độ port in của toNode
      const x2 = this.panX + toNode.x * this.scale;
      const y2 = this.panY + (toNode.y + nodeHeight / 2) * this.scale;

      // Tính điểm điều khiển đường cong Bézier mượt mà
      const deltaX = Math.abs(x2 - x1) * 0.55;
      const pathData = `M ${x1} ${y1} C ${x1 + deltaX} ${y1}, ${x2 - deltaX} ${y2}, ${x2} ${y2}`;

      // Đường dây nền
      const bgPath = document.createElementNS("http://www.w3.org/2000/svg", "path");
      bgPath.setAttribute("d", pathData);
      bgPath.setAttribute("class", "flow-edge-path");

      // Đường dây phát sáng động (pulse)
      const pulsePath = document.createElementNS("http://www.w3.org/2000/svg", "path");
      pulsePath.setAttribute("d", pathData);
      pulsePath.setAttribute("class", "flow-edge-pulse");

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
