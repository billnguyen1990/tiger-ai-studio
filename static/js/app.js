/**
 * TIGER AI • FLOW STUDIO & COMMAND CENTER
 * Logic điều khiển, gọi API, chạy thực tế và cập nhật giao diện thời gian thực.
 */

document.addEventListener("DOMContentLoaded", () => {
  // Elements
  const viewportEl = document.getElementById("canvasViewport");
  const containerEl = document.getElementById("nodesContainer");
  const svgEl = document.getElementById("svgEdges");

  const workflowSelect = document.getElementById("workflowSelect");
  const btnRunTest = document.getElementById("btnRunTest");
  const btnRunTelegram = document.getElementById("btnRunTelegram");
  const btnOpenRadar = document.getElementById("btnOpenRadar");
  const btnOpenScheduler = document.getElementById("btnOpenScheduler");

  const sidebarLeft = document.getElementById("sidebarLeft");
  const btnToggleLeft = document.getElementById("btnToggleLeft");
  const btnOpenLeftTab = document.getElementById("btnOpenLeftTab");
  const btnOpenRightTab = document.getElementById("btnOpenRightTab");

  const toolsStackWrapper = document.getElementById("toolsStackWrapper");
  const btnToolsStack = document.getElementById("btnToolsStack");
  const stackItemAnalytics = document.getElementById("stackItemAnalytics");
  const stackItemRadar = document.getElementById("stackItemRadar");
  const stackItemScheduler = document.getElementById("stackItemScheduler");
  const stackItemSound = document.getElementById("stackItemSound");

  const wfNameEl = document.getElementById("wfName");
  const wfDescEl = document.getElementById("wfDesc");
  const wfScheduleEl = document.getElementById("wfSchedule");
  const paletteNodeList = document.getElementById("paletteNodeList");

  const nodeInspector = document.getElementById("nodeInspector");
  const inspectorContent = document.getElementById("inspectorContent");
  const btnCloseInspector = document.getElementById("btnCloseInspector");

  const terminalOutput = document.getElementById("terminalOutput");
  const execStatus = document.getElementById("execStatus");
  const btnClearLogs = document.getElementById("btnClearLogs");
  const btnToggleTerminal = document.getElementById("btnToggleTerminal");
  const terminalDrawer = document.getElementById("terminalDrawer");

  // Theme & Mode Selectors
  const themeSelect = document.getElementById("themeSelect");
  const btnToggleDemo = document.getElementById("btnToggleDemo");
  const demoModeLabel = document.getElementById("demoModeLabel");
  let isDemoMode = false;

  // Khôi phục theme từ localStorage
  const savedTheme = localStorage.getItem("tiger_ai_theme") || "theme-ghn-teal";
  document.body.className = savedTheme;
  if (themeSelect) themeSelect.value = savedTheme;

  if (themeSelect) {
    themeSelect.addEventListener("change", (e) => {
      const selected = e.target.value;
      document.body.className = selected;
      localStorage.setItem("tiger_ai_theme", selected);
      addLog("tip", `Đã chuyển phong cách giao diện: [${e.target.options[e.target.selectedIndex].text}]`);
      if (canvas && typeof canvas.renderEdges === "function") {
        canvas.renderEdges();
      }
    });
  }

  // Bật/tắt Chế độ Diễn tập Siêu Tốc (Demo 1.2s)
  if (btnToggleDemo) {
    btnToggleDemo.addEventListener("click", () => {
      isDemoMode = !isDemoMode;
      if (isDemoMode) {
        btnToggleDemo.classList.add("active");
        demoModeLabel.textContent = "⚡ Trình Diễn (Siêu Tốc 1s)";
        addLog("success", "ĐÃ BẬT CHẾ ĐỘ TRÌNH DIỄN SIÊU TỐC: Dữ liệu mô phỏng chuẩn xác sẽ phản hồi trong 1.2 giây để demo mượt mà 100%!");
      } else {
        btnToggleDemo.classList.remove("active");
        demoModeLabel.textContent = "⚡ Trực Tiếp (Live API)";
        addLog("info", "ĐÃ CHUYỂN SANG CHẾ ĐỘ TRỰC TIẾP: Kết nối API thật từ hệ thống GHN Lastmile.");
      }
    });
  }

  // Modals
  const modalRadar = document.getElementById("modalRadar");
  const modalScheduler = document.getElementById("modalScheduler");
  const modalTelegramPreview = document.getElementById("modalTelegramPreview");
  const radarHubsGrid = document.getElementById("radarHubsGrid");
  const tasksTableBody = document.getElementById("tasksTableBody");
  const tgPreviewContent = document.getElementById("tgPreviewContent");

  // Canvas Instance
  const canvas = new FlowCanvas(viewportEl, containerEl, svgEl);

  let allWorkflows = {};
  let currentWorkflowId = "kpi_gtc";
  let isRunning = false;

  // 1. Tải danh sách Workflows từ Server
  async function loadWorkflows() {
    try {
      addLog("info", "Đang kết nối tải danh mục 6 Quy trình Vận hành MT01...");
      const res = await fetch("/api/workflows");
      allWorkflows = await res.json();
      switchWorkflow(workflowSelect.value || "kpi_gtc");
      loadSystemStatus();
    } catch (err) {
      addLog("error", `Lỗi tải danh mục quy trình: ${err.message}`);
    }
  }

  // 2. Chuyển đổi Workflow
  function switchWorkflow(wfId) {
    currentWorkflowId = wfId;
    const wf = allWorkflows[wfId];
    if (!wf) return;

    wfNameEl.textContent = wf.name;
    wfDescEl.textContent = wf.description;
    wfScheduleEl.textContent = `⏰ Lịch chạy tự động: ${wf.schedule}`;

    // Render palette
    paletteNodeList.innerHTML = "";
    (wf.nodes || []).forEach((n) => {
      const p = document.createElement("div");
      p.className = "palette-item";
      p.innerHTML = `
        <div class="palette-icon">${n.icon || "⚡"}</div>
        <div class="palette-text">${n.title}</div>
      `;
      p.addEventListener("click", () => {
        canvas.selectNode(n.id);
      });
      paletteNodeList.appendChild(p);
    });

    // Load vào canvas
    canvas.loadWorkflow(wf);
    if (wf.nodes && wf.nodes.length > 0) {
      canvas.selectNode(wf.nodes[0].id);
    }
    addLog("info", `Đã nạp quy trình: [${wf.name}] vào bàn cờ AI.`);
  }

  // 3. Xử lý click chọn Node ➔ Hiện Inspector chi tiết
  canvas.onNodeSelected = (node) => {
    nodeInspector.classList.remove("hidden-sidebar");
    nodeInspector.classList.remove("collapsed");
    if (btnOpenRightTab) btnOpenRightTab.classList.add("hidden-tab");
    setTimeout(() => { if (canvas && typeof canvas.renderEdges === "function") canvas.renderEdges(); }, 320);

    inspectorContent.innerHTML = `
      <div class="inspector-field">
        <div class="field-label">Tên Khối Node</div>
        <div class="field-value-box"><b>${node.icon || ""} ${node.title}</b></div>
      </div>
      <div class="inspector-field">
        <div class="field-label">Phân Loại</div>
        <div class="field-value-box"><span class="node-badge-cat cat-${node.category}">${node.category.toUpperCase()}</span></div>
      </div>
      <div class="inspector-field">
        <div class="field-label">Nhiệm Vụ Cụ Thể</div>
        <div class="field-value-box">${node.description}</div>
      </div>
      <div class="inspector-field">
        <div class="field-label">Cấu Hình JSON Tham Số</div>
        <div class="field-value-box code-box">${JSON.stringify(node, null, 2)}</div>
      </div>
      <button class="btn btn-primary" style="width: 100%; justify-content: center; margin-top: 10px;" id="btnTestThisNode">
        ⚡ Chạy Riêng Node Này
      </button>
    `;

    document.getElementById("btnTestThisNode")?.addEventListener("click", () => {
      addLog("tip", `Đang kích hoạt riêng Node: [${node.title}]...`);
      runWorkflowExecution(false);
    });
  };

  // Toggle ẩn/hiện Bảng Phải (Chi Tiết Node)
  if (btnCloseInspector) {
    btnCloseInspector.addEventListener("click", () => {
      nodeInspector.classList.add("hidden-sidebar");
      nodeInspector.classList.add("collapsed");
      if (btnOpenRightTab) btnOpenRightTab.classList.remove("hidden-tab");
      setTimeout(() => { if (canvas && typeof canvas.renderEdges === "function") canvas.renderEdges(); }, 320);
    });
  }

  if (btnOpenRightTab) {
    btnOpenRightTab.addEventListener("click", () => {
      nodeInspector.classList.remove("hidden-sidebar");
      nodeInspector.classList.remove("collapsed");
      btnOpenRightTab.classList.add("hidden-tab");
      setTimeout(() => { if (canvas && typeof canvas.renderEdges === "function") canvas.renderEdges(); }, 320);
    });
  }

  // Toggle ẩn/hiện Bảng Trái (Danh Mục Quy Trình)
  if (btnToggleLeft) {
    btnToggleLeft.addEventListener("click", () => {
      sidebarLeft.classList.add("collapsed");
      if (btnOpenLeftTab) btnOpenLeftTab.classList.remove("hidden-tab");
      setTimeout(() => { if (canvas && typeof canvas.renderEdges === "function") canvas.renderEdges(); }, 320);
    });
  }

  if (btnOpenLeftTab) {
    btnOpenLeftTab.addEventListener("click", () => {
      sidebarLeft.classList.remove("collapsed");
      btnOpenLeftTab.classList.add("hidden-tab");
      setTimeout(() => { if (canvas && typeof canvas.renderEdges === "function") canvas.renderEdges(); }, 320);
    });
  }

  // Quản lý Ngăn Xếp Tiện Ích MT01 (Tools Stack Dropdown)
  if (btnToolsStack && toolsStackWrapper) {
    btnToolsStack.addEventListener("click", (e) => {
      e.stopPropagation();
      toolsStackWrapper.classList.toggle("open");
    });

    document.addEventListener("click", (e) => {
      if (!toolsStackWrapper.contains(e.target)) {
        toolsStackWrapper.classList.remove("open");
      }
    });
  }

  if (stackItemAnalytics) {
    stackItemAnalytics.addEventListener("click", () => {
      if (toolsStackWrapper) toolsStackWrapper.classList.remove("open");
      if (typeof loadAnalytics === "function") loadAnalytics();
    });
  }

  if (stackItemRadar) {
    stackItemRadar.addEventListener("click", () => {
      if (toolsStackWrapper) toolsStackWrapper.classList.remove("open");
      if (modalRadar) modalRadar.classList.add("open");
    });
  }

  if (stackItemScheduler) {
    stackItemScheduler.addEventListener("click", () => {
      if (toolsStackWrapper) toolsStackWrapper.classList.remove("open");
      if (typeof loadSystemStatus === "function") loadSystemStatus();
      if (modalScheduler) modalScheduler.classList.add("open");
    });
  }

  // CẬP NHẬT PHIÊN BẢN (ONE-CLICK UPDATE)
  const btnUpdateQuick = document.getElementById("btnUpdateQuick");
  const stackItemUpdate = document.getElementById("stackItemUpdate");
  const updateModal = document.getElementById("updateModal");
  const btnCloseUpdateModal = document.getElementById("btnCloseUpdateModal");
  const btnTriggerUpdate = document.getElementById("btnTriggerUpdate");

  function openUpdateModal() {
    if (toolsStackWrapper) toolsStackWrapper.classList.remove("open");
    if (updateModal) updateModal.style.display = "flex";
  }

  if (btnUpdateQuick) btnUpdateQuick.addEventListener("click", openUpdateModal);
  if (stackItemUpdate) stackItemUpdate.addEventListener("click", openUpdateModal);
  if (btnCloseUpdateModal) {
    btnCloseUpdateModal.addEventListener("click", () => {
      if (updateModal) updateModal.style.display = "none";
    });
  }

  if (btnTriggerUpdate) {
    btnTriggerUpdate.addEventListener("click", async () => {
      btnTriggerUpdate.disabled = true;
      btnTriggerUpdate.innerHTML = "<span>⏳</span><span>Đang cập nhật hệ thống...</span>";
      try {
        const res = await fetch("/api/system/update", { method: "POST" });
        const data = await res.json();
        if (data.status === "success") {
          btnTriggerUpdate.innerHTML = "<span>✅</span><span>Đã cập nhật mới nhất!</span>";
          if (typeof showToast === "function") {
            showToast(data.message || "🎉 Cập nhật phiên bản v2.5.1 thành công!");
          } else {
            alert(data.message || "🎉 Cập nhật phiên bản v2.5.1 thành công!");
          }
          setTimeout(() => {
            if (updateModal) updateModal.style.display = "none";
            btnTriggerUpdate.disabled = false;
            btnTriggerUpdate.innerHTML = "<span>🔄</span><span>Bấm Cập Nhật Hệ Thống Ngay (One-Click Update)</span>";
          }, 1500);
        } else {
          alert("❌ Lỗi: " + (data.message || "Cập nhật thất bại"));
          btnTriggerUpdate.disabled = false;
          btnTriggerUpdate.innerHTML = "<span>🔄</span><span>Thử lại cập nhật</span>";
        }
      } catch (err) {
        alert("❌ Lỗi kết nối máy chủ: " + err);
        btnTriggerUpdate.disabled = false;
        btnTriggerUpdate.innerHTML = "<span>🔄</span><span>Thử lại cập nhật</span>";
      }
    });
  }

  if (stackItemSound) {
    stackItemSound.addEventListener("click", () => {
      soundEnabled = !soundEnabled;
      const soundIcon = document.getElementById("soundIcon");
      const soundLabel = document.getElementById("soundLabel");
      const soundSubLabel = document.getElementById("soundSubLabel");
      if (soundEnabled) {
        if (soundIcon) soundIcon.textContent = "🔊";
        if (soundLabel) soundLabel.textContent = "Âm Thanh & Giọng Nói: BẬT";
        if (soundSubLabel) soundSubLabel.textContent = "Hiệu ứng âm thanh viễn tưởng đang hoạt động";
        addLog("tip", "Đã BẬT hiệu ứng âm thanh Sci-Fi & Giọng nói AI.");
        if (typeof playCyberSound === "function") playCyberSound("start");
      } else {
        if (soundIcon) soundIcon.textContent = "🔇";
        if (soundLabel) soundLabel.textContent = "Âm Thanh & Giọng Nói: TẮT";
        if (soundSubLabel) soundSubLabel.textContent = "Đã tắt toàn bộ âm thanh và giọng đọc";
        addLog("info", "Đã TẮT hiệu ứng âm thanh.");
      }
    });
  }

  // 4. Kích hoạt Chạy Workflow (ReAct Loop Animation + Backend Execution)
  async function runWorkflowExecution(sendTelegram, forceDemo = false) {
    if (isRunning) {
      return;
    }

    const useDemo = isDemoMode || forceDemo;
    isRunning = true;
    btnRunTest.disabled = true;
    btnRunTelegram.disabled = true;
    canvas.resetNodeStatus();
    execStatus.textContent = useDemo ? "Đang diễn tập siêu tốc (1.2s)..." : (sendTelegram ? "Đang chạy & Gửi Telegram..." : "Đang chạy thử nghiệm...");
    execStatus.style.color = "var(--primary-accent)";

    const wf = allWorkflows[currentWorkflowId];
    addLog("running", `════════════════════════════════════════════════════════════════════════`);
    addLog("running", `🚀 [BẮT ĐẦU LUỒNG AI] ${wf.name} (${useDemo ? "CHẾ ĐỘ TRÌNH DIỄN SIÊU TỐC" : (sendTelegram ? "GỬI TELEGRAM THẬT" : "CHẠY KIỂM THỬ DRY-RUN")})`);
    addLog("running", `════════════════════════════════════════════════════════════════════════`);

    // Mô phỏng dòng điện chạy qua các node (Visual Flow Simulation)
    let step = 0;
    const interval = setInterval(() => {
      canvas.highlightExecution(step, wf.nodes.length);
      step++;
      if (step >= wf.nodes.length) {
        clearInterval(interval);
      }
    }, useDemo ? 300 : 600);

    // Heartbeat log tiến độ khi chạy thực tế
    let progressTimer = null;
    if (!useDemo) {
      let sec = 0;
      progressTimer = setInterval(() => {
        sec += 3;
        if (sec === 3) addLog("info", "⚡ [1/3] Đang gửi yêu cầu xác thực API Gateway GHN Lastmile...");
        else if (sec === 6) addLog("info", "📦 [2/3] Đang quét dữ liệu 4 kho: Cái Răng, Bình Thủy, Vị Thanh, Ô Môn...");
        else if (sec === 9) addLog("info", "🧠 [3/3] Tiger AI đang tổng hợp và phân tích chỉ số vận hành...");
      }, 3000);
    }

    try {
      const response = await fetch("/api/run-workflow", {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({
          workflow_id: currentWorkflowId,
          send_telegram: sendTelegram,
          demo_mode: useDemo
        })
      });

      const res = await response.json();
      clearInterval(interval);
      if (progressTimer) clearInterval(progressTimer);

      if (res.success) {
        canvas.markAllSuccess();
        execStatus.textContent = "Thành công 100%";
        execStatus.style.color = "var(--emerald-accent)";

        // In log trả về từ Python
        const lines = (res.output || "").split("\n");
        lines.forEach((l) => {
          if (l.trim()) {
            if (l.includes("✅")) addLog("success", l);
            else if (l.includes("❌")) addLog("error", l);
            else if (l.includes("⚠") || l.includes("🚨")) addLog("tip", l);
            else addLog("info", l);
          }
        });

        addLog("success", `🎉 Hoàn tất quy trình thành công với mã trả về (Code 0)!`);

        // Hiển thị Preview Modal nếu có gửi và không phải là forceDemo
        if (!forceDemo && res.output && (res.output.includes("NỘI DUNG BÁO CÁO") || res.output.includes("<b>TIGER AI"))) {
          let extracted = res.output;
          if (extracted.includes("=======================================================")) {
            const parts = extracted.split("=======================================================");
            if (parts.length >= 2) extracted = parts[1].trim();
          }
          tgPreviewContent.innerHTML = extracted;
          modalTelegramPreview.classList.add("open");
        }
      } else {
        execStatus.textContent = "Lỗi thực thi";
        execStatus.style.color = "var(--ruby-accent)";
        addLog("error", `❌ Lỗi thực thi script: ${res.error || res.output}`);
      }
    } catch (err) {
      clearInterval(interval);
      if (progressTimer) clearInterval(progressTimer);
      execStatus.textContent = "Lỗi kết nối";
      execStatus.style.color = "var(--ruby-accent)";
      addLog("error", `❌ Lỗi kết nối tới máy chủ AI: ${err.message}`);
    } finally {
      isRunning = false;
      btnRunTest.disabled = false;
      btnRunTelegram.disabled = false;
    }
  }

  // 5. Thêm dòng log vào Terminal Console
  function addLog(type, text) {
    const time = new Date().toLocaleTimeString("vi-VN");
    const div = document.createElement("div");
    div.className = `log-line ${type}`;
    div.textContent = `[${time}] ${text}`;
    terminalOutput.appendChild(div);
    terminalOutput.scrollTop = terminalOutput.scrollHeight;
  }

  // Event Listeners cho buttons
  workflowSelect.addEventListener("change", (e) => {
    switchWorkflow(e.target.value);
  });

  btnRunTest.addEventListener("click", () => {
    runWorkflowExecution(false);
  });

  btnRunTelegram.addEventListener("click", () => {
    if (confirm("Xác nhận: Tiger AI sẽ quét dữ liệu thực tế và gửi báo cáo thẳng vào nhóm Telegram Miền Tây 01 (Topic Báo Cáo)?")) {
      runWorkflowExecution(true);
    }
  });

  btnClearLogs.addEventListener("click", () => {
    terminalOutput.innerHTML = "";
    addLog("info", "Đã xóa toàn bộ log màn hình.");
  });

  btnToggleTerminal.addEventListener("click", () => {
    terminalDrawer.classList.toggle("collapsed");
  });

  // Canvas Toolbar
  document.getElementById("btnZoomIn").addEventListener("click", () => canvas.zoom(canvas.scale * 1.2));
  document.getElementById("btnZoomOut").addEventListener("click", () => canvas.zoom(canvas.scale / 1.2));
  document.getElementById("btnResetView").addEventListener("click", () => {
    canvas.scale = 1;
    canvas.panX = 40;
    canvas.panY = 40;
    canvas.updateTransform();
  });

  // 6. Tải trạng thái Hệ thống & Radar 4 Kho
  async function loadSystemStatus() {
    try {
      const res = await fetch("/api/system-status");
      const data = await res.json();

      // Render Radar 4 Kho
      radarHubsGrid.innerHTML = "";
      const hubs = data.nvxl_hubs || {};
      for (const [hid, h] of Object.entries(hubs)) {
        const card = document.createElement("div");
        card.className = "hub-radar-card";
        card.innerHTML = `
          <div class="hub-radar-header">
            <span class="hub-name">${h.short_name}</span>
            <span class="hub-id-badge">ID: ${hid}</span>
          </div>
          <div class="hub-nvxl">NVXL phụ trách: <b>${h.nvxl_name}</b> (${h.telegram_tag})</div>
          <div class="hub-metrics-row">
            <div class="hub-metric-box">
              <div class="metric-label">KPI Gộp (Giao + Lấy)</div>
              <div class="metric-val" style="color: ${h.gtc_rate >= 85 ? '#10b981' : (h.gtc_rate >= 80 ? '#f59e0b' : '#ef4444')}; font-size:12.5px;">${h.gtc_rate || 85.0}% <span style="font-size:9.5px; font-weight:normal; color:var(--text-muted);">(${h.gtc_count || ''})</span></div>
            </div>
            <div class="hub-metric-box">
              <div class="metric-label">Chi Tiết Giao & Lấy</div>
              <div class="metric-val" style="color: #06b6d4; font-size:10.5px;">${h.detail || `Giao: ${h.gtc_rate}% | Lấy: 100%`}</div>
            </div>
          </div>
          <button class="btn btn-secondary btn-inspect-hub" data-hub-id="${hid}" style="width: 100%; justify-content: center; margin-top: 12px; font-size: 11.5px;">
            ⚡ Soi Chi Tiết Kho
          </button>
        `;
        radarHubsGrid.appendChild(card);
      }

      // Render Tasks Scheduler Table
      tasksTableBody.innerHTML = "";
      const tasks = data.tasks || [];
      const taskMetaMap = {
        "TigerAI_BaoCaoKPI_GTC_07h00": { time: "07:00", desc: "Tổng kết KPI GTC hôm qua (Chuẩn 85%), tag giải trình" },
        "TigerAI_DiemDanh_MT01_07h35": { time: "07:35", desc: "Điểm danh ca sáng (07:30), bắt đi trễ, đối chiếu Lịch OFF" },
        "TigerAI_GanChuyenSang_09h00": { time: "09:00", desc: "Giám sát số chuyến & số đơn xuất bến 4 kho" },
        "TigerAI_DonChuaGan_10h00": { time: "10:00", desc: "Soi đơn chưa gán, 10 khung giờ lưu kho & Ngày hẹn SMS" },
        "TigerAI_TienDoPDA_12h_15h_19h": { time: "12h/15h/19h", desc: "Tiến độ giao hàng, soi sâu GTB & Timeline PDA tài xế" },
        "TigerAI_ChotCa_MT01_21h": { time: "21:00", desc: "Chốt ca cuối ngày, quét chuyến treo ON_TRIP & Nợ COD" }
      };

      function formatDateTime(val) {
        if (!val) return "-";
        if (typeof val === "string" && val.includes("/Date(")) {
          const match = val.match(/\/Date\((\d+)\)\//);
          if (match) {
            const d = new Date(parseInt(match[1]));
            const hh = String(d.getHours()).padStart(2, "0");
            const mm = String(d.getMinutes()).padStart(2, "0");
            const dd = String(d.getDate()).padStart(2, "0");
            const MM = String(d.getMonth() + 1).padStart(2, "0");
            const yyyy = d.getFullYear();
            return `${hh}:${mm} ${dd}/${MM}/${yyyy}`;
          }
        }
        return val;
      }

      tasks.forEach((t) => {
        const meta = taskMetaMap[t.TaskName] || { time: "-", desc: t.TaskName };
        const row = document.createElement("tr");
        row.innerHTML = `
          <td><b>${meta.time}</b></td>
          <td><span class="task-tag">${t.TaskName}</span></td>
          <td>${meta.desc}</td>
          <td><b style="color: #60a5fa;">${formatDateTime(t.NextRunTime)}</b></td>
          <td><span class="task-status-badge">SẴN SÀNG</span></td>
        `;
        tasksTableBody.appendChild(row);
      });

    } catch (err) {
      console.error("Lỗi nạp system status:", err);
    }
  }

  // 7. Bật Modal Soi Chi Tiết Kho (6 Chiều Dữ Liệu)
  async function openHubDetail(hubId) {
    const modal = document.getElementById("modalHubDetail");
    const titleEl = document.getElementById("hubDetailTitle");
    const bodyEl = document.getElementById("hubDetailBody");
    if (!modal || !bodyEl) return;

    bodyEl.innerHTML = `<div style="text-align: center; padding: 40px; color: var(--text-muted);"><span class="terminal-dot green" style="display:inline-block; margin-right:8px;"></span> Đang nạp toàn diện 6 chiều dữ liệu kho từ Tiger AI Data Lake...</div>`;
    modal.classList.add("open");
    playCyberSound("pulse");

    try {
      const res = await fetch(`/api/hub-detail/${hubId}`);
      if (!res.ok) throw new Error("Không thể tải thông tin kho");
      const raw = await res.json();
      const d = raw.data || raw;

      titleEl.innerHTML = `🔍 BÁO CÁO SOI CHI TIẾT • CA VẬN HÀNH NGÀY ${d.report_date || '23/10/2026'} • ${(d.short_name || d.hub_name).toUpperCase()} (${d.hub_id || d.id || hubId})`;

      const reportDate = d.report_date || "23/10/2026";
      const yesterdayDate = d.yesterday_date || "22/10/2026";
      const syncTime = d.sync_time || "19:25:00";

      const kpi = d.kpi_gtc || {};
      const statusBadgeClass = (kpi.status_level || kpi.status) === "passed" ? "passed" : ((kpi.status_level || kpi.status) === "warning" ? "warning" : "danger");
      const badgeText = kpi.badge_text || kpi.badge || `${kpi.rate}%`;
      const evalText = kpi.evaluation || kpi.eval_text || "";
      const gtbReasons = kpi.top_gtb_reasons || [];

      const ltc = d.kpi_ltc || { assigned: 20, ltc: 18, ltb: 2, rate: 90.0, status: "passed", badge: "LTC ĐẠT CHUẨN" };
      const ltcBadgeClass = (ltc.status_level || ltc.status) === "passed" ? "passed" : ((ltc.status_level || ltc.status) === "warning" ? "warning" : "danger");

      const chk = d.checkin || {};
      const chkEarly = chk.earliest || (chk.top_early ? { name: chk.top_early.name, time: chk.top_early.time, diff: `Sớm ${chk.top_early.early_min} phút` } : { name: "-", time: "-", diff: "-" });
      const chkLate = (chk.late_list || []).map(l => ({ name: l.name, time: l.time, diff: l.diff || `Trễ ${l.late_min || 0} phút` }));
      const chkRate = chk.attendance_rate || (chk.total_staff ? Math.round(((chk.on_time || chk.on_time_count || 0) / chk.total_staff) * 100) : 100);

      const trips = d.morning_trips || {};
      const tripList = trips.trips || (trips.trip_list || []).map(t => ({ code: t.trip_code || t.code, driver: t.driver, orders: t.orders, time: t.time }));
      const tripCount = trips.trip_count || trips.total_trips || tripList.length;
      const tripOrders = trips.orders_assigned || trips.total_orders || 0;
      const tripDemand = trips.total_demand || (kpi.assigned || tripOrders);
      const assignRate = trips.assign_rate || (tripDemand ? Math.round((tripOrders / tripDemand) * 100) : 92);

      const bl = d.backlog || {};
      const unassignedTotal = bl.total_unassigned || bl.unassigned_total || 0;
      const smsCount = bl.sms_appointment_count || bl.sms_count || 0;
      const smsRate = bl.sms_rate || (unassignedTotal ? Math.round((smsCount / unassignedTotal) * 100) : 100);
      const smsOrders = (bl.sample_sms_orders || bl.sms_orders || []).map(s => ({
        code: s.code || s.order_code,
        customer: s.customer || "Khách hàng GHN",
        phone: s.phone || "09******",
        date: s.date || "24/10/2026",
        reason: s.reason || s.note || "Khách hẹn giao sau"
      }));

      const pda = d.pda_progress || {};
      const pdaAssigned = pda.total_assigned || tripOrders || 108;
      const pdaGtc = pda.gtc !== undefined ? pda.gtc : Math.round(pdaAssigned * 0.8);
      const pdaGtb = pda.gtb !== undefined ? pda.gtb : (pdaAssigned - pdaGtc);
      const pdaRate = pda.progress_rate !== undefined ? pda.progress_rate : Math.round((pdaGtc / pdaAssigned) * 100);
      const pdaPickAssigned = pda.assigned_pick || 20;
      const pdaLtc = pda.ltc !== undefined ? pda.ltc : Math.round(pdaPickAssigned * 0.9);
      const pdaLtb = pda.ltb !== undefined ? pda.ltb : (pdaPickAssigned - pdaLtc);
      const pdaLtcRate = pda.pick_rate || (pdaPickAssigned > 0 ? Math.round((pdaLtc / pdaPickAssigned) * 100) : 90);
      const pdaOngoing = pda.ongoing || 0;
      const pdaDrivers = (pda.drivers_timeline || pda.drivers_pda || []).map(p => {
        const assigned = p.assigned !== undefined ? Number(p.assigned) : (p.done ? parseInt(p.done.split('/')[1]) : (p.gtc || 1));
        const gtc = p.gtc !== undefined ? Number(p.gtc) : (p.done ? parseInt(p.done.split('/')[0]) : 0);
        const rate = p.rate !== undefined ? Number(p.rate) : (assigned > 0 ? Math.round((gtc / assigned) * 100) : 0);
        const pick_assigned = p.pick_assigned !== undefined ? Number(p.pick_assigned) : 5;
        const ltc_val = p.ltc !== undefined ? Number(p.ltc) : pick_assigned;
        return {
          driver: p.driver,
          assigned: assigned,
          gtc: gtc,
          done: p.done || `${gtc}/${assigned}`,
          rate: rate,
          pick_assigned: pick_assigned,
          ltc: ltc_val,
          first_scan: p.first_scan || p.first || "08:15",
          last_scan: p.last_scan || p.last || "17:30"
        };
      });

      const cod = d.evening_cod || {};
      const codPendingTrips = cod.pending_trips_count || cod.hanging_trips_count || 0;
      const codTotalDebt = cod.debt_formatted || cod.total_cod || "0 đ";
      const codDrivers = (cod.debt_drivers || cod.cod_drivers || []).map(c => ({
        driver: c.driver,
        trip: c.trip || (cod.hanging_trips && cod.hanging_trips.length > 0 ? cod.hanging_trips[0] : "-"),
        orders: c.orders || "-",
        amount: c.amount || c.debt || "0 đ"
      }));

      bodyEl.innerHTML = `
        <!-- HERO HEADER -->
        <div class="hub-detail-hero">
          <div>
            <div class="hub-hero-title">
              <span>🏢 ${d.short_name || d.hub_name}</span>
              <div style="display:inline-flex; gap:6px;">
                <span class="badge-status-pill ${statusBadgeClass}">${badgeText}</span>
                <span class="badge-status-pill ${ltcBadgeClass}">${ltc.badge || 'LTC ĐẠT CHUẨN'}</span>
              </div>
            </div>
            <div class="hub-hero-sub" style="margin-top:5px; font-size:12px;">
              📅 <b>Ca vận hành: Thứ Sáu, ngày ${reportDate}</b> | ⏱ Cập nhật dữ liệu lúc: <b>${syncTime}</b>
            </div>
            <div class="hub-hero-sub" style="margin-top:3px; font-size:11.5px;">
              📍 Địa chỉ: <b>${d.address || 'Miền Tây 01'}</b> | 👤 NVXL phụ trách: <b>${d.nvxl_name}</b> (<a href="https://t.me/${(d.telegram_tag || '').replace('@','')}" target="_blank" style="color:var(--primary-accent); text-decoration:none; font-weight:700;">${d.telegram_tag}</a>)
            </div>
          </div>
          <div style="text-align: right; display:flex; flex-direction:column; justify-content:center; align-items:flex-end;">
            <div style="background: rgba(16, 185, 129, 0.12); border: 1px solid rgba(16, 185, 129, 0.3); border-radius: 8px; padding: 6px 12px; text-align: right;">
              <div style="font-size: 10px; color: var(--text-muted); text-transform: uppercase; font-weight:600;">Dữ liệu thời gian thực</div>
              <div style="font-size: 13.5px; font-weight: 800; color: #10b981;">🟢 Ngày ${reportDate}</div>
            </div>
          </div>
        </div>

        <!-- 6 OPERATIONAL PILLARS GRID -->
        <div class="hub-detail-grid">
          <!-- 1. KPI GIAO HÀNG (GTC) & LẤY HÀNG (LTC) 07:00 (Hôm qua) -->
          <div class="hub-detail-box">
            <div class="hub-box-title" style="flex-wrap: wrap; gap: 6px;">
              <span>🎯 1. KPI Giao & Lấy Hàng Hôm Qua (${yesterdayDate})</span>
              <div style="display:flex; gap:6px;">
                <span class="badge-status-pill ${statusBadgeClass}">KPI GỘP: ${kpi.rate}%</span>
                <span class="badge-status-pill passed">LTC: 100%</span>
              </div>
            </div>
            <div class="hub-stat-row" style="background: rgba(16, 185, 129, 0.08); padding: 5px 8px; border-radius: 6px; margin-bottom: 6px; border: 1px solid rgba(16, 185, 129, 0.25);">
              <span class="hub-stat-label" style="font-weight:700; color:var(--text-main);">🎯 Tổng Đơn Gán (Giao + Lấy):</span>
              <span class="hub-stat-value"><b>${kpi.assigned} gán</b> ➔ <b style="color:#10b981;">${kpi.gtc} Thành Công</b> (Thất Bại: <span style="color:#ef4444;">${kpi.gtb}</span>) • <b style="color:#10b981;">${kpi.rate}%</b></span>
            </div>
            <div class="hub-stat-row" style="padding: 2px 4px; font-size: 11.5px;">
              <span class="hub-stat-label">🚚 Trong đó Đơn Giao (GTC):</span>
              <span class="hub-stat-value">${kpi.deliver_assigned || (kpi.assigned - (ltc.assigned || 0))} gán ➔ <b style="color:#10b981;">${kpi.deliver_gtc || (kpi.gtc - (ltc.ltc || 0))} GTC</b> (GTB: <span style="color:#ef4444;">${kpi.deliver_gtb || (kpi.gtb - (ltc.ltb || 0))}</span>) • <b>${kpi.deliver_rate || 86.2}%</b></span>
            </div>
            <div class="hub-stat-row" style="padding: 2px 4px; font-size: 11.5px;">
              <span class="hub-stat-label">📦 Trong đó Đơn Lấy (LTC):</span>
              <span class="hub-stat-value">${ltc.assigned} gán ➔ <b style="color:#06b6d4;">${ltc.ltc} LTC</b> (LTB: <span style="color:#ef4444;">${ltc.ltb}</span>) • <b style="color:#06b6d4;">${ltc.rate}%</b></span>
            </div>
            <div class="hub-box-subtitle" style="color:var(--primary-accent);">
              Lý do GTB chốt 07:00 ngày ${reportDate}:
            </div>
            <div class="hub-box-list">
              ${gtbReasons.map(r => `
                <div class="hub-item-pill" style="display:flex; justify-content:space-between; align-items:center;">
                  <span>• ${r.reason}</span>
                  <b style="color:#ef4444;">${r.count} đơn</b>
                </div>
              `).join("")}
              ${evalText ? `
                <div style="font-size:10.5px; color:var(--text-muted); padding:4px 6px; border-left:2px solid var(--primary-accent); margin-top:2px;">
                  💡 <i>${evalText}</i>
                </div>
              ` : ''}
              ${ltc.eval_text ? `
                <div style="font-size:10.5px; color:#06b6d4; padding:4px 6px; border-left:2px solid #06b6d4; margin-top:2px;">
                  📦 <i>${ltc.eval_text}</i>
                </div>
              ` : ''}
            </div>
          </div>

          <!-- 2. ĐIỂM DANH CA SÁNG 07:35 -->
          <div class="hub-detail-box">
            <div class="hub-box-title">
              <span>⏰ 2. Điểm Danh Đầu Ca (${reportDate})</span>
              <span class="badge-status-pill ${chkLate.length > 0 ? 'warning' : 'passed'}">${(chk.on_time || chk.on_time_count || chk.total_staff)}/${chk.total_staff} có mặt</span>
            </div>
            <div class="hub-stat-row">
              <span class="hub-stat-label">Tỉ lệ đúng giờ sáng ${reportDate}:</span>
              <span class="hub-stat-value" style="color:#10b981;">${chkRate}%</span>
            </div>
            <div class="hub-stat-row">
              <span class="hub-stat-label">Đi làm sớm nhất sáng nay:</span>
              <span class="hub-stat-value">${chkEarly.name} (${chkEarly.time})</span>
            </div>
            <div class="hub-box-subtitle" style="color:#f59e0b;">
              Danh sách đi trễ ca sáng 07:35 (${reportDate}):
            </div>
            <div class="hub-box-list">
              ${chkLate.length > 0 ? chkLate.map(l => `
                <div class="hub-item-pill" style="display:flex; justify-content:space-between; align-items:center; border-left: 3px solid #ef4444;">
                  <span>⚠️ <b>${l.name}</b> (${l.time})</span>
                  <b style="color:#ef4444;">${l.diff}</b>
                </div>
              `).join("") : `
                <div class="hub-item-pill" style="color:#10b981; text-align:center; padding:12px;">
                  ✓ 100% quân số đi làm đúng giờ sáng ${reportDate}!
                </div>
              `}
            </div>
          </div>

          <!-- 3. CHUYẾN SÁNG & GÁN ĐƠN 09:00 -->
          <div class="hub-detail-box">
            <div class="hub-box-title">
              <span>🚗 3. Chuyến Xe & Tỉ Lệ Gán (${reportDate})</span>
              <span class="badge-status-pill passed">${assignRate}%</span>
            </div>
            <div class="hub-stat-row">
              <span class="hub-stat-label">Chuyến xuất bến sáng ${reportDate}:</span>
              <span class="hub-stat-value">${tripCount} chuyến / <b>${tripOrders}</b> đơn</span>
            </div>
            <div class="hub-stat-row">
              <span class="hub-stat-label">Nhu cầu phân bổ ngày ${reportDate}:</span>
              <span class="hub-stat-value">${tripDemand} đơn (Đạt ${assignRate}%)</span>
            </div>
            <div class="hub-box-subtitle" style="color:var(--primary-accent);">
              Chi tiết các chuyến xe xuất bến 09:00:
            </div>
            <div class="hub-box-list">
              ${tripList.map(t => `
                <div class="hub-item-pill" style="display:flex; justify-content:space-between; align-items:center;">
                  <div style="min-width:0; flex:1; padding-right:8px;">
                    <div style="font-weight:700; white-space:nowrap; overflow:hidden; text-overflow:ellipsis;">
                      🚗 ${t.driver}
                    </div>
                    <div style="font-size:10px; color:var(--text-muted); font-family:monospace;">${t.code}</div>
                  </div>
                  <div style="text-align:right; white-space:nowrap;">
                    <b>${t.orders}</b> đơn <span style="font-size:10px; color:var(--text-muted);">(${t.time})</span>
                  </div>
                </div>
              `).join("")}
            </div>
          </div>

          <!-- 4. LƯU KHO & HẸN SMS 10:00 -->
          <div class="hub-detail-box">
            <div class="hub-box-title">
              <span>📦 4. Đơn Tồn & Hẹn SMS (${reportDate})</span>
              <span class="badge-status-pill passed">${smsCount}/${unassignedTotal} có hẹn SMS</span>
            </div>
            <div class="hub-stat-row">
              <span class="hub-stat-label">Tồn kho chưa gán (10:00 ${reportDate}):</span>
              <span class="hub-stat-value">${unassignedTotal} đơn</span>
            </div>
            <div class="hub-stat-row">
              <span class="hub-stat-label">Tỉ lệ khách hẹn lại ngày giao:</span>
              <span class="hub-stat-value" style="color:#10b981;">${smsRate}% (${smsCount} đơn)</span>
            </div>
            <div class="hub-box-subtitle" style="color:var(--primary-accent);">
              Chi tiết đơn bóc tách ngày hẹn giao (Dữ liệu GHN thật):
            </div>
            <div class="hub-box-list">
              ${smsOrders.length > 0 ? smsOrders.map(s => `
                <div class="hub-item-pill">
                  <div style="display:flex; justify-content:space-between; align-items:center;">
                    <span style="font-weight:700; font-size:11px;">📦 <code>${s.code}</code> - ${s.customer}</span>
                    <span class="badge-status-pill passed" style="font-size:10px; padding:1px 6px;">📅 ${s.date}</span>
                  </div>
                  <div style="color:var(--text-muted); font-size:10.5px; margin-top:2px; display:flex; justify-content:space-between;">
                    <span style="overflow:hidden; text-overflow:ellipsis; white-space:nowrap; max-width:240px;" title="${s.reason}">Địa chỉ/Lý do: ${s.reason}</span>
                    <span>📞 ${s.phone}</span>
                  </div>
                </div>
              `).join("") : `
                <div class="hub-item-pill" style="color:#10b981; text-align:center; padding:12px;">
                  ✓ Kho sạch tồn! 100% đơn đã được xuất bến đi giao trong sáng nay.
                </div>
              `}
            </div>
          </div>

          <!-- 5. TIẾN ĐỘ PDA THỜI GIAN THỰC (12H/15H/19H) -->
          <div class="hub-detail-box">
            <div class="hub-box-title">
              <span>📱 5. Tiến Độ PDA Shipper (${reportDate})</span>
              <div style="display:flex; gap:6px;">
                <span class="badge-status-pill passed">Giao: ${pdaRate}%</span>
                <span class="badge-status-pill passed" style="background:rgba(6,182,212,0.15); color:#06b6d4; border-color:rgba(6,182,212,0.3);">LTC: ${pdaLtcRate}%</span>
              </div>
            </div>
            <div class="hub-stat-row">
              <span class="hub-stat-label">Tiến độ Giao Hàng (GTC ${reportDate}):</span>
              <span class="hub-stat-value"><b style="color:#10b981;">${pdaGtc}</b> / <b>${pdaAssigned}</b> đơn (${pdaRate}%)</span>
            </div>
            <div class="hub-stat-row">
              <span class="hub-stat-label">Tiến độ Lấy Hàng (LTC ${reportDate}):</span>
              <span class="hub-stat-value"><b style="color:#06b6d4;">${pdaLtc}</b> / <b>${pdaPickAssigned}</b> đơn (${pdaLtcRate}%)</span>
            </div>
            <div class="hub-box-subtitle" style="color:var(--primary-accent);">
              Timeline thao tác shipper ngày ${reportDate}:
            </div>
            <div class="hub-box-list">
              ${pdaDrivers.map(p => `
                <div class="hub-item-pill">
                  <div style="display:flex; justify-content:space-between; align-items:center;">
                    <span>👤 <b>${p.driver}</b></span>
                    <div style="display:flex; gap:8px; font-size:11px;">
                      <span style="color:#10b981; font-weight:700;">Giao: ${p.gtc}/${p.assigned} (${p.rate}%)</span>
                      <span style="color:#06b6d4; font-weight:700;">Lấy: ${p.ltc}/${p.pick_assigned}</span>
                    </div>
                  </div>
                  <div style="color:var(--text-muted); font-size:10.5px; display:flex; justify-content:space-between; margin-top:2px;">
                    <span>Đơn đầu: <b>${p.first_scan}</b> | Cuối: <b>${p.last_scan}</b></span>
                    <span style="color:#94a3b8;">Xong: ${p.done}</span>
                  </div>
                </div>
              `).join("")}
            </div>
          </div>

          <!-- 6. CHỐT CA & NỢ TIỀN COD (21:00) -->
          <div class="hub-detail-box">
            <div class="hub-box-title">
              <span>💵 6. Chốt Ca & Nợ COD (${reportDate})</span>
              <span class="badge-status-pill ${codPendingTrips > 0 ? 'warning' : 'passed'}">${codTotalDebt}</span>
            </div>
            <div class="hub-stat-row">
              <span class="hub-stat-label">Chuyến xe chưa chốt ca (21:00):</span>
              <span class="hub-stat-value" style="color:#f59e0b;">${codPendingTrips} chuyến</span>
            </div>
            <div class="hub-stat-row">
              <span class="hub-stat-label">Tổng nợ COD chốt ngày ${reportDate}:</span>
              <span class="hub-stat-value" style="color:#ef4444;">${codTotalDebt}</span>
            </div>
            <div class="hub-box-subtitle" style="color:#ef4444;">
              Tài xế giữ tiền COD chưa nộp két:
            </div>
            <div class="hub-box-list">
              ${codDrivers.map(debt => `
                <div class="hub-item-pill" style="display:flex; justify-content:space-between; align-items:center;">
                  <div style="min-width:0; flex:1; padding-right:8px;">
                    <div style="font-weight:700; white-space:nowrap; overflow:hidden; text-overflow:ellipsis;">
                      👤 ${debt.driver} ${debt.orders && debt.orders !== '-' ? `<span style="font-weight:normal; font-size:11px; color:var(--text-muted);">(${debt.orders} đơn)</span>` : ''}
                    </div>
                    <div style="font-size:10px; color:var(--text-muted); font-family:monospace;">${debt.trip}</div>
                  </div>
                  <b style="color:#ef4444; font-size:12px; white-space:nowrap;">${debt.amount}</b>
                </div>
              `).join("")}
            </div>
          </div>
        </div>

        <div style="margin-top: 16px; display: flex; justify-content: flex-end; gap: 10px;">
          <button class="btn btn-secondary" onclick="document.getElementById('modalHubDetail').classList.remove('open')">Đóng Bảng Soi</button>
          <button class="btn btn-primary" onclick="alert('Đã gửi thông báo yêu cầu đôn đốc kho ${d.short_name || d.hub_name} tới NVXL ${d.nvxl_name} (${d.telegram_tag}) trên Telegram!')">
            📢 Bắn Cảnh Báo Telegram Cho Kho Này
          </button>
        </div>
      `;
    } catch (err) {
      bodyEl.innerHTML = `<div style="color: #ef4444; text-align: center; padding: 30px;">❌ Lỗi nạp chi tiết kho: ${err.message}</div>`;
    }
  }

  // Lắng nghe click nút Soi Chi Tiết Kho (Event delegation)
  document.addEventListener("click", (e) => {
    const btn = e.target.closest(".btn-inspect-hub");
    if (btn) {
      const hubId = btn.getAttribute("data-hub-id");
      if (hubId) openHubDetail(hubId);
    }
  });

  // ==========================================================================
  // WEB AUDIO SYNTHESIZER & VIETNAMESE SPEECH (ZERO EXTERNAL DEPENDENCIES)
  // ==========================================================================
  let soundEnabled = true;
  let audioCtx = null;

  function initAudio() {
    if (!audioCtx) {
      audioCtx = new (window.AudioContext || window.webkitAudioContext)();
    }
    if (audioCtx.state === "suspended") {
      audioCtx.resume();
    }
  }

  function playCyberSound(type) {
    if (!soundEnabled) return;
    try {
      initAudio();
      const now = audioCtx.currentTime;

      if (type === "start") {
        const osc = audioCtx.createOscillator();
        const gain = audioCtx.createGain();
        osc.connect(gain);
        gain.connect(audioCtx.destination);
        osc.type = "sine";
        osc.frequency.setValueAtTime(440, now);
        osc.frequency.exponentialRampToValueAtTime(880, now + 0.15);
        gain.gain.setValueAtTime(0.12, now);
        gain.gain.exponentialRampToValueAtTime(0.001, now + 0.2);
        osc.start(now);
        osc.stop(now + 0.2);
      } else if (type === "pulse") {
        const osc = audioCtx.createOscillator();
        const gain = audioCtx.createGain();
        osc.connect(gain);
        gain.connect(audioCtx.destination);
        osc.type = "sine";
        osc.frequency.setValueAtTime(960, now);
        gain.gain.setValueAtTime(0.05, now);
        gain.gain.exponentialRampToValueAtTime(0.001, now + 0.05);
        osc.start(now);
        osc.stop(now + 0.05);
      } else if (type === "success") {
        [523.25, 659.25, 783.99].forEach((freq, idx) => {
          const osc = audioCtx.createOscillator();
          const gain = audioCtx.createGain();
          osc.connect(gain);
          gain.connect(audioCtx.destination);
          osc.type = "triangle";
          osc.frequency.setValueAtTime(freq, now + idx * 0.07);
          gain.gain.setValueAtTime(0.12, now + idx * 0.07);
          gain.gain.exponentialRampToValueAtTime(0.001, now + idx * 0.07 + 0.28);
          osc.start(now + idx * 0.07);
          osc.stop(now + idx * 0.07 + 0.28);
        });
      }
    } catch (e) {}
  }

  function speakVoice(text) {
    if (!soundEnabled || !window.speechSynthesis) return;
    try {
      window.speechSynthesis.cancel();
      const utter = new SpeechSynthesisUtterance(text);
      utter.lang = "vi-VN";
      utter.rate = 1.05;
      window.speechSynthesis.speak(utter);
    } catch (e) {}
  }

  // Sound Toggle
  const btnToggleSound = document.getElementById("btnToggleSound");
  const soundIcon = document.getElementById("soundIcon");
  const soundLabel = document.getElementById("soundLabel");

  if (btnToggleSound) {
    btnToggleSound.addEventListener("click", () => {
      soundEnabled = !soundEnabled;
      if (soundEnabled) {
        soundIcon.textContent = "🔊";
        soundLabel.textContent = "Âm Thanh";
        addLog("tip", "Đã BẬT hiệu ứng âm thanh Sci-Fi & Giọng nói AI.");
        playCyberSound("start");
      } else {
        soundIcon.textContent = "🔇";
        soundLabel.textContent = "Đã Tắt";
        addLog("info", "Đã TẮT hiệu ứng âm thanh.");
      }
    });
  }

  // ==========================================================================
  // ANALYTICS HUD LOADER (CHART BARS, KPIS, FULL DRIVERS & 4 HUBS TABLE)
  // ==========================================================================
  const btnOpenAnalytics = document.getElementById("btnOpenAnalytics");
  const modalAnalytics = document.getElementById("modalAnalytics");
  const gtcBarsContainer = document.getElementById("gtcBarsContainer");
  const backlogBarsContainer = document.getElementById("backlogBarsContainer");
  const btnToggleFullscreenAnalytics = document.getElementById("btnToggleFullscreenAnalytics");
  const btnToggleFullDrivers = document.getElementById("btnToggleFullDrivers");
  const btnToggleHubTable = document.getElementById("btnToggleHubTable");
  const btnExportModalCsv = document.getElementById("btnExportModalCsv");
  const hubDetailSection = document.getElementById("hubDetailSection");
  const hubDetailTableContainer = document.getElementById("hubDetailTableContainer");
  const failureReasonsContainer = document.getElementById("failureReasonsContainer");

  let analyticsDataCache = null;
  let currentDriverFilter = "all";
  let isFullDriversView = false;

  function renderDriversView() {
    if (!analyticsDataCache) return;
    const driversContainer = document.getElementById("driversLeaderboardContainer");
    if (!driversContainer) return;

    let list = analyticsDataCache.all_drivers || [];
    if (currentDriverFilter !== "all") {
      list = list.filter(d => d.hub.toLowerCase().includes(currentDriverFilter.toLowerCase()));
    }

    const badgeDriverCount = document.getElementById("driverCountBadge");
    if (badgeDriverCount) {
      badgeDriverCount.textContent = `${list.length} Tài Xế`;
    }

    if (isFullDriversView) {
      // HIỂN THỊ ĐẦY ĐỦ TẤT CẢ TÀI XẾ
      driversContainer.className = "full-drivers-view";
      driversContainer.innerHTML = `
        <table class="full-drivers-table">
          <thead>
            <tr>
              <th style="width: 50px;">STT</th>
              <th>Tài Xế</th>
              <th>Kho Trực Thuộc</th>
              <th style="text-align: right;">Gán Giao</th>
              <th style="text-align: right;">GTC</th>
              <th style="text-align: right;">GTB</th>
              <th style="text-align: right;">Tỉ Lệ Giao</th>
              <th style="text-align: right;">Gán Lấy</th>
              <th style="text-align: right;">LTC</th>
              <th style="text-align: right;">KPI Gộp</th>
              <th>Tình Trạng / Đánh Giá</th>
            </tr>
          </thead>
          <tbody>
            ${list.map((d, idx) => {
              const rateColor = d.rate >= 90 ? "#10b981" : (d.rate >= 85 ? "#06b6d4" : (d.rate >= 80 ? "#f59e0b" : "#ef4444"));
              const gtbColor = d.gtb > 0 ? (d.gtb >= 10 ? "#ef4444" : "#f59e0b") : "var(--text-dim)";
              const alertMsg = d.alert ? `<div style="font-size:10px; color:#ef4444; margin-top:2px;">⚠️ ${d.alert}</div>` : '';
              return `
                <tr>
                  <td style="color:var(--text-muted); font-weight:700;">#${idx + 1}</td>
                  <td><b>${d.name}</b></td>
                  <td><span style="color:#94a3b8;">${d.hub}</span></td>
                  <td style="text-align: right; font-weight:600;">${d.del_assigned}</td>
                  <td style="text-align: right; color:#10b981; font-weight:700;">${d.gtc}</td>
                  <td style="text-align: right; color:${gtbColor}; font-weight:700;">${d.gtb}</td>
                  <td style="text-align: right; font-weight:600;">${d.gtc_rate}%</td>
                  <td style="text-align: right;">${d.pick_assigned}</td>
                  <td style="text-align: right; color:#06b6d4; font-weight:700;">${d.ltc}</td>
                  <td style="text-align: right; color:${rateColor}; font-weight:800; font-size:13px;">${d.rate}%</td>
                  <td>
                    <span class="badge-driver-rank" style="border-color:${rateColor}; color:${rateColor}; background: ${rateColor}20;">
                      ${d.badge}
                    </span>
                    ${alertMsg}
                  </td>
                </tr>
              `;
            }).join("")}
          </tbody>
        </table>
        <div class="view-full-banner" id="bannerCollapseDrivers" style="margin-top:14px; background:rgba(255,255,255,0.05); border-color:rgba(255,255,255,0.2); color:#cbd5e1;">
          <span>🔼 Đang hiển thị đầy đủ tất cả ${list.length} tài xế. Bấm vào đây nếu muốn thu gọn lại.</span>
          <b>Thu Gọn ✕</b>
        </div>
      `;

      const bannerCollapse = document.getElementById("bannerCollapseDrivers");
      if (bannerCollapse) {
        bannerCollapse.addEventListener("click", () => {
          toggleFullView(false);
        });
      }
    } else {
      // HIỂN THỊ MẶC ĐỊNH (TOP 5 + RISK DRIVERS + BANNER XEM ĐẦY ĐỦ)
      driversContainer.className = "drivers-leaderboard-container";
      const topList = list.slice(0, 5);
      const riskList = (analyticsDataCache.risk_drivers || []).filter(d => 
        currentDriverFilter === "all" || d.hub.toLowerCase().includes(currentDriverFilter.toLowerCase())
      );

      driversContainer.innerHTML = `
        <div class="top-drivers-col">
          <table class="drivers-table">
            <thead>
              <tr>
                <th>Tài Xế</th>
                <th>Kho</th>
                <th>Gán Giao</th>
                <th>GTC</th>
                <th>Tỉ Lệ GTC</th>
                <th>Đơn Lấy</th>
                <th>Danh Hiệu</th>
              </tr>
            </thead>
            <tbody>
              ${topList.map(d => `
                <tr>
                  <td><b>${d.name}</b></td>
                  <td>${d.hub}</td>
                  <td>${d.assigned}</td>
                  <td style="color: #10b981; font-weight:700;">${d.gtc}</td>
                  <td><b>${d.rate}%</b></td>
                  <td style="color: #06b6d4; font-weight:700;">${d.ltc || 0} LTC</td>
                  <td><span class="badge-driver-rank">${d.badge}</span></td>
                </tr>
              `).join("")}
            </tbody>
          </table>
          <div class="view-full-banner" id="bannerExpandDrivers">
            <span>👁️ Bạn muốn xem đầy đủ số liệu toàn bộ ${analyticsDataCache.all_drivers.length} tài xế 4 kho?</span>
            <b>Bấm Để Xem Đầy Đủ ➔</b>
          </div>
        </div>
        <div class="risk-drivers-col">
          <div style="font-size: 11px; font-weight: 700; color: #ef4444; margin-bottom: 8px;">⚠️ TÀI XẾ CẦN HỖ TRỢ ĐIỀU PHỐI:</div>
          ${riskList.map(r => `
            <div class="risk-driver-card">
              <div class="risk-driver-header">
                <span>${r.name} (${r.hub})</span>
                <span>GTC: ${r.rate}%</span>
              </div>
              <div class="risk-driver-desc">${r.alert}</div>
            </div>
          `).join("")}
        </div>
      `;

      const bannerExpand = document.getElementById("bannerExpandDrivers");
      if (bannerExpand) {
        bannerExpand.addEventListener("click", () => {
          toggleFullView(true);
        });
      }
    }
  }

  function toggleFullView(forceState) {
    isFullDriversView = (typeof forceState === "boolean") ? forceState : !isFullDriversView;
    const btnText = document.getElementById("toggleFullDriversText");
    const btnIcon = document.getElementById("toggleFullDriversIcon");
    if (btnText) {
      btnText.textContent = isFullDriversView ? "Thu Gọn (Top 5)" : "Xem Đầy Đủ (21 Tài Xế)";
    }
    if (btnIcon) {
      btnIcon.textContent = isFullDriversView ? "🔼" : "👁️";
    }
    renderDriversView();
  }

  function renderHubDetailTable() {
    if (!analyticsDataCache || !hubDetailTableContainer) return;
    const hubs = analyticsDataCache.hubs_gtc || [];
    const sum = analyticsDataCache.summary || {};

    hubDetailTableContainer.innerHTML = `
      <table class="hub-detail-table">
        <thead>
          <tr>
            <th>Kho Miền Tây 01</th>
            <th>NVXL Phụ Trách</th>
            <th style="text-align: right;">Tổng Gán</th>
            <th style="text-align: right;">Hoàn Thành</th>
            <th style="text-align: right;">KPI Gộp</th>
            <th style="text-align: right;">Gán Giao</th>
            <th style="text-align: right;">GTC</th>
            <th style="text-align: right;">GTB</th>
            <th style="text-align: right;">Tỉ Lệ Giao</th>
            <th style="text-align: right;">Gán Lấy</th>
            <th style="text-align: right;">LTC</th>
            <th style="text-align: right;">Tỉ Lệ Lấy</th>
            <th style="text-align: right;">Nợ COD</th>
            <th style="text-align: right;">Đơn Hẹn SMS</th>
            <th>Đánh Giá Chỉ Tiêu</th>
          </tr>
        </thead>
        <tbody>
          ${hubs.map(h => {
            const kpiColor = h.rate >= 85 ? "#10b981" : (h.rate >= 80 ? "#f59e0b" : "#ef4444");
            const badgeClass = h.status === "passed" ? "GTC & LTC ĐẠT" : (h.status === "warning" ? "CẬN CHUẨN (84.3%)" : "GIẢI TRÌNH (<80%)");
            return `
              <tr>
                <td><b>${h.hub_name}</b></td>
                <td><span style="color:#60a5fa;">${h.nvxl}</span></td>
                <td style="text-align: right; font-weight:700;">${h.assigned}</td>
                <td style="text-align: right; color:#10b981; font-weight:700;">${h.gtc}</td>
                <td style="text-align: right; color:${kpiColor}; font-weight:800; font-size:13px;">${h.rate}%</td>
                <td style="text-align: right;">${h.deliver_assigned}</td>
                <td style="text-align: right; color:#10b981;">${h.deliver_gtc}</td>
                <td style="text-align: right; color:#ef4444;">${h.deliver_gtb}</td>
                <td style="text-align: right;">${Math.round(h.deliver_gtc/h.deliver_assigned*1000)/10}%</td>
                <td style="text-align: right;">${h.assigned_pick}</td>
                <td style="text-align: right; color:#06b6d4;">${h.ltc}</td>
                <td style="text-align: right;">100.0%</td>
                <td style="text-align: right; color:#10b981; font-weight:600;">${h.cod_unpaid}</td>
                <td style="text-align: right; color:#8b5cf6; font-weight:700;">${h.sms_count} đơn</td>
                <td><span class="badge-driver-rank" style="border-color:${kpiColor}; color:${kpiColor}; background:${kpiColor}15;">${badgeClass}</span></td>
              </tr>
            `;
          }).join("")}
          <tr style="background: rgba(255,255,255,0.06); font-weight: 700; border-top: 2px solid var(--border-glow);">
            <td colspan="2"><b>TỔNG TOÀN CỤM MT01</b></td>
            <td style="text-align: right; color:#f59e0b;">${sum.total_assigned}</td>
            <td style="text-align: right; color:#10b981;">${sum.total_gtc}</td>
            <td style="text-align: right; color:#10b981; font-size:14px; font-weight:800;">${sum.overall_rate}%</td>
            <td style="text-align: right;">${sum.total_deliver_assigned}</td>
            <td style="text-align: right; color:#10b981;">${sum.total_deliver_gtc}</td>
            <td style="text-align: right; color:#ef4444;">${sum.total_deliver_gtb}</td>
            <td style="text-align: right;">85.38%</td>
            <td style="text-align: right;">${sum.total_assigned_pick}</td>
            <td style="text-align: right; color:#06b6d4;">${sum.total_ltc}</td>
            <td style="text-align: right;">100.0%</td>
            <td style="text-align: right; color:#10b981;">0 đ</td>
            <td style="text-align: right; color:#8b5cf6;">128 đơn</td>
            <td><span class="badge-driver-rank" style="border-color:#10b981; color:#10b981; background:#10b98120;">⭐ ĐẠT MỤC TIÊU 85.0%</span></td>
          </tr>
        </tbody>
      </table>
    `;
  }

  function renderFailureReasons() {
    if (!analyticsDataCache || !failureReasonsContainer) return;
    const reasons = analyticsDataCache.failure_reasons || [];
    if (!reasons.length) {
      failureReasonsContainer.innerHTML = `<div style="color:var(--text-dim); font-size:12px;">Không có dữ liệu lý do thất bại.</div>`;
      return;
    }

    failureReasonsContainer.innerHTML = reasons.map(([reason, count]) => `
      <div class="failure-reason-card">
        <span class="reason-title">🔴 ${reason}</span>
        <span class="reason-count">${count} đơn</span>
      </div>
    `).join("");
  }

  async function refreshAnalyticsDatesDropdown(selectedKey) {
    const select = document.getElementById("analyticsDateSelect");
    if (!select) return;
    try {
      const res = await fetch("/api/analytics-dates");
      const json = await res.json();
      if (json && json.dates && json.dates.length > 0) {
        const activeKey = selectedKey || json.dates[0].date_key;
        select.innerHTML = json.dates.map(d => `
          <option value="${d.date_key}" ${d.date_key === activeKey ? 'selected' : ''}>
            ${d.label}
          </option>
        `).join("");
      }
    } catch(e) {
      console.warn("Lỗi tải danh sách ngày:", e);
    }
  }

  async function loadAnalytics(targetDate) {
    try {
      addLog("info", `Đang nạp dữ liệu thống kê từ kho lưu trữ snapshot...`);
      playCyberSound("pulse");
      const url = targetDate ? `/api/analytics-data?date=${targetDate}` : "/api/analytics-data";
      const res = await fetch(url);
      const data = await res.json();
      analyticsDataCache = data;

      // Update date select dropdown
      await refreshAnalyticsDatesDropdown(data.date_key);

      // Update sync time & chart badge
      const syncBadge = document.getElementById("analyticsSyncTime");
      if (syncBadge) {
        syncBadge.textContent = `🕒 Đồng bộ: ${data.sync_time || "07:00"}`;
      }
      const chartDateBadge = document.getElementById("chartDateBadge");
      if (chartDateBadge) {
        chartDateBadge.textContent = `KPI Ngày ${data.date_str}`;
      }

      // Update top stat cards
      if (data.summary) {
        const statAssigned = document.getElementById("statAssigned");
        const statAssignedSub = document.getElementById("statAssignedSub");
        const statGtc = document.getElementById("statGtc");
        const statSms = document.getElementById("statSms");
        const statCod = document.getElementById("statCod");
        if (statAssigned) statAssigned.textContent = data.summary.total_assigned.toLocaleString();
        if (statAssignedSub) {
          statAssignedSub.textContent = `Giao ${data.summary.total_deliver_assigned} + Lấy ${data.summary.total_assigned_pick} • Toàn cụm MT01`;
        }
        if (statGtc) {
          statGtc.textContent = data.summary.total_gtc.toLocaleString();
          const sub = statGtc.nextElementSibling;
          if (sub) sub.textContent = `Đạt ${data.summary.overall_rate}% (Chuẩn mục tiêu >= 85%)`;
        }
        if (statSms) {
          statSms.textContent = (data.summary.total_sms_appointment || 128).toLocaleString();
        }
        if (statCod) {
          statCod.textContent = data.summary.cod_unpaid_amount || "0 VNĐ";
        }
      }

      // Update hub filter pills counts dynamically
      const allDr = data.all_drivers || [];
      const pillContainer = document.getElementById("hubFilterPills");
      if (pillContainer) {
        const btns = pillContainer.querySelectorAll(".pill-btn");
        btns.forEach(b => {
          const filt = b.getAttribute("data-filter");
          if (filt === "all") {
            b.textContent = `Tất Cả (${allDr.length})`;
          } else {
            const cnt = allDr.filter(d => d.hub.toLowerCase().includes(filt.toLowerCase())).length;
            b.textContent = `${filt} (${cnt})`;
          }
        });
      }

      // Render GTC & LTC Bars
      gtcBarsContainer.innerHTML = "";
      data.hubs_gtc.forEach((h) => {
        const color = h.status === "passed" ? "#10b981" : (h.status === "warning" ? "#f59e0b" : "#ef4444");
        const ltcColor = (h.ltc_rate || 90) >= 85 ? "#06b6d4" : "#f59e0b";
        const badge = h.status === "passed" ? "GTC & LTC ĐẠT" : (h.status === "warning" ? "CẬN CHUẨN (84.3%)" : "GIẢI TRÌNH (<80%)");
        const row = document.createElement("div");
        row.className = "gtc-bar-row";
        row.innerHTML = `
          <div class="gtc-bar-meta">
            <span><b>${h.hub_name}</b> (NVXL: ${h.nvxl}) • Tổng gán: ${h.assigned.toLocaleString()} (Giao ${h.deliver_assigned || h.assigned} + Lấy ${h.assigned_pick || 0})</span>
            <span>
              <b style="color: ${color};">KPI Gộp: ${h.rate}%</b> • 
              <b style="color: ${ltcColor};">LTC: ${h.ltc_rate || 100.0}%</b> • 
              <span style="font-size:10.5px; font-weight:700; color:${color};">${badge}</span>
            </span>
          </div>
          <div class="bar-track" style="margin-bottom: 4px;">
            <div class="target-line-indicator" title="Mục tiêu chuẩn 85%"></div>
            <div class="bar-progress" style="width: ${h.rate}%; background: ${color};" title="GTC: ${h.rate}%"></div>
          </div>
          <div class="bar-track" style="height: 4px; opacity: 0.85;">
            <div class="bar-progress" style="width: ${h.ltc_rate || 90.0}%; background: ${ltcColor};" title="LTC: ${h.ltc_rate || 90.0}%"></div>
          </div>
        `;
        gtcBarsContainer.appendChild(row);
      });

      // Render Backlog Bars
      backlogBarsContainer.innerHTML = "";
      const maxCount = Math.max(...data.backlog_buckets.map(b => b.count));
      data.backlog_buckets.forEach((b) => {
        const pct = Math.min(100, Math.round((b.count / maxCount) * 100));
        const row = document.createElement("div");
        row.className = "gtc-bar-row";
        row.innerHTML = `
          <div class="gtc-bar-meta">
            <span>${b.label}</span>
            <span style="color: ${b.color}; font-weight: 700;">${b.count} đơn</span>
          </div>
          <div class="bar-track">
            <div class="bar-progress" style="width: ${pct}%; background: ${b.color};"></div>
          </div>
        `;
        backlogBarsContainer.appendChild(row);
      });

      // Render Drivers Leaderboard
      renderDriversView();

      // Render Hub Detail Table
      renderHubDetailTable();

      // Render Failure Reasons
      renderFailureReasons();

      modalAnalytics.classList.add("open");
    } catch (e) {
      addLog("error", `Lỗi tải biểu đồ: ${e.message}`);
    }
  }

  // Khởi tạo các sự kiện cho Modal Analytics (nếu chưa gán)
  if (!window._analyticsEventsAttached) {
    window._analyticsEventsAttached = true;

    // Toggle Fullscreen
    if (btnToggleFullscreenAnalytics && modalAnalytics) {
      btnToggleFullscreenAnalytics.addEventListener("click", () => {
        modalAnalytics.classList.toggle("is-fullscreen");
        const isFull = modalAnalytics.classList.contains("is-fullscreen");
        btnToggleFullscreenAnalytics.textContent = isFull ? "🗗" : "⛶";
        btnToggleFullscreenAnalytics.title = isFull ? "Thu nhỏ cửa sổ" : "Phóng to toàn màn hình";
      });
    }

    // Dropdown chọn ngày lịch sử lưu trữ
    const dateSelect = document.getElementById("analyticsDateSelect");
    if (dateSelect) {
      dateSelect.addEventListener("change", (e) => {
        const chosenDate = e.target.value;
        addLog("info", `Đang mở dữ liệu lưu trữ ngày: ${chosenDate}...`);
        loadAnalytics(chosenDate);
      });
    }

    // Toggle Full Drivers View
    if (btnToggleFullDrivers) {
      btnToggleFullDrivers.addEventListener("click", () => {
        toggleFullView();
      });
    }

    // Toggle Hub Table
    if (btnToggleHubTable && hubDetailSection) {
      btnToggleHubTable.addEventListener("click", () => {
        const isHidden = hubDetailSection.style.display === "none";
        hubDetailSection.style.display = isHidden ? "block" : "none";
        btnToggleHubTable.classList.toggle("btn-primary", isHidden);
        btnToggleHubTable.classList.toggle("btn-secondary", !isHidden);
      });
    }

    // Export CSV from Modal (Đúng theo ngày đang xem)
    if (btnExportModalCsv) {
      btnExportModalCsv.addEventListener("click", () => {
        const curDate = analyticsDataCache ? analyticsDataCache.date_key : "";
        const url = curDate ? `/api/export-csv?date=${curDate}` : "/api/export-csv";
        window.open(url, "_blank");
      });
    }

    // Filter pills
    const pillContainer = document.getElementById("hubFilterPills");
    if (pillContainer) {
      pillContainer.addEventListener("click", (e) => {
        const btn = e.target.closest(".pill-btn");
        if (!btn) return;
        pillContainer.querySelectorAll(".pill-btn").forEach(p => p.classList.remove("active"));
        btn.classList.add("active");
        currentDriverFilter = btn.getAttribute("data-filter") || "all";
        renderDriversView();
      });
    }
  }

  window.loadAnalytics = loadAnalytics;
  if (btnOpenAnalytics) {
    btnOpenAnalytics.addEventListener("click", () => loadAnalytics());
  }

  // ==========================================================================
  // AI COPILOT INTERACTIVE DRAWER
  // ==========================================================================
  const btnOpenCopilot = document.getElementById("btnOpenCopilot");
  const copilotDrawer = document.getElementById("copilotDrawer");
  const btnCloseCopilot = document.getElementById("btnCloseCopilot");
  const copilotChatBody = document.getElementById("copilotChatBody");
  const copilotInput = document.getElementById("copilotInput");
  const btnSendCopilot = document.getElementById("btnSendCopilot");

  if (btnOpenCopilot) {
    btnOpenCopilot.addEventListener("click", () => {
      copilotDrawer.classList.toggle("hidden-copilot");
      playCyberSound("start");
      if (!copilotDrawer.classList.contains("hidden-copilot")) {
        copilotInput.focus();
      }
    });
  }

  if (btnCloseCopilot) {
    btnCloseCopilot.addEventListener("click", () => {
      copilotDrawer.classList.add("hidden-copilot");
    });
  }

  async function sendCopilotMessage(text) {
    if (!text || !text.trim()) return;
    const q = text.trim();

    // Append user message
    const uMsg = document.createElement("div");
    uMsg.className = "chat-msg msg-user";
    uMsg.textContent = q;
    copilotChatBody.appendChild(uMsg);
    copilotInput.value = "";
    copilotChatBody.scrollTop = copilotChatBody.scrollHeight;

    // Loading message
    const lMsg = document.createElement("div");
    lMsg.className = "chat-msg msg-ai";
    lMsg.innerHTML = "<i>Tiger AI đang phân tích dữ liệu 4 kho...</i>";
    copilotChatBody.appendChild(lMsg);
    copilotChatBody.scrollTop = copilotChatBody.scrollHeight;
    playCyberSound("pulse");

    try {
      const res = await fetch("/api/copilot-ask", {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ prompt: q })
      });
      const data = await res.json();
      lMsg.innerHTML = data.answer.replace(/\n/g, "<br>");
      copilotChatBody.scrollTop = copilotChatBody.scrollHeight;
      playCyberSound("success");
    } catch (err) {
      lMsg.textContent = `Lỗi: ${err.message}`;
    }
  }

  if (btnSendCopilot) {
    btnSendCopilot.addEventListener("click", () => sendCopilotMessage(copilotInput.value));
  }
  if (copilotInput) {
    copilotInput.addEventListener("keydown", (e) => {
      if (e.key === "Enter") sendCopilotMessage(copilotInput.value);
    });
  }

  // Chips
  document.querySelectorAll(".chip-item").forEach((chip) => {
    chip.addEventListener("click", () => {
      const ask = chip.getAttribute("data-ask");
      sendCopilotMessage(ask);
    });
  });

  // ==========================================================================
  // CUSTOM NODE BUILDER & BRIEFING EXPORT
  // ==========================================================================
  const btnAddNode = document.getElementById("btnAddNode");
  const modalAddNode = document.getElementById("modalAddNode");
  const btnExportBrief = document.getElementById("btnExportBrief");
  const modalBriefing = document.getElementById("modalBriefing");
  const briefTime = document.getElementById("briefTime");

  if (btnAddNode) {
    btnAddNode.addEventListener("click", () => modalAddNode.classList.add("open"));
  }

  document.querySelectorAll(".lib-node-card").forEach((card) => {
    card.addEventListener("click", () => {
      const type = card.getAttribute("data-node-type");
      const title = card.querySelector(".lib-node-title").textContent;
      const desc = card.querySelector(".lib-node-desc").textContent;
      const icon = card.querySelector(".lib-node-icon").textContent;

      const wf = allWorkflows[currentWorkflowId];
      if (wf && wf.nodes) {
        const newNodeId = `node_${type}_${Date.now()}`;
        const lastNode = wf.nodes[wf.nodes.length - 1];
        const newX = lastNode ? lastNode.x + 280 : 300;
        const newY = lastNode ? lastNode.y : 180;

        const newNode = {
          id: newNodeId,
          title: title,
          category: "custom",
          icon: icon,
          x: newX,
          y: newY,
          description: desc,
          status: "ready"
        };
        wf.nodes.push(newNode);
        if (lastNode) {
          wf.edges.push({ from: lastNode.id, to: newNodeId });
        }
        canvas.loadWorkflow(wf);
        modalAddNode.classList.remove("open");
        addLog("success", `Đã ghép nối thành công khối [${title}] vào bàn cờ AI!`);
        playCyberSound("success");
      }
    });
  });

  if (btnExportBrief) {
    btnExportBrief.addEventListener("click", () => {
      if (briefTime) briefTime.textContent = new Date().toLocaleString("vi-VN");
      modalBriefing.classList.add("open");
    });
  }

  // Modal Handlers
  if (btnOpenRadar) btnOpenRadar.addEventListener("click", () => modalRadar.classList.add("open"));
  if (btnOpenScheduler) btnOpenScheduler.addEventListener("click", () => {
    loadSystemStatus();
    modalScheduler.classList.add("open");
  });

  document.querySelectorAll("[data-close]").forEach((btn) => {
    btn.addEventListener("click", (e) => {
      const modalId = btn.getAttribute("data-close");
      document.getElementById(modalId)?.classList.remove("open");
    });
  });

  // Copy Briefing Report Handler
  const btnCopyBriefing = document.getElementById("btnCopyBriefing");
  const copyBriefLabel = document.getElementById("copyBriefLabel");
  if (btnCopyBriefing) {
    btnCopyBriefing.addEventListener("click", () => {
      const text = document.getElementById("briefingContent")?.innerText || "";
      navigator.clipboard.writeText(text).then(() => {
        if (copyBriefLabel) copyBriefLabel.textContent = "✓ Đã Sao Chép!";
        addLog("success", "Đã sao chép nội dung Bản tin Điều hành vào bộ nhớ tạm!");
        playCyberSound("success");
        setTimeout(() => { if (copyBriefLabel) copyBriefLabel.textContent = "Copy Báo Cáo"; }, 2000);
      });
    });
  }

  // ⏱️ Auto-Pilot 24H Time Warp Simulation Engine
  const btnTimeWarp = document.getElementById("btnTimeWarp");
  const timeWarpLabel = document.getElementById("timeWarpLabel");
  let isTimeWarpRunning = false;

  const timeWarpSchedule = [
    { id: "kpi_gtc", time: "07:00", voice: "Bắt đầu mốc không bảy giờ sáng: Đánh giá KPI GTC ngày hôm qua.", log: "[07:00] Tiger AI kích hoạt kiểm tra KPI GTC toàn cụm 4 kho..." },
    { id: "checkin", time: "07:35", voice: "Mốc không bảy giờ ba mươi lăm: Đối chiếu lịch làm việc và điểm danh check in.", log: "[07:35] Quét lịch làm việc 68 tài xế, phát hiện nhân viên đi làm đúng giờ..." },
    { id: "assigned", time: "09:00", voice: "Mốc không chín giờ sáng: Giám sát toàn bộ chuyến xe xuất bến.", log: "[09:00] Khởi động giám sát 68 chuyến xe xuất bến, kiểm tra tỉ lệ gán đơn..." },
    { id: "unassigned", time: "10:00", voice: "Mốc mười giờ: Bóc tách đơn lưu kho và trích xuất tin nhắn hẹn.", log: "[10:00] Bóc tách 142 đơn tồn, nhận diện 128 đơn có hẹn SMS..." },
    { id: "pda", time: "12:00", voice: "Mốc mười hai giờ trưa: Theo dõi tiến độ giao hàng và timeline PDA.", log: "[12:00] Phân tích tốc độ giao hàng tài xế, ghi nhận 2180 đơn giao thành công..." },
    { id: "evening_cod", time: "21:00", voice: "Mốc hai mốt giờ đêm: Chốt ca và đối soát tiền thu hộ COD.", log: "[21:00] Chốt ca đêm hoàn tất. Toàn bộ tiền COD đã nộp đủ về két!" }
  ];

  async function runTimeWarpSimulation() {
    if (isTimeWarpRunning) return;
    isTimeWarpRunning = true;
    if (btnTimeWarp) btnTimeWarp.classList.add("running");
    if (timeWarpLabel) timeWarpLabel.textContent = "Đang Diễn Tập...";
    addLog("tip", ">>> BẮT ĐẦU CHẾ ĐỘ DIỄN TẬP TỰ ĐỘNG 24H (TIME WARP)... <<<");
    playCyberSound("start");

    for (let i = 0; i < timeWarpSchedule.length; i++) {
      const step = timeWarpSchedule[i];
      if (workflowSelect) workflowSelect.value = step.id;
      switchWorkflow(step.id);
      addLog("info", step.log);
      speakVietnamese(step.voice);
      playCyberSound("pulse");

      // Animate execution với forceDemo = true
      runWorkflowExecution(false, true);

      // Đợi 3.5 giây mỗi mốc giờ
      await new Promise(r => setTimeout(r, 3500));
    }

    isTimeWarpRunning = false;
    if (btnTimeWarp) btnTimeWarp.classList.remove("running");
    if (timeWarpLabel) timeWarpLabel.textContent = "Diễn Tập 24H";
    addLog("success", ">>> HOÀN TẤT DIỄN TẬP 24H VẬN HÀNH TOÀN DIỆN MIỀN TÂY 01! <<<");
    playCyberSound("success");
    speakVietnamese("Mô phỏng 24 giờ vận hành Miền Tây 01 đã hoàn tất xuất sắc!");

    // Mở Bản tin Điều Hành Tổng Hợp
    setTimeout(() => {
      const modalBriefing = document.getElementById("modalBriefing");
      const briefTime = document.getElementById("briefTime");
      if (briefTime) briefTime.textContent = new Date().toLocaleString("vi-VN");
      if (modalBriefing) modalBriefing.classList.add("open");
    }, 1000);
  }

  if (btnTimeWarp) {
    btnTimeWarp.addEventListener("click", runTimeWarpSimulation);
  }

  // Start initialization
  loadWorkflows();
});
