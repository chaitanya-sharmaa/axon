import React, { useMemo } from 'react';
import ReactECharts from 'echarts-for-react';
import { assembleECharts } from 'flint-chart';

/**
 * FlintViewer
 * 
 * Takes a Flint ChartAssemblyInput and renders it using ECharts.
 * 
 * @param {Object} props.spec - The Flint ChartAssemblyInput
 * @param {string} props.height - Optional height override
 * @param {string} props.width - Optional width override
 */
export default function FlintViewer({ spec, height = "400px", width = "100%" }) {
  const echartsOption = useMemo(() => {
    try {
      if (!spec || !spec.data) return null;
      return assembleECharts(spec);
    } catch (error) {
      console.error("Flint compilation error:", error);
      return null;
    }
  }, [spec]);

  if (!echartsOption) {
    return (
      <div className="flex items-center justify-center bg-zinc-900 border border-zinc-800 rounded-lg text-zinc-500" style={{ height, width }}>
        Invalid or missing chart spec
      </div>
    );
  }

  // Override some base styles to make charts much more intuitive and beautiful
  const isPie = echartsOption.series?.some(s => s.type === 'pie' || s.type === 'donut');
  
  const mergedOptions = {
    ...echartsOption,
    backgroundColor: 'transparent',
    tooltip: {
      trigger: isPie ? 'item' : 'axis',
      backgroundColor: 'rgba(24, 24, 27, 0.95)',
      borderColor: 'rgba(63, 63, 70, 0.5)',
      padding: [8, 12],
      textStyle: { color: '#e4e4e7', fontFamily: 'Inter, sans-serif', fontSize: 13 },
      axisPointer: { type: 'cross', label: { backgroundColor: '#6366f1' } },
      ...echartsOption.tooltip
    },
    grid: {
      top: 30, right: 30, bottom: 20, left: 20, containLabel: true,
      ...echartsOption.grid
    },
    textStyle: {
      ...echartsOption.textStyle,
      fontFamily: 'Inter, sans-serif'
    }
  };

  // Enhance series with smooth lines, better bar radiuses, and gradients
  if (mergedOptions.series) {
    mergedOptions.series = mergedOptions.series.map(s => {
      const newS = { ...s };
      if (newS.type === 'line') {
        newS.smooth = true;
        newS.showSymbol = false; // Hide dots unless hovering
        newS.lineStyle = { width: 3 };
      }
      if (newS.type === 'bar') {
        // Add rounded corners to bars depending on orientation
        const isHorizontal = mergedOptions.xAxis?.type === 'value' || (Array.isArray(mergedOptions.xAxis) && mergedOptions.xAxis[0]?.type === 'value');
        newS.itemStyle = { ...newS.itemStyle, borderRadius: isHorizontal ? [0, 4, 4, 0] : [4, 4, 0, 0] };
      }
      if (newS.type === 'pie') {
        // Make pie charts look more like donuts with nice spacing
        newS.radius = ['50%', '80%'];
        newS.itemStyle = { ...newS.itemStyle, borderRadius: 5, borderColor: '#18181b', borderWidth: 2 };
        newS.label = { show: true, formatter: '{b}\n{d}%', color: '#a1a1aa' };
        newS.labelLine = { smooth: true, lineStyle: { color: 'rgba(255,255,255,0.2)' } };
      }
      return newS;
    });
  }

  // Clean up axes for a cleaner dark mode look
  ['xAxis', 'yAxis'].forEach(axis => {
    if (mergedOptions[axis]) {
      const axList = Array.isArray(mergedOptions[axis]) ? mergedOptions[axis] : [mergedOptions[axis]];
      axList.forEach(a => {
        if (!a.splitLine) a.splitLine = {};
        a.splitLine.lineStyle = { color: 'rgba(255,255,255,0.05)', type: 'dashed' };
        if (!a.axisLine) a.axisLine = {};
        a.axisLine.lineStyle = { color: 'rgba(255,255,255,0.1)' };
        if (!a.axisLabel) a.axisLabel = {};
        a.axisLabel.color = '#a1a1aa';
      });
    }
  });

  return (
    <div className="flint-viewer w-full rounded-lg overflow-hidden border border-zinc-800/50 bg-zinc-900/50 p-2" style={{ height, width }}>
      <ReactECharts 
        option={mergedOptions} 
        style={{ height: '100%', width: '100%' }}
        opts={{ renderer: 'canvas' }}
        theme="dark" // Provide dark theme hint to ECharts
        notMerge={true}
        lazyUpdate={true}
      />
    </div>
  );
}
