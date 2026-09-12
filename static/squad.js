// 4-3-3 formation positions (% from top-left of pitch)
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

let allPlayers = {};
let benchPlayers = [];
let targetPlayers = [];
let currentSquad = {};   // { position: playerId }
let squadData = {};      // { position: playerObject }
let chemistryData = null;

async function fetchJSON(url, opts) {
    const resp = await fetch(url, opts);
    return resp.json();
}

function chemColor(score) {
    if (score >= 65) return "#22c55e";
    if (score >= 45) return "#eab308";
    return "#ef4444";
}

function chemClass(score) {
    if (score >= 65) return "high";
    if (score >= 45) return "mid";
    return "low";
}

function shortName(name) {
    const parts = name.split(" ");
    if (parts.length === 1) return name;
    return parts[parts.length - 1];
}

function formatStatName(key) {
    return key
        .replace(/_per90/g, "/90")
        .replace(/_pct/g, " %")
        .replace(/_/g, " ");
}

// --- Render pitch ---
function renderPitch() {
    const pitch = document.getElementById("pitch");

    // Remove old nodes
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
            <div class="player-pos">${player.position}</div>
        `;
        node.addEventListener("click", () => openSwapPanel(pos));
        pitch.appendChild(node);
    }
}

// --- Render chemistry lines ---
function renderLines() {
    const svg = document.getElementById("chem-lines");
    svg.innerHTML = "";

    if (!chemistryData) return;

    const pitch = document.getElementById("pitch");
    const w = pitch.offsetWidth;
    const h = pitch.offsetHeight;

    for (const link of chemistryData.links) {
        const from = FORMATION[link.from];
        const to = FORMATION[link.to];
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

// --- Compute chemistry ---
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

// --- Swap panel ---
function openSwapPanel(position) {
    const panel = document.getElementById("swap-panel");
    const overlay = document.getElementById("swap-overlay");
    const currentPlayer = squadData[position];

    document.getElementById("swap-title").textContent = `Replace ${currentPlayer.name}`;

    // Current player card
    const cpCard = document.getElementById("current-player-card");
    cpCard.innerHTML = `
        <div class="cp-name">${currentPlayer.name}</div>
        <div class="cp-meta">${currentPlayer.position} | ${currentPlayer.nation} | Age ${currentPlayer.age}</div>
        <div class="stat-grid">${renderStats(currentPlayer.stats)}</div>
    `;

    // Transfer targets for this position
    const candidates = targetPlayers.filter(p => p.position === position);
    const candidateList = document.getElementById("candidate-list");
    candidateList.innerHTML = "";

    if (candidates.length === 0) {
        candidateList.innerHTML = '<p class="loading-text">No external targets for this position</p>';
    }

    for (const candidate of candidates) {
        const card = createCandidateCard(candidate, currentPlayer, position);
        candidateList.appendChild(card);
    }

    // Bench / squad rotation options for same position
    const benchOpts = benchPlayers.filter(p => p.position === position && p.id !== currentPlayer.id);
    // Also include any starters for the same position who aren't currently in that slot
    const squadOpts = allPlayers.arsenal.filter(
        p => p.position === position && p.id !== currentPlayer.id
            && !benchOpts.some(b => b.id === p.id)
    );
    const allOpts = [...benchOpts, ...squadOpts];

    const squadList = document.getElementById("squad-options-list");
    squadList.innerHTML = "";
    if (allOpts.length === 0) {
        squadList.innerHTML = '<p class="loading-text">No alternatives in squad</p>';
    }
    for (const opt of allOpts) {
        const card = createCandidateCard(opt, currentPlayer, position);
        squadList.appendChild(card);
    }

    panel.classList.add("active");
    overlay.classList.add("active");
}

function closeSwapPanel() {
    document.getElementById("swap-panel").classList.remove("active");
    document.getElementById("swap-overlay").classList.remove("active");
}

function createCandidateCard(candidate, currentPlayer, position) {
    const card = document.createElement("div");
    card.className = "candidate-card";

    // Quick chemistry estimate based on shared stats
    const compStats = Object.keys(candidate.stats).filter(k => k in currentPlayer.stats);

    card.innerHTML = `
        <div class="candidate-top">
            <span class="candidate-name">${candidate.name}</span>
        </div>
        <div class="candidate-meta">${candidate.nation} | Age ${candidate.age}</div>
        ${renderComparison(currentPlayer, candidate, compStats)}
    `;

    card.addEventListener("click", () => {
        swapPlayer(position, candidate);
    });

    return card;
}

function renderStats(stats) {
    return Object.entries(stats)
        .map(([k, v]) => `
            <div class="stat-row">
                <span class="stat-label">${formatStatName(k)}</span>
                <span class="stat-value">${v}</span>
            </div>
        `)
        .join("");
}

function renderComparison(current, candidate, statKeys) {
    const rows = statKeys.slice(0, 8).map(k => {
        const cv = current.stats[k] || 0;
        const nv = candidate.stats[k] || 0;
        const diff = nv - cv;
        const cClass = diff > 0.01 ? "better" : diff < -0.01 ? "worse" : "same";
        const nClass = diff > 0.01 ? "better" : diff < -0.01 ? "worse" : "same";
        return `
            <div class="comp-row">
                <div class="comp-val ${diff < -0.01 ? 'better' : diff > 0.01 ? 'worse' : 'same'}">${cv}</div>
                <div class="comp-label">${formatStatName(k)}</div>
                <div class="comp-val ${nClass}">${nv}</div>
            </div>
        `;
    });

    return `
        <div class="comparison">
            <div class="comp-row">
                <div class="comp-val same" style="color:#888;font-size:0.65rem">Current</div>
                <div class="comp-label"></div>
                <div class="comp-val same" style="color:#888;font-size:0.65rem">New</div>
            </div>
            ${rows.join("")}
        </div>
    `;
}

// --- Swap logic ---
function swapPlayer(position, newPlayer) {
    currentSquad[position] = newPlayer.id;
    squadData[position] = newPlayer;
    renderPitch();
    updateChemistry();
    closeSwapPanel();
}

// --- Reset ---
function resetSquad() {
    for (const p of allPlayers.arsenal) {
        currentSquad[p.position] = p.id;
        squadData[p.position] = p;
    }
    renderPitch();
    updateChemistry();
}

// --- Init ---
async function init() {
    const rawData = await fetchJSON("/api/squad");
    allPlayers = rawData;
    benchPlayers = rawData.bench || [];
    targetPlayers = rawData.targets || [];

    // Build initial squad from starters
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

    document.getElementById("swap-close").addEventListener("click", closeSwapPanel);
    document.getElementById("swap-overlay").addEventListener("click", closeSwapPanel);
    document.getElementById("reset-btn").addEventListener("click", resetSquad);
    document.getElementById("optimize-btn").addEventListener("click", runOptimizer);

    // Re-render lines on resize
    window.addEventListener("resize", renderLines);
}

// --- Optimizer ---
async function runOptimizer() {
    const btn = document.getElementById("optimize-btn");
    const container = document.getElementById("optimize-results");
    const maxSignings = parseInt(document.getElementById("max-signings").value);

    btn.disabled = true;
    btn.textContent = "Calculating...";
    container.innerHTML = '<p class="loading-text">Searching all combinations...</p>';

    try {
        const data = await fetchJSON("/api/optimize", {
            method: "POST",
            headers: { "Content-Type": "application/json" },
            body: JSON.stringify({ max_signings: maxSignings }),
        });

        container.innerHTML = "";

        if (!data.results || data.results.length === 0) {
            container.innerHTML = '<p class="loading-text">No improvements found</p>';
            return;
        }

        // Group by number of signings
        const grouped = {};
        for (const r of data.results) {
            const n = r.signings.length;
            if (!grouped[n]) grouped[n] = [];
            grouped[n].push(r);
        }

        let isFirst = true;
        for (const [n, results] of Object.entries(grouped)) {
            const heading = document.createElement("div");
            heading.style.cssText = "font-size:0.7rem;font-weight:700;color:#555;text-transform:uppercase;letter-spacing:0.1em;margin-top:0.5rem;";
            heading.textContent = n === "1" ? "Best single signing" : `Best ${n} signings`;
            container.appendChild(heading);

            const combosSearched = n === "1" ? data.results.filter(r => r.signings.length === 1).length
                : data.results.filter(r => r.signings.length === parseInt(n)).length;

            for (let i = 0; i < results.length; i++) {
                const r = results[i];
                const card = document.createElement("div");
                card.className = "opt-combo" + (isFirst ? " best" : "");

                const deltaClass = r.improvement > 0.5 ? "positive" : r.improvement < -0.5 ? "negative" : "neutral";
                const deltaSign = r.improvement > 0 ? "+" : "";

                const signingPills = r.signings.map(s => {
                    // Find who they're replacing
                    const currentPlayer = allPlayers.arsenal.find(p => p.position === s.position);
                    const currentName = currentPlayer ? currentPlayer.name : s.position;
                    return `
                        <div class="opt-signing-pill">
                            <span class="opt-signing-pos">${s.position}</span>
                            <span class="opt-signing-arrow">${currentName} &rarr;</span>
                            <span class="opt-signing-name">${s.player.name}</span>
                        </div>
                    `;
                }).join("");

                card.innerHTML = `
                    <div class="opt-header">
                        <span class="opt-rank ${isFirst ? 'gold' : ''}">${isFirst ? 'Optimal' : '#' + (i + 1)}</span>
                        <div class="opt-score">
                            <span class="opt-delta ${deltaClass}">${deltaSign}${r.improvement.toFixed(1)}</span>
                            <span class="opt-chemistry" style="color: ${chemColor(r.chemistry)}">${r.chemistry}</span>
                        </div>
                    </div>
                    <div class="opt-signings">${signingPills}</div>
                    <div class="opt-apply-hint">Click to apply</div>
                `;

                card.addEventListener("click", () => applyOptResult(r));
                container.appendChild(card);
                isFirst = false;
            }
        }

        // Algorithm summary
        const best = data.results[0];
        const summary = document.createElement("div");
        summary.className = "opt-stats-bar";
        summary.innerHTML = `
            <div class="opt-stat">Algorithm: <span>${data.algorithm || "Branch and Bound"}</span></div>
            <div class="opt-stat">Baseline: <span>${data.baseline}</span></div>
            <div class="opt-stat">Best: <span>${best.chemistry}</span></div>
            <div class="opt-stat">Nodes explored: <span>${data.nodes_explored}</span></div>
            <div class="opt-stat">Pruned: <span>${data.nodes_pruned}</span></div>
        `;
        container.appendChild(summary);

    } catch (e) {
        container.innerHTML = `<p class="loading-text">Error: ${e.message}</p>`;
    } finally {
        btn.disabled = false;
        btn.textContent = "Find Best Combo";
    }
}

function applyOptResult(result) {
    resetSquad();
    for (const s of result.signings) {
        const player = s.player;
        currentSquad[s.position] = player.id;
        squadData[s.position] = player;
    }
    renderPitch();
    updateChemistry();
    window.scrollTo({ top: 0, behavior: "smooth" });
}

init();
