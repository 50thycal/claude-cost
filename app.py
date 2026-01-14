#!/usr/bin/env python3
"""
Claude Code Usage Monitor - A lightweight dashboard for tracking Claude Code usage and costs.
"""

import json
import os
from datetime import datetime, timedelta
from pathlib import Path
from collections import defaultdict
from flask import Flask, render_template_string, jsonify

app = Flask(__name__)

# Pricing per 1M tokens (Updated January 2025)
# Source: https://platform.claude.com/docs/en/about-claude/pricing
PRICING = {
    # Claude 4.5 Series (Latest - January 2025)
    "claude-opus-4-5-20250514": {
        "name": "Claude Opus 4.5",
        "input": 5.00,
        "output": 25.00,
        "cache_read": 0.50,  # 90% off input price
        "cache_creation": 6.25,  # 25% more than input
    },
    "claude-sonnet-4-5-20250514": {
        "name": "Claude Sonnet 4.5",
        "input": 3.00,
        "output": 15.00,
        "cache_read": 0.30,  # 90% off input price
        "cache_creation": 3.75,  # 25% more than input
    },
    # Claude 4 Series
    "claude-opus-4-20250514": {
        "name": "Claude Opus 4",
        "input": 15.00,
        "output": 75.00,
        "cache_read": 1.50,
        "cache_creation": 18.75,
    },
    "claude-sonnet-4-20250514": {
        "name": "Claude Sonnet 4",
        "input": 3.00,
        "output": 15.00,
        "cache_read": 0.30,
        "cache_creation": 3.75,
    },
    # Legacy model ID for Opus 4.5 (backwards compatibility)
    "claude-opus-4-5-20251101": {
        "name": "Claude Opus 4.5",
        "input": 5.00,
        "output": 25.00,
        "cache_read": 0.50,
        "cache_creation": 6.25,
    },
    # Claude 3.5 Series
    "claude-3-5-sonnet-20241022": {
        "name": "Claude 3.5 Sonnet",
        "input": 3.00,
        "output": 15.00,
        "cache_read": 0.30,
        "cache_creation": 3.75,
    },
    "claude-3-5-haiku-20241022": {
        "name": "Claude 3.5 Haiku",
        "input": 0.80,
        "output": 4.00,
        "cache_read": 0.08,
        "cache_creation": 1.00,
    },
    # Claude 3 Series (Legacy)
    "claude-3-haiku-20240307": {
        "name": "Claude 3 Haiku",
        "input": 0.25,
        "output": 1.25,
        "cache_read": 0.025,
        "cache_creation": 0.3125,
    },
    # Haiku 4.5 (Latest Haiku)
    "claude-haiku-4-5-20250514": {
        "name": "Claude Haiku 4.5",
        "input": 1.00,
        "output": 5.00,
        "cache_read": 0.10,
        "cache_creation": 1.25,
    },
}

# Default pricing for unknown models (use Sonnet pricing as fallback)
DEFAULT_PRICING = {
    "name": "Unknown Model",
    "input": 3.00,
    "output": 15.00,
    "cache_read": 0.30,
    "cache_creation": 3.75,
}


def get_claude_data_dir():
    """Find the Claude Code data directory."""
    home = Path.home()
    claude_dir = home / ".claude" / "projects"
    if claude_dir.exists():
        return claude_dir
    # Try root's home directory (for some system configurations)
    root_claude = Path("/root/.claude/projects")
    if root_claude.exists():
        return root_claude
    return None


def parse_jsonl_files(data_dir):
    """Parse all JSONL files and extract usage data."""
    usage_records = []

    if not data_dir or not data_dir.exists():
        return usage_records

    for project_dir in data_dir.iterdir():
        if not project_dir.is_dir():
            continue

        for jsonl_file in project_dir.glob("*.jsonl"):
            try:
                with open(jsonl_file, 'r') as f:
                    for line in f:
                        try:
                            record = json.loads(line.strip())
                            if record.get("type") == "assistant" and "message" in record:
                                msg = record["message"]
                                if "usage" in msg and "model" in msg:
                                    usage = msg["usage"]
                                    timestamp_str = record.get("timestamp", "")

                                    # Parse timestamp
                                    try:
                                        timestamp = datetime.fromisoformat(timestamp_str.replace('Z', '+00:00'))
                                    except:
                                        continue

                                    usage_records.append({
                                        "timestamp": timestamp,
                                        "model": msg["model"],
                                        "input_tokens": usage.get("input_tokens", 0),
                                        "output_tokens": usage.get("output_tokens", 0),
                                        "cache_read_tokens": usage.get("cache_read_input_tokens", 0),
                                        "cache_creation_tokens": usage.get("cache_creation_input_tokens", 0),
                                    })
                        except json.JSONDecodeError:
                            continue
            except Exception as e:
                print(f"Error reading {jsonl_file}: {e}")

    return usage_records


def calculate_cost(record):
    """Calculate cost for a single usage record."""
    model = record["model"]
    pricing = PRICING.get(model, DEFAULT_PRICING)

    input_cost = (record["input_tokens"] / 1_000_000) * pricing["input"]
    output_cost = (record["output_tokens"] / 1_000_000) * pricing["output"]
    cache_read_cost = (record["cache_read_tokens"] / 1_000_000) * pricing["cache_read"]
    cache_creation_cost = (record["cache_creation_tokens"] / 1_000_000) * pricing["cache_creation"]

    return input_cost + output_cost + cache_read_cost + cache_creation_cost


def aggregate_usage(records, start_time=None, end_time=None):
    """Aggregate usage data within a time range."""
    if start_time:
        records = [r for r in records if r["timestamp"] >= start_time]
    if end_time:
        records = [r for r in records if r["timestamp"] <= end_time]

    totals = {
        "input_tokens": 0,
        "output_tokens": 0,
        "cache_read_tokens": 0,
        "cache_creation_tokens": 0,
        "total_cost": 0,
        "by_model": defaultdict(lambda: {
            "input_tokens": 0,
            "output_tokens": 0,
            "cache_read_tokens": 0,
            "cache_creation_tokens": 0,
            "cost": 0,
            "requests": 0,
        }),
        "requests": 0,
    }

    for record in records:
        totals["input_tokens"] += record["input_tokens"]
        totals["output_tokens"] += record["output_tokens"]
        totals["cache_read_tokens"] += record["cache_read_tokens"]
        totals["cache_creation_tokens"] += record["cache_creation_tokens"]

        cost = calculate_cost(record)
        totals["total_cost"] += cost
        totals["requests"] += 1

        model_name = PRICING.get(record["model"], DEFAULT_PRICING)["name"]
        if model_name == "Unknown Model":
            model_name = record["model"]

        totals["by_model"][model_name]["input_tokens"] += record["input_tokens"]
        totals["by_model"][model_name]["output_tokens"] += record["output_tokens"]
        totals["by_model"][model_name]["cache_read_tokens"] += record["cache_read_tokens"]
        totals["by_model"][model_name]["cache_creation_tokens"] += record["cache_creation_tokens"]
        totals["by_model"][model_name]["cost"] += cost
        totals["by_model"][model_name]["requests"] += 1

    # Convert defaultdict to regular dict for JSON serialization
    totals["by_model"] = dict(totals["by_model"])

    return totals


def get_daily_breakdown(records, days=7):
    """Get daily breakdown for the last N days."""
    now = datetime.now(records[0]["timestamp"].tzinfo) if records else datetime.now()
    daily = []

    for i in range(days):
        day_start = (now - timedelta(days=i)).replace(hour=0, minute=0, second=0, microsecond=0)
        day_end = day_start + timedelta(days=1)

        day_records = [r for r in records if day_start <= r["timestamp"] < day_end]
        day_totals = aggregate_usage(day_records)

        daily.append({
            "date": day_start.strftime("%Y-%m-%d"),
            "day_name": day_start.strftime("%A"),
            **day_totals
        })

    return daily


def get_usage_data():
    """Get all usage data for the dashboard."""
    data_dir = get_claude_data_dir()
    records = parse_jsonl_files(data_dir)

    if not records:
        return {
            "error": "No usage data found",
            "data_dir": str(data_dir) if data_dir else "Not found",
        }

    # Sort records by timestamp
    records.sort(key=lambda x: x["timestamp"])

    now = datetime.now(records[0]["timestamp"].tzinfo)
    today_start = now.replace(hour=0, minute=0, second=0, microsecond=0)
    five_hours_ago = now - timedelta(hours=5)
    month_start = now.replace(day=1, hour=0, minute=0, second=0, microsecond=0)

    return {
        "today": aggregate_usage(records, start_time=today_start),
        "last_5_hours": aggregate_usage(records, start_time=five_hours_ago),
        "last_7_days": get_daily_breakdown(records, days=7),
        "monthly": aggregate_usage(records, start_time=month_start),
        "all_time": aggregate_usage(records),
        "last_updated": now.isoformat(),
        "data_dir": str(data_dir),
        "total_records": len(records),
    }


DASHBOARD_HTML = """
<!DOCTYPE html>
<html lang="en">
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <title>Claude Code Usage Monitor</title>
    <style>
        * {
            margin: 0;
            padding: 0;
            box-sizing: border-box;
        }

        body {
            font-family: -apple-system, BlinkMacSystemFont, 'Segoe UI', Roboto, Oxygen, Ubuntu, sans-serif;
            background: linear-gradient(135deg, #1a1a2e 0%, #16213e 100%);
            color: #e8e8e8;
            min-height: 100vh;
            padding: 20px;
        }

        .container {
            max-width: 1400px;
            margin: 0 auto;
        }

        header {
            display: flex;
            justify-content: space-between;
            align-items: center;
            margin-bottom: 30px;
            padding-bottom: 20px;
            border-bottom: 1px solid rgba(255,255,255,0.1);
        }

        h1 {
            font-size: 1.8rem;
            font-weight: 600;
            color: #fff;
        }

        .header-actions {
            display: flex;
            gap: 15px;
            align-items: center;
        }

        .refresh-btn {
            background: linear-gradient(135deg, #667eea 0%, #764ba2 100%);
            border: none;
            color: white;
            padding: 10px 20px;
            border-radius: 8px;
            cursor: pointer;
            font-size: 0.9rem;
            transition: transform 0.2s, box-shadow 0.2s;
        }

        .refresh-btn:hover {
            transform: translateY(-2px);
            box-shadow: 0 4px 15px rgba(102, 126, 234, 0.4);
        }

        .auto-refresh {
            display: flex;
            align-items: center;
            gap: 8px;
            font-size: 0.85rem;
            color: #888;
        }

        .last-updated {
            font-size: 0.85rem;
            color: #666;
        }

        .grid {
            display: grid;
            grid-template-columns: repeat(auto-fit, minmax(300px, 1fr));
            gap: 20px;
            margin-bottom: 30px;
        }

        .card {
            background: rgba(255, 255, 255, 0.05);
            border-radius: 16px;
            padding: 24px;
            backdrop-filter: blur(10px);
            border: 1px solid rgba(255, 255, 255, 0.1);
        }

        .card-header {
            display: flex;
            justify-content: space-between;
            align-items: center;
            margin-bottom: 20px;
        }

        .card-title {
            font-size: 0.9rem;
            text-transform: uppercase;
            letter-spacing: 1px;
            color: #888;
        }

        .card-icon {
            width: 40px;
            height: 40px;
            border-radius: 10px;
            display: flex;
            align-items: center;
            justify-content: center;
            font-size: 1.2rem;
        }

        .icon-today { background: linear-gradient(135deg, #f093fb 0%, #f5576c 100%); }
        .icon-5h { background: linear-gradient(135deg, #4facfe 0%, #00f2fe 100%); }
        .icon-month { background: linear-gradient(135deg, #43e97b 0%, #38f9d7 100%); }
        .icon-model { background: linear-gradient(135deg, #fa709a 0%, #fee140 100%); }

        .cost-value {
            font-size: 2.5rem;
            font-weight: 700;
            color: #fff;
            margin-bottom: 10px;
        }

        .token-breakdown {
            display: grid;
            grid-template-columns: 1fr 1fr;
            gap: 10px;
            margin-top: 15px;
            padding-top: 15px;
            border-top: 1px solid rgba(255,255,255,0.1);
        }

        .token-item {
            font-size: 0.8rem;
        }

        .token-label {
            color: #666;
            display: block;
        }

        .token-value {
            color: #fff;
            font-weight: 500;
        }

        .model-list {
            display: flex;
            flex-direction: column;
            gap: 12px;
        }

        .model-item {
            background: rgba(255,255,255,0.03);
            padding: 15px;
            border-radius: 10px;
        }

        .model-name {
            font-weight: 600;
            color: #fff;
            margin-bottom: 8px;
        }

        .model-stats {
            display: flex;
            justify-content: space-between;
            font-size: 0.85rem;
        }

        .model-cost {
            color: #4facfe;
            font-weight: 600;
        }

        .model-requests {
            color: #888;
        }

        .daily-chart {
            margin-top: 20px;
        }

        .daily-bar {
            display: flex;
            align-items: center;
            margin-bottom: 10px;
            gap: 10px;
        }

        .daily-label {
            width: 80px;
            font-size: 0.8rem;
            color: #888;
        }

        .daily-bar-container {
            flex: 1;
            height: 24px;
            background: rgba(255,255,255,0.05);
            border-radius: 4px;
            overflow: hidden;
        }

        .daily-bar-fill {
            height: 100%;
            background: linear-gradient(90deg, #667eea 0%, #764ba2 100%);
            border-radius: 4px;
            transition: width 0.5s ease;
        }

        .daily-value {
            width: 80px;
            text-align: right;
            font-size: 0.85rem;
            font-weight: 500;
        }

        .wide-card {
            grid-column: 1 / -1;
        }

        .error-message {
            background: rgba(255, 107, 107, 0.1);
            border: 1px solid rgba(255, 107, 107, 0.3);
            padding: 20px;
            border-radius: 10px;
            color: #ff6b6b;
        }

        .info-footer {
            margin-top: 30px;
            padding-top: 20px;
            border-top: 1px solid rgba(255,255,255,0.1);
            font-size: 0.8rem;
            color: #666;
            text-align: center;
        }

        @keyframes spin {
            from { transform: rotate(0deg); }
            to { transform: rotate(360deg); }
        }

        .loading .refresh-btn {
            pointer-events: none;
        }

        .loading .refresh-btn::after {
            content: '';
            display: inline-block;
            width: 12px;
            height: 12px;
            border: 2px solid #fff;
            border-top-color: transparent;
            border-radius: 50%;
            animation: spin 0.8s linear infinite;
            margin-left: 8px;
        }
    </style>
</head>
<body>
    <div class="container">
        <header>
            <h1>Claude Code Usage Monitor</h1>
            <div class="header-actions">
                <label class="auto-refresh">
                    <input type="checkbox" id="autoRefresh" checked>
                    Auto-refresh (2 min)
                </label>
                <button class="refresh-btn" onclick="refreshData()">Refresh</button>
                <span class="last-updated" id="lastUpdated"></span>
            </div>
        </header>

        <div id="dashboard">
            <div class="grid">
                <div class="card" id="todayCard">
                    <div class="card-header">
                        <span class="card-title">Today's Usage</span>
                        <div class="card-icon icon-today">&#x1F4C5;</div>
                    </div>
                    <div class="cost-value" id="todayCost">$0.00</div>
                    <div class="token-breakdown" id="todayTokens"></div>
                </div>

                <div class="card" id="fiveHourCard">
                    <div class="card-header">
                        <span class="card-title">Last 5 Hours</span>
                        <div class="card-icon icon-5h">&#x23F1;</div>
                    </div>
                    <div class="cost-value" id="fiveHourCost">$0.00</div>
                    <div class="token-breakdown" id="fiveHourTokens"></div>
                </div>

                <div class="card" id="monthCard">
                    <div class="card-header">
                        <span class="card-title">This Month</span>
                        <div class="card-icon icon-month">&#x1F4C8;</div>
                    </div>
                    <div class="cost-value" id="monthCost">$0.00</div>
                    <div class="token-breakdown" id="monthTokens"></div>
                </div>
            </div>

            <div class="grid">
                <div class="card">
                    <div class="card-header">
                        <span class="card-title">Last 7 Days</span>
                    </div>
                    <div class="daily-chart" id="dailyChart"></div>
                </div>

                <div class="card">
                    <div class="card-header">
                        <span class="card-title">Usage by Model</span>
                        <div class="card-icon icon-model">&#x1F916;</div>
                    </div>
                    <div class="model-list" id="modelList"></div>
                </div>
            </div>
        </div>

        <div class="info-footer">
            <p>Data source: <span id="dataDir">~/.claude/projects/</span> | Total records: <span id="totalRecords">0</span></p>
        </div>
    </div>

    <script>
        let autoRefreshInterval = null;

        function formatCost(cost) {
            return '$' + cost.toFixed(4);
        }

        function formatTokens(tokens) {
            if (tokens >= 1000000) {
                return (tokens / 1000000).toFixed(2) + 'M';
            } else if (tokens >= 1000) {
                return (tokens / 1000).toFixed(1) + 'K';
            }
            return tokens.toString();
        }

        function renderTokenBreakdown(containerId, data) {
            const container = document.getElementById(containerId);
            container.innerHTML = `
                <div class="token-item">
                    <span class="token-label">Input</span>
                    <span class="token-value">${formatTokens(data.input_tokens)}</span>
                </div>
                <div class="token-item">
                    <span class="token-label">Output</span>
                    <span class="token-value">${formatTokens(data.output_tokens)}</span>
                </div>
                <div class="token-item">
                    <span class="token-label">Cache Read</span>
                    <span class="token-value">${formatTokens(data.cache_read_tokens)}</span>
                </div>
                <div class="token-item">
                    <span class="token-label">Cache Create</span>
                    <span class="token-value">${formatTokens(data.cache_creation_tokens)}</span>
                </div>
            `;
        }

        function renderDailyChart(data) {
            const container = document.getElementById('dailyChart');
            const maxCost = Math.max(...data.map(d => d.total_cost), 0.01);

            container.innerHTML = data.map(day => {
                const percentage = (day.total_cost / maxCost) * 100;
                return `
                    <div class="daily-bar">
                        <span class="daily-label">${day.day_name.slice(0, 3)}</span>
                        <div class="daily-bar-container">
                            <div class="daily-bar-fill" style="width: ${percentage}%"></div>
                        </div>
                        <span class="daily-value">${formatCost(day.total_cost)}</span>
                    </div>
                `;
            }).join('');
        }

        function renderModelList(models) {
            const container = document.getElementById('modelList');
            const modelEntries = Object.entries(models).sort((a, b) => b[1].cost - a[1].cost);

            if (modelEntries.length === 0) {
                container.innerHTML = '<p style="color: #666;">No model data available</p>';
                return;
            }

            container.innerHTML = modelEntries.map(([name, data]) => `
                <div class="model-item">
                    <div class="model-name">${name}</div>
                    <div class="model-stats">
                        <span class="model-cost">${formatCost(data.cost)}</span>
                        <span class="model-requests">${data.requests} requests | ${formatTokens(data.input_tokens + data.output_tokens)} tokens</span>
                    </div>
                </div>
            `).join('');
        }

        async function refreshData() {
            document.body.classList.add('loading');

            try {
                const response = await fetch('/api/usage');
                const data = await response.json();

                if (data.error) {
                    document.getElementById('dashboard').innerHTML = `
                        <div class="error-message">
                            <strong>Error:</strong> ${data.error}<br>
                            <small>Data directory: ${data.data_dir || 'Not found'}</small>
                        </div>
                    `;
                    return;
                }

                // Update today's usage
                document.getElementById('todayCost').textContent = formatCost(data.today.total_cost);
                renderTokenBreakdown('todayTokens', data.today);

                // Update 5-hour usage
                document.getElementById('fiveHourCost').textContent = formatCost(data.last_5_hours.total_cost);
                renderTokenBreakdown('fiveHourTokens', data.last_5_hours);

                // Update monthly usage
                document.getElementById('monthCost').textContent = formatCost(data.monthly.total_cost);
                renderTokenBreakdown('monthTokens', data.monthly);

                // Update daily chart
                renderDailyChart(data.last_7_days);

                // Update model breakdown (using all-time data for better representation)
                renderModelList(data.all_time.by_model);

                // Update footer info
                document.getElementById('dataDir').textContent = data.data_dir;
                document.getElementById('totalRecords').textContent = data.total_records;
                document.getElementById('lastUpdated').textContent = 'Updated: ' + new Date().toLocaleTimeString();

            } catch (error) {
                console.error('Error fetching data:', error);
            } finally {
                document.body.classList.remove('loading');
            }
        }

        function toggleAutoRefresh() {
            const checkbox = document.getElementById('autoRefresh');

            if (checkbox.checked) {
                autoRefreshInterval = setInterval(refreshData, 120000); // 2 minutes
            } else {
                clearInterval(autoRefreshInterval);
                autoRefreshInterval = null;
            }
        }

        // Initialize
        document.getElementById('autoRefresh').addEventListener('change', toggleAutoRefresh);
        refreshData();
        toggleAutoRefresh();
    </script>
</body>
</html>
"""


@app.route('/')
def dashboard():
    return render_template_string(DASHBOARD_HTML)


@app.route('/api/usage')
def api_usage():
    return jsonify(get_usage_data())


if __name__ == '__main__':
    print("Starting Claude Code Usage Monitor...")
    print("Dashboard available at: http://localhost:5000")
    app.run(host='0.0.0.0', port=5000, debug=True)
