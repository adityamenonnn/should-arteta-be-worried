const F = url => fetch(url).then(r => r.json());

function wc(s) { return s < 35 ? "#16a34a" : s < 55 ? "#ca8a04" : "#dc2626"; }

function verdict(s) {
    if (s < 25) return "nah, vibes are good";
    if (s < 40) return "not really";
    if (s < 55) return "a little bit yeah";
    if (s < 70) return "yeah fans are not happy";
    if (s < 85) return "absolutely";
    return "full meltdown";
}

function ago(utc) {
    const d = Math.floor(Date.now() / 1000) - utc;
    if (d < 3600) return Math.floor(d / 60) + "m";
    if (d < 86400) return Math.floor(d / 3600) + "h";
    return Math.floor(d / 86400) + "d";
}

const chartOpts = {
    responsive: true,
    maintainAspectRatio: false,
    plugins: {
        legend: { display: false },
        tooltip: { cornerRadius: 2, padding: 6 },
    },
    scales: {
        y: { min: 0, max: 100, grid: { color: "#f5f5f5" }, border: { display: false } },
        x: { grid: { display: false }, ticks: { font: { size: 9 }, maxRotation: 45 }, border: { display: false } },
    },
};

async function init() {
    const [idx, matches] = await Promise.all([
        F("/api/index?days=60"),
        F("/api/matches?limit=20"),
    ]);

    // worry number
    const latest = idx[idx.length - 1];
    if (latest) {
        const s = Math.round(latest.worry_score);
        const el = document.getElementById("worry-number");
        el.textContent = s;
        el.style.color = wc(s);
        document.getElementById("worry-verdict").textContent = verdict(s);
    }

    // trend chart
    const labels = idx.map(d => d.date);
    const scores = idx.map(d => d.worry_score);

    const mp = matches.filter(m => labels.includes(m.date)).map(m => ({
        x: m.date,
        y: scores[labels.indexOf(m.date)],
        c: m.arsenal_goals > m.opponent_goals ? "#16a34a" : m.arsenal_goals < m.opponent_goals ? "#dc2626" : "#ca8a04",
    }));

    new Chart(document.getElementById("trend-chart"), {
        type: "line",
        data: {
            labels,
            datasets: [
                { data: scores, borderColor: "#c1272d", borderWidth: 1.5, fill: false, tension: 0.3, pointRadius: 1.5 },
                { data: mp.map(m => ({x:m.x,y:m.y})), type: "scatter", pointRadius: 4, pointStyle: "rectRot", pointBackgroundColor: mp.map(m=>m.c), showLine: false },
            ],
        },
        options: chartOpts,
    });

    // matches
    const ml = document.getElementById("match-list");
    matches.slice(-10).forEach(m => {
        const r = m.arsenal_goals > m.opponent_goals ? "w" : m.arsenal_goals < m.opponent_goals ? "l" : "d";
        ml.innerHTML += `<span class="match">${m.opponent} <span class="${r}">${m.arsenal_goals}-${m.opponent_goals}</span></span>`;
    });

    // topics
    const topics = await F("/api/topics");
    const tl = document.getElementById("topic-list");
    for (const [name, info] of Object.entries(topics)) {
        const s = Math.round(info.worry_score);
        tl.innerHTML += `<div class="topic-row"><span>${name}</span><span style="color:${wc(s)};font-weight:600">${s}</span></div>`;
    }

    // posts
    const posts = await F("/api/posts?limit=50");
    document.getElementById("post-count").textContent = `(${posts.length})`;
    const pl = document.getElementById("post-list");
    posts.forEach(p => {
        const cls = p.sentiment > 0.05 ? "pos" : p.sentiment < -0.05 ? "neg" : "neu";
        const rid = p.id.startsWith("t3_") ? p.id.slice(3) : p.id;
        const url = p.url || `https://www.reddit.com/r/Gunners/comments/${rid}/`;
        pl.innerHTML += `<div class="post">
            <span class="dot ${cls}"></span>
            <a href="${url}" target="_blank">${p.title}</a>
            <span class="score ${cls}">${p.sentiment > 0 ? "+" : ""}${p.sentiment.toFixed(2)}</span>
            <span class="time">${ago(p.created_utc)}</span>
        </div>`;
    });

    // forecast
    try {
        const fc = await F("/api/forecast?days=7");
        if (fc.forecast && fc.forecast.length) {
            document.getElementById("forecast-info").textContent =
                `ridge regression, r²=${fc.r_squared}, trained on ${fc.train_size + fc.test_size} days`;

            const recent = idx.slice(-14);
            const rl = recent.map(d => d.date);
            const rs = recent.map(d => d.worry_score);
            const fl = fc.forecast.map(f => "+" + f.day_offset + "d");
            const fs = fc.forecast.map(f => f.predicted_worry);

            new Chart(document.getElementById("forecast-chart"), {
                type: "line",
                data: {
                    labels: [...rl, ...fl],
                    datasets: [
                        { label: "actual", data: [...rs, ...Array(fl.length).fill(null)], borderColor: "#c1272d", borderWidth: 1.5, fill: false, tension: 0.3, pointRadius: 1.5 },
                        { label: "predicted", data: [...Array(rl.length-1).fill(null), rs[rs.length-1], ...fs], borderColor: "#999", borderWidth: 1.5, borderDash: [4,3], fill: false, tension: 0.3, pointRadius: 3, pointBackgroundColor: "#999" },
                    ],
                },
                options: {...chartOpts, plugins: { legend: { labels: { font: { size: 10 } } }, tooltip: { cornerRadius: 2, padding: 6 } }},
            });

            if (fc.top_features) {
                document.getElementById("forecast-features").textContent =
                    "top features: " + fc.top_features.map(f => f.name + " (" + f.importance + ")").join(", ");
            }
        }
    } catch(e) {}

    // model info
    try {
        const mi = await F("/api/model-info");
        document.getElementById("footer").textContent =
            `sentiment: ${mi.model}${mi.model_f1 ? " (f1=" + mi.model_f1 + ")" : ""} · data from r/Gunners · not affiliated with Arsenal FC`;
    } catch(e) {}
}

init();
