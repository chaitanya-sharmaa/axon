import React, { useState, useEffect } from 'react';
import { Bot, Sparkles, Filter, Activity } from 'lucide-react';
import FlintViewer from '../components/FlintViewer';

// Example semantic dataset for Agent token savings
const TOKEN_SAVINGS_DATA = [
  { date: '2026-06-23', type: 'Semantic Cache', tokens: 150000 },
  { date: '2026-06-23', type: 'Context Pruning', tokens: 80000 },
  { date: '2026-06-23', type: 'Tool Compression', tokens: 120000 },
  { date: '2026-06-24', type: 'Semantic Cache', tokens: 180000 },
  { date: '2026-06-24', type: 'Context Pruning', tokens: 95000 },
  { date: '2026-06-24', type: 'Tool Compression', tokens: 145000 },
  { date: '2026-06-25', type: 'Semantic Cache', tokens: 165000 },
  { date: '2026-06-25', type: 'Context Pruning', tokens: 110000 },
  { date: '2026-06-25', type: 'Tool Compression', tokens: 130000 },
  { date: '2026-06-26', type: 'Semantic Cache', tokens: 210000 },
  { date: '2026-06-26', type: 'Context Pruning', tokens: 125000 },
  { date: '2026-06-26', type: 'Tool Compression', tokens: 160000 },
  { date: '2026-06-27', type: 'Semantic Cache', tokens: 235000 },
  { date: '2026-06-27', type: 'Context Pruning', tokens: 140000 },
  { date: '2026-06-27', type: 'Tool Compression', tokens: 175000 },
];

const LATENCY_DATA = [
  { endpoint: '/v1/chat/completions', provider: 'OpenAI', ms: 1200 },
  { endpoint: '/v1/chat/completions', provider: 'Anthropic', ms: 1800 },
  { endpoint: '/v1/chat/completions', provider: 'Google', ms: 1100 },
  { endpoint: '/v1/embeddings', provider: 'OpenAI', ms: 300 },
  { endpoint: '/v1/embeddings', provider: 'Google', ms: 250 },
  { endpoint: '/v1/assistants', provider: 'OpenAI', ms: 2100 },
];

// Define Flint specs for the charts
const savingsSpec = {
  data: { values: TOKEN_SAVINGS_DATA },
  semantic_types: { date: 'Date', type: 'Category', tokens: 'Quantity' },
  chart_spec: {
    chartType: 'Stacked Bar Chart', 
    encodings: {
      x: { field: 'date' },
      y: { field: 'tokens' },
      color: { field: 'type' }
    },
    baseSize: { width: 600, height: 350 },
  }
};

const latencySpec = {
  data: { values: LATENCY_DATA },
  semantic_types: { endpoint: 'Category', provider: 'Category', ms: 'Duration' },
  chart_spec: {
    chartType: 'Grouped Bar Chart',
    encodings: {
      x: { field: 'endpoint' },
      y: { field: 'ms' },
      color: { field: 'provider' }
    },
    baseSize: { width: 600, height: 350 },
  }
};

export default function AgenticAnalytics() {
  return (
    <>
      <div style={{ marginBottom: '2rem' }}>
        <h2 style={{ fontSize: '1.5rem', fontWeight: 600, display: 'flex', alignItems: 'center', gap: '0.5rem', marginBottom: '0.5rem' }}>
          <Sparkles size={24} color="var(--accent-primary)" /> Agentic Insights
        </h2>
        <p style={{ color: 'var(--text-secondary)' }}>
          Advanced LLM telemetry and optimization metrics powered by Flint Chart.
        </p>
      </div>

      <div className="layout-grid" style={{ gridTemplateColumns: '1fr 1fr' }}>
        
        {/* Token Savings Chart */}
        <div className="glass-panel">
          <div className="section-header">
            <div>
              <h2 className="section-title">Token Reductions</h2>
              <p className="section-sub">Tokens saved per optimization technique over time</p>
            </div>
          </div>
          <div className="chart-container" style={{ height: '350px' }}>
            <FlintViewer spec={savingsSpec} height="350px" />
          </div>
        </div>

        {/* Latency Distribution Chart */}
        <div className="glass-panel">
          <div className="section-header">
            <div>
              <h2 className="section-title">Provider Latency</h2>
              <p className="section-sub">Average latency (ms) across different endpoints</p>
            </div>
          </div>
          <div className="chart-container" style={{ height: '350px' }}>
            <FlintViewer spec={latencySpec} height="350px" />
          </div>
        </div>

      </div>
    </>
  );
}
