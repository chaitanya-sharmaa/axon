from fastapi import APIRouter
from fastapi.responses import HTMLResponse

router = APIRouter(tags=["dashboard"])

DASHBOARD_HTML = """
<!DOCTYPE html>
<html>
<head>
    <title>Axon Bridge Dashboard</title>
    <script src="https://cdn.jsdelivr.net/npm/chart.js"></script>
    <style>
        body { font-family: 'Inter', sans-serif; background-color: #0f172a; color: #f8fafc; margin: 0; padding: 20px; }
        .container { max-width: 1200px; margin: 0 auto; }
        .header { display: flex; justify-content: space-between; align-items: center; border-bottom: 1px solid #334155; padding-bottom: 20px; margin-bottom: 30px; }
        h1 { margin: 0; font-size: 24px; color: #38bdf8; }
        .grid { display: grid; grid-template-columns: repeat(auto-fit, minmax(300px, 1fr)); gap: 20px; }
        .card { background-color: #1e293b; padding: 20px; border-radius: 8px; box-shadow: 0 4px 6px -1px rgba(0, 0, 0, 0.1); }
        .stat-value { font-size: 36px; font-weight: bold; margin: 10px 0; color: #10b981; }
        .stat-label { font-size: 14px; color: #94a3b8; text-transform: uppercase; letter-spacing: 0.05em; }
    </style>
</head>
<body>
    <div class="container">
        <div class="header">
            <h1>⚡ Axon Bridge Dashboard</h1>
            <div id="status" style="color: #10b981;">● Online</div>
        </div>
        
        <div class="grid">
            <div class="card">
                <div class="stat-label">Total Tokens Saved</div>
                <div class="stat-value" id="tokens-saved">0</div>
            </div>
            <div class="card">
                <div class="stat-label">Est. Cost Saved</div>
                <div class="stat-value" id="cost-saved">$0.00</div>
            </div>
        </div>
        
        <div class="card" style="margin-top: 20px;">
            <canvas id="savingsChart" height="100"></canvas>
        </div>
    </div>

    <script>
        // Simple polling to /metrics to parse Prometheus data
        let chart;
        const history = [];
        
        async function fetchMetrics() {
            try {
                const res = await fetch('/metrics');
                const text = await res.text();
                
                // Parse prometheus output roughly
                let tokensSaved = 0;
                const lines = text.split('\\n');
                for (const line of lines) {
                    if (line.startsWith('axon_tokens_saved_total')) {
                        tokensSaved = parseInt(line.split(' ')[1]);
                    }
                }
                
                document.getElementById('tokens-saved').innerText = tokensSaved.toLocaleString();
                // Rough estimation of savings: $1.50 per 1M tokens
                const costSaved = (tokensSaved / 1000000) * 1.5;
                document.getElementById('cost-saved').innerText = '$' + costSaved.toFixed(4);
                
                // Update chart
                const time = new Date().toLocaleTimeString();
                history.push({x: time, y: tokensSaved});
                if (history.length > 20) history.shift();
                
                if (!chart) {
                    const ctx = document.getElementById('savingsChart').getContext('2d');
                    chart = new Chart(ctx, {
                        type: 'line',
                        data: {
                            labels: history.map(d => d.x),
                            datasets: [{
                                label: 'Tokens Saved',
                                data: history.map(d => d.y),
                                borderColor: '#38bdf8',
                                tension: 0.4,
                                fill: false
                            }]
                        },
                        options: {
                            animation: false,
                            scales: {
                                y: { beginAtZero: true, grid: { color: '#334155' } },
                                x: { grid: { display: false } }
                            }
                        }
                    });
                } else {
                    chart.data.labels = history.map(d => d.x);
                    chart.data.datasets[0].data = history.map(d => d.y);
                    chart.update();
                }
                
            } catch(e) {
                console.error(e);
                document.getElementById('status').innerText = '● Offline';
                document.getElementById('status').style.color = '#ef4444';
            }
        }
        
        setInterval(fetchMetrics, 2000);
        fetchMetrics();
    </script>
</body>
</html>
"""

@router.get("/dashboard")
async def get_dashboard():
    """Serve the real-time Axon metrics dashboard."""
    return HTMLResponse(content=DASHBOARD_HTML)
