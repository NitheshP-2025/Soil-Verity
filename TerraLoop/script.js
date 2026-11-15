const $ = (id) => document.getElementById(id);
const form = $("farmForm");
const resultContent = $("resultContent");
const status = $("formStatus");

function escapeHtml(value) {
  return String(value ?? "").replace(/[&<>"']/g, (char) => ({
    "&": "&amp;", "<": "&lt;", ">": "&gt;", '"': "&quot;", "'": "&#39;"
  })[char]);
}

async function loadCrops() {
  try {
    const response = await fetch("/api/crops");
    if (!response.ok) throw new Error("Could not load crop list");
    const { crops } = await response.json();
    ["crop1", "crop2", "crop3"].forEach((id, index) => {
      const select = $(id);
      select.innerHTML = crops.map((crop) => `<option value="${escapeHtml(crop)}">${escapeHtml(crop)}</option>`).join("");
      select.value = index < 2 ? "Rice (short duration)" : "Fallow";
    });
    status.textContent = "Connected to local SoilVerity engine";
  } catch (error) {
    status.textContent = "Start the app with: python backend/server.py";
    status.classList.add("error");
  }
}

function optionCard(option) {
  const score = Math.round(option.mean_score * 100);
  const stability = option.stability;
  const stress = Object.entries(option.facts.shortage_share_by_season || {})
    .map(([season, share]) => `${season}: ${Math.round(share * 100)}% stress`).join(" · ");
  const badges = Object.entries(option.lights || {}).map(([name, light]) =>
    `<span class="chip">${escapeHtml(name.replace("_", " "))}: ${escapeHtml(light)}</span>`).join("");
  return `<article class="option">
    <div class="option-top"><span class="tag">#${option.rank}${option.is_current ? " · CURRENT" : ""}${option.is_top ? " · TOP PICK" : ""}</span><strong>${score}/100</strong></div>
    <h3>${escapeHtml(option.name)}</h3><div class="scorebar"><span style="width:${score}%"></span></div>
    <p>Trust stability: <strong>${escapeHtml(stability.label)}</strong> · first in ${stability.first_in} of ${stability.of} checks</p>
    <div class="chips">${badges}</div>
    <p class="demo-note">Estimated irrigation need: ${option.facts.irrigation_needed_mm} mm per season-cycle · ${escapeHtml(stress || "Seasonal stress not reported")}</p>
  </article>`;
}

function renderResult(data) {
  const verdict = data.verdict;
  const decision = verdict.decision || "review";
  const assumptions = (data.assumptions || []).map((item) =>
    `<li>${escapeHtml(item.input.replaceAll("_", " "))}: ${escapeHtml(item.note)}</li>`).join("") || "<li>All key soil and irrigation inputs supplied.</li>";
  const decisive = data.decisive_check
    ? `<p><strong>Input that could change the top pick:</strong> ${escapeHtml(data.decisive_check.label)} · low: ${escapeHtml(data.decisive_check.top_if_low)} · high: ${escapeHtml(data.decisive_check.top_if_high)}</p>`
    : "<p>No missing input changed the top rotation in this run.</p>";
  resultContent.innerHTML = `
    <div class="verdict"><span class="tag">ENGINE VERDICT</span><h3>${escapeHtml(decision.toUpperCase())} · ${escapeHtml(verdict.reason_code.replaceAll("_", " "))}</h3>
      <p>Best: <strong>${escapeHtml(verdict.best)}</strong></p><p>Current: ${escapeHtml(verdict.current)}</p>
      <p>Win rate: ${Math.round((verdict.win_rate || 0) * 100)}% · Median score gap: ${verdict.median_gap}</p></div>
    <h3>Rotation options</h3><div class="options">${data.options.map(optionCard).join("")}</div>
    <div class="trust-grid">
      <div class="trust-card"><h3>Climate source agreement</h3><p>${data.source_agreement.agree ? "Sources agree" : "Sources do not all agree"} across ${data.source_agreement.n_combos} source combinations.</p><p class="demo-note">Checks per option: ${data.meta.checks_per_option}; data years: ${(data.meta.years || []).join(", ")}</p></div>
      <div class="trust-card"><h3>What is assumed?</h3><ul>${assumptions}</ul></div>
    </div>
    <div class="trust-card" style="margin-top:14px"><h3>Decision sensitivity</h3>${decisive}<p>${data.weights_flip_top ? "Changing priority weights can change the top option." : "Top option stayed stable under tested priority changes."}</p></div>
    <div class="demo-banner">${escapeHtml(data.demo_notice)} Results compare rotations for this demo farm; they are not yield or income forecasts.</div>`;
}

form?.addEventListener("submit", async (event) => {
  event.preventDefault();
  const button = $("runButton");
  button.disabled = true;
  status.classList.remove("error");
  status.textContent = "Running crop rotation analysis…";
  resultContent.innerHTML = "<p>Scoring crop rotations against the demo climate set…</p>";
  const numberOrNull = (id) => $(id).value === "" ? null : Number($(id).value);
  const payload = {
    water_source: $("water").value,
    start_season: $("startSeason").value,
    current_rotation: [$("crop1").value, $("crop2").value, $("crop3").value],
    soil: { ph: numberOrNull("soilPh"), ec: numberOrNull("soilEc"), organic_carbon: numberOrNull("organicCarbon") },
    priorities: {
      water: Number($("priorityWater").value), soil: Number($("prioritySoil").value),
      cost: Number($("priorityCost").value), risk: Number($("priorityRisk").value)
    }
  };
  try {
    const response = await fetch("/api/recommendations", {
      method: "POST", headers: { "Content-Type": "application/json" }, body: JSON.stringify(payload)
    });
    const data = await response.json();
    if (!response.ok) throw new Error(data.error || "The recommendation request failed.");
    renderResult(data);
    status.textContent = `Report generated for ${$("location").value || "your farm"}`;
    $("results").scrollIntoView({ behavior: "smooth", block: "start" });
  } catch (error) {
    status.textContent = error.message;
    status.classList.add("error");
    resultContent.innerHTML = `<p class="error">${escapeHtml(error.message)}. Make sure the app server is running.</p>`;
  } finally {
    button.disabled = false;
  }
});

$("themeToggle")?.addEventListener("click", (event) => {
  document.body.classList.toggle("dark-mode");
  event.currentTarget.textContent = document.body.classList.contains("dark-mode") ? "☀️" : "🌙";
});

loadCrops();
