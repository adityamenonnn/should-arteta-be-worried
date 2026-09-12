async function fetchJSON(url) {
    const resp = await fetch(url);
    return resp.json();
}

function worryColor(score) {
    if (score < 35) return "#22c55e";
    if (score < 50) return "#eab308";
    if (score < 65) return "#f97316";
    return "#ef4444";
}

function sentimentClass(val) {
    if (val > 0.05) return "positive";
    if (val < -0.05) return "negative";
    return "neutral";
}

function sentimentLabel(val) {
    if (val > 0.05) return "+" + val.toFixed(2);
    return val.toFixed(2);
}

function verdict(score) {
    if (score < 25) return "Not at all. The fanbase is buzzing.";
    if (score < 40) return "Nah. Vibes are good right now.";
    if (score < 55) return "A little. Fans have mixed feelings.";
    if (score < 70) return "Yeah. The fanbase is getting restless.";
    if (score < 85) return "Absolutely. Things are heating up.";
    return "Full meltdown. r/Gunners is on fire.";
}

function timeAgo(utc) {
    const diff = Math.floor(Date.now() / 1000) - utc;
    if (diff < 3600) return Math.floor(diff / 60) + "m";
    if (diff < 86400) return Math.floor(diff / 3600) + "h";
    return Math.floor(diff / 86400) + "d";
}

function escapeHtml(text) {
    const div = document.createElement("div");
    div.textContent = text;
    return div.innerHTML;
}

// --- Hero ring ---
function loadHero(indexData) {
    const latest = indexData[indexData.length - 1];
    if (!latest) return;

    const score = Math.round(latest.worry_score);
    const color = worryColor(score);

    document.getElementById("worry-number").textContent = score;
    document.getElementById("worry-number").style.color = color;
    document.getElementById("worry-verdict").textContent = verdict(score);

    // Animate ring
    const ring = document.getElementById("ring-fill");
    const circumference = 534; // 2 * PI * 85
    const offset = circumference - (score / 100) * circumference;
    ring.style.stroke = color;
    ring.style.strokeDashoffset = offset;
}

// --- Trend chart ---
function loadChart(indexData, matchData) {
    const ctx = document.getElementById("trend-chart").getContext("2d");

    const labels = indexData.map(d => d.date);
    const scores = indexData.map(d => d.worry_score);

    if (labels.length > 1) {
        document.getElementById("trend-range").textContent =
            labels[0] + " to " + labels[labels.length - 1];
    }

    const matchAnnotations = matchData
        .filter(m => labels.includes(m.date))
        .map(m => {
            const result = m.arsenal_goals > m.opponent_goals ? "W"
                : m.arsenal_goals < m.opponent_goals ? "L" : "D";
            const color = result === "W" ? "#22c55e" : result === "L" ? "#ef4444" : "#eab308";
            return { date: m.date, label: result + " vs " + m.opponent, color };
        });

    const matchPoints = matchAnnotations.map(m => ({
        x: m.date,
        y: scores[labels.indexOf(m.date)],
    }));

    new Chart(ctx, {
        type: "line",
        data: {
            labels,
            datasets: [
                {
                    label: "Worry Index",
                    data: scores,
                    borderColor: "#ef0107",
                    borderWidth: 2,
                    backgroundColor: (ctx) => {
                        const gradient = ctx.chart.ctx.createLinearGradient(0, 0, 0, 280);
                        gradient.addColorStop(0, "rgba(239, 1, 7, 0.15)");
                        gradient.addColorStop(1, "rgba(239, 1, 7, 0)");
                        return gradient;
                    },
                    fill: true,
                    tension: 0.35,
                    pointRadius: 4,
                    pointBackgroundColor: scores.map(s => worryColor(s)),
                    pointBorderColor: "transparent",
                },
                {
                    label: "Match Days",
                    data: matchPoints,
                    type: "scatter",
                    pointRadius: 7,
                    pointStyle: "rectRot",
                    pointBackgroundColor: matchAnnotations.map(m => m.color),
                    showLine: false,
                },
            ],
        },
        options: {
            responsive: true,
            maintainAspectRatio: false,
            interaction: { intersect: false, mode: "index" },
            scales: {
                y: {
                    min: 0, max: 100,
                    grid: { color: "#111114" },
                    ticks: { color: "#333", font: { size: 11 } },
                    border: { color: "transparent" },
                },
                x: {
                    grid: { display: false },
                    ticks: { color: "#333", font: { size: 10 }, maxRotation: 45 },
                    border: { color: "transparent" },
                },
            },
            plugins: {
                legend: { display: false },
                tooltip: {
                    backgroundColor: "#1a1a1e",
                    titleColor: "#888",
                    bodyColor: "#ddd",
                    borderColor: "#333",
                    borderWidth: 1,
                    cornerRadius: 8,
                    padding: 10,
                    callbacks: {
                        label(ctx) {
                            if (ctx.datasetIndex === 1) {
                                const m = matchAnnotations[ctx.dataIndex];
                                return m ? m.label : "";
                            }
                            return "Worry: " + ctx.parsed.y.toFixed(1);
                        },
                    },
                },
            },
        },
    });
}

// --- Topics ---
async function loadTopics() {
    const data = await fetchJSON("/api/topics");
    const container = document.getElementById("topics-grid");
    container.innerHTML = "";

    for (const [name, info] of Object.entries(data)) {
        const score = Math.round(info.worry_score);
        const div = document.createElement("div");
        div.className = "topic-card";
        div.innerHTML = `
            <div class="topic-name">${name}</div>
            <div class="topic-score" style="color: ${worryColor(score)}">${score}</div>
            <div class="topic-posts">${info.post_count} posts</div>
        `;
        container.appendChild(div);
    }
}

// --- Matches ---
function loadMatches(matchData) {
    const container = document.getElementById("match-list");
    container.innerHTML = "";

    const recent = matchData.slice(-10);
    for (const m of recent) {
        const result = m.arsenal_goals > m.opponent_goals ? "win"
            : m.arsenal_goals < m.opponent_goals ? "loss" : "draw";
        const div = document.createElement("div");
        div.className = "match-chip";
        div.innerHTML = `
            <span class="match-opponent">${escapeHtml(m.opponent)}</span>
            <span class="match-result ${result}">${m.arsenal_goals}-${m.opponent_goals}</span>
            <span class="match-date">${m.date}</span>
        `;
        container.appendChild(div);
    }

    if (recent.length === 0) {
        container.innerHTML = '<span class="loading-text">No match data yet</span>';
    }
}

// --- Posts ---
async function loadPosts() {
    const posts = await fetchJSON("/api/posts?limit=80");
    const list = document.getElementById("post-list");
    list.innerHTML = "";

    document.getElementById("post-count").textContent = posts.length + " posts";

    for (const p of posts) {
        const cls = sentimentClass(p.sentiment);
        const li = document.createElement("li");
        li.className = "post-item";

        const url = p.url || `https://www.reddit.com/r/Gunners/comments/${p.id}/`;

        li.innerHTML = `
            <span class="post-dot ${cls}"></span>
            <a class="post-link" href="${escapeHtml(url)}" target="_blank" rel="noopener">${escapeHtml(p.title)}</a>
            <div class="post-meta">
                <span class="post-time">${timeAgo(p.created_utc)}</span>
                <span class="post-score-badge ${cls}">${sentimentLabel(p.sentiment)}</span>
            </div>
        `;
        list.appendChild(li);
    }
}

// --- Init ---
async function init() {
    const [indexData, matchData] = await Promise.all([
        fetchJSON("/api/index?days=60"),
        fetchJSON("/api/matches?limit=20"),
    ]);

    loadHero(indexData);
    loadChart(indexData, matchData);
    loadMatches(matchData);
    loadTopics();
    loadPosts();
}

init();
