const FORMATION = {
    GK:  { x: 50, y: 92 },
    RB:  { x: 82, y: 75 },
    RCB: { x: 62, y: 78 },
    LCB: { x: 38, y: 78 },
    LB:  { x: 18, y: 75 },
    CDM: { x: 50, y: 60 },
    RCM: { x: 70, y: 48 },
    LCM: { x: 30, y: 48 },
    RW:  { x: 82, y: 28 },
    ST:  { x: 50, y: 22 },
    LW:  { x: 18, y: 28 },
};

const LINKS = [
    ["RB", "RCB"], ["RCB", "LCB"], ["LCB", "LB"],
    ["RB", "RCM"], ["RCB", "CDM"], ["LCB", "CDM"], ["LB", "LCM"],
    ["CDM", "RCM"], ["CDM", "LCM"],
    ["RCM", "RW"], ["RCM", "ST"], ["LCM", "LW"], ["LCM", "ST"],
    ["RW", "ST"], ["LW", "ST"], ["RB", "RW"], ["LB", "LW"],
];

const STAT_RANGES = {
    tackles_per90: [0.5, 4.0], interceptions_per90: [0.3, 3.0],
    progressive_passes_per90: [1.0, 12.0], crosses_per90: [0.2, 6.0],
    key_passes_per90: [0.3, 4.0], through_balls_per90: [0.0, 1.2],
    dribbles_per90: [0.3, 6.0], aerial_won_pct: [25.0, 85.0],
    pass_completion: [65.0, 95.0], press_per90: [5.0, 25.0],
    xa_per90: [0.0, 0.40], xg_per90: [0.0, 0.80],
    shot_creating_actions_per90: [1.0, 7.0], progressive_carries_per90: [0.5, 7.0],
    blocks_per90: [0.3, 2.5], clearances_per90: [1.0, 6.0],
};

let allPlayers = {};
let benchPlayers = [];
let targetPlayers = [];
let currentSquad = {};
let squadData = {};
let chemistryData = null;

async function fetchJSON(url, opts) {
    return (await fetch(url, opts)).json();
}

function chemColor(s) { return s >= 65 ? "#22c55e" : s >= 45 ? "#eab308" : "#ef4444"; }
function shortName(n) { const p = n.split(" "); return p[p.length - 1]; }
function fmtStat(k) { return k.replace(/_per90/g, "/90").replace(/_pct/g, "%").replace(/_/g, " "); }
function normStat(v, k) { const [lo, hi] = STAT_RANGES[k] || [0, 1]; return Math.max(0, Math.min(1, (v - lo) / (hi - lo))); }

// --- Pitch ---
function renderPitch() {
    const pitch = document.getElementById("pitch");
    pitch.querySelectorAll(".player-node").forEach(n => n.remove());

    for (const [pos, coords] of Object.entries(FORMATION)) {
        const player = squadData[pos];
        if (!player) continue;
        const isTarget = !allPlayers.arsenal.some(p => p.id === player.id);
        const node = document.createElement("div");
        node.className = "player-node" + (isTarget ? " is-target" : "");
        node.style.left = coords.x + "%";
        node.style.top = coords.y + "%";
        node.innerHTML = `
            <div class="player-circle">${pos}</div>
            <div class="player-name">${shortName(player.name)}</div>
        `;
        node.addEventListener("click", () => openSwapPanel(pos));
        pitch.appendChild(node);
    }
}

function renderLines() {
    const svg = document.getElementById("chem-lines");
    svg.innerHTML = "";
    if (!chemistryData) return;
    const pitch = document.getElementById("pitch");
    const w = pitch.offsetWidth, h = pitch.offsetHeight;

    for (const link of chemistryData.links) {
        const from = FORMATION[link.from], to = FORMATION[link.to];
        if (!from || !to) continue;
        const line = document.createElementNS("http://www.w3.org/2000/svg", "line");
        line.setAttribute("x1", (from.x / 100) * w);
        line.setAttribute("y1", (from.y / 100) * h);
        line.setAttribute("x2", (to.x / 100) * w);
        line.setAttribute("y2", (to.y / 100) * h);
        line.setAttribute("class", "chem-line");
        line.setAttribute("stroke", chemColor(link.score));
        svg.appendChild(line);
    }
}

async function updateChemistry() {
    chemistryData = await fetchJSON("/api/chemistry", {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify(currentSquad),
    });
    const el = document.getElementById("overall-chem");
    const score = Math.round(chemistryData.overall);
    el.textContent = score;
    el.style.color = chemColor(score);
    renderLines();
}

// --- Radar ---
function drawRadar(p1, p2) {
    const svg = document.getElementById("radar-chart");
    svg.innerHTML = "";
    const keys = Object.keys(p1.stats).filter(k => k in p2.stats).slice(0, 8);
    if (keys.length < 3) return;

    const cx = 150, cy = 150, maxR = 105, n = keys.length;
    const step = (2 * Math.PI) / n;

    for (let ring = 0.25; ring <= 1; ring += 0.25) {
        let d = "";
        for (let i = 0; i < n; i++) {
            const a = i * step - Math.PI / 2;
            d += (i === 0 ? "M" : "L") + (cx + Math.cos(a) * maxR * ring) + "," + (cy + Math.sin(a) * maxR * ring);
        }
        const path = document.createElementNS("http://www.w3.org/2000/svg", "path");
        path.setAttribute("d", d + "Z");
        path.setAttribute("fill", "none");
        path.setAttribute("stroke", "#ddd");
        svg.appendChild(path);
    }

    for (let i = 0; i < n; i++) {
        const a = i * step - Math.PI / 2;
        const line = document.createElementNS("http://www.w3.org/2000/svg", "line");
        line.setAttribute("x1", cx); line.setAttribute("y1", cy);
        line.setAttribute("x2", cx + Math.cos(a) * maxR);
        line.setAttribute("y2", cy + Math.sin(a) * maxR);
        line.setAttribute("stroke", "#eee");
        svg.appendChild(line);

        const text = document.createElementNS("http://www.w3.org/2000/svg", "text");
        text.setAttribute("x", cx + Math.cos(a) * (maxR + 12));
        text.setAttribute("y", cy + Math.sin(a) * (maxR + 12));
        text.setAttribute("text-anchor", "middle");
        text.setAttribute("dominant-baseline", "middle");
        text.setAttribute("fill", "#999");
        text.setAttribute("font-size", "8");
        text.textContent = fmtStat(keys[i]);
        svg.appendChild(text);
    }

    function poly(player, color, alpha) {
        let d = "";
        for (let i = 0; i < n; i++) {
            const v = normStat(player.stats[keys[i]] || 0, keys[i]);
            const a = i * step - Math.PI / 2;
            d += (i === 0 ? "M" : "L") + (cx + Math.cos(a) * maxR * v) + "," + (cy + Math.sin(a) * maxR * v);
        }
        const path = document.createElementNS("http://www.w3.org/2000/svg", "path");
        path.setAttribute("d", d + "Z");
        path.setAttribute("fill", color.replace(")", "," + alpha + ")").replace("rgb", "rgba"));
        path.setAttribute("stroke", color);
        path.setAttribute("stroke-width", "1.5");
        svg.appendChild(path);
    }

    poly(p1, "rgb(193, 39, 45)", 0.15);
    poly(p2, "rgb(59, 130, 246)", 0.15);

    [{c:"#c1272d",l:p1.name},{c:"#3b82f6",l:p2.name}].forEach((item, i) => {
        const r = document.createElementNS("http://www.w3.org/2000/svg", "rect");
        r.setAttribute("x", 8); r.setAttribute("y", 8 + i * 14);
        r.setAttribute("width", 8); r.setAttribute("height", 8);
        r.setAttribute("fill", item.c); r.setAttribute("rx", 1);
        svg.appendChild(r);
        const t = document.createElementNS("http://www.w3.org/2000/svg", "text");
        t.setAttribute("x", 20); t.setAttribute("y", 15 + i * 14);
        t.setAttribute("fill", "#888"); t.setAttribute("font-size", "9");
        t.textContent = item.l;
        svg.appendChild(t);
    });
}

// --- Swap panel ---
function openSwapPanel(position) {
    const panel = document.getElementById("swap-panel");
    const overlay = document.getElementById("swap-overlay");
    const currentPlayer = squadData[position];

    document.getElementById("swap-title").textContent = "Replace " + currentPlayer.name;

    const cpCard = document.getElementById("current-player-card");
    cpCard.innerHTML = `
        <div class="cp-name">${currentPlayer.name}</div>
        <div class="cp-meta">${currentPlayer.position}</div>
        <div class="stat-grid">${Object.entries(currentPlayer.stats).map(([k,v]) =>
            `<div class="stat-row"><span class="stat-label">${fmtStat(k)}</span><span class="stat-value">${v}</span></div>`
        ).join("")}</div>
    `;

    document.getElementById("radar-container").style.display = "none";

    const candidates = targetPlayers.filter(p => p.position === position);
    const candidateList = document.getElementById("candidate-list");
    candidateList.innerHTML = candidates.length ? "" : '<p style="color:#222;font-size:11px">None</p>';
    for (const c of candidates) candidateList.appendChild(makeCard(c, currentPlayer, position));

    const benchOpts = benchPlayers.filter(p => p.position === position && p.id !== currentPlayer.id);
    const squadOpts = allPlayers.arsenal.filter(p => p.position === position && p.id !== currentPlayer.id && !benchOpts.some(b => b.id === p.id));
    const opts = [...benchOpts, ...squadOpts];

    const squadList = document.getElementById("squad-options-list");
    squadList.innerHTML = opts.length ? "" : '<p style="color:#222;font-size:11px">None</p>';
    for (const o of opts) squadList.appendChild(makeCard(o, currentPlayer, position));

    panel.classList.add("active");
    overlay.classList.add("active");
}

function closeSwapPanel() {
    document.getElementById("swap-panel").classList.remove("active");
    document.getElementById("swap-overlay").classList.remove("active");
}

function makeCard(candidate, currentPlayer, position) {
    const card = document.createElement("div");
    card.className = "candidate-card";
    const compStats = Object.keys(candidate.stats).filter(k => k in currentPlayer.stats).slice(0, 8);

    const rows = compStats.map(k => {
        const cv = currentPlayer.stats[k] || 0, nv = candidate.stats[k] || 0;
        const diff = nv - cv;
        const ccls = diff < -0.01 ? "better" : diff > 0.01 ? "worse" : "same";
        const ncls = diff > 0.01 ? "better" : diff < -0.01 ? "worse" : "same";
        return `<div class="comp-row">
            <div class="comp-val ${ccls}">${cv}</div>
            <div class="comp-label">${fmtStat(k)}</div>
            <div class="comp-val ${ncls}">${nv}</div>
        </div>`;
    }).join("");

    card.innerHTML = `
        <div class="candidate-top"><span class="candidate-name">${candidate.name}</span></div>
        <div class="comparison">
            <div class="comp-row"><div class="comp-val same" style="color:#333;font-size:10px">current</div><div class="comp-label"></div><div class="comp-val same" style="color:#333;font-size:10px">new</div></div>
            ${rows}
        </div>
    `;

    card.addEventListener("click", () => { swapPlayer(position, candidate); });
    card.addEventListener("mouseenter", () => {
        drawRadar(currentPlayer, candidate);
        document.getElementById("radar-container").style.display = "block";
    });

    return card;
}

function swapPlayer(position, newPlayer) {
    currentSquad[position] = newPlayer.id;
    squadData[position] = newPlayer;
    renderPitch();
    updateChemistry();
    closeSwapPanel();
}

function resetSquad() {
    for (const p of allPlayers.arsenal) {
        currentSquad[p.position] = p.id;
        squadData[p.position] = p;
    }
    renderPitch();
    updateChemistry();
}

// --- Monte Carlo ---
async function runMonteCarlo() {
    const btn = document.getElementById("mc-btn");
    const container = document.getElementById("mc-results");
    btn.disabled = true;
    btn.textContent = "simulating...";
    container.innerHTML = "";

    try {
        const data = await fetchJSON("/api/montecarlo", {
            method: "POST",
            headers: { "Content-Type": "application/json" },
            body: JSON.stringify(currentSquad),
        });

        const maxCount = Math.max(...data.histogram.counts);
        const bars = data.histogram.counts.map((count, i) => {
            const pct = maxCount > 0 ? (count / maxCount) * 100 : 0;
            const mid = (data.histogram.edges[i] + data.histogram.edges[i + 1]) / 2;
            return `<div class="mc-bar" style="height:${pct}%;background:${chemColor(mid)}" title="${count}"></div>`;
        }).join("");

        container.innerHTML = `
            <div class="mc-stats">
                mean: <strong style="color:${chemColor(data.mean)}">${data.mean}</strong>
                std: <strong>${data.std}</strong>
                p5: <strong>${data.p5}</strong>
                p95: <strong>${data.p95}</strong>
            </div>
            <div class="mc-bars">${bars}</div>
            <div class="mc-axis"><span>0</span><span>25</span><span>50</span><span>75</span><span>100</span></div>
            <div class="mc-ci">90% CI: ${data.p5} to ${data.p95} over ${data.n_simulations} simulations. IQR: ${data.p25} to ${data.p75}.</div>
        `;
    } catch (e) {
        container.innerHTML = `<p style="color:#333">${e.message}</p>`;
    } finally {
        btn.disabled = false;
        btn.textContent = "Run simulation";
    }
}

// --- Optimizer ---
async function runOptimizer() {
    const btn = document.getElementById("optimize-btn");
    const container = document.getElementById("optimize-results");
    const maxSignings = parseInt(document.getElementById("max-signings").value);

    btn.disabled = true;
    btn.textContent = "searching...";
    container.innerHTML = "";

    try {
        const data = await fetchJSON("/api/optimize", {
            method: "POST",
            headers: { "Content-Type": "application/json" },
            body: JSON.stringify({ max_signings: maxSignings }),
        });

        if (!data.results || !data.results.length) {
            container.innerHTML = '<p style="color:#333">no improvements found</p>';
            return;
        }

        let first = true;
        for (const r of data.results) {
            const d = document.createElement("div");
            d.className = "opt-result" + (first ? " best" : "");

            const diff = r.improvement;
            const dcls = diff > 0.5 ? "up" : diff < -0.5 ? "down" : "flat";
            const sign = diff > 0 ? "+" : "";

            d.innerHTML = `
                <div class="opt-head">
                    <span class="opt-label ${first ? 'gold' : ''}">${first ? 'optimal' : r.signings.length + ' signing' + (r.signings.length > 1 ? 's' : '')}</span>
                    <span class="opt-nums">
                        <span class="opt-diff ${dcls}">${sign}${diff.toFixed(1)}</span>
                        <span class="opt-chem" style="color:${chemColor(r.chemistry)}">${r.chemistry}</span>
                    </span>
                </div>
                <div class="opt-swaps">${r.signings.map(s => {
                    const cur = allPlayers.arsenal.find(p => p.position === s.position);
                    return `<span class="opt-swap">${s.position}: ${cur ? cur.name : '?'} &rarr; <strong>${s.player.name}</strong></span>`;
                }).join("")}</div>
            `;

            d.addEventListener("click", () => {
                resetSquad();
                for (const s of r.signings) {
                    currentSquad[s.position] = s.player.id;
                    squadData[s.position] = s.player;
                }
                renderPitch();
                updateChemistry();
                window.scrollTo({ top: 0, behavior: "smooth" });
            });

            container.appendChild(d);
            first = false;
        }

        const meta = document.createElement("div");
        meta.className = "opt-meta";
        meta.innerHTML = `baseline: <span>${data.baseline}</span> &middot; explored: <span>${data.nodes_explored}</span> &middot; pruned: <span>${data.nodes_pruned}</span>`;
        container.appendChild(meta);

    } catch (e) {
        container.innerHTML = `<p style="color:#333">${e.message}</p>`;
    } finally {
        btn.disabled = false;
        btn.textContent = "Find best combo";
    }
}

// --- Init ---
async function init() {
    const rawData = await fetchJSON("/api/squad");
    allPlayers = rawData;
    benchPlayers = rawData.bench || [];
    targetPlayers = rawData.targets || [];

    for (const p of rawData.arsenal) {
        allPlayers[p.id] = p;
        currentSquad[p.position] = p.id;
        squadData[p.position] = p;
    }
    for (const p of [...benchPlayers, ...targetPlayers]) {
        allPlayers[p.id] = p;
    }

    renderPitch();
    await updateChemistry();

    document.getElementById("swap-close").addEventListener("click", e => { e.preventDefault(); closeSwapPanel(); });
    document.getElementById("swap-overlay").addEventListener("click", closeSwapPanel);
    document.getElementById("reset-btn").addEventListener("click", e => { e.preventDefault(); resetSquad(); });
    document.getElementById("optimize-btn").addEventListener("click", runOptimizer);
    document.getElementById("mc-btn").addEventListener("click", runMonteCarlo);
    window.addEventListener("resize", renderLines);
}

init();
