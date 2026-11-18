/**
 * 一二壘有人：封殺三壘決策模擬器前端引擎
 * 與 src/force_3b_model.py 採用完全一致的物理時間差邏輯斯模型與 RE24/WPA 查詢表
 */

const THIRD_BASE_X = -63.6396;
const THIRD_BASE_Y = 63.6396;
const FIRST_BASE_X = 63.6396;
const FIRST_BASE_Y = 63.6396;
const SECOND_BASE_X = 0;
const SECOND_BASE_Y = 127.2792;

let MODEL_DATA = null;

const state = {
  league: "CPBL_Rebas_Ref",
  playType: "bunt",
  comparison: "vs_1b",
  ev: 52,
  showOverlay: true,
  leftOuts: 0,
  rightInning: 9,
  rightHalf: "bot",
  rightDiff: 0,
  rightOuts: 0,
  runner90: 4.02,
  leadFt: 12,
  armOffset: 0,
  exchangeOffset: 0,
};

function assignFielderPos(x, y, isBunt) {
  const distHP = Math.hypot(x, y);
  if (distHP < 26) return "C";
  if (isBunt) {
    if (x < -22 && y > 28) return "3B";
    if (x > 22 && y > 28) return "1B";
    return "P";
  }
  if (distHP < 72 && Math.abs(x) < 22) return "P";
  if (x < -36) return "3B";
  if (x < 0) return "SS";
  if (x > 36) return "1B";
  return "SS";
}

function predictForce3B(x, y, overrides = {}) {
  const isBunt = overrides.isBunt !== undefined ? overrides.isBunt : state.playType === "bunt";
  const ev = overrides.ev !== undefined ? overrides.ev : state.ev;
  const runner90 = overrides.runner90 !== undefined ? overrides.runner90 : state.runner90;
  const leadFt = overrides.leadFt !== undefined ? overrides.leadFt : state.leadFt;

  const pos = overrides.pos || assignFielderPos(x, y, isBunt);
  const bench = MODEL_DATA.pos_benchmarks[pos] || MODEL_DATA.pos_benchmarks["P"];
  const armMph = Math.max(55, bench.arm_mph + state.armOffset);
  const exchangeBase = Math.max(0.35, bench.exchange_sec + state.exchangeOffset);

  const distHP = Math.hypot(x, y);
  const dist3B = Math.hypot(x - THIRD_BASE_X, y - THIRD_BASE_Y);

  const evFts = Math.max(20, ev * 1.46667);
  const vRoll = isBunt ? Math.max(16, evFts * 0.38) : Math.max(28, evFts * 0.56);
  const tRoll = distHP / vRoll;

  let tExchange, tThrow;
  if (dist3B <= 8.0) {
    tExchange = 0.28;
    tThrow = dist3B / 22.0;
  } else {
    tExchange = exchangeBase;
    const vThrowFts = Math.max(60, armMph * 1.46667 * 0.90);
    tThrow = dist3B / vThrowFts;
  }

  const tBall = tRoll + tExchange + tThrow + 0.08;
  const effSpeedFts = 90 / Math.max(2.8, runner90 - 0.55);
  const runDist = Math.max(62, 90 - leadFt);
  const startOffset = isBunt ? -0.15 : 0.22;
  const tRunner = runDist / effSpeedFts + startOffset;

  const margin = tRunner - tBall;
  const prob = 1 / (1 + Math.exp(-Math.max(-20, Math.min(20, margin / 0.18))));

  return { pos, armMph, distHP, dist3B, tRoll, tExchange, tThrow, tBall, tRunner, margin, prob };
}

function getScenarioBEPs() {
  const leftKey = `${state.leftOuts}_${state.comparison}`;
  const leftObj = MODEL_DATA.re24_bep[state.league][leftKey];

  const rightKey = `${state.rightInning}_${state.rightHalf}_${state.rightDiff}_${state.rightOuts}_${state.comparison}`;
  const rightObj = MODEL_DATA.wpa_bep[state.league][rightKey];

  return { leftObj, rightObj };
}

function toSvg(fx, fy) {
  return { sx: fx, sy: 155 - fy };
}
function fromSvg(sx, sy) {
  return { fx: sx, fy: 155 - sy };
}

function isInFairInfield(fx, fy) {
  if (fy < 4 || fy > 158) return false;
  if (Math.abs(fx) > fy + 2) return false;
  return Math.hypot(fx, fy) <= 162;
}

function renderTreeBox(containerId, obj) {
  const el = document.getElementById(containerId);
  const isWPA = obj.mode === "WPA";
  const fmt = (v) => (isWPA ? `${(v * 100).toFixed(1)}%` : `${v.toFixed(3)} 分`);

  el.innerHTML = `
    <div class="tree-node">
      <span class="lbl">封殺三壘成功 (${obj.succ_state})</span>
      <span class="val good">${fmt(obj.val_succ)}</span>
    </div>
    <div class="tree-node">
      <span class="lbl">穩傳安全選項 (${obj.safe_state})</span>
      <span class="val neutral">${fmt(obj.val_safe)}</span>
    </div>
    <div class="tree-node">
      <span class="lbl">傳三壘失敗 (${obj.fail_state})</span>
      <span class="val bad">${fmt(obj.val_fail)}</span>
    </div>
  `;
}

function drawDiamond(svgId, mode, bepCons, bepAgg) {
  const svg = document.getElementById(svgId);
  const step = 4.5;
  const cells = [];

  const hp = toSvg(0, 0);
  const b1 = toSvg(FIRST_BASE_X, FIRST_BASE_Y);
  const b2 = toSvg(SECOND_BASE_X, SECOND_BASE_Y);
  const b3 = toSvg(THIRD_BASE_X, THIRD_BASE_Y);
  const lfEdge = toSvg(-115, 115);
  const rfEdge = toSvg(115, 115);

  let html = `
    <defs>
      <clipPath id="clip-${svgId}">
        <path d="M ${hp.sx} ${hp.sy} L ${lfEdge.sx} ${lfEdge.sy} Q 0 -18 ${rfEdge.sx} ${rfEdge.sy} Z" />
      </clipPath>
    </defs>
    <path d="M ${hp.sx} ${hp.sy} L ${lfEdge.sx} ${lfEdge.sy} Q 0 -18 ${rfEdge.sx} ${rfEdge.sy} Z" fill="#13223b" stroke="#2e4469" stroke-width="1"/>
    <g clip-path="url(#clip-${svgId})">
  `;

  const maxY = state.playType === "bunt" ? 105 : 155;
  for (let fy = 6; fy <= maxY; fy += step) {
    for (let fx = -fy; fx <= fy; fx += step) {
      if (!isInFairInfield(fx, fy)) continue;
      const res = predictForce3B(fx, fy);
      let fill = "#1b2e4f";
      let opacity = 0.62;
      if (mode === "left") {
        if (res.prob >= bepCons) {
          fill = "#10b981";
          opacity = 0.72;
        }
      } else {
        if (res.prob >= bepCons) {
          fill = "#10b981";
          opacity = 0.72;
        } else if (res.prob >= bepAgg) {
          fill = "#f59e0b";
          opacity = 0.78;
        }
      }
      const p = toSvg(fx - step / 2, fy + step / 2);
      cells.push(`<rect x="${p.sx.toFixed(1)}" y="${p.sy.toFixed(1)}" width="${(step + 0.4).toFixed(1)}" height="${(step + 0.4).toFixed(1)}" fill="${fill}" fill-opacity="${opacity}" />`);
    }
  }
  html += cells.join("");

  const mound = toSvg(0, 60.5);
  html += `
    </g>
    <polygon points="${hp.sx},${hp.sy} ${b1.sx},${b1.sy} ${b2.sx},${b2.sy} ${b3.sx},${b3.sy}" fill="none" stroke="rgba(255,255,255,0.45)" stroke-width="1.2" stroke-dasharray="3,2"/>
    <circle cx="${mound.sx}" cy="${mound.sy}" r="6" fill="#233759" stroke="rgba(255,255,255,0.5)" stroke-width="1"/>
    <text x="${mound.sx}" y="${mound.sy + 2.5}" text-anchor="middle" font-size="6.5" fill="#d9e6fa" font-weight="700">P</text>
    <circle cx="${b3.sx}" cy="${b3.sy}" r="30" fill="none" stroke="rgba(255,255,255,0.22)" stroke-width="0.8" stroke-dasharray="2,2"/>
    <circle cx="${b3.sx}" cy="${b3.sy}" r="60" fill="none" stroke="rgba(255,255,255,0.18)" stroke-width="0.8" stroke-dasharray="2,2"/>
    <rect x="${b1.sx - 3.5}" y="${b1.sy - 3.5}" width="7" height="7" transform="rotate(45 ${b1.sx} ${b1.sy})" fill="#f8fafc"/>
    <rect x="${b2.sx - 3.5}" y="${b2.sy - 3.5}" width="7" height="7" transform="rotate(45 ${b2.sx} ${b2.sy})" fill="#f8fafc"/>
    <rect x="${b3.sx - 4}" y="${b3.sy - 4}" width="8" height="8" transform="rotate(45 ${b3.sx} ${b3.sy})" fill="#fde047" stroke="#111" stroke-width="0.8"/>
    <polygon points="${hp.sx},${hp.sy + 3} ${hp.sx - 3.5},${hp.sy - 1} ${hp.sx - 3.5},${hp.sy - 4} ${hp.sx + 3.5},${hp.sy - 4} ${hp.sx + 3.5},${hp.sy - 1}" fill="#f8fafc"/>
    <text x="${b3.sx - 10}" y="${b3.sy + 14}" text-anchor="end" font-size="7.5" fill="#fde047" font-weight="800">3B 封殺目標</text>
    <text x="${b1.sx + 9}" y="${b1.sy + 14}" text-anchor="start" font-size="7.5" fill="#cbd5e1">1B</text>
    <text x="${b2.sx}" y="${b2.sy - 11}" text-anchor="middle" font-size="7.5" fill="#cbd5e1" font-weight="600">2B (跑者起點)</text>
  `;

  if (state.showOverlay) {
    const wantBunt = state.playType === "bunt";
    const targetOuts = mode === "left" ? state.leftOuts : state.rightOuts;
    const pts = MODEL_DATA.empirical_plays.filter((p) => p.bunt === wantBunt && p.outs === targetOuts);

    for (const pt of pts) {
      const sp = toSvg(pt.x, pt.y);
      let color = null;
      let r = 2.0;
      if (pt.choice === "FORCE_3B_SUCCESS" || pt.choice === "DP_WITH_3B_OUT") {
        color = "#22c55e";
        r = 2.8;
      } else if (pt.choice === "FC_ALL_SAFE_OR_ERROR") {
        color = "#ef4444";
        r = 2.6;
      } else if (pt.choice === "OUT_1B_ONLY") {
        color = "#60a5fa";
        r = 1.9;
      }
      if (color) {
        html += `<circle cx="${sp.sx.toFixed(1)}" cy="${sp.sy.toFixed(1)}" r="${r}" fill="${color}" stroke="#0b1220" stroke-width="0.6" opacity="0.9">
          <title>${pt.date} | ${pt.choice} | 距三壘 ${pt.d3b} ft | EV ${pt.ev ?? "?"} mph&#10;${pt.des}</title>
        </circle>`;
      }
    }
  }

  html += `<circle id="cursor-${svgId}" cx="-999" cy="-999" r="3.6" fill="#fff" stroke="#000" stroke-width="1.2" pointer-events="none" />`;
  svg.innerHTML = html;

  const refPts = state.playType === "bunt"
    ? [
        { label: "三壘線短打 (35ft)", x: -24, y: 34 },
        { label: "投手前短打 (50ft)", x: 0, y: 50 },
        { label: "一壘側短打 (45ft)", x: 28, y: 42 },
      ]
    : [
        { label: "三壘手防區", x: -55, y: 85 },
        { label: "游擊防區", x: -28, y: 118 },
        { label: "投手正面", x: 0, y: 62 },
      ];
  const threshold = mode === "left" ? bepCons : bepAgg;
  const readoutEl = document.getElementById(mode === "left" ? "cutoff-left" : "cutoff-right");
  readoutEl.innerHTML = refPts
    .map((rp) => {
      const pr = predictForce3B(rp.x, rp.y);
      const ok = pr.prob >= threshold;
      return `<span>${rp.label}：<strong>${(pr.prob * 100).toFixed(0)}%</strong> ${ok ? "🟢傳三壘" : "🔵傳一/二壘"}</span>`;
    })
    .join("");
}

function calcMaxThrowRadiusFt(runner90, targetBEP) {
  let maxDist = 0;
  for (let d = 10; d <= 125; d += 2) {
    const x = THIRD_BASE_X + d * 0.88;
    const y = THIRD_BASE_Y - d * 0.25;
    if (y < 10) continue;
    const pr = predictForce3B(x, y, { runner90 });
    if (pr.prob >= targetBEP) {
      maxDist = Math.round(pr.dist3B);
    }
  }
  return maxDist;
}

function renderLineupTable(bepCons, bepAgg) {
  const tbody = document.getElementById("lineup-tbody");
  tbody.innerHTML = "";
  MODEL_DATA.runner_presets.forEach((rp, idx) => {
    const tr = document.createElement("tr");
    const effSpeedFts = 90 / Math.max(2.8, rp.sec_90ft - 0.55);
    const runDist = Math.max(62, 90 - state.leadFt);
    const startOffset = state.playType === "bunt" ? -0.15 : 0.22;
    const tRunner = runDist / effSpeedFts + startOffset;
    const rCons = calcMaxThrowRadiusFt(rp.sec_90ft, bepCons);
    const rAgg = calcMaxThrowRadiusFt(rp.sec_90ft, bepAgg);

    let advice = "一壘側短打仍穩抓一壘";
    if (rCons >= 75) advice = "腳程偏慢：內野正中與一壘側皆可積極抓三壘";
    else if (rCons <= 42) advice = "頂尖快腿：除非三壘線近距離，否則優先穩抓一壘";

    tr.innerHTML = `
      <td><strong>${rp.tier}</strong></td>
      <td>${rp.name}</td>
      <td><input type="number" step="0.02" min="3.4" max="5.2" value="${rp.sec_90ft.toFixed(2)}" data-idx="${idx}" class="lineup-sec-input" /></td>
      <td>${tRunner.toFixed(2)} 秒</td>
      <td><strong style="color:#34d399">${rCons} ft</strong>（距三壘）</td>
      <td><strong style="color:#fcd34d">${rAgg} ft</strong>（距三壘）</td>
      <td>${advice}</td>
    `;
    tbody.appendChild(tr);
  });

  document.querySelectorAll(".lineup-sec-input").forEach((inp) => {
    inp.addEventListener("change", (e) => {
      const i = Number(e.target.dataset.idx);
      const val = parseFloat(e.target.value);
      if (!isNaN(val)) {
        MODEL_DATA.runner_presets[i].sec_90ft = val;
        renderAll();
      }
    });
  });
}

function bindHoverProbe(svgId) {
  const svg = document.getElementById(svgId);
  svg.addEventListener("mousemove", (evt) => {
    const pt = svg.createSVGPoint();
    pt.x = evt.clientX;
    pt.y = evt.clientY;
    const loc = pt.matrixTransform(svg.getScreenCTM().inverse());
    const { fx, fy } = fromSvg(loc.x, loc.y);
    if (!isInFairInfield(fx, fy)) return;

    const { leftObj, rightObj } = getScenarioBEPs();
    const res = predictForce3B(fx, fy);

    ["svg-left", "svg-right"].forEach((id) => {
      const c = document.getElementById(`cursor-${id}`);
      if (c) {
        c.setAttribute("cx", loc.x.toFixed(1));
        c.setAttribute("cy", loc.y.toFixed(1));
      }
    });

    let pill = `<span class="probe-pill hold">🔵 穩傳一／二壘（勿冒險）</span>`;
    if (res.prob >= leftObj.bep) {
      pill = `<span class="probe-pill go">🟢 傳三壘封殺（保守即達標）</span>`;
    } else if (res.prob >= rightObj.bep) {
      pill = `<span class="probe-pill agg">🟠 僅關鍵搶勝局數拚三壘</span>`;
    }

    const probe = document.getElementById("probe-bar");
    probe.innerHTML = `
      ${pill}
      <span>落點距本壘 <strong>${res.distHP.toFixed(0)} ft</strong>｜距三壘 <strong>${res.dist3B.toFixed(0)} ft</strong></span>
      <span>接球守位 <strong>${res.pos}</strong> (${res.armMph.toFixed(0)} mph)</span>
      <span>球抵三壘 <strong>${res.tBall.toFixed(2)}s</strong> vs 跑者 <strong>${res.tRunner.toFixed(2)}s</strong> (差 ${res.margin >= 0 ? "+" : ""}${res.margin.toFixed(2)}s)</span>
      <span>封殺三壘成功率：<strong>${(res.prob * 100).toFixed(1)}%</strong></span>
    `;
  });
}

function renderAll() {
  const { leftObj, rightObj } = getScenarioBEPs();
  document.getElementById("bep-left").textContent = `${(leftObj.bep * 100).toFixed(1)}%`;
  document.getElementById("bep-right").textContent = `${(rightObj.bep * 100).toFixed(1)}%`;
  document.getElementById("title-bep-left").textContent = `門檻 ${(leftObj.bep * 100).toFixed(1)}%`;
  document.getElementById("title-bep-right").textContent = `門檻 ${(rightObj.bep * 100).toFixed(1)}%`;

  renderTreeBox("tree-left", leftObj);
  renderTreeBox("tree-right", rightObj);

  drawDiamond("svg-left", "left", leftObj.bep, rightObj.bep);
  drawDiamond("svg-right", "right", leftObj.bep, rightObj.bep);
  renderLineupTable(leftObj.bep, rightObj.bep);
}

function bindControls() {
  const bind = (id, key, transform = (v) => v, onUpdate = null) => {
    const el = document.getElementById(id);
    el.addEventListener("input", () => {
      state[key] = transform(el.type === "checkbox" ? el.checked : el.value);
      if (onUpdate) onUpdate(state[key]);
      renderAll();
    });
  };

  bind("sel-league", "league");
  bind("sel-playtype", "playType", (v) => v, (v) => {
    state.ev = v === "bunt" ? 52 : 88;
    document.getElementById("rng-ev").value = state.ev;
    document.getElementById("val-ev").textContent = `${state.ev} mph`;
  });
  bind("sel-comparison", "comparison");
  bind("rng-ev", "ev", Number, (v) => {
    document.getElementById("val-ev").textContent = `${v} mph`;
  });
  bind("chk-overlay", "showOverlay", Boolean);

  bind("left-outs", "leftOuts", Number);
  bind("right-inning", "rightInning", Number);
  bind("right-half", "rightHalf");
  bind("right-diff", "rightDiff", Number);
  bind("right-outs", "rightOuts", Number);

  bind("rng-runner-90", "runner90", Number, (v) => {
    document.getElementById("val-runner-90").textContent = `${v.toFixed(2)} s`;
  });
  bind("rng-lead", "leadFt", Number, (v) => {
    document.getElementById("val-lead").textContent = `${v} ft`;
  });
  bind("rng-arm-offset", "armOffset", Number, (v) => {
    document.getElementById("val-arm-offset").textContent = `${v > 0 ? "+" : ""}${v} mph`;
  });
  bind("rng-ex-offset", "exchangeOffset", Number, (v) => {
    document.getElementById("val-ex-offset").textContent = `${v > 0 ? "+" : ""}${v.toFixed(2)} s`;
  });

  document.getElementById("sel-runner-preset").addEventListener("change", (e) => {
    const v = parseFloat(e.target.value);
    state.runner90 = v;
    document.getElementById("rng-runner-90").value = v;
    document.getElementById("val-runner-90").textContent = `${v.toFixed(2)} s`;
    renderAll();
  });

  document.getElementById("btn-print").addEventListener("click", () => window.print());
  document.getElementById("btn-reset").addEventListener("click", () => window.location.reload());

  bindHoverProbe("svg-left");
  bindHoverProbe("svg-right");
}

async function init() {
  const resp = await fetch("data/force_3b_model_data.json");
  MODEL_DATA = await resp.json();

  document.getElementById("meta-play-count").textContent =
    `2026 MLB 實戰內野事件：${MODEL_DATA.meta.total_infield_plays.toLocaleString()} 筆`;

  const presetSel = document.getElementById("sel-runner-preset");
  MODEL_DATA.runner_presets.forEach((rp, idx) => {
    const opt = document.createElement("option");
    opt.value = rp.sec_90ft;
    opt.textContent = `${rp.tier} — ${rp.name} (${rp.sec_90ft}s)`;
    if (idx === 3) opt.selected = true;
    presetSel.appendChild(opt);
  });

  state.runner90 = MODEL_DATA.runner_presets[3].sec_90ft;
  document.getElementById("rng-runner-90").value = state.runner90;
  document.getElementById("val-runner-90").textContent = `${state.runner90.toFixed(2)} s`;

  bindControls();
  renderAll();
}

init();
