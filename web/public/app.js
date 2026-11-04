// Czarterowe okazje: renders deals.json (scripts/export_deals.py). No framework, no build.
// All data goes into the DOM via textContent, never innerHTML.

const CONFIG = {
  donateUrl: null,          // e.g. "https://buycoffee.to/<name>"; the link stays hidden while null
  bookingUrl: "https://r.pl/bilety-czarterowe",
  staleAfterHours: 14,      // ingest runs every 6 h; two missed runs = warn
};

// useGrouping "always": pl-PL skips the separator for 4-digit numbers by default (1249 vs 1 249).
const zl = new Intl.NumberFormat("pl-PL", { maximumFractionDigits: 0, useGrouping: "always" });
const pct = new Intl.NumberFormat("pl-PL", { maximumFractionDigits: 1 });
const num = new Intl.NumberFormat("pl-PL", { useGrouping: "always" });
const dayMonth = new Intl.DateTimeFormat("pl-PL", { day: "numeric", month: "short" });
const fullDate = new Intl.DateTimeFormat("pl-PL", { day: "numeric", month: "short", year: "numeric" });
const dateTime = new Intl.DateTimeFormat("pl-PL", { day: "numeric", month: "long", hour: "2-digit", minute: "2-digit" });

const $ = (sel) => document.querySelector(sel);
const d = (iso) => new Date(`${iso}T00:00:00`);

function el(tag, attrs = {}, ...children) {
  const node = document.createElement(tag);
  for (const [k, v] of Object.entries(attrs)) {
    if (k === "class") node.className = v;
    else if (k === "style") for (const [p, val] of Object.entries(v)) node.style.setProperty(p, val);
    else node.setAttribute(k, v);
  }
  for (const c of children.flat()) if (c != null) node.append(c);
  return node;
}

const money = (v) => `${zl.format(v)} zł`;
const days = (n) => `${n} ${n === 1 ? "dzień" : "dni"}`;

function dataSource() {
  // ?src=../dev/sample-deals.json for local previews only; production always reads deals.json.
  const src = new URLSearchParams(location.search).get("src");
  const local = ["localhost", "127.0.0.1"].includes(location.hostname);
  return local && src && /^[\w./-]+\.json$/.test(src) ? src : "deals.json";
}

async function load() {
  const res = await fetch(dataSource(), { cache: "no-cache" });
  if (!res.ok) throw new Error(`HTTP ${res.status}`);
  return res.json();
}

// ---------- status ----------

function renderStatus(data) {
  const s = data.status;
  const box = $("#status");
  box.replaceChildren();

  const updated = s.last_successful_fetch ? new Date(s.last_successful_fetch) : null;
  const stale = !updated || Date.now() - updated.getTime() > CONFIG.staleAfterHours * 3600e3;
  box.classList.toggle("stale", stale);

  const meta = el("p", { class: "meta" },
    updated ? `Ostatnie sprawdzenie cen: ${dateTime.format(updated)}. ` : "",
    `Śledzimy ${num.format(s.flights_priced ?? 0)} lotów.`);

  if (data.deals.length) {
    box.append(
      el("h2", {}, dealsHeadline(data.deals.length)),
      el("p", {}, `Ceny z ${fullDate.format(d(data.as_of))}, porównane ze średnią z ${data.params.window_days} poprzednich dni.`),
      meta,
    );
  } else if ((s.segments_with_baseline ?? 0) === 0) {
    const window = data.params.window_days;
    const hist = s.history_days ?? 0;
    box.append(
      el("h2", {}, "Zbieramy historię cen"),
      el("p", {}, `Ceny sprawdzamy od ${s.first_snapshot_date ? fullDate.format(d(s.first_snapshot_date)) : "niedawna"}. ` +
        "Okazję można ogłosić dopiero wtedy, gdy mamy z czym porównać dzisiejszą cenę: ceny z poprzednich dni dla co najmniej " +
        `${data.params.min_baseline_flights} podobnych lotów. Pierwsze okazje pojawią się w ciągu kilku dni.`),
      progressRow("Dni historii", hist, window, `${hist} z ${window}`),
      progressRow("Trasy gotowe do porównania", s.segments_with_baseline ?? 0, s.segments_upcoming || 1,
        `${num.format(s.segments_with_baseline ?? 0)} z ${num.format(s.segments_upcoming ?? 0)}`),
      meta,
    );
  } else {
    box.append(
      el("h2", {}, "Dziś bez okazji"),
      el("p", {}, `Żaden lot nie kosztuje dziś co najmniej ${pct.format(data.params.discount_threshold * 100)}% mniej niż średnia. ` +
        `Porównujemy ${num.format(s.segments_with_baseline)} tras; sprawdzamy ceny co 6 godzin.`),
      meta,
    );
  }
  if (stale) box.append(el("p", {}, "Dane mogą być nieaktualne: ostatnie sprawdzenie cen było dawno. Przed zakupem sprawdź cenę u organizatora."));
}

function dealsHeadline(n) {
  const word = n === 1 ? "okazja" : n % 10 >= 2 && n % 10 <= 4 && (n % 100 < 12 || n % 100 > 14) ? "okazje" : "okazji";
  return `${n} ${word} na dziś`;
}

function progressRow(label, value, max, text) {
  const share = Math.max(0, Math.min(1, value / max));
  return el("div", { class: "progress-row" },
    el("span", {}, label),
    el("div", { class: "bar", role: "presentation" }, el("span", { style: { width: `${share * 100}%` } })),
    el("output", {}, text));
}

// ---------- deals ----------

function ruler(deal) {
  const lo = Math.min(deal.current_price, deal.threshold_price) * 0.9;
  const hi = deal.baseline_used * 1.06;
  const x = (v) => `${((v - lo) / (hi - lo)) * 100}%`;
  const label = `Średnia ${money(deal.baseline_used)}, próg ${money(deal.threshold_price)}, cena dziś ${money(deal.current_price)}`;
  return el("div", { class: "ruler", role: "img", "aria-label": label },
    el("div", { class: "axis" }),
    el("div", { class: "zone", style: { left: "0", width: x(deal.threshold_price) } }),
    el("div", { class: "mark avg", style: { left: x(deal.baseline_used) } }),
    el("div", { class: "mark thr", style: { left: x(deal.threshold_price) } }),
    el("span", { class: "lbl avg", style: { left: x(deal.baseline_used) } }, `średnia ${money(deal.baseline_used)}`),
    el("span", { class: "lbl thr", style: { left: x(deal.threshold_price) } }, `próg ${money(deal.threshold_price)}`),
    el("div", { class: "dot", style: { left: x(deal.current_price), "--from": x(deal.baseline_used) } }));
}

function proof(deal, params) {
  const factor = num.format(1 - params.discount_threshold);
  const other = params.baseline_stat === "median"
    ? `średnia ${money(deal.baseline_avg)}` : `mediana ${money(deal.baseline_median)}`;
  return el("p", { class: "proof" },
    el("span", { class: "eq" },
      el("span", { class: "ok" }, money(deal.current_price)),
      ` ≤ ${factor} × ${money(deal.baseline_used)} = ${money(deal.threshold_price)}`),
    el("span", { class: "src" },
      `${pct.format(deal.discount_pct)}% poniżej ${params.baseline_stat === "median" ? "mediany" : "średniej"} ` +
      `(${other}). Policzone z ${deal.baseline_flights} lotów i ${num.format(deal.baseline_obs)} odczytów cen ` +
      `z dni ${fullDate.format(d(deal.window_start))} – ${fullDate.format(d(deal.window_end))}.`));
}

// Regular airlines on the same route (Aviasales data). Context only: it never decides a deal.
const AVIASALES = "https://www.aviasales.com/";

function market(deal, params) {
  const m = deal.market;
  if (!m) return null;  // segment not checked recently
  const tol = params.market_stay_tolerance_days ?? 2;
  const checked = m.checked_at ? `Sprawdzono ${dayMonth.format(new Date(m.checked_at))}.` : "";
  if (m.price == null) {
    return el("p", { class: "market" },
      `Linie regularne: w danych Aviasales brak lotów bez przesiadek w tym miesiącu ` +
      `przy podobnej długości pobytu (±${days(tol)}). ${checked}`);
  }
  const when = m.same_dates ? "te same daty"
    : `${dayMonth.format(d(m.outbound_date))} – ${dayMonth.format(d(m.return_date))}`;
  const from = m.origin_airport && m.origin_airport !== deal.origin_iata
    ? `, wylot: ${m.origin_airport_name ?? m.origin_airport}` : "";
  const diff = deal.current_price - m.price;
  const cmp = Math.abs(diff) < 1 ? "Czarter kosztuje tyle samo."
    : `Czarter jest o ${money(Math.abs(diff))} ${diff > 0 ? "droższy" : "tańszy"}.`;
  const url = typeof m.url === "string" && m.url.startsWith(AVIASALES) ? m.url : AVIASALES;
  return el("p", { class: "market" },
    "Linie regularne bez przesiadek: ", el("b", {}, `od ${money(m.price)}`),
    ` (${m.airline_name}, ${when}${from}), cena bez bagażu rejestrowanego. ${cmp} `,
    "Źródło: ", el("a", { href: url, rel: "noopener nofollow", target: "_blank" }, "Aviasales"),
    m.found_date ? `, cena znaleziona ${dayMonth.format(d(m.found_date))}.` : ".");
}

function strip(deal, params) {
  const out = d(deal.outbound_date);
  const back = deal.return_date ? d(deal.return_date) : null;
  const when = back
    ? `${dayMonth.format(out)} – ${fullDate.format(back)}, ${days(deal.stay_days)}`
    : `${fullDate.format(out)}, w jedną stronę`;
  return el("li", { class: "strip" },
    el("div", { class: "strip-route" },
      el("span", { "aria-hidden": "true" }, deal.origin_iata),
      el("span", { "aria-hidden": "true" }, deal.dest_iata),
      el("small", {}, deal.flight_no ? `lot ${deal.flight_no}` : "")),
    el("div", { class: "strip-body" },
      el("h3", {}, `${deal.origin_name} – ${deal.dest_name}`, deal.dest_country ? `, ${deal.dest_country}` : ""),
      el("p", { class: "when" }, when),
      ruler(deal),
      proof(deal, params),
      market(deal, params)),
    el("div", { class: "strip-price" },
      el("span", { class: "now" }, money(deal.current_price)),
      el("span", { class: "per" }, "za osobę, tam i z powrotem"),
      el("span", { class: "off" }, `−${pct.format(deal.discount_pct)}%`),
      el("a", { href: CONFIG.bookingUrl, rel: "noopener", target: "_blank" }, "Sprawdź na r.pl")));
}

function renderDeals(data) {
  const list = $("#list");
  const origin = $("#origin").value;
  const sort = $("#sort").value;
  const rows = data.deals.filter((x) => !origin || x.origin_iata === origin);
  const by = {
    discount: (a, b) => b.discount_pct - a.discount_pct || a.current_price - b.current_price,
    price: (a, b) => a.current_price - b.current_price,
    date: (a, b) => a.outbound_date.localeCompare(b.outbound_date),
  }[sort];
  list.replaceChildren(...rows.sort(by).map((x) => strip(x, data.params)));
}

function setupToolbar(data) {
  if (!data.deals.length) return;
  const origins = new Map(data.deals.map((x) => [x.origin_iata, x.origin_name]));
  const select = $("#origin");
  for (const [code, name] of [...origins].sort((a, b) => a[1].localeCompare(b[1], "pl"))) {
    select.append(el("option", { value: code }, name));
  }
  $("#toolbar").hidden = false;
  select.addEventListener("change", () => renderDeals(data));
  $("#sort").addEventListener("change", () => renderDeals(data));
}

function renderZones(data) {
  const names = { short: "do 3 h lotu", medium: "3–5,5 h", long: "5,5–8 h", exotic: "ponad 8 h" };
  const parts = data.zones.map((z) => `${names[z.zone] ?? z.zone}: min. ${days(z.min_sensible_stay_days)}`);
  if (parts.length) $("#zones-text").textContent =
    `Pomijamy wyjazdy zbyt krótkie jak na odległość (${parts.join("; ")}). Takie loty nie liczą się też do średniej.`;
}

function setupDonate() {
  if (!CONFIG.donateUrl) return;
  $("#donate-link").href = CONFIG.donateUrl;
  $("#donate").hidden = false;
}

async function main() {
  setupDonate();
  try {
    const data = await load();
    renderStatus(data);
    renderZones(data);
    setupToolbar(data);
    renderDeals(data);
    $("#list").classList.add("reveal");
  } catch (err) {
    const box = $("#status");
    box.classList.add("error");
    box.replaceChildren(
      el("h2", {}, "Nie udało się wczytać okazji"),
      el("p", {}, "Odśwież stronę za chwilę. Jeśli problem się powtarza, dane mogą być właśnie aktualizowane."),
      el("p", { class: "meta" }, String(err.message || err)));
  }
}

main();
