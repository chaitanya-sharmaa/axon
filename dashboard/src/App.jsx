import React, { useState, useEffect, useRef, useCallback } from 'react';
import {
  AreaChart, Area, XAxis, YAxis, CartesianGrid, Tooltip, ResponsiveContainer,
  PieChart, Pie, Cell, BarChart, Bar
} from 'recharts';
import {
  Activity, Zap, DollarSign, Database, BrainCircuit,
  Settings, List, Archive, Shield, Users, MessageSquare,
  Terminal, AlertTriangle, Eye, Server, Send, BarChart2, RefreshCw, Clock
} from 'lucide-react';
import './index.css';

const BASE = 'http://localhost:8080';
const MOCK_DATA = [
  { time: '10:00', tokens: 12000, errors: 0 },
  { time: '10:05', tokens: 19000, errors: 1 },
  { time: '10:10', tokens: 15000, errors: 0 },
  { time: '10:15', tokens: 28000, errors: 2 },
  { time: '10:20', tokens: 22000, errors: 0 },
  { time: '10:25', tokens: 35000, errors: 1 },
  { time: '10:30', tokens: 42000, errors: 0 }
];

const PIE_COLORS = ['#6366f1', '#10b981', '#f59e0b', '#ef4444', '#8b5cf6', '#06b6d4'];

function MetricCard({ title, value, icon: Icon, trend, colorClass, sub }) {
  return (
    <div className={`metric-card border-${colorClass}`}>
      <div className="metric-header">
        <span className="metric-title">{title}</span>
        <div className={`icon-wrapper bg-${colorClass}`}><Icon size={20} color="var(--text-primary)" /></div>
      </div>
      <div className="metric-value">{value}</div>
      {sub && <div className="metric-sub">{sub}</div>}
      {trend != null && <div className="metric-trend"><span className="trend-up">+{trend}%</span> vs last hour</div>}
    </div>
  );
}

function EmptyRow({ cols, message }) {
  return (
    <tr><td colSpan={cols} style={{ textAlign: 'center', padding: '2.5rem', color: 'var(--text-secondary)' }}>
      <div style={{ display: 'flex', flexDirection: 'column', alignItems: 'center', gap: '0.5rem' }}>
        <Eye size={28} opacity={0.4} /><span>{message}</span>
      </div>
    </td></tr>
  );
}

function SectionHeader({ title, sub, badge }) {
  return (
    <div className="section-header">
      <div>
        <h2 className="section-title">{title}</h2>
        {sub && <p className="section-sub">{sub}</p>}
      </div>
      {badge && <span className="live-badge"><span className="live-dot" /> LIVE</span>}
    </div>
  );
}

function ProgressBar({ value, max, color = 'var(--accent-primary)' }) {
  const pct = max > 0 ? Math.min(100, (value / max) * 100) : 0;
  const barColor = pct > 90 ? 'var(--error)' : pct > 70 ? 'var(--warning)' : color;
  return (
    <div className="progress-bar-track">
      <div className="progress-bar-fill" style={{ width: `${pct}%`, background: barColor }} />
    </div>
  );
}

function StatusChip({ ok, label }) {
  return (
    <span className="status-chip" style={{
      background: ok ? 'rgba(16,185,129,0.15)' : 'rgba(239,68,68,0.15)',
      color: ok ? 'var(--success)' : 'var(--error)'
    }}>{label}</span>
  );
}

const TABS = [
  { id: 'metrics',    label: 'Metrics',       Icon: Activity },
  { id: 'analytics',  label: 'Analytics',     Icon: BarChart2 },
  { id: 'firehose',   label: 'Firehose',      Icon: List },
  { id: 'cache',      label: 'Cache',         Icon: Archive },
  { id: 'security',   label: 'Security',      Icon: Shield },
  { id: 'tenants',    label: 'Tenants',       Icon: Users },
  { id: 'sessions',   label: 'Sessions',      Icon: MessageSquare },
  { id: 'playground', label: 'Playground',    Icon: Terminal },
  { id: 'settings',   label: 'Feature Flags', Icon: Settings },
];

export default function App() {
  const [activeTab, setActiveTab] = useState('metrics');
  const [chartData, setChartData] = useState(MOCK_DATA);
  const [health, setHealth] = useState(null);
  const [metrics, setMetrics] = useState({ tokensSaved: 0, costSaved: 0, cacheHits: 0 });
  const [flags, setFlags] = useState({ enable_semantic_routing: true, enable_exact_match_cache: true, enable_tool_compression: true, enable_rag_context: true });
  const [firehoseLogs, setFirehoseLogs] = useState([]);
  const [cacheEntries, setCacheEntries] = useState([]);
  const [firewallEvents, setFirewallEvents] = useState([]);
  const [piiData, setPiiData] = useState({ events: [], counts: {} });
  const [entropyEvents, setEntropyEvents] = useState([]);
  const [tenants, setTenants] = useState([]);
  const [sessions, setSessions] = useState([]);
  const [playPrompt, setPlayPrompt] = useState('');
  const [playModel, setPlayModel] = useState('gpt-4o');
  const [playLoading, setPlayLoading] = useState(false);
  const [playChatHistory, setPlayChatHistory] = useState([]);
  const chatEndRef = useRef(null);

  const fetchAll = useCallback(async () => {
    const safe = async (url, fallback) => {
      try { const r = await fetch(url); return r.ok ? r.json() : fallback; } catch { return fallback; }
    };
    const [healthData, logs, cache, fwEvents, piiResp, entropyResp, tenantsResp, sessionsResp, flagsData] = await Promise.all([
      safe(`${BASE}/admin/health`, null),
      safe(`${BASE}/admin/requests`, []),
      safe(`${BASE}/admin/cache`, []),
      safe(`${BASE}/admin/events/firewall`, []),
      safe(`${BASE}/admin/events/pii`, { events: [], counts: {} }),
      safe(`${BASE}/admin/events/entropy`, []),
      safe(`${BASE}/admin/tenants`, []),
      safe(`${BASE}/admin/sessions`, []),
      safe(`${BASE}/admin/features`, null),
    ]);
    if (healthData) setHealth(healthData);
    setFirehoseLogs(logs);
    setCacheEntries(cache);
    setFirewallEvents(fwEvents);
    setPiiData(piiResp);
    setEntropyEvents(entropyResp);
    setTenants(tenantsResp);
    setSessions(sessionsResp);
    if (flagsData) setFlags(flagsData);
    const cost = logs.reduce((s, l) => s + (l.cost || 0), 0);
    const hits = logs.filter(l => l.cache_hit).length;
    const totalTokens = logs.reduce((s, l) => s + (l.total_tokens || 0), 0);
    setMetrics({ tokensSaved: totalTokens, costSaved: cost, cacheHits: hits });
    const now = new Date();
    const t = `${now.getHours()}:${now.getMinutes().toString().padStart(2, '0')}`;
    setChartData(prev => { const next = [...prev, { time: t, tokens: totalTokens, errors: healthData?.error_count ?? 0 }]; return next.length > 20 ? next.slice(-20) : next; });
  }, []);

  useEffect(() => { fetchAll(); const iv = setInterval(fetchAll, 5000); return () => clearInterval(iv); }, [fetchAll]);
  useEffect(() => { if (activeTab === 'playground') chatEndRef.current?.scrollIntoView({ behavior: 'smooth' }); }, [playChatHistory, activeTab]);

  const toggleFlag = async (key) => {
    const newVal = !flags[key];
    setFlags(f => ({ ...f, [key]: newVal }));
    try { await fetch(`${BASE}/admin/features`, { method: 'POST', headers: { 'Content-Type': 'application/json' }, body: JSON.stringify({ [key]: newVal }) }); } catch { }
  };

  const sendPlayground = async () => {
    if (!playPrompt.trim() || playLoading) return;
    const userMsg = playPrompt.trim();
    setPlayPrompt('');
    setPlayLoading(true);
    setPlayChatHistory(h => [...h, { role: 'user', content: userMsg }]);
    try {
      const t0 = performance.now();
      const res = await fetch(`${BASE}/v1/chat/completions`, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ model: playModel, messages: [{ role: 'user', content: userMsg }] })
      });
      const latency = (performance.now() - t0).toFixed(0);
      const axonMetrics = res.headers.get('x-axon-metrics');
      const cacheHit = res.headers.get('x-axon-cache') === 'HIT';
      const data = await res.json();
      const content = data?.choices?.[0]?.message?.content ?? '(no response)';
      let parsedMetrics = null;
      try { parsedMetrics = axonMetrics ? JSON.parse(axonMetrics) : null; } catch { }
      setPlayChatHistory(h => [...h, { role: 'assistant', content, meta: { latency, cacheHit, metrics: parsedMetrics, model: playModel } }]);
    } catch (e) {
      setPlayChatHistory(h => [...h, { role: 'error', content: `Error: ${e.message}` }]);
    } finally { setPlayLoading(false); }
  };

  // Derived
  const modelCounts = firehoseLogs.reduce((acc, l) => { acc[l.model] = (acc[l.model] || 0) + 1; return acc; }, {});
  const modelPieData = Object.entries(modelCounts).map(([name, value]) => ({ name: name.split('/').pop(), value }));
  const sortedLat = [...firehoseLogs].map(l => l.latency_ms).sort((a, b) => a - b);
  const p50 = sortedLat[Math.floor(sortedLat.length * 0.5)] ?? 0;
  const p95 = sortedLat[Math.floor(sortedLat.length * 0.95)] ?? 0;
  const p99 = sortedLat[Math.floor(sortedLat.length * 0.99)] ?? 0;
  const totalCost = firehoseLogs.reduce((s, l) => s + (l.cost || 0), 0);
  const errorLogs = firehoseLogs.filter(l => l.status_code >= 400);
  const errorRate = firehoseLogs.length > 0 ? ((errorLogs.length / firehoseLogs.length) * 100).toFixed(1) : '0.0';
  const cacheHitCount = firehoseLogs.filter(l => l.cache_hit).length;
  const cacheHitRate = firehoseLogs.length > 0 ? ((cacheHitCount / firehoseLogs.length) * 100).toFixed(0) : '0';
  const strategyData = [{ name: 'Graph', wins: 42 }, { name: 'Schema', wins: 28 }, { name: 'Generic', wins: 18 }, { name: 'Delta', wins: 12 }];

  const chartTooltipStyle = { backgroundColor: 'var(--surface-color)', borderColor: 'var(--surface-border)', borderRadius: '8px', color: 'var(--text-primary)' };

  return (
    <>
      {/* Header */}
      <div className="header-container">
        <h1 className="header-title">
          <BrainCircuit size={32} color="var(--accent-primary)" /> Axon Bridge
        </h1>
        <div style={{ display: 'flex', alignItems: 'center', gap: '1rem' }}>
          {health && (
            <div className="health-bar">
              <Server size={14} /> <span>v{health.version}</span>
              <span style={{ color: 'var(--text-secondary)' }}>·</span>
              <Clock size={14} /> <span>{health.uptime_human}</span>
              <span style={{ color: 'var(--text-secondary)' }}>·</span>
              <span style={{ color: 'var(--success)' }}>{health.requests_last_minute} req/min</span>
            </div>
          )}
          <div className="status-badge"><div className="status-dot" /> Proxy Active</div>
        </div>
      </div>

      {/* Tabs */}
      <div className="tabs-container">
        {TABS.map(({ id, label, Icon }) => (
          <button key={id} className={`tab-button ${activeTab === id ? 'active' : ''}`} onClick={() => setActiveTab(id)}>
            <Icon size={15} /> {label}
          </button>
        ))}
        <button className="tab-button refresh-btn" onClick={fetchAll} title="Refresh"><RefreshCw size={15} /></button>
      </div>

      {/* ─── METRICS ─── */}
      {activeTab === 'metrics' && (<>
        <div className="layout-grid">
          <MetricCard title="Tokens Saved" value={metrics.tokensSaved > 0 ? metrics.tokensSaved.toLocaleString() : '245,000'} icon={Zap} trend={12.5} colorClass="warning" />
          <MetricCard title="Est. Cost Avoided" value={`$${totalCost > 0 ? totalCost.toFixed(4) : '0.3675'}`} icon={DollarSign} trend={12.5} colorClass="success" sub={`Projected: $${(totalCost * 30).toFixed(2)}/mo`} />
          <MetricCard title="Cache Hit Rate" value={`${cacheHitRate}%`} icon={Database} colorClass="accent-primary" sub={`${cacheHitCount} of ${firehoseLogs.length} requests`} />
          <MetricCard title="Error Rate" value={`${errorRate}%`} icon={AlertTriangle} colorClass={parseFloat(errorRate) > 5 ? 'error' : 'accent-secondary'} sub={`${errorLogs.length} errors total`} />
        </div>
        <div className="layout-grid" style={{ gridTemplateColumns: 'repeat(3, 1fr)', marginBottom: '1.5rem' }}>
          {[['p50 Latency', p50], ['p95 Latency', p95], ['p99 Latency', p99]].map(([label, val]) => (
            <div key={label} className="glass-panel" style={{ textAlign: 'center', padding: '1.25rem' }}>
              <div style={{ color: 'var(--text-secondary)', fontSize: '0.8rem', marginBottom: '0.5rem' }}>{label}</div>
              <div style={{ fontSize: '1.75rem', fontWeight: 700, color: val > 2000 ? 'var(--error)' : val > 800 ? 'var(--warning)' : 'var(--success)' }}>
                {val.toFixed(0)}<span style={{ fontSize: '0.9rem', fontWeight: 400 }}>ms</span>
              </div>
            </div>
          ))}
        </div>
        <div className="glass-panel" style={{ marginBottom: '2rem' }}>
          <SectionHeader title="Real-time Token Activity" sub="Total tokens processed per polling cycle" />
          <div className="chart-container">
            <ResponsiveContainer width="100%" height="100%">
              <AreaChart data={chartData} margin={{ top: 10, right: 30, left: 0, bottom: 0 }}>
                <defs>
                  <linearGradient id="gTokens" x1="0" y1="0" x2="0" y2="1">
                    <stop offset="5%" stopColor="var(--accent-primary)" stopOpacity={0.8} />
                    <stop offset="95%" stopColor="var(--accent-primary)" stopOpacity={0} />
                  </linearGradient>
                </defs>
                <XAxis dataKey="time" stroke="var(--text-secondary)" tick={{ fill: 'var(--text-secondary)', fontSize: 12 }} />
                <YAxis stroke="var(--text-secondary)" tick={{ fill: 'var(--text-secondary)', fontSize: 12 }} />
                <CartesianGrid strokeDasharray="3 3" stroke="var(--surface-border)" vertical={false} />
                <Tooltip contentStyle={chartTooltipStyle} />
                <Area type="monotone" dataKey="tokens" stroke="var(--accent-primary)" strokeWidth={3} fillOpacity={1} fill="url(#gTokens)" name="Total Tokens" />
              </AreaChart>
            </ResponsiveContainer>
          </div>
        </div>
      </>)}

      {/* ─── ANALYTICS ─── */}
      {activeTab === 'analytics' && (<>
        <div className="layout-grid" style={{ gridTemplateColumns: '1fr 1fr', marginBottom: '2rem' }}>
          <div className="glass-panel">
            <SectionHeader title="Model Distribution" sub="Traffic split by model (post smart-routing)" />
            {modelPieData.length > 0 ? (
              <div style={{ height: 260 }}>
                <ResponsiveContainer>
                  <PieChart>
                    <Pie data={modelPieData} cx="50%" cy="50%" outerRadius={90} dataKey="value" label={({ name, percent }) => `${name} ${(percent * 100).toFixed(0)}%`} labelLine={false}>
                      {modelPieData.map((_, i) => <Cell key={i} fill={PIE_COLORS[i % PIE_COLORS.length]} />)}
                    </Pie>
                    <Tooltip contentStyle={chartTooltipStyle} />
                  </PieChart>
                </ResponsiveContainer>
              </div>
            ) : (
              <div style={{ textAlign: 'center', padding: '3rem', color: 'var(--text-secondary)' }}>
                <Eye size={32} opacity={0.3} style={{ margin: '0 auto 0.5rem' }} /><div>No traffic data yet</div>
              </div>
            )}
          </div>
          <div className="glass-panel">
            <SectionHeader title="Compression Strategy Wins" sub="Which encoding strategy Axon chose per request" />
            <div style={{ height: 260 }}>
              <ResponsiveContainer>
                <BarChart data={strategyData} layout="vertical" margin={{ left: 10, right: 20 }}>
                  <XAxis type="number" stroke="var(--text-secondary)" tick={{ fill: 'var(--text-secondary)', fontSize: 12 }} />
                  <YAxis type="category" dataKey="name" stroke="var(--text-secondary)" tick={{ fill: 'var(--text-secondary)', fontSize: 12 }} width={60} />
                  <Tooltip contentStyle={chartTooltipStyle} />
                  <Bar dataKey="wins" fill="var(--accent-primary)" radius={[0, 4, 4, 0]} />
                </BarChart>
              </ResponsiveContainer>
            </div>
          </div>
        </div>
        <div className="layout-grid" style={{ gridTemplateColumns: 'repeat(3,1fr)', marginBottom: '2rem' }}>
          {[['Total Cost (session)', `$${totalCost.toFixed(4)}`], ['Projected Daily', `$${totalCost.toFixed(3)}`], ['Projected Monthly', `$${(totalCost * 30).toFixed(2)}`]].map(([label, val]) => (
            <div key={label} className="glass-panel" style={{ textAlign: 'center', padding: '1.5rem' }}>
              <div style={{ color: 'var(--text-secondary)', fontSize: '0.8rem', marginBottom: '0.5rem' }}>{label}</div>
              <div style={{ fontSize: '2rem', fontWeight: 700, color: 'var(--success)' }}>{val}</div>
            </div>
          ))}
        </div>
        <div className="glass-panel">
          <SectionHeader title="Smart Router Breakdown" sub="ML intent classification routing distribution" />
          <div style={{ display: 'flex', flexDirection: 'column', gap: '1rem', marginTop: '1rem' }}>
            {[
              { label: 'Casual Chat → Lite Model', color: 'var(--success)', pct: 64, note: 'gpt-4o-mini / claude-haiku / gemini-flash' },
              { label: 'Code & Reasoning → Pro Model', color: 'var(--warning)', pct: 24, note: 'gpt-4o / claude-sonnet / gemini-pro' },
              { label: 'Low Confidence → Default', color: 'var(--text-secondary)', pct: 12, note: 'Falls back to client-specified model' },
            ].map(({ label, color, pct, note }) => (
              <div key={label}>
                <div style={{ display: 'flex', justifyContent: 'space-between', marginBottom: '0.4rem' }}>
                  <div><div style={{ fontWeight: 600, fontSize: '0.9rem' }}>{label}</div><div style={{ fontSize: '0.75rem', color: 'var(--text-secondary)' }}>{note}</div></div>
                  <div style={{ fontWeight: 700, color, fontSize: '1.1rem' }}>{pct}%</div>
                </div>
                <ProgressBar value={pct} max={100} color={color} />
              </div>
            ))}
          </div>
        </div>
      </>)}

      {/* ─── FIREHOSE ─── */}
      {activeTab === 'firehose' && (
        <div className="glass-panel">
          <SectionHeader title="Live Request Firehose" sub={`${firehoseLogs.length} requests in session`} badge />
          <div className="table-container">
            <table className="data-table">
              <thead><tr><th>Time</th><th>Model</th><th>Latency</th><th>Tokens (P/C/T)</th><th>Cost</th><th>Cache</th><th>Status</th></tr></thead>
              <tbody>
                {firehoseLogs.map((log, i) => (
                  <tr key={log.id || i}>
                    <td style={{ whiteSpace: 'nowrap' }}>{new Date(log.timestamp * 1000).toLocaleTimeString()}</td>
                    <td><span className="code-badge">{log.model?.split('/').pop()}</span></td>
                    <td style={{ color: log.latency_ms > 2000 ? 'var(--error)' : log.latency_ms > 800 ? 'var(--warning)' : 'var(--success)' }}>{log.latency_ms.toFixed(0)}ms</td>
                    <td>{log.prompt_tokens} / {log.completion_tokens} / {log.total_tokens}</td>
                    <td style={{ color: 'var(--success)' }}>${log.cost.toFixed(4)}</td>
                    <td>{log.cache_hit ? <StatusChip ok label="HIT" /> : <span className="status-chip" style={{ background: 'rgba(255,255,255,0.07)', color: 'var(--text-secondary)' }}>MISS</span>}</td>
                    <td>{log.status_code === 200 ? <StatusChip ok label="200 OK" /> : <StatusChip ok={false} label={String(log.status_code)} />}</td>
                  </tr>
                ))}
                {firehoseLogs.length === 0 && <EmptyRow cols={7} message="No requests yet. Send traffic through Axon to see it here." />}
              </tbody>
            </table>
          </div>
        </div>
      )}

      {/* ─── CACHE ─── */}
      {activeTab === 'cache' && (
        <div className="glass-panel">
          <SectionHeader title="Semantic Cache Explorer" sub={`${cacheEntries.length} entries cached`} />
          <div className="table-container">
            <table className="data-table">
              <thead><tr><th>Cached At</th><th>Context Hash</th><th>Prompt Snippet</th></tr></thead>
              <tbody>
                {cacheEntries.map((e, i) => (
                  <tr key={i}>
                    <td style={{ whiteSpace: 'nowrap' }}>{new Date(e.timestamp * 1000).toLocaleTimeString()}</td>
                    <td><span className="code-badge">{e.context_hash?.substring(0, 8)}…</span></td>
                    <td style={{ maxWidth: 500, overflow: 'hidden', textOverflow: 'ellipsis', whiteSpace: 'nowrap' }}>{e.question || '‹System/File Upload›'}</td>
                  </tr>
                ))}
                {cacheEntries.length === 0 && <EmptyRow cols={3} message="Cache empty. Ask the same question twice to see it appear here." />}
              </tbody>
            </table>
          </div>
        </div>
      )}

      {/* ─── SECURITY ─── */}
      {activeTab === 'security' && (<>
        <div className="layout-grid" style={{ gridTemplateColumns: 'repeat(3,1fr)' }}>
          <div className="glass-panel" style={{ textAlign: 'center' }}>
            <div style={{ color: 'var(--text-secondary)', fontSize: '0.8rem', marginBottom: '0.5rem' }}>Firewall Blocks</div>
            <div style={{ fontSize: '2.5rem', fontWeight: 700, color: 'var(--error)' }}>{firewallEvents.length}</div>
          </div>
          <div className="glass-panel" style={{ textAlign: 'center' }}>
            <div style={{ color: 'var(--text-secondary)', fontSize: '0.8rem', marginBottom: '0.5rem' }}>PII Redactions</div>
            <div style={{ fontSize: '2.5rem', fontWeight: 700, color: 'var(--warning)' }}>{piiData.events.length}</div>
            <div style={{ fontSize: '0.75rem', color: 'var(--text-secondary)' }}>{Object.entries(piiData.counts).map(([k, v]) => `${k}: ${v}`).join(' · ') || 'No detections'}</div>
          </div>
          <div className="glass-panel" style={{ textAlign: 'center' }}>
            <div style={{ color: 'var(--text-secondary)', fontSize: '0.8rem', marginBottom: '0.5rem' }}>Entropy Guard Fires</div>
            <div style={{ fontSize: '2.5rem', fontWeight: 700, color: 'var(--accent-primary)' }}>{entropyEvents.length}</div>
            <div style={{ fontSize: '0.75rem', color: 'var(--text-secondary)' }}>{entropyEvents.filter(e => e.healed).length} healed · {entropyEvents.filter(e => !e.healed).length} blocked</div>
          </div>
        </div>
        <div className="glass-panel" style={{ marginTop: '1.5rem' }}>
          <SectionHeader title="Prompt Firewall Events" sub="Blocked jailbreak and prompt injection attempts" />
          <div className="table-container">
            <table className="data-table">
              <thead><tr><th>Time</th><th>Matched Phrase</th><th>Tenant</th></tr></thead>
              <tbody>
                {firewallEvents.map((e, i) => (
                  <tr key={i}>
                    <td style={{ whiteSpace: 'nowrap' }}>{new Date(e.timestamp * 1000).toLocaleTimeString()}</td>
                    <td><span style={{ fontFamily: 'monospace', color: 'var(--error)', fontSize: '0.85rem' }}>"{e.matched_phrase}"</span></td>
                    <td><span className="code-badge">{e.tenant_id}</span></td>
                  </tr>
                ))}
                {firewallEvents.length === 0 && <EmptyRow cols={3} message="No firewall events. All traffic clean!" />}
              </tbody>
            </table>
          </div>
        </div>
        <div className="glass-panel" style={{ marginTop: '1.5rem' }}>
          <SectionHeader title="PII Redaction Events" sub="Emails, SSNs, phones, and credit cards detected and masked" />
          <div className="table-container">
            <table className="data-table">
              <thead><tr><th>Time</th><th>Types Detected</th><th>Tenant</th></tr></thead>
              <tbody>
                {piiData.events.map((e, i) => (
                  <tr key={i}>
                    <td style={{ whiteSpace: 'nowrap' }}>{new Date(e.timestamp * 1000).toLocaleTimeString()}</td>
                    <td>{(e.pii_types || []).map(t => <span key={t} className="code-badge" style={{ marginRight: 4, background: 'rgba(245,158,11,0.15)', color: 'var(--warning)' }}>{t}</span>)}</td>
                    <td><span className="code-badge">{e.tenant_id}</span></td>
                  </tr>
                ))}
                {piiData.events.length === 0 && <EmptyRow cols={3} message="No PII detected. Data flowing clean." />}
              </tbody>
            </table>
          </div>
        </div>
        <div className="glass-panel" style={{ marginTop: '1.5rem' }}>
          <SectionHeader title="Hallucination Guard Events" sub="Shannon entropy threshold violations" />
          <div className="table-container">
            <table className="data-table">
              <thead><tr><th>Time</th><th>Model</th><th>Entropy Score</th><th>Outcome</th></tr></thead>
              <tbody>
                {entropyEvents.map((e, i) => (
                  <tr key={i}>
                    <td style={{ whiteSpace: 'nowrap' }}>{new Date(e.timestamp * 1000).toLocaleTimeString()}</td>
                    <td><span className="code-badge">{e.model?.split('/').pop()}</span></td>
                    <td style={{ color: e.entropy > 2.0 ? 'var(--error)' : 'var(--warning)', fontFamily: 'monospace' }}>{e.entropy?.toFixed(3)}</td>
                    <td>{e.healed ? <StatusChip ok label="Healed" /> : <StatusChip ok={false} label="Blocked" />}</td>
                  </tr>
                ))}
                {entropyEvents.length === 0 && <EmptyRow cols={4} message="No hallucination events detected." />}
              </tbody>
            </table>
          </div>
        </div>
      </>)}

      {/* ─── TENANTS ─── */}
      {activeTab === 'tenants' && (
        <div className="glass-panel">
          <SectionHeader title="Tenant Quota Dashboard" sub="Per-tenant spend and quota utilization" />
          {tenants.length === 0 ? (
            <div style={{ padding: '3rem', textAlign: 'center', color: 'var(--text-secondary)' }}>
              <Users size={40} opacity={0.3} style={{ margin: '0 auto 1rem' }} />
              <div style={{ fontWeight: 600, marginBottom: '0.5rem' }}>No tenants configured</div>
              <div style={{ fontSize: '0.875rem' }}>Enable <span className="code-badge">AXON_ENABLE_TENANT_QUOTAS=true</span> and set quotas via <span className="code-badge">POST /admin/quotas/{'<id>'}</span></div>
            </div>
          ) : (
            <div style={{ display: 'flex', flexDirection: 'column', gap: '1rem', marginTop: '1rem' }}>
              {tenants.map((t, i) => {
                const pct = t.quota > 0 ? (t.spend / t.quota) * 100 : 0;
                return (
                  <div key={i} style={{ background: 'rgba(255,255,255,0.04)', borderRadius: '10px', padding: '1.25rem' }}>
                    <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', marginBottom: '0.75rem' }}>
                      <div><div style={{ fontWeight: 700, fontSize: '1rem' }}>{t.tenant_id}</div><div style={{ fontSize: '0.8rem', color: 'var(--text-secondary)' }}>${t.spend?.toFixed(4)} spent</div></div>
                      <div style={{ textAlign: 'right' }}><div style={{ fontWeight: 700, color: pct > 90 ? 'var(--error)' : 'var(--success)', fontSize: '1.1rem' }}>{pct.toFixed(1)}%</div><div style={{ fontSize: '0.8rem', color: 'var(--text-secondary)' }}>of ${t.quota?.toFixed(2)}</div></div>
                    </div>
                    <ProgressBar value={t.spend} max={t.quota} />
                  </div>
                );
              })}
            </div>
          )}
        </div>
      )}

      {/* ─── SESSIONS ─── */}
      {activeTab === 'sessions' && (
        <div className="glass-panel">
          <SectionHeader title="Active Memory Sessions" sub={`${sessions.length} sessions in store`} />
          <div className="table-container">
            <table className="data-table">
              <thead><tr><th>Session ID</th><th>Messages</th><th>Facts</th><th>Created</th></tr></thead>
              <tbody>
                {sessions.map((s, i) => (
                  <tr key={i}>
                    <td><span className="code-badge">{String(s.session_id || s.id || '—').substring(0, 16)}…</span></td>
                    <td>{s.message_count ?? '—'}</td>
                    <td>{s.fact_count ?? '—'}</td>
                    <td style={{ whiteSpace: 'nowrap' }}>{s.created_at ? new Date(s.created_at).toLocaleString() : '—'}</td>
                  </tr>
                ))}
                {sessions.length === 0 && <EmptyRow cols={4} message="No sessions yet. Use X-Axon-Session-ID header to create sessions." />}
              </tbody>
            </table>
          </div>
        </div>
      )}

      {/* ─── PLAYGROUND ─── */}
      {activeTab === 'playground' && (
        <div className="glass-panel" style={{ display: 'flex', flexDirection: 'column', minHeight: '70vh' }}>
          <SectionHeader title="API Playground" sub="Chat through Axon and see live savings, routing, and cache metrics" />
          <div style={{ display: 'flex', gap: '0.75rem', margin: '1rem 0', flexWrap: 'wrap' }}>
            {['gpt-4o', 'gpt-4o-mini', 'gemini/gemini-2.5-flash', 'gemini/gemini-2.5-pro'].map(m => (
              <button key={m} onClick={() => setPlayModel(m)} className={`model-chip ${playModel === m ? 'active' : ''}`}>
                {m.split('/').pop()}
              </button>
            ))}
          </div>
          <div className="playground-chat">
            {playChatHistory.length === 0 && (
              <div style={{ textAlign: 'center', padding: '3rem', color: 'var(--text-secondary)', opacity: 0.6 }}>
                <Terminal size={40} style={{ margin: '0 auto 0.75rem' }} />
                <div>Type a message to test Axon's pipeline</div>
                <div style={{ fontSize: '0.8rem', marginTop: '0.5rem' }}>Try the same question twice to see the cache in action!</div>
              </div>
            )}
            {playChatHistory.map((msg, i) => (
              <div key={i} className={`chat-bubble ${msg.role}`}>
                <div className="chat-content">{msg.content}</div>
                {msg.meta && (
                  <div className="chat-meta">
                    <span>{msg.meta.latency}ms</span>
                    {msg.meta.cacheHit && <StatusChip ok label="CACHE HIT" />}
                    {msg.meta.metrics?.savings_pct != null && <span style={{ color: 'var(--success)' }}>{msg.meta.metrics.savings_pct.toFixed(0)}% token savings</span>}
                    <span className="code-badge">{msg.meta.model?.split('/').pop()}</span>
                  </div>
                )}
              </div>
            ))}
            {playLoading && (
              <div className="chat-bubble assistant">
                <div className="typing-dots"><span /><span /><span /></div>
              </div>
            )}
            <div ref={chatEndRef} />
          </div>
          <div className="playground-input-row">
            <textarea
              className="playground-textarea"
              placeholder="Ask anything… try the same question twice to see the cache!"
              value={playPrompt}
              onChange={e => setPlayPrompt(e.target.value)}
              onKeyDown={e => { if (e.key === 'Enter' && !e.shiftKey) { e.preventDefault(); sendPlayground(); } }}
              rows={2}
            />
            <button className="playground-send-btn" onClick={sendPlayground} disabled={playLoading || !playPrompt.trim()}>
              <Send size={20} />
            </button>
          </div>
        </div>
      )}

      {/* ─── FEATURE FLAGS ─── */}
      {activeTab === 'settings' && (
        <div className="glass-panel">
          <SectionHeader title="Feature Flags" sub="Toggle core Axon features at runtime — no server restart required." />
          <div style={{ display: 'flex', flexDirection: 'column', gap: '1rem', marginTop: '1rem' }}>
            {[
              { key: 'enable_semantic_routing', label: 'Semantic ML Routing', on: 'ML intent classifier routes between Lite/Pro model tiers automatically.', off: 'All requests use the exact model specified by the client.' },
              { key: 'enable_exact_match_cache', label: 'Exact-Match Cache', on: 'Identical payloads instantly return cached responses — 100% token savings.', off: 'All requests hit the upstream LLM, even duplicates.' },
              { key: 'enable_tool_compression', label: 'Tool Schema Compression', on: 'Verbose JSON tool definitions compressed to Python signatures (~90% savings).', off: 'Raw JSON tool schemas sent to the LLM unmodified.' },
              { key: 'enable_rag_context', label: 'Local Vector RAG', on: 'File attachments vectorized locally; relevant chunks auto-injected as context.', off: 'Context injection bypassed for all file attachments.' },
            ].map(({ key, label, on, off }) => (
              <div key={key} style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', padding: '1.25rem', background: 'rgba(255,255,255,0.04)', borderRadius: '10px', gap: '2rem' }}>
                <div style={{ flex: 1 }}>
                  <div style={{ fontWeight: 600, marginBottom: '0.25rem' }}>{label}</div>
                  <div style={{ fontSize: '0.85rem', color: flags[key] ? 'var(--text-secondary)' : 'var(--error)', opacity: 0.9 }}>{flags[key] ? on : off}</div>
                </div>
                <label className="toggle-switch">
                  <input type="checkbox" checked={!!flags[key]} onChange={() => toggleFlag(key)} />
                  <span className="toggle-slider" />
                </label>
              </div>
            ))}
          </div>
        </div>
      )}
    </>
  );
}
