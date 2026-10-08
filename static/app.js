const TZ_HOURS = 5; // часовой пояс водителя, совпадает с DRIVER_TZ_OFFSET на сервере
const TZ = "+" + String(TZ_HOURS).padStart(2, "0") + ":00";
const $ = (id) => document.getElementById(id);
const money = (n) => n.toLocaleString("ru-RU") + " ₸";
const PAYMENT = { cash: "Наличные", card: "Карта" };
const plural = new Intl.PluralRules("ru-RU");
const TRIPS_WORD = { one: "поездка", few: "поездки", many: "поездок", other: "поездки" };
const tripsLabel = (n) => `${n} ${TRIPS_WORD[plural.select(n)]}`;

function shiftDay(iso, delta) {
  const d = new Date(iso + "T00:00:00Z");
  d.setUTCDate(d.getUTCDate() + delta);
  return d.toISOString().slice(0, 10);
}

// Время в поясе водителя, а не браузера: "2026-10-01T08:10:00+05:00" -> "2026-10-01 08:10"
function toDriverTz(iso) {
  const shifted = new Date(new Date(iso).getTime() + TZ_HOURS * 3600e3);
  return shifted.toISOString().slice(0, 16).replace("T", " ");
}

async function load(day) {
  $("day").value = day;
  history.replaceState(null, "", "#" + day);
  const res = await fetch("/api/days/" + day);
  const { summary: s, trips } = await res.json();

  $("s-count").textContent = s.trips_count;
  $("s-revenue").textContent = money(s.revenue);
  $("s-commission").textContent = money(s.commission);
  $("s-net").textContent = money(s.net);
  $("s-cash").textContent = money(s.cash.amount);
  $("s-cash-n").textContent = tripsLabel(s.cash.count);
  $("s-card").textContent = money(s.card.amount);
  $("s-card-n").textContent = tripsLabel(s.card.count);

  $("trips").innerHTML = "";
  for (const t of trips) {
    const mins = Math.round((new Date(t.end) - new Date(t.start)) / 60000);
    const tr = document.createElement("tr");
    const end = toDriverTz(t.end);
    const endLabel = end.slice(0, 10) === day ? end.slice(11) : end.slice(11) + " (+1)";
    for (const [text, cls] of [
      [`${toDriverTz(t.start).slice(11)}–${endLabel}`, ""],
      [mins + " мин", ""],
      [PAYMENT[t.payment], ""],
      [money(t.amount), "num"],
      [money(t.commission), "num"],
    ]) {
      const td = document.createElement("td");
      td.textContent = text;
      if (cls) td.className = cls;
      tr.append(td);
    }
    $("trips").append(tr);
  }
  $("empty").hidden = trips.length > 0;
}

function errorText(body) {
  if (typeof body.detail === "string") return body.detail;
  if (Array.isArray(body.detail)) return body.detail.map((e) => e.msg.replace(/^Value error, /, "")).join("; ");
  return "Ошибка сервера";
}

$("add").addEventListener("submit", async (e) => {
  e.preventDefault();
  const f = new FormData(e.target);
  const day = $("day").value;
  const start = `${day}T${f.get("start")}:00${TZ}`;
  // Если окончание раньше начала по часам — поездка закончилась после полуночи.
  const endDay = f.get("end") < f.get("start") ? shiftDay(day, 1) : day;
  const trip = {
    start,
    end: `${endDay}T${f.get("end")}:00${TZ}`,
    amount: Number(f.get("amount")),
    commission: Number(f.get("commission")),
    payment: f.get("payment"),
  };
  const res = await fetch("/api/trips", {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify(trip),
  });
  const body = await res.json();
  const msg = $("msg");
  if (res.status === 201) { msg.className = "ok"; msg.textContent = "Поездка добавлена."; e.target.reset(); }
  else if (res.status === 200) { msg.className = "ok"; msg.textContent = "Такая поездка уже есть — дубль не создан."; }
  else { msg.className = "error"; msg.textContent = errorText(body); }
  load(day);
});

$("prev").onclick = () => load(shiftDay($("day").value, -1));
$("next").onclick = () => load(shiftDay($("day").value, 1));
$("day").onchange = (e) => e.target.value && load(e.target.value);

(async () => {
  const fromHash = location.hash.slice(1);
  if (/^\d{4}-\d{2}-\d{2}$/.test(fromHash)) return load(fromHash);
  const days = await (await fetch("/api/days")).json();
  load(days.at(-1) ?? new Date().toISOString().slice(0, 10));
})();
