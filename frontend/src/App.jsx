import { useEffect, useState, useCallback } from "react";
import "./App.css";

const API_URL = import.meta.env.VITE_API_URL
  ? import.meta.env.VITE_API_URL.replace(/\/+$/, "")
  : "http://127.0.0.1:8000";

export default function App() {
  const [activePage, setActivePage] = useState("dashboard");
  const [toasts, setToasts] = useState([]);
  const [systemHealth, setSystemHealth] = useState({ status: "checking", postgres: "unknown", redis: "unknown" });
  const [pendingApprovalsCount, setPendingApprovalsCount] = useState(0);

  const addToast = useCallback((message, type = "info") => {
    const id = Date.now() + Math.random();
    setToasts((prev) => [...prev, { id, message, type }]);
    setTimeout(() => {
      setToasts((prev) => prev.filter((t) => t.id !== id));
    }, 4000);
  }, []);

  const checkHealth = useCallback(async () => {
    try {
      const res = await fetch(`${API_URL}/health`);
      if (res.ok) {
        const data = await res.json();
        setSystemHealth(data);
      } else {
        setSystemHealth({ status: "unhealthy", postgres: "failed", redis: "failed" });
      }
    } catch {
      setSystemHealth({ status: "offline", postgres: "unreachable", redis: "unreachable" });
    }
  }, []);

  const refreshPendingCount = useCallback(async () => {
    try {
      const res = await fetch(`${API_URL}/dashboard/approvals/pending`);
      if (res.ok) {
        const data = await res.json();
        setPendingApprovalsCount(data.length);
      }
    } catch {
      // ignore
    }
  }, []);

  useEffect(() => {
    checkHealth();
    refreshPendingCount();
    const interval = setInterval(() => {
      checkHealth();
      refreshPendingCount();
    }, 15000);
    return () => clearInterval(interval);
  }, [checkHealth, refreshPendingCount]);

  return (
    <div className="app-container">
      {/* Toast Notifications */}
      <div className="toast-container">
        {toasts.map((toast) => (
          <div key={toast.id} className={`toast ${toast.type}`}>
            <span>{toast.type === "success" ? "✓" : toast.type === "error" ? "✕" : "ℹ"}</span>
            <span>{toast.message}</span>
          </div>
        ))}
      </div>

      {/* Left Sidebar */}
      <aside className="sidebar">
        <div className="sidebar-header">
          <div className="brand-logo">
            <div className="brand-icon">C</div>
            <div className="brand-text">
              <h2>CCMS</h2>
              <p>Real-Time Config Platform</p>
            </div>
          </div>
        </div>

        <nav className="sidebar-nav">
          <button
            className={`nav-item ${activePage === "dashboard" ? "active" : ""}`}
            onClick={() => setActivePage("dashboard")}
          >
            <span className="nav-label">Dashboard</span>
          </button>

          <button
            className={`nav-item ${activePage === "services" ? "active" : ""}`}
            onClick={() => setActivePage("services")}
          >
            <span className="nav-label">Services</span>
          </button>

          <button
            className={`nav-item ${activePage === "configs" ? "active" : ""}`}
            onClick={() => setActivePage("configs")}
          >
            <span className="nav-label">Configurations</span>
          </button>

          <button
            className={`nav-item ${activePage === "approvals" ? "active" : ""}`}
            onClick={() => setActivePage("approvals")}
          >
            <span className="nav-label">Approvals</span>
            {pendingApprovalsCount > 0 && (
              <span className="nav-badge">{pendingApprovalsCount}</span>
            )}
          </button>

          <button
            className={`nav-item ${activePage === "history" ? "active" : ""}`}
            onClick={() => setActivePage("history")}
          >
            <span className="nav-label">History & Rollback</span>
          </button>
        </nav>
      </aside>

      {/* Main Content Area */}
      <main className="main-wrapper">
        <header className="top-bar">
          <div className="top-bar-title">
            <h1>
              {activePage === "dashboard" && "Dashboard Overview"}
              {activePage === "services" && "Registered Client Services"}
              {activePage === "configs" && "Configuration Management"}
              {activePage === "approvals" && "Pending Approval Queue"}
              {activePage === "history" && "Version History & Rollback"}
            </h1>
            <p>Real-time centralized configuration distribution</p>
          </div>

          <div className="top-bar-actions">
            <span className="env-pill">
              DB: {systemHealth.postgres === "ok" ? "🟢 Neon" : "🔴 Error"} | Redis: {systemHealth.redis === "ok" ? "🟢 Upstash" : "🔴 Error"}
            </span>
          </div>
        </header>

        <div className="content-area">
          {activePage === "dashboard" && (
            <DashboardPage addToast={addToast} onNavigate={setActivePage} />
          )}
          {activePage === "services" && (
            <ServicesPage addToast={addToast} />
          )}
          {activePage === "configs" && (
            <ConfigurationsPage addToast={addToast} />
          )}
          {activePage === "approvals" && (
            <ApprovalsPage addToast={addToast} onRefreshPending={refreshPendingCount} />
          )}
          {activePage === "history" && (
            <HistoryPage addToast={addToast} />
          )}
        </div>
      </main>
    </div>
  );
}

/* ========================================================================= */
/* PAGE: Dashboard                                                           */
/* ========================================================================= */
function DashboardPage({ addToast, onNavigate }) {
  const [services, setServices] = useState([]);
  const [configs, setConfigs] = useState([]);
  const [pendingApprovals, setPendingApprovals] = useState([]);
  const [loading, setLoading] = useState(true);

  const loadData = useCallback(async () => {
    try {
      const [svcRes, apprRes] = await Promise.all([
        fetch(`${API_URL}/dashboard/services`),
        fetch(`${API_URL}/dashboard/approvals/pending`)
      ]);

      const svcData = await svcRes.json();
      const apprData = await apprRes.json();

      setServices(Array.isArray(svcData) ? svcData : []);
      setPendingApprovals(Array.isArray(apprData) ? apprData : []);

      if (Array.isArray(svcData) && svcData.length > 0) {
        const cfgRes = await fetch(`${API_URL}/dashboard/services/${svcData[0].id}/configs`);
        const cfgData = await cfgRes.json();
        setConfigs(Array.isArray(cfgData) ? cfgData : []);
      } else {
        setConfigs([]);
      }
    } catch {
      addToast("Failed to fetch dashboard data from CCMS backend", "error");
    } finally {
      setLoading(false);
    }
  }, [addToast]);

  useEffect(() => {
    loadData();
    const interval = setInterval(loadData, 15000);
    return () => clearInterval(interval);
  }, [loadData]);

  if (loading) {
    return <div className="empty-state"><p>Loading dashboard metrics...</p></div>;
  }

  const onlineServices = services.filter((s) => s.status === "online");

  return (
    <>
      <section className="stats-grid">
        <div className="stat-card">
          <div className="stat-title">Registered Services</div>
          <div className="stat-value">{services.length}</div>
          <div className="stat-sub">Across all environments</div>
        </div>

        <div className="stat-card">
          <div className="stat-title">Agent Status</div>
          <div className="stat-value" style={{ color: onlineServices.length > 0 ? "#16a34a" : "#dc2626" }}>
            {onlineServices.length} / {services.length}
          </div>
          <div className="stat-sub">{onlineServices.length} Online ({services.length - onlineServices.length} Offline)</div>
        </div>

        <div className="stat-card">
          <div className="stat-title">Managed Config Keys</div>
          <div className="stat-value">{configs.length}</div>
          <div className="stat-sub">{services.length > 0 ? `In ${services[0].service_name}` : "No service selected"}</div>
        </div>

        <div className="stat-card">
          <div className="stat-title">Pending Approvals</div>
          <div className="stat-value" style={{ color: pendingApprovals.length > 0 ? "#d97706" : "#0f172a" }}>
            {pendingApprovals.length}
          </div>
          <div className="stat-sub">Requires admin review</div>
        </div>
      </section>

      {/* Services summary */}
      <section className="panel">
        <div className="panel-header">
          <div className="panel-title">
            <h2>Registered Services Status</h2>
            <p>Live agent heartbeat detection (auto-refreshes every 15s)</p>
          </div>
          <button className="btn btn-secondary btn-sm" onClick={() => onNavigate("services")}>
            Manage Services →
          </button>
        </div>

        {services.length === 0 ? (
          <div className="empty-state">
            <h3>No services registered yet</h3>
            <p>Register your first service to start managing real-time configurations.</p>
            <button className="btn btn-primary" onClick={() => onNavigate("services")}>
              + Register First Service
            </button>
          </div>
        ) : (
          <div className="service-list">
            {services.map((service) => (
              <div key={service.id} className="service-card">
                <div className="service-info">
                  <h3>
                    {service.service_name}
                    <span className={`badge-tag ${service.environment === "production" ? "prod" : service.environment === "staging" ? "staging" : "dev"}`}>
                      {service.environment}
                    </span>
                  </h3>
                  <p>{service.description || "No description provided"}</p>
                  <div className="service-meta">
                    <span>ID: {service.id}</span>
                    <span>Last heartbeat: {service.last_seen ? new Date(service.last_seen).toLocaleTimeString() : "Never"}</span>
                  </div>
                </div>
                <div className="service-actions">
                  <span className={`status-badge ${service.status === "online" ? "online" : "offline"}`}>
                    {service.status === "online" ? "Online" : "Offline"}
                  </span>
                </div>
              </div>
            ))}
          </div>
        )}
      </section>
    </>
  );
}

/* ========================================================================= */
/* PAGE: Services                                                            */
/* ========================================================================= */
function ServicesPage({ addToast }) {
  const [services, setServices] = useState([]);
  const [loading, setLoading] = useState(true);
  const [showRegisterModal, setShowRegisterModal] = useState(false);
  const [deleteTargetService, setDeleteTargetService] = useState(null);

  // Form state
  const [serviceName, setServiceName] = useState("");
  const [environment, setEnvironment] = useState("development");
  const [description, setDescription] = useState("");
  const [submitting, setSubmitting] = useState(false);

  const loadServices = useCallback(async () => {
    try {
      const res = await fetch(`${API_URL}/dashboard/services`);
      const data = await res.json();
      setServices(Array.isArray(data) ? data : []);
    } catch {
      addToast("Failed to load services", "error");
    } finally {
      setLoading(false);
    }
  }, [addToast]);

  useEffect(() => {
    loadServices();
    const interval = setInterval(loadServices, 15000);
    return () => clearInterval(interval);
  }, [loadServices]);

  async function handleRegister(e) {
    e.preventDefault();
    if (!serviceName.trim()) return;

    setSubmitting(true);
    try {
      const res = await fetch(`${API_URL}/services/register`, {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({
          service_name: serviceName.trim(),
          environment,
          description: description.trim() || null,
        }),
      });

      const data = await res.json();
      if (!res.ok) {
        throw new Error(data.detail || "Registration failed");
      }

      addToast(`Service "${data.service_name}" registered successfully!`, "success");
      setShowRegisterModal(false);
      setServiceName("");
      setDescription("");
      loadServices();
    } catch (err) {
      addToast(err.message, "error");
    } finally {
      setSubmitting(false);
    }
  }

  async function handleDeleteService() {
    if (!deleteTargetService) return;

    try {
      const res = await fetch(`${API_URL}/services/${deleteTargetService.id}`, {
        method: "DELETE",
      });
      const data = await res.json();

      if (!res.ok) {
        throw new Error(data.detail || "Delete failed");
      }

      addToast(`Service "${deleteTargetService.service_name}" deleted successfully`, "success");
      setDeleteTargetService(null);
      loadServices();
    } catch (err) {
      addToast(err.message, "error");
    }
  }

  async function handleDownloadAgent(service) {
    try {
      addToast(`Preparing agent package for ${service.service_name}...`, "info");
      const res = await fetch(`${API_URL}/agent/download/${service.id}`);
      if (!res.ok) throw new Error("Failed to generate agent download package");

      const blob = await res.blob();
      const url = window.URL.createObjectURL(blob);
      const link = document.createElement("a");
      link.href = url;
      link.download = `${service.service_name}-ccms-agent.zip`;
      document.body.appendChild(link);
      link.click();
      link.remove();
      window.URL.revokeObjectURL(url);

      addToast(`Agent package downloaded for ${service.service_name}`, "success");
    } catch (err) {
      addToast(err.message, "error");
    }
  }

  return (
    <section className="panel">
      <div className="panel-header">
        <div className="panel-title">
          <h2>Registered Client Services</h2>
          <p>Download client agents and manage service lifecycles</p>
        </div>
        <button className="btn btn-primary" onClick={() => setShowRegisterModal(true)}>
          + Register Service
        </button>
      </div>

      {loading ? (
        <div className="empty-state"><p>Loading services...</p></div>
      ) : services.length === 0 ? (
        <div className="empty-state">
          <h3>No services found</h3>
          <p>Register a service to generate its dedicated CCMS sync agent.</p>
        </div>
      ) : (
        <div className="service-list">
          {services.map((service) => (
            <div key={service.id} className="service-card">
              <div className="service-info">
                <h3>
                  {service.service_name}
                  <span className={`badge-tag ${service.environment === "production" ? "prod" : service.environment === "staging" ? "staging" : "dev"}`}>
                    {service.environment}
                  </span>
                </h3>
                <p>{service.description || "No description provided"}</p>
                <div className="service-meta">
                  <span>Service ID: <strong>{service.id}</strong></span>
                  <span>Registered: {service.created_at ? new Date(service.created_at).toLocaleDateString() : "N/A"}</span>
                  <span>Last Seen: {service.last_seen ? new Date(service.last_seen).toLocaleTimeString() : "Never"}</span>
                </div>
              </div>

              <div className="service-actions">
                <span className={`status-badge ${service.status === "online" ? "online" : "offline"}`}>
                  {service.status === "online" ? "Online" : "Offline"}
                </span>

                <button
                  className="btn btn-secondary btn-sm"
                  onClick={() => handleDownloadAgent(service)}
                  title="Download configured agent zip package"
                >
                  ⬇ Download Agent
                </button>

                <button
                  className="btn btn-danger btn-sm"
                  onClick={() => setDeleteTargetService(service)}
                  title="Delete service"
                >
                  🗑 Delete
                </button>
              </div>
            </div>
          ))}
        </div>
      )}

      {/* Register Service Modal */}
      {showRegisterModal && (
        <div className="modal-overlay" onClick={() => setShowRegisterModal(false)}>
          <div className="modal-content" onClick={(e) => e.stopPropagation()}>
            <div className="modal-header">
              <h3>Register New Client Service</h3>
              <button className="modal-close-btn" onClick={() => setShowRegisterModal(false)}>✕</button>
            </div>
            <form onSubmit={handleRegister}>
              <div className="modal-body">
                <div className="form-group">
                  <label>Service Name *</label>
                  <input
                    type="text"
                    value={serviceName}
                    onChange={(e) => setServiceName(e.target.value)}
                    placeholder="e.g. payment-service, notes-service"
                    required
                  />
                  <span className="form-help">Unique identifier for this service</span>
                </div>

                <div className="form-group">
                  <label>Deployment Environment</label>
                  <select value={environment} onChange={(e) => setEnvironment(e.target.value)}>
                    <option value="development">Development</option>
                    <option value="staging">Staging</option>
                    <option value="production">Production</option>
                  </select>
                </div>

                <div className="form-group">
                  <label>Description</label>
                  <textarea
                    value={description}
                    onChange={(e) => setDescription(e.target.value)}
                    placeholder="Brief description of the service's role..."
                  />
                </div>
              </div>
              <div className="modal-footer">
                <button type="button" className="btn btn-secondary" onClick={() => setShowRegisterModal(false)}>
                  Cancel
                </button>
                <button type="submit" className="btn btn-primary" disabled={submitting}>
                  {submitting ? "Registering..." : "Register Service"}
                </button>
              </div>
            </form>
          </div>
        </div>
      )}

      {/* Delete Service Confirmation Modal */}
      {deleteTargetService && (
        <div className="modal-overlay" onClick={() => setDeleteTargetService(null)}>
          <div className="modal-content" onClick={(e) => e.stopPropagation()}>
            <div className="modal-header">
              <h3>Delete Service Confirmation</h3>
              <button className="modal-close-btn" onClick={() => setDeleteTargetService(null)}>✕</button>
            </div>
            <div className="modal-body">
              <p>
                Are you sure you want to delete service <strong>{deleteTargetService.service_name}</strong> (ID: {deleteTargetService.id})?
              </p>
              <p style={{ fontSize: "13px", color: "var(--danger)" }}>
                ⚠️ This will permanently remove all associated configurations, version histories, and approvals. Running agents for this service will no longer authenticate.
              </p>
            </div>
            <div className="modal-footer">
              <button className="btn btn-secondary" onClick={() => setDeleteTargetService(null)}>
                Cancel
              </button>
              <button className="btn btn-danger" onClick={handleDeleteService}>
                Yes, Delete Service
              </button>
            </div>
          </div>
        </div>
      )}
    </section>
  );
}

/* ========================================================================= */
/* PAGE: Configurations                                                      */
/* ========================================================================= */
function ConfigurationsPage({ addToast }) {
  const [services, setServices] = useState([]);
  const [selectedServiceId, setSelectedServiceId] = useState("");
  const [configs, setConfigs] = useState([]);
  const [loading, setLoading] = useState(true);

  // Change modal state
  const [selectedConfig, setSelectedConfig] = useState(null);
  const [newValueInput, setNewValueInput] = useState("");
  const [valueType, setValueType] = useState("string");
  const [reason, setReason] = useState("");
  const [submitting, setSubmitting] = useState(false);

  const loadServices = useCallback(async () => {
    try {
      const res = await fetch(`${API_URL}/dashboard/services`);
      const data = await res.json();
      if (Array.isArray(data) && data.length > 0) {
        setServices(data);
        if (!selectedServiceId) {
          setSelectedServiceId(String(data[0].id));
        }
      }
    } catch {
      addToast("Failed to load services", "error");
    } finally {
      setLoading(false);
    }
  }, [addToast, selectedServiceId]);

  const loadConfigs = useCallback(async (serviceId) => {
    if (!serviceId) return;
    try {
      const res = await fetch(`${API_URL}/dashboard/services/${serviceId}/configs`);
      const data = await res.json();
      setConfigs(Array.isArray(data) ? data : []);
    } catch {
      addToast("Failed to load configurations", "error");
      setConfigs([]);
    }
  }, [addToast]);

  useEffect(() => {
    loadServices();
  }, [loadServices]);

  useEffect(() => {
    if (selectedServiceId) {
      loadConfigs(selectedServiceId);
    }
  }, [selectedServiceId, loadConfigs]);

  function openChangeModal(config) {
    setSelectedConfig(config);
    const curr = config.current_value;

    let detectedType = typeof curr;
    if (curr === null) detectedType = "string";
    else if (Array.isArray(curr)) detectedType = "json";
    else if (detectedType === "object") detectedType = "json";

    setValueType(detectedType);
    setNewValueInput(typeof curr === "object" ? JSON.stringify(curr, null, 2) : String(curr));
    setReason("");
  }

  async function submitConfigChange(e) {
    e.preventDefault();
    if (!selectedConfig) return;

    let parsedValue = newValueInput;

    try {
      if (valueType === "boolean") {
        if (newValueInput.trim().toLowerCase() === "true") parsedValue = true;
        else if (newValueInput.trim().toLowerCase() === "false") parsedValue = false;
        else throw new Error("Boolean must be 'true' or 'false'");
      } else if (valueType === "number") {
        if (isNaN(newValueInput) || newValueInput.trim() === "") throw new Error("Invalid number");
        parsedValue = Number(newValueInput);
      } else if (valueType === "json") {
        parsedValue = JSON.parse(newValueInput);
      }
    } catch (err) {
      addToast(`Invalid value format: ${err.message}`, "error");
      return;
    }

    setSubmitting(true);
    try {
      const res = await fetch(`${API_URL}/configs/${selectedConfig.id}/change`, {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({
          new_value: parsedValue,
          reason: reason.trim() || `Update ${selectedConfig.config_key}`,
        }),
      });

      const data = await res.json();
      if (!res.ok) throw new Error(data.detail || "Change request failed");

      addToast(`Change submitted for approval (Proposed Version: ${data.proposed_version})`, "success");
      setSelectedConfig(null);
      loadConfigs(selectedServiceId);
    } catch (err) {
      addToast(err.message, "error");
    } finally {
      setSubmitting(false);
    }
  }

  return (
    <section className="panel">
      <div className="panel-header">
        <div className="panel-title">
          <h2>Configuration Keys</h2>
          <p>View current values and request typed configuration modifications</p>
        </div>
      </div>

      <div className="filter-bar">
        <label>Select Service:</label>
        <select
          value={selectedServiceId}
          onChange={(e) => setSelectedServiceId(e.target.value)}
        >
          {services.map((s) => (
            <option key={s.id} value={s.id}>
              {s.service_name} ({s.environment})
            </option>
          ))}
        </select>
      </div>

      {loading ? (
        <div className="empty-state"><p>Loading configurations...</p></div>
      ) : configs.length === 0 ? (
        <div className="empty-state">
          <h3>No configurations imported</h3>
          <p>Download and run the CCMS Agent for this service to automatically upload its initial config.json.</p>
        </div>
      ) : (
        <table className="config-table">
          <thead>
            <tr>
              <th>Configuration Key</th>
              <th>Current Version</th>
              <th>Current JSON Value</th>
              <th>Last Updated</th>
              <th>Action</th>
            </tr>
          </thead>
          <tbody>
            {configs.map((config) => (
              <tr key={config.id}>
                <td>
                  <span className="config-key-badge">{config.config_key}</span>
                </td>
                <td>
                  <span className="version-pill">v{config.current_version}</span>
                </td>
                <td>
                  <code className="config-value-preview">
                    {JSON.stringify(config.current_value)}
                  </code>
                </td>
                <td style={{ fontSize: "12px", color: "var(--text-muted)" }}>
                  {config.updated_at ? new Date(config.updated_at).toLocaleString() : "Initial"}
                </td>
                <td>
                  <button
                    className="btn btn-secondary btn-sm"
                    onClick={() => openChangeModal(config)}
                  >
                    ✏ Request Change
                  </button>
                </td>
              </tr>
            ))}
          </tbody>
        </table>
      )}

      {/* Change Configuration Modal */}
      {selectedConfig && (
        <div className="modal-overlay" onClick={() => setSelectedConfig(null)}>
          <div className="modal-content" onClick={(e) => e.stopPropagation()}>
            <div className="modal-header">
              <h3>Request Configuration Change</h3>
              <button className="modal-close-btn" onClick={() => setSelectedConfig(null)}>✕</button>
            </div>
            <form onSubmit={submitConfigChange}>
              <div className="modal-body">
                <div className="form-group">
                  <label>Configuration Key</label>
                  <input type="text" value={selectedConfig.config_key} disabled />
                </div>

                <div className="form-group">
                  <label>Current Value (v{selectedConfig.current_version})</label>
                  <input type="text" value={JSON.stringify(selectedConfig.current_value)} disabled />
                </div>

                <div className="form-group">
                  <label>Value Type</label>
                  <select value={valueType} onChange={(e) => setValueType(e.target.value)}>
                    <option value="string">String</option>
                    <option value="number">Number</option>
                    <option value="boolean">Boolean (true / false)</option>
                    <option value="json">JSON Object / Array</option>
                  </select>
                </div>

                <div className="form-group">
                  <label>New Proposed Value *</label>
                  {valueType === "boolean" ? (
                    <select value={newValueInput} onChange={(e) => setNewValueInput(e.target.value)}>
                      <option value="true">true</option>
                      <option value="false">false</option>
                    </select>
                  ) : valueType === "json" ? (
                    <textarea
                      value={newValueInput}
                      onChange={(e) => setNewValueInput(e.target.value)}
                      placeholder='{"key": "value"}'
                      required
                    />
                  ) : (
                    <input
                      type={valueType === "number" ? "number" : "text"}
                      value={newValueInput}
                      onChange={(e) => setNewValueInput(e.target.value)}
                      placeholder="Enter new value..."
                      required
                    />
                  )}
                </div>

                <div className="form-group">
                  <label>Change Reason *</label>
                  <textarea
                    value={reason}
                    onChange={(e) => setReason(e.target.value)}
                    placeholder="Why is this change needed? (Visible in approvals & audit log)"
                    required
                  />
                </div>
              </div>
              <div className="modal-footer">
                <button type="button" className="btn btn-secondary" onClick={() => setSelectedConfig(null)}>
                  Cancel
                </button>
                <button type="submit" className="btn btn-primary" disabled={submitting}>
                  {submitting ? "Submitting..." : "Submit for Approval"}
                </button>
              </div>
            </form>
          </div>
        </div>
      )}
    </section>
  );
}

/* ========================================================================= */
/* PAGE: Approvals                                                           */
/* ========================================================================= */
function ApprovalsPage({ addToast, onRefreshPending }) {
  const [approvals, setApprovals] = useState([]);
  const [loading, setLoading] = useState(true);
  const [rejectingApproval, setRejectingApproval] = useState(null);
  const [rejectReason, setRejectReason] = useState("");

  const loadApprovals = useCallback(async () => {
    try {
      const res = await fetch(`${API_URL}/dashboard/approvals/pending`);
      const data = await res.json();
      setApprovals(Array.isArray(data) ? data : []);
      onRefreshPending();
    } catch {
      addToast("Failed to load approvals", "error");
    } finally {
      setLoading(false);
    }
  }, [addToast, onRefreshPending]);

  useEffect(() => {
    loadApprovals();
  }, [loadApprovals]);

  async function handleApprove(approvalId) {
    try {
      const res = await fetch(`${API_URL}/approvals/${approvalId}/approve`, {
        method: "POST",
      });
      const data = await res.json();

      if (!res.ok) throw new Error(data.detail || "Approval failed");

      addToast("Change approved! Real-time update pushed to Redis Pub/Sub.", "success");
      loadApprovals();
    } catch (err) {
      addToast(err.message, "error");
    }
  }

  async function handleReject() {
    if (!rejectingApproval) return;
    try {
      const res = await fetch(`${API_URL}/approvals/${rejectingApproval.approval_id}/reject`, {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ comment: rejectReason }),
      });
      const data = await res.json();

      if (!res.ok) throw new Error(data.detail || "Rejection failed");

      addToast("Change request rejected.", "info");
      setRejectingApproval(null);
      setRejectReason("");
      loadApprovals();
    } catch (err) {
      addToast(err.message, "error");
    }
  }

  return (
    <section className="panel">
      <div className="panel-header">
        <div className="panel-title">
          <h2>Pending Approvals Queue</h2>
          <p>Review and deploy configuration changes in real time</p>
        </div>
        <span className="version-pill">{approvals.length} Pending</span>
      </div>

      {loading ? (
        <div className="empty-state"><p>Loading approvals...</p></div>
      ) : approvals.length === 0 ? (
        <div className="empty-state">
          <h3>No Pending Approvals</h3>
          <p>All configuration changes and rollbacks have been processed.</p>
        </div>
      ) : (
        <div className="approval-list">
          {approvals.map((appr) => (
            <div key={appr.approval_id} className="approval-card">
              <div className="approval-card-top">
                <div>
                  <span className="approval-service-name">{appr.service_name}</span>
                  <h3 style={{ fontSize: "16px", marginTop: "2px" }}>{appr.config_key}</h3>
                </div>
                <span className="version-pill">Target: v{appr.proposed_version}</span>
              </div>

              <div className="approval-diff">
                <div className="diff-box old">
                  <label>Current Value</label>
                  <code>{JSON.stringify(appr.current_value)}</code>
                </div>
                <span style={{ fontSize: "18px", color: "var(--text-muted)" }}>➔</span>
                <div className="diff-box new">
                  <label>Proposed New Value (v{appr.proposed_version})</label>
                  <code>{JSON.stringify(appr.proposed_value)}</code>
                </div>
              </div>

              <div className="approval-reason">
                <strong>Reason:</strong> {appr.reason || "No reason provided"}
              </div>

              <div className="approval-actions">
                <button
                  className="btn btn-secondary btn-sm"
                  onClick={() => {
                    setRejectingApproval(appr);
                    setRejectReason("");
                  }}
                >
                  ✕ Reject
                </button>
                <button
                  className="btn btn-primary btn-sm"
                  onClick={() => handleApprove(appr.approval_id)}
                >
                  ✓ Approve & Deploy (Real-Time)
                </button>
              </div>
            </div>
          ))}
        </div>
      )}

      {/* Reject Modal */}
      {rejectingApproval && (
        <div className="modal-overlay" onClick={() => setRejectingApproval(null)}>
          <div className="modal-content" onClick={(e) => e.stopPropagation()}>
            <div className="modal-header">
              <h3>Reject Configuration Change</h3>
              <button className="modal-close-btn" onClick={() => setRejectingApproval(null)}>✕</button>
            </div>
            <div className="modal-body">
              <p>Reject change for <strong>{rejectingApproval.config_key}</strong> in {rejectingApproval.service_name}?</p>
              <div className="form-group">
                <label>Rejection Reason (Optional)</label>
                <textarea
                  value={rejectReason}
                  onChange={(e) => setRejectReason(e.target.value)}
                  placeholder="Explain why this change was rejected..."
                />
              </div>
            </div>
            <div className="modal-footer">
              <button className="btn btn-secondary" onClick={() => setRejectingApproval(null)}>
                Cancel
              </button>
              <button className="btn btn-danger" onClick={handleReject}>
                Reject Change
              </button>
            </div>
          </div>
        </div>
      )}
    </section>
  );
}

/* ========================================================================= */
/* PAGE: History & Rollback                                                  */
/* ========================================================================= */
function HistoryPage({ addToast }) {
  const [services, setServices] = useState([]);
  const [selectedServiceId, setSelectedServiceId] = useState("");
  const [history, setHistory] = useState([]);
  const [loading, setLoading] = useState(true);

  // Rollback modal state
  const [rollbackTarget, setRollbackTarget] = useState(null);
  const [rollbackReason, setRollbackReason] = useState("");
  const [submitting, setSubmitting] = useState(false);

  const loadServices = useCallback(async () => {
    try {
      const res = await fetch(`${API_URL}/dashboard/services`);
      const data = await res.json();
      if (Array.isArray(data) && data.length > 0) {
        setServices(data);
        if (!selectedServiceId) {
          setSelectedServiceId(String(data[0].id));
        }
      }
    } catch {
      addToast("Failed to load services", "error");
    } finally {
      setLoading(false);
    }
  }, [addToast, selectedServiceId]);

  const loadHistory = useCallback(async (serviceId) => {
    if (!serviceId) return;
    try {
      const res = await fetch(`${API_URL}/dashboard/history/${serviceId}`);
      const data = await res.json();
      setHistory(Array.isArray(data) ? data : []);
    } catch {
      addToast("Failed to load configuration history", "error");
      setHistory([]);
    }
  }, [addToast]);

  useEffect(() => {
    loadServices();
  }, [loadServices]);

  useEffect(() => {
    if (selectedServiceId) {
      loadHistory(selectedServiceId);
    }
  }, [selectedServiceId, loadHistory]);

  async function handleRollbackSubmit(e) {
    e.preventDefault();
    if (!rollbackTarget) return;

    setSubmitting(true);
    try {
      const res = await fetch(`${API_URL}/configs/${rollbackTarget.config_id}/rollback`, {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({
          version_id: rollbackTarget.version_id,
          reason: rollbackReason.trim() || `Rollback to version ${rollbackTarget.version}`,
        }),
      });

      const data = await res.json();
      if (!res.ok) throw new Error(data.detail || "Rollback request failed");

      addToast(`Rollback request created for approval as v${data.proposed_version}`, "success");
      setRollbackTarget(null);
      setRollbackReason("");
      loadHistory(selectedServiceId);
    } catch (err) {
      addToast(err.message, "error");
    } finally {
      setSubmitting(false);
    }
  }

  return (
    <section className="panel">
      <div className="panel-header">
        <div className="panel-title">
          <h2>Configuration Version History & Rollback</h2>
          <p>Audit historical values and trigger version-safe rollbacks</p>
        </div>
      </div>

      <div className="filter-bar">
        <label>Select Service:</label>
        <select
          value={selectedServiceId}
          onChange={(e) => setSelectedServiceId(e.target.value)}
        >
          {services.map((s) => (
            <option key={s.id} value={s.id}>
              {s.service_name} ({s.environment})
            </option>
          ))}
        </select>
      </div>

      {loading ? (
        <div className="empty-state"><p>Loading history...</p></div>
      ) : history.length === 0 ? (
        <div className="empty-state">
          <h3>No version history available</h3>
          <p>Changes will appear here as configurations are modified over time.</p>
        </div>
      ) : (
        <div className="history-list">
          {history.map((item) => (
            <div
              key={`${item.config_id}-${item.version_id || item.version}`}
              className={`history-card ${item.is_current ? "current" : ""}`}
            >
              <div className="history-details">
                <div className="history-header">
                  <span className="config-key-badge">{item.config_key}</span>
                  <span className="version-pill">v{item.version}</span>
                  {item.is_current && (
                    <span className="badge-tag prod" style={{ backgroundColor: "#dcfce7", color: "#166534" }}>
                      CURRENT ACTIVE
                    </span>
                  )}
                </div>

                <div style={{ marginTop: "6px" }}>
                  <code className="config-value-preview">{JSON.stringify(item.value)}</code>
                </div>

                <p className="history-reason">
                  <strong>Reason:</strong> {item.reason || "Direct import/update"}
                </p>

                <span className="history-timestamp">
                  {item.created_at ? new Date(item.created_at).toLocaleString() : "Historical"}
                </span>
              </div>

              {!item.is_current && (
                <button
                  className="btn btn-secondary btn-sm"
                  onClick={() => {
                    setRollbackTarget(item);
                    setRollbackReason(`Rollback to historical version ${item.version}`);
                  }}
                  title="Create a new version rolling back to this value"
                >
                  ↩ Rollback to v{item.version}
                </button>
              )}
            </div>
          ))}
        </div>
      )}

      {/* Rollback Modal */}
      {rollbackTarget && (
        <div className="modal-overlay" onClick={() => setRollbackTarget(null)}>
          <div className="modal-content" onClick={(e) => e.stopPropagation()}>
            <div className="modal-header">
              <h3>Confirm Version Rollback</h3>
              <button className="modal-close-btn" onClick={() => setRollbackTarget(null)}>✕</button>
            </div>
            <form onSubmit={handleRollbackSubmit}>
              <div className="modal-body">
                <p>
                  Rollback <strong>{rollbackTarget.config_key}</strong> to value from <strong>version {rollbackTarget.version}</strong>:
                </p>
                <div className="diff-box new" style={{ marginTop: "10px" }}>
                  <label>Target Value</label>
                  <code>{JSON.stringify(rollbackTarget.value)}</code>
                </div>
                <div className="form-group" style={{ marginTop: "14px" }}>
                  <label>Rollback Reason</label>
                  <textarea
                    value={rollbackReason}
                    onChange={(e) => setRollbackReason(e.target.value)}
                    placeholder="Why are you rolling back to this version?"
                    required
                  />
                </div>
                <p style={{ fontSize: "12px", color: "var(--text-muted)" }}>
                  ℹ A new version will be created and submitted to the Approvals queue. Historical versions remain preserved.
                </p>
              </div>
              <div className="modal-footer">
                <button type="button" className="btn btn-secondary" onClick={() => setRollbackTarget(null)}>
                  Cancel
                </button>
                <button type="submit" className="btn btn-primary" disabled={submitting}>
                  {submitting ? "Submitting..." : "Submit Rollback Request"}
                </button>
              </div>
            </form>
          </div>
        </div>
      )}
    </section>
  );
}