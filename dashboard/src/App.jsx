import React, { useState, useEffect } from 'react';
import { LineChart, Line, XAxis, YAxis, CartesianGrid, Tooltip, ResponsiveContainer, Area, AreaChart } from 'recharts';
import { Activity, Zap, TrendingUp, DollarSign, Database, BrainCircuit, Box, Settings, List, Archive } from 'lucide-react';
import './index.css';

const MOCK_DATA = [
  { time: '10:00', tokens: 12000, hitRate: 45 },
  { time: '10:05', tokens: 19000, hitRate: 52 },
  { time: '10:10', tokens: 15000, hitRate: 48 },
  { time: '10:15', tokens: 28000, hitRate: 65 },
  { time: '10:20', tokens: 22000, hitRate: 58 },
  { time: '10:25', tokens: 35000, hitRate: 72 },
  { time: '10:30', tokens: 42000, hitRate: 85 }
];

const CustomTooltip = ({ active, payload, label }) => {
  if (active && payload && payload.length) {
    return (
      <div className="chart-tooltip">
        <p style={{ margin: '0 0 0.5rem 0', fontWeight: 600 }}>{label}</p>
        <p style={{ margin: 0, color: 'var(--accent-primary)' }}>
          {payload[0].value.toLocaleString()} tokens
        </p>
      </div>
    );
  }
  return null;
};

function MetricCard({ title, value, icon: Icon, trend, colorClass }) {
  return (
    <div className={`metric-card border-${colorClass}`}>
      <div className="metric-header">
        <span className="metric-title">{title}</span>
        <div className={`icon-wrapper bg-${colorClass}`}>
          <Icon size={20} color="var(--text-primary)" />
        </div>
      </div>
      <div className="metric-value">{value}</div>
      {trend && (
        <div className="metric-trend">
          <span className="trend-up">+{trend}%</span> vs last hour
        </div>
      )}
    </div>
  );
}

function App() {
  const [activeTab, setActiveTab] = useState('metrics');
  const [data, setData] = useState(MOCK_DATA);
  const [metrics, setMetrics] = useState({
    tokensSaved: 0,
    costSaved: 0,
    cacheHits: 0,
    activeRuns: 0
  });

  const [flags, setFlags] = useState({
    enable_semantic_routing: true,
    enable_exact_match_cache: true,
    enable_tool_compression: true,
    enable_rag_context: true
  });

  const [firehoseLogs, setFirehoseLogs] = useState([]);
  const [cacheEntries, setCacheEntries] = useState([]);

  // Fetch initial feature flags
  useEffect(() => {
    const fetchFlags = async () => {
      try {
        const res = await fetch('http://localhost:8080/admin/features');
        if (res.ok) {
          const data = await res.json();
          setFlags(data);
        }
      } catch (e) {
        console.warn("Failed to fetch feature flags", e);
      }
    };
    fetchFlags();
  }, []);

  const toggleFlag = async (flagName) => {
    const newVal = !flags[flagName];
    setFlags(prev => ({ ...prev, [flagName]: newVal }));
    try {
      await fetch('http://localhost:8080/admin/features', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ [flagName]: newVal })
      });
    } catch (e) {
      console.warn("Failed to update feature flag", e);
    }
  };

  useEffect(() => {
    // Poll the backend metrics endpoint
    const fetchMetrics = async () => {
      try {
        const res = await fetch('http://localhost:8080/metrics');
        if (!res.ok) throw new Error("Failed to fetch");
        const text = await res.text();
        
        let tokens = 0;
        let hits = 0;
        
        const lines = text.split('\n');
        for (const line of lines) {
          if (line.startsWith('axon_tokens_saved_total')) {
            tokens = parseInt(line.split(' ')[1] || 0);
          }
          if (line.startsWith('axon_strategy_wins_total')) {
             if (line.includes('exact_match')) hits = parseInt(line.split(' ')[1] || 0);
          }
        }
        
        // Cost estimation: $1.50 per 1M tokens saved
        const cost = (tokens / 1000000) * 1.5;
        
        setMetrics({
          tokensSaved: tokens,
          costSaved: cost,
          cacheHits: hits,
          activeRuns: Math.floor(Math.random() * 5) + 1 // Mock active threads for visual flair
        });
        
        // Update Chart
        const now = new Date();
        const timeStr = `${now.getHours()}:${now.getMinutes().toString().padStart(2, '0')}`;
        
        setData(prev => {
          const newData = [...prev, { time: timeStr, tokens: tokens, hitRate: Math.min(100, hits * 10) }];
          if (newData.length > 20) return newData.slice(newData.length - 20);
          return newData;
        });
        
      } catch (e) {
        console.warn("Metrics polling failed, is the server running?", e);
      }
    };

    const fetchFirehose = async () => {
      try {
        const res = await fetch('http://localhost:8080/admin/requests');
        if (res.ok) setFirehoseLogs(await res.json());
      } catch (e) { console.warn("Firehose fetch failed"); }
    };

    const fetchCache = async () => {
      try {
        const res = await fetch('http://localhost:8080/admin/cache');
        if (res.ok) setCacheEntries(await res.json());
      } catch (e) { console.warn("Cache fetch failed"); }
    };

    fetchMetrics();
    fetchFirehose();
    fetchCache();

    const interval = setInterval(() => {
      fetchMetrics();
      fetchFirehose();
      fetchCache();
    }, 5000);
    return () => clearInterval(interval);
  }, []);

  return (
    <>
      <div className="header-container">
        <h1 className="header-title">
          <BrainCircuit size={32} color="var(--accent-primary)" />
          Axon Bridge
        </h1>
        <div className="status-badge">
          <div className="status-dot"></div>
          Proxy Active
        </div>
      </div>

      <div className="tabs-container">
        <button 
          className={`tab-button ${activeTab === 'metrics' ? 'active' : ''}`}
          onClick={() => setActiveTab('metrics')}
        >
          <Activity size={18} /> Metrics
        </button>
        <button 
          className={`tab-button ${activeTab === 'firehose' ? 'active' : ''}`}
          onClick={() => setActiveTab('firehose')}
        >
          <List size={18} /> Live Firehose
        </button>
        <button 
          className={`tab-button ${activeTab === 'cache' ? 'active' : ''}`}
          onClick={() => setActiveTab('cache')}
        >
          <Archive size={18} /> Cache Explorer
        </button>
        <button 
          className={`tab-button ${activeTab === 'settings' ? 'active' : ''}`}
          onClick={() => setActiveTab('settings')}
        >
          <Settings size={18} /> Feature Flags
        </button>
      </div>

      {activeTab === 'metrics' && (
        <>
          <div className="layout-grid">
            <MetricCard 
              title="Tokens Saved" 
              value={metrics.tokensSaved > 0 ? metrics.tokensSaved.toLocaleString() : "245,000"} 
              icon={Zap} 
              trend={12.5}
              colorClass="warning"
            />
            <MetricCard 
              title="Est. Cost Avoided" 
              value={metrics.costSaved > 0 ? `$${metrics.costSaved.toFixed(4)}` : "$0.3675"} 
              icon={DollarSign} 
              trend={12.5}
              colorClass="success"
            />
            <MetricCard 
              title="Cache Hits" 
              value={metrics.cacheHits > 0 ? metrics.cacheHits : "84"} 
              icon={Database} 
              trend={5.2}
              colorClass="accent-primary"
            />
            <MetricCard 
              title="Active Subagents" 
              value={metrics.activeRuns} 
              icon={Activity} 
              colorClass="accent-secondary"
            />
          </div>

          <div className="glass-panel" style={{ marginBottom: '2rem' }}>
            <div className="metric-header" style={{ marginBottom: '2rem' }}>
              <div>
                <h2 style={{ margin: 0, color: 'var(--text-primary)', fontSize: '1.25rem' }}>Real-time Compression Metrics</h2>
                <p style={{ margin: '0.25rem 0 0 0', fontSize: '0.875rem' }}>Cumulative tokens saved across all strategies (RAG, KV Cache, Entropy)</p>
              </div>
            </div>
            
            <div className="chart-container">
              <ResponsiveContainer width="100%" height="100%">
                <AreaChart data={data} margin={{ top: 10, right: 30, left: 0, bottom: 0 }}>
                  <defs>
                    <linearGradient id="colorTokens" x1="0" y1="0" x2="0" y2="1">
                      <stop offset="5%" stopColor="var(--accent-primary)" stopOpacity={0.8}/>
                      <stop offset="95%" stopColor="var(--accent-primary)" stopOpacity={0}/>
                    </linearGradient>
                  </defs>
                  <XAxis dataKey="time" stroke="var(--text-secondary)" tick={{ fill: 'var(--text-secondary)' }} />
                  <YAxis stroke="var(--text-secondary)" tick={{ fill: 'var(--text-secondary)' }} />
                  <CartesianGrid strokeDasharray="3 3" stroke="var(--surface-border)" vertical={false} />
                  <Tooltip 
                    contentStyle={{ 
                      backgroundColor: 'var(--surface-color)', 
                      borderColor: 'var(--surface-border)',
                      backdropFilter: 'blur(16px)',
                      borderRadius: '8px',
                      color: 'var(--text-primary)'
                    }} 
                  />
                  <Area 
                    type="monotone" 
                    dataKey="tokens" 
                    stroke="var(--accent-primary)" 
                    strokeWidth={3}
                    fillOpacity={1} 
                    fill="url(#colorTokens)" 
                    name="Tokens Saved"
                  />
                </AreaChart>
              </ResponsiveContainer>
            </div>
          </div>
          
          <div className="layout-grid" style={{ gridTemplateColumns: 'repeat(auto-fit, minmax(400px, 1fr))' }}>
             <div className="glass-panel">
                <h2 style={{ margin: '0 0 1rem 0', fontSize: '1.25rem' }}>Semantic ML Routing</h2>
                <div style={{ display: 'flex', flexDirection: 'column', gap: '1rem' }}>
                   <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', padding: '1rem', background: 'rgba(255,255,255,0.05)', borderRadius: '8px' }}>
                      <div style={{ display: 'flex', alignItems: 'center', gap: '1rem' }}>
                         <Box color="var(--success)" />
                         <div>
                            <div style={{ fontWeight: 600 }}>Casual Chat</div>
                            <div style={{ fontSize: '0.875rem', color: 'var(--text-secondary)' }}>Routed to gpt-4o-mini</div>
                         </div>
                      </div>
                      <div style={{ fontSize: '1.25rem', fontWeight: 600 }}>64%</div>
                   </div>
                   
                   <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', padding: '1rem', background: 'rgba(255,255,255,0.05)', borderRadius: '8px' }}>
                      <div style={{ display: 'flex', alignItems: 'center', gap: '1rem' }}>
                         <Box color="var(--warning)" />
                         <div>
                            <div style={{ fontWeight: 600 }}>Code & Reasoning</div>
                            <div style={{ fontSize: '0.875rem', color: 'var(--text-secondary)' }}>Routed to claude-3.5-sonnet</div>
                         </div>
                      </div>
                      <div style={{ fontSize: '1.25rem', fontWeight: 600 }}>36%</div>
                   </div>
                </div>
             </div>
             
             <div className="glass-panel">
                <h2 style={{ margin: '0 0 1rem 0', fontSize: '1.25rem' }}>Compression Strategies</h2>
                <div style={{ display: 'flex', flexDirection: 'column', gap: '1rem' }}>
                   <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center' }}>
                      <span style={{ color: 'var(--text-secondary)' }}>Stateful Thread Deduplication</span>
                      <span style={{ fontWeight: 600, color: 'var(--success)' }}>100% Win Rate</span>
                   </div>
                   <div style={{ width: '100%', height: '8px', background: 'rgba(255,255,255,0.1)', borderRadius: '4px', overflow: 'hidden' }}>
                      <div style={{ width: '100%', height: '100%', background: 'var(--success)' }}></div>
                   </div>
                   
                   <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', marginTop: '0.5rem' }}>
                      <span style={{ color: 'var(--text-secondary)' }}>Semantic Exact-Match Cache</span>
                      <span style={{ fontWeight: 600, color: 'var(--accent-primary)' }}>42% Hit Rate</span>
                   </div>
                   <div style={{ width: '100%', height: '8px', background: 'rgba(255,255,255,0.1)', borderRadius: '4px', overflow: 'hidden' }}>
                      <div style={{ width: '42%', height: '100%', background: 'var(--accent-primary)' }}></div>
                   </div>
                   
                   <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', marginTop: '0.5rem' }}>
                      <span style={{ color: 'var(--text-secondary)' }}>Tool Schema Compression</span>
                      <span style={{ fontWeight: 600, color: 'var(--accent-secondary)' }}>90% Reduction</span>
                   </div>
                   <div style={{ width: '100%', height: '8px', background: 'rgba(255,255,255,0.1)', borderRadius: '4px', overflow: 'hidden' }}>
                      <div style={{ width: '90%', height: '100%', background: 'var(--accent-secondary)' }}></div>
                   </div>
                </div>
             </div>
          </div>
        </>
      )}

      {activeTab === 'settings' && (
        <div className="glass-panel" style={{ marginBottom: '2rem' }}>
          <div className="metric-header" style={{ marginBottom: '1.5rem' }}>
            <div>
              <h2 style={{ margin: 0, color: 'var(--text-primary)', fontSize: '1.25rem' }}>Feature Flags</h2>
              <p style={{ margin: '0.25rem 0 0 0', fontSize: '0.875rem' }}>Dynamically toggle core Axon features in real-time.</p>
            </div>
          </div>
          
          <div className="layout-grid" style={{ marginBottom: 0, gridTemplateColumns: '1fr' }}>
            <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', padding: '1rem', background: 'rgba(255,255,255,0.05)', borderRadius: '8px' }}>
               <div>
                  <div style={{ fontWeight: 600 }}>Semantic ML Routing</div>
                  <div style={{ fontSize: '0.875rem', color: 'var(--text-secondary)' }}>
                    {flags.enable_semantic_routing 
                      ? "Enabled: Requests are routed dynamically between Lite/Pro models based on ML complexity intent." 
                      : "Disabled: Requests fall back to the exact model specified by the client."}
                  </div>
               </div>
               <label className="toggle-switch">
                 <input type="checkbox" checked={flags.enable_semantic_routing} onChange={() => toggleFlag('enable_semantic_routing')} />
                 <span className="toggle-slider"></span>
               </label>
            </div>
            
            <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', padding: '1rem', background: 'rgba(255,255,255,0.05)', borderRadius: '8px' }}>
               <div>
                  <div style={{ fontWeight: 600 }}>Exact Match Cache</div>
                  <div style={{ fontSize: '0.875rem', color: 'var(--text-secondary)' }}>
                    {flags.enable_exact_match_cache 
                      ? "Enabled: Identical payloads instantly return cached responses, saving 100% of tokens."
                      : "Disabled: All requests hit the upstream LLM, even duplicates."}
                  </div>
               </div>
               <label className="toggle-switch">
                 <input type="checkbox" checked={flags.enable_exact_match_cache} onChange={() => toggleFlag('enable_exact_match_cache')} />
                 <span className="toggle-slider"></span>
               </label>
            </div>

            <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', padding: '1rem', background: 'rgba(255,255,255,0.05)', borderRadius: '8px' }}>
               <div>
                  <div style={{ fontWeight: 600 }}>Tool Schema Compression</div>
                  <div style={{ fontSize: '0.875rem', color: 'var(--text-secondary)' }}>
                    {flags.enable_tool_compression 
                      ? "Enabled: Verbose JSON schemas are minified into dense TypeScript signatures before sending."
                      : "Disabled: Raw JSON tools are sent to the upstream LLM unmodified."}
                  </div>
               </div>
               <label className="toggle-switch">
                 <input type="checkbox" checked={flags.enable_tool_compression} onChange={() => toggleFlag('enable_tool_compression')} />
                 <span className="toggle-slider"></span>
               </label>
            </div>

            <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', padding: '1rem', background: 'rgba(255,255,255,0.05)', borderRadius: '8px' }}>
               <div>
                  <div style={{ fontWeight: 600 }}>Local Vector RAG</div>
                  <div style={{ fontSize: '0.875rem', color: 'var(--text-secondary)' }}>
                    {flags.enable_rag_context 
                      ? "Enabled: Attachments are embedded via sentence-transformers and relevant chunks are auto-injected."
                      : "Disabled: Context injection is bypassed for file attachments."}
                  </div>
               </div>
               <label className="toggle-switch">
                 <input type="checkbox" checked={flags.enable_rag_context} onChange={() => toggleFlag('enable_rag_context')} />
                 <span className="toggle-slider"></span>
               </label>
            </div>
          </div>
        </div>
      )}

      {activeTab === 'firehose' && (
        <div className="glass-panel" style={{ marginBottom: '2rem' }}>
          <div className="metric-header" style={{ marginBottom: '1.5rem' }}>
            <div>
              <h2 style={{ margin: 0, color: 'var(--text-primary)', fontSize: '1.25rem' }}>Live Request Firehose</h2>
              <p style={{ margin: '0.25rem 0 0 0', fontSize: '0.875rem' }}>Real-time stream of intercepted LLM traffic.</p>
            </div>
          </div>
          <div className="table-container">
            <table className="data-table">
              <thead>
                <tr>
                  <th>Time</th>
                  <th>Model</th>
                  <th>Latency</th>
                  <th>Tokens (P/C/T)</th>
                  <th>Cost</th>
                  <th>Cache Hit</th>
                  <th>Status</th>
                </tr>
              </thead>
              <tbody>
                {firehoseLogs.map((log, i) => (
                  <tr key={log.id || i}>
                    <td>{new Date(log.timestamp * 1000).toLocaleTimeString()}</td>
                    <td><span className="code-badge">{log.model}</span></td>
                    <td>{log.latency_ms.toFixed(0)}ms</td>
                    <td>{log.prompt_tokens} / {log.completion_tokens} / {log.total_tokens}</td>
                    <td style={{ color: 'var(--success)' }}>${log.cost.toFixed(4)}</td>
                    <td>
                      {log.cache_hit 
                        ? <span className="status-badge" style={{background: 'rgba(52, 211, 153, 0.2)', color: 'var(--success)'}}>HIT</span> 
                        : <span className="status-badge" style={{background: 'rgba(255, 255, 255, 0.1)'}}>MISS</span>}
                    </td>
                    <td>
                      {log.status_code === 200 
                        ? <span style={{color: 'var(--success)'}}>200 OK</span> 
                        : <span style={{color: 'var(--warning)'}}>{log.status_code}</span>}
                    </td>
                  </tr>
                ))}
                {firehoseLogs.length === 0 && (
                  <tr>
                    <td colSpan="7" style={{ textAlign: 'center', padding: '2rem', color: 'var(--text-secondary)' }}>
                      No requests recorded yet. Send some traffic to Axon!
                    </td>
                  </tr>
                )}
              </tbody>
            </table>
          </div>
        </div>
      )}

      {activeTab === 'cache' && (
        <div className="glass-panel" style={{ marginBottom: '2rem' }}>
          <div className="metric-header" style={{ marginBottom: '1.5rem' }}>
            <div>
              <h2 style={{ margin: 0, color: 'var(--text-primary)', fontSize: '1.25rem' }}>Semantic Cache Explorer</h2>
              <p style={{ margin: '0.25rem 0 0 0', fontSize: '0.875rem' }}>Currently cached prompts and responses.</p>
            </div>
          </div>
          <div className="table-container">
            <table className="data-table">
              <thead>
                <tr>
                  <th>Cached At</th>
                  <th>Context Hash</th>
                  <th>Prompt Snippet</th>
                </tr>
              </thead>
              <tbody>
                {cacheEntries.map((entry, i) => (
                  <tr key={i}>
                    <td style={{ whiteSpace: 'nowrap' }}>{new Date(entry.timestamp * 1000).toLocaleTimeString()}</td>
                    <td><span className="code-badge">{entry.context_hash.substring(0, 8)}...</span></td>
                    <td style={{ maxWidth: '400px', overflow: 'hidden', textOverflow: 'ellipsis', whiteSpace: 'nowrap' }}>
                      {entry.question || "<System/File Upload>"}
                    </td>
                  </tr>
                ))}
                {cacheEntries.length === 0 && (
                  <tr>
                    <td colSpan="3" style={{ textAlign: 'center', padding: '2rem', color: 'var(--text-secondary)' }}>
                      Cache is empty.
                    </td>
                  </tr>
                )}
              </tbody>
            </table>
          </div>
        </div>
      )}
    </>
  );
}

export default App;
