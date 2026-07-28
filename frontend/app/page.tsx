"use client";

import { FormEvent, useCallback, useEffect, useState } from "react";
import { useAuth, User } from "./context/AuthContext";

type Business = {
  id: string;
  name: string;
  business_type?: string | null;
  country?: string | null;
  city: string;
  address?: string | null;
  phone?: string | null;
  website?: string | null;
  website_available: boolean;
  email?: string | null;
  owner_manager_name?: string | null;
  rating?: number | null;
  reviews_count?: number | null;
  contact_page_url?: string | null;
  facebook_url?: string | null;
  instagram_url?: string | null;
  whatsapp_number?: string | null;
  linkedin_url?: string | null;
  assigned_to?: string | null;
  is_duplicate: boolean;
  created_at: string;
};

type Lead = {
  id: string;
  business_id: string;
  lead_ref?: number | null;
  order_method: string;
  order_method_detail?: string | null;
  delivery_system?: string | null;
  automation_status: string;
  automation_status_detail?: string | null;
  priority: "high" | "medium" | "low";
  notes?: string | null;
  call_status: string;
  week_number?: number | null;
  created_at: string;
  business?: Business | null;
};

type WeeklyDashboard = {
  week_number: number;
  headline: {
    total_leads_this_week: number;
    weekly_target: number;
    percent_of_target: number;
    leads_still_needed: number;
  };
  by_country: Array<{ country: string; leads_this_week: number; total_leads: number }>;
  by_intern: Array<{
    intern: string;
    cities: string[];
    leads_this_week: number;
    target_per_week: number;
    on_track: boolean;
    shortfall: number;
  }>;
  by_business_type: Array<{ business_type: string; total_leads: number }>;
};

type Assignments = {
  current_week: number;
  weekly_team_target: number;
  target_per_intern: number;
  interns: Array<{ name: string; cities: string[]; country: string }>;
};

type DiscoveryResult = {
  summary: { created: number; merged_as_duplicate: number; skipped: number };
  assigned_to?: string | null;
  businesses: Business[];
};

const API_BASE = process.env.NEXT_PUBLIC_API_URL || "http://localhost:8000";

const emptyBusiness = {
  name: "",
  business_type: "Supermarket",
  country: "Pakistan",
  city: "Lahore",
  website: "",
  phone: "",
  email: "",
  assigned_to: "",
};

function fieldValue(value?: string | number | null) {
  return value === null || value === undefined || value === "" ? "Not available" : String(value);
}

function priorityClass(priority: string) {
  if (priority === "high") return "pill danger";
  if (priority === "low") return "pill calm";
  return "pill warn";
}

export default function Home() {
  const { token, user, isLoading, login, logout, authFetch } = useAuth();

  const [authMode, setAuthMode] = useState<"login" | "signup">("login");
  const [authForm, setAuthForm] = useState({
    full_name: "Lead Manager",
    email: "owner@example.com",
    password: "password123",
    role: "owner",
  });
  const [tab, setTab] = useState<"overview" | "leads" | "discovery" | "tools">("overview");
  const [leads, setLeads] = useState<Lead[]>([]);
  const [businesses, setBusinesses] = useState<Business[]>([]);
  const [dashboard, setDashboard] = useState<WeeklyDashboard | null>(null);
  const [assignments, setAssignments] = useState<Assignments | null>(null);
  const [message, setMessage] = useState("Connect to the backend to load live modules.");
  const [loading, setLoading] = useState(false);
  const [filters, setFilters] = useState({ city: "", priority: "" });
  const [discovery, setDiscovery] = useState({
    category: "supermarket",
    city: "Lahore",
    country: "Pakistan",
    max_results: 10,
  });
  const [businessForm, setBusinessForm] = useState(emptyBusiness);
  const [scrapeUrl, setScrapeUrl] = useState("https://example.com");
  const [scrapeResult, setScrapeResult] = useState<Record<string, unknown> | null>(null);

  const loadAll = useCallback(async () => {
    setLoading(true);
    try {
      const query = new URLSearchParams();
      if (filters.city) query.set("city", filters.city);
      if (filters.priority) query.set("priority", filters.priority);

      const [leadRows, businessRows, report, assignmentRows] = await Promise.all([
        authFetch<Lead[]>(`/api/v1/leads${query.toString() ? `?${query}` : ""}`),
        authFetch<Business[]>("/api/v1/businesses?limit=100"),
        authFetch<WeeklyDashboard>("/api/v1/reports/weekly"),
        authFetch<Assignments>("/api/v1/reports/assignments"),
      ]);

      setLeads(leadRows);
      setBusinesses(businessRows);
      setDashboard(report);
      setAssignments(assignmentRows);
      setMessage("Live dashboard loaded.");
    } catch (error) {
      setMessage(error instanceof Error ? error.message : "Could not load dashboard.");
    } finally {
      setLoading(false);
    }
  }, [authFetch, filters.city, filters.priority]);

  useEffect(() => {
    if (!token || isLoading) return;
    const timer = window.setTimeout(() => {
      void loadAll();
    }, 0);
    return () => window.clearTimeout(timer);
  }, [loadAll, token, isLoading]);

  useEffect(() => {
    if (!token || isLoading) return;
    const hasPending = leads.some(
      (l) =>
        l.automation_status === "in_progress" ||
        l.automation_status_detail === "Queued" ||
        l.automation_status_detail === "Processing"
    );
    if (!hasPending) return;

    const interval = setInterval(() => {
      void loadAll();
    }, 3000);

    return () => clearInterval(interval);
  }, [leads, loadAll, token, isLoading]);

  async function submitAuth(event: FormEvent) {
    event.preventDefault();
    setLoading(true);
    try {
      const path = authMode === "signup" ? "/api/v1/auth/signup" : "/api/v1/auth/login";
      const init =
        authMode === "signup"
          ? {
              method: "POST",
              headers: { "Content-Type": "application/json" },
              body: JSON.stringify(authForm),
            }
          : {
              method: "POST",
              headers: { "Content-Type": "application/x-www-form-urlencoded" },
              body: new URLSearchParams({
                username: authForm.email,
                password: authForm.password,
              }),
            };

      const response = await fetch(`${API_BASE}${path}`, init);
      if (!response.ok) throw new Error(await response.text());
      const payload = (await response.json()) as { access_token: string; user: User };
      login(payload.access_token, payload.user);
      setMessage(`Signed in as ${payload.user.full_name}.`);
    } catch (error) {
      setMessage(error instanceof Error ? error.message : "Auth failed.");
    } finally {
      setLoading(false);
    }
  }

  function handleLogout() {
    logout();
    setLeads([]);
    setBusinesses([]);
    setDashboard(null);
    setMessage("Signed out.");
  }

  async function runDiscovery(event: FormEvent) {
    event.preventDefault();
    setLoading(true);
    try {
      const result = await authFetch<DiscoveryResult>("/api/v1/discovery/google-maps", {
        method: "POST",
        body: JSON.stringify(discovery),
      });
      setBusinesses(result.businesses);
      setMessage(
        `Discovery done: ${result.summary.created} new, ${result.summary.merged_as_duplicate} merged, ${result.summary.skipped} skipped.`,
      );
      await loadAll();
    } catch (error) {
      setMessage(error instanceof Error ? error.message : "Discovery failed.");
    } finally {
      setLoading(false);
    }
  }

  async function createBusiness(event: FormEvent) {
    event.preventDefault();
    setLoading(true);
    try {
      await authFetch<Business>("/api/v1/businesses", {
        method: "POST",
        body: JSON.stringify({
          ...businessForm,
          website: businessForm.website || null,
          phone: businessForm.phone || null,
          email: businessForm.email || null,
          assigned_to: businessForm.assigned_to || null,
        }),
      });
      setBusinessForm(emptyBusiness);
      setMessage("Business saved through the shared dedup pipeline.");
      await loadAll();
    } catch (error) {
      setMessage(error instanceof Error ? error.message : "Could not save business.");
    } finally {
      setLoading(false);
    }
  }

  async function enrichBusiness(id: string) {
    setLoading(true);
    try {
      await authFetch<Business>(`/api/v1/businesses/${id}/enrich-website`, { method: "POST" });
      setMessage("Website scraper enriched the business.");
      await loadAll();
    } catch (error) {
      setMessage(error instanceof Error ? error.message : "Website enrichment failed.");
    } finally {
      setLoading(false);
    }
  }

  async function scoreBusiness(id: string) {
    setLoading(true);
    try {
      await authFetch<Lead>(`/api/v1/businesses/${id}/score`, { method: "POST" });
      setMessage("Lead scored and added to the leads dashboard.");
      await loadAll();
    } catch (error) {
      setMessage(error instanceof Error ? error.message : "Scoring failed.");
    } finally {
      setLoading(false);
    }
  }

  async function scrapeStandalone(event: FormEvent) {
    event.preventDefault();
    setLoading(true);
    try {
      const result = await authFetch<Record<string, unknown>>("/website-scraper/scrape", {
        method: "POST",
        body: JSON.stringify({ website: scrapeUrl }),
      });
      setScrapeResult(result);
      setMessage("Website scraper returned a result.");
    } catch (error) {
      setMessage(error instanceof Error ? error.message : "Scrape failed.");
    } finally {
      setLoading(false);
    }
  }

  async function downloadExport(path: string, filename: string) {
    setLoading(true);
    try {
      const savedToken = token || (typeof window !== "undefined" ? localStorage.getItem("leadgen_token") : null);
      const response = await fetch(`${API_BASE}${path}`, {
        headers: {
          ...(savedToken ? { Authorization: `Bearer ${savedToken}` } : {}),
        },
      });
      if (response.status === 401) {
        logout();
        throw new Error("Session expired. Please log in again.");
      }
      if (!response.ok) throw new Error(await response.text());
      const blob = await response.blob();
      const url = URL.createObjectURL(blob);
      const link = document.createElement("a");
      link.href = url;
      link.download = filename;
      document.body.appendChild(link);
      link.click();
      link.remove();
      URL.revokeObjectURL(url);
      setMessage(`Downloaded ${filename}.`);
    } catch (error) {
      setMessage(error instanceof Error ? error.message : "Download failed.");
    } finally {
      setLoading(false);
    }
  }

  // Delay rendering until auth state is restored on client mount to eliminate hydration mismatch
  if (isLoading) {
    return (
      <main className="auth-shell">
        <section className="auth-panel">
          <div>
            <p className="eyebrow">Mart Lead Generator</p>
            <h1>Loading dashboard...</h1>
            <p className="muted">Restoring session state...</p>
          </div>
        </section>
      </main>
    );
  }

  if (!token || !user) {
    return (
      <main className="auth-shell">
        <section className="auth-panel">
          <div>
            <p className="eyebrow">Mart Lead Generator</p>
            <h1>One dashboard for discovery, enrichment, scoring and reports.</h1>
            <p className="muted">
              Sign in to connect the frontend with the FastAPI modules running at {API_BASE}.
            </p>
          </div>
          <form className="auth-form" onSubmit={submitAuth}>
            <div className="segmented">
              <button type="button" className={authMode === "login" ? "active" : ""} onClick={() => setAuthMode("login")}>
                Login
              </button>
              <button type="button" className={authMode === "signup" ? "active" : ""} onClick={() => setAuthMode("signup")}>
                Signup
              </button>
            </div>
            {authMode === "signup" && (
              <>
                <label>
                  Full name
                  <input value={authForm.full_name} onChange={(event) => setAuthForm({ ...authForm, full_name: event.target.value })} />
                </label>
                <label>
                  Role
                  <select value={authForm.role} onChange={(event) => setAuthForm({ ...authForm, role: event.target.value })}>
                    <option value="owner">Owner</option>
                    <option value="member">Member</option>
                  </select>
                </label>
              </>
            )}
            <label>
              Email
              <input type="email" value={authForm.email} onChange={(event) => setAuthForm({ ...authForm, email: event.target.value })} />
            </label>
            <label>
              Password
              <input
                type="password"
                value={authForm.password}
                onChange={(event) => setAuthForm({ ...authForm, password: event.target.value })}
              />
            </label>
            <button className="primary" disabled={loading}>
              {loading ? "Working..." : authMode === "signup" ? "Create account" : "Sign in"}
            </button>
            <p className="status">{message}</p>
          </form>
        </section>
      </main>
    );
  }

  return (
    <main className="app-shell">
      <aside className="sidebar">
        <div>
          <p className="eyebrow">Mart Lead Generator</p>
          <h1>Lead Ops</h1>
        </div>
        <nav>
          {(["overview", "leads", "discovery", "tools"] as const).map((item) => (
            <button key={item} className={tab === item ? "active" : ""} onClick={() => setTab(item)}>
              {item}
            </button>
          ))}
        </nav>
        <div className="user-box">
          <strong>{user.full_name}</strong>
          <span>{user.email}</span>
          <span>{user.role}</span>
          <button onClick={handleLogout}>Logout</button>
        </div>
      </aside>

      <section className="workspace">
        <header className="topbar">
          <div>
            <p className="eyebrow">API {API_BASE}</p>
            <h2>{tab === "overview" ? "Weekly dashboard" : tab}</h2>
          </div>
          <div className="toolbar">
            <button onClick={() => void loadAll()} disabled={loading}>
              Refresh
            </button>
            <button onClick={() => void downloadExport("/api/v1/exports/csv", "leads.csv")} disabled={loading}>
              Export leads
            </button>
            <button onClick={() => void downloadExport("/api/v1/reports/weekly/csv", "weekly-dashboard.csv")} disabled={loading}>
              Export report
            </button>
          </div>
        </header>

        <p className="status">{loading ? "Working..." : message}</p>

        {tab === "overview" && (
          <section className="stack">
            <div className="stats-grid">
              <article>
                <span>This week</span>
                <strong>{dashboard?.headline.total_leads_this_week ?? 0}</strong>
              </article>
              <article>
                <span>Target</span>
                <strong>{dashboard?.headline.weekly_target ?? assignments?.weekly_team_target ?? 100}</strong>
              </article>
              <article>
                <span>Progress</span>
                <strong>{dashboard?.headline.percent_of_target ?? 0}%</strong>
              </article>
              <article>
                <span>Still needed</span>
                <strong>{dashboard?.headline.leads_still_needed ?? 0}</strong>
              </article>
            </div>

            <section className="panel" style={{ width: "100%", maxWidth: "800px", margin: "0 auto" }}>
              <h3>Leads Progress</h3>
              <div className="table-wrap">
                <table>
                  <thead>
                    <tr>
                      <th>Cities</th>
                      <th>Leads</th>
                      <th>Status</th>
                    </tr>
                  </thead>
                  <tbody>
                    {(dashboard?.by_intern || []).map((row, index) => (
                      <tr key={row.cities.join("-") || index}>
                        <td>{row.cities.join(", ")}</td>
                        <td>{row.leads_this_week}/{row.target_per_week}</td>
                        <td><span className={row.on_track ? "pill calm" : "pill warn"}>{row.on_track ? "On Track" : `${row.shortfall} Short`}</span></td>
                      </tr>
                    ))}
                  </tbody>
                </table>
              </div>
            </section>
          </section>
        )}

        {tab === "leads" && (
          <section className="stack">
            <div className="filters">
              <label>
                City
                <input value={filters.city} onChange={(event) => setFilters({ ...filters, city: event.target.value })} placeholder="Karachi" />
              </label>
              <label>
                Priority
                <select value={filters.priority} onChange={(event) => setFilters({ ...filters, priority: event.target.value })}>
                  <option value="">All</option>
                  <option value="high">High</option>
                  <option value="medium">Medium</option>
                  <option value="low">Low</option>
                </select>
              </label>
              <button onClick={() => void loadAll()}>Apply</button>
            </div>

            <section className="panel">
              <h3>Leads</h3>
              <div className="table-wrap">
                <table>
                  <thead>
                    <tr>
                      <th>Lead</th>
                      <th>Business & Owner</th>
                      <th>City</th>
                      <th>Contact</th>
                      <th>Order & Delivery</th>
                      <th>Priority</th>
                      <th>Status & Tech</th>
                    </tr>
                  </thead>
                  <tbody>
                    {leads.map((lead) => (
                      <tr key={lead.id}>
                        <td>{lead.lead_ref ? `#${lead.lead_ref}` : "New"}</td>
                        <td>
                          <strong>{lead.business?.name || lead.business_id}</strong>
                          <span>{fieldValue(lead.business?.business_type)}</span>
                          {lead.business?.owner_manager_name && (
                            <span style={{ fontSize: "0.85em", color: "#666" }}>
                              Owner: {lead.business.owner_manager_name}
                            </span>
                          )}
                        </td>
                        <td>{fieldValue(lead.business?.city)}</td>
                        <td>
                          <span>{fieldValue(lead.business?.phone)}</span>
                          <span>{fieldValue(lead.business?.email)}</span>
                        </td>
                        <td>
                          <span>{fieldValue(lead.order_method_detail || lead.order_method)}</span>
                          {lead.delivery_system && (
                            <span style={{ fontSize: "0.85em", color: "#555" }}>
                              Delivery: {lead.delivery_system}
                            </span>
                          )}
                        </td>
                        <td><span className={priorityClass(lead.priority)}>{lead.priority}</span></td>
                        <td>
                          <strong>{lead.automation_status_detail || lead.automation_status}</strong>
                          {lead.notes && (
                            <span style={{ fontSize: "0.8em", color: "#666", display: "block" }}>
                              {lead.notes}
                            </span>
                          )}
                        </td>
                      </tr>
                    ))}
                  </tbody>
                </table>
              </div>
            </section>
          </section>
        )}

        {tab === "discovery" && (
          <section className="stack">
            <form className="grid-form" onSubmit={runDiscovery}>
              <label>
                Category
                <input value={discovery.category} onChange={(event) => setDiscovery({ ...discovery, category: event.target.value })} />
              </label>
              <label>
                City
                <input value={discovery.city} onChange={(event) => setDiscovery({ ...discovery, city: event.target.value })} />
              </label>
              <label>
                Country
                <input value={discovery.country} onChange={(event) => setDiscovery({ ...discovery, country: event.target.value })} />
              </label>
              <label>
                Max results
                <input
                  type="number"
                  min="1"
                  max="100"
                  value={discovery.max_results}
                  onChange={(event) => setDiscovery({ ...discovery, max_results: Number(event.target.value) })}
                />
              </label>
              <button className="primary">Run Google Maps discovery</button>
            </form>

            <form className="grid-form" onSubmit={createBusiness}>
              <h3>Manual add</h3>
              <label>
                Name
                <input value={businessForm.name} onChange={(event) => setBusinessForm({ ...businessForm, name: event.target.value })} required />
              </label>
              <label>
                Type
                <input value={businessForm.business_type} onChange={(event) => setBusinessForm({ ...businessForm, business_type: event.target.value })} />
              </label>
              <label>
                City
                <input value={businessForm.city} onChange={(event) => setBusinessForm({ ...businessForm, city: event.target.value })} required />
              </label>
              <label>
                Country
                <input value={businessForm.country} onChange={(event) => setBusinessForm({ ...businessForm, country: event.target.value })} />
              </label>
              <label>
                Website
                <input value={businessForm.website} onChange={(event) => setBusinessForm({ ...businessForm, website: event.target.value })} />
              </label>
              <label>
                Phone
                <input value={businessForm.phone} onChange={(event) => setBusinessForm({ ...businessForm, phone: event.target.value })} />
              </label>
              <button className="primary">Save business</button>
            </form>

            <section className="panel">
              <h3>Businesses</h3>
              <div className="business-grid">
                {businesses.map((business) => (
                  <article key={business.id} className="business-card">
                    <div>
                      <strong>{business.name}</strong>
                      <span>{fieldValue(business.business_type)} in {fieldValue(business.city)}</span>
                      <span>{business.website_available ? "Website available" : "No website"}</span>
                    </div>
                    <div className="card-actions">
                      <button disabled={!business.website || loading} onClick={() => void enrichBusiness(business.id)}>
                        Enrich
                      </button>
                      <button disabled={loading} onClick={() => void scoreBusiness(business.id)}>
                        Score
                      </button>
                    </div>
                  </article>
                ))}
              </div>
            </section>
          </section>
        )}

        {tab === "tools" && (
          <section className="stack">
            <form className="grid-form" onSubmit={scrapeStandalone}>
              <h3>Website scraper</h3>
              <label>
                Website URL
                <input value={scrapeUrl} onChange={(event) => setScrapeUrl(event.target.value)} />
              </label>
              <button className="primary">Scrape website</button>
            </form>
            <section className="panel">
              <h3>Scraper result</h3>
              <pre>{scrapeResult ? JSON.stringify(scrapeResult, null, 2) : "No scrape run yet."}</pre>
            </section>
            <section className="panel">
              <h3>Business types</h3>
              <div className="type-list">
                {(dashboard?.by_business_type || []).map((row) => (
                  <span key={row.business_type}>{row.business_type}: {row.total_leads}</span>
                ))}
              </div>
            </section>
          </section>
        )}
      </section>
    </main>
  );
}
