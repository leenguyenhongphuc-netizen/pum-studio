
"use strict";
const T = window.TRIP;
const $ = s => document.querySelector(s);
const esc = s => String(s ?? "").replace(/[&<>"']/g, c => ({"&":"&amp;","<":"&lt;",">":"&gt;",'"':"&quot;","'":"&#39;"}[c]));
const fmtVND = n => Math.round(n).toLocaleString("vi-VN") + "đ";
const fmtTr = n => (n/1e6).toLocaleString("vi-VN",{maximumFractionDigits:1}) + " triệu";
const img = k => k ? `img/${k}.jpg` : "";
const ICON = {
  fx:'<svg width="22" height="22" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2.2"><rect x="3" y="5" width="18" height="14" rx="3"/><path d="M10 9l5 3-5 3z"/></svg>',
  today:'<svg width="22" height="22" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2.2"><path d="M12 20s-7-4.4-7-10a4 4 0 0 1 7-2.6A4 4 0 0 1 19 10c0 5.6-7 10-7 10z"/></svg>',
  trip:'<svg width="22" height="22" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2.2"><path d="M4 19c4 0 3-6 8-6s4-6 8-6"/><circle cx="4" cy="19" r="1.5"/><circle cx="20" cy="7" r="1.5"/></svg>',
  money:'<svg width="22" height="22" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2.2"><rect x="3" y="6" width="18" height="12" rx="3"/><circle cx="12" cy="12" r="2.5"/></svg>',
  prod:'<svg width="22" height="22" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2.2"><rect x="7" y="3" width="10" height="18" rx="2.5"/><path d="M11 17h2"/></svg>',
  brand:'<svg width="22" height="22" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2.2"><path d="M5 6l14-2-1 6-14 2z"/><path d="M6 14h12v6H6z"/></svg>'
};
const ROUTES = [
  {k:"hom-nay", name:"Hôm nay", icon:ICON.today},
  {k:"lich-trinh", name:"Lịch trình", icon:ICON.trip},
  {k:"san-xuat", name:"Quay & dựng", tab:"Quay", icon:ICON.prod},
  {k:"chi-tieu", name:"Chi tiêu", icon:ICON.money},
  {k:"kenh", name:"Cẩm nang", icon:ICON.brand}
];
const LS = {
  get(k, d){ try{ const v = localStorage.getItem("pum:"+k); return v ? JSON.parse(v) : d; }catch(e){ return d; } },
  set(k, v){ try{ localStorage.setItem("pum:"+k, JSON.stringify(v)); }catch(e){} }
};

/* ---------- dữ liệu ---------- */
const S = { db:null, assets:null, sample:null, dictation:null,
  expenses:{}, days:{}, beats:{}, vids:{}, prep:{}, settings:{rate:T.rate, budget:0, plans:{}},
  scripts:{}, sync:"Đang mở dữ liệu…", previewDay: LS.get("previewDay", null) };
const COLS = ["expenses","days","beats","vids","prep","settings"];
async function put(col, id, data){
  S[col][id] = Object.assign({}, S[col][id] || {}, data);
  if (S.db){
    const clean = {}; Object.keys(S[col][id]).forEach(k => { if (k[0] !== "_") clean[k] = S[col][id][k]; });
    try{ await S.db.doc(col+"/"+id).set(clean); }
    catch(e){ toast(e && e.code === "quota_exceeded" ? "Hết chỗ lưu dữ liệu." : "Chưa lưu được, thử lại sau."); }
  } else LS.set(col, S[col]);
  render();
}
async function del(col, id){
  delete S[col][id];
  if (S.db){ try{ await S.db.doc(col+"/"+id).delete(); }catch(e){ toast("Chưa xóa được."); } }
  else LS.set(col, S[col]);
  render();
}
async function setSetting(o){
  S.settings = Object.assign({}, S.settings, o);
  if (S.db){ try{ await S.db.doc("settings/main").set(S.settings); }catch(e){ toast("Chưa lưu được."); } } else LS.set("settings", S.settings);
  render();
}
async function boot(){
  COLS.forEach(c => { const v = LS.get(c, null); if (v) S[c] = Object.assign(S[c], v); });
  render();
  if (!window.claude || !window.claude.use){ S.sync = "Lưu trên máy này"; render(); return; }
  const timer = setTimeout(()=>{ if (!S.db){ S.sync = "Lưu trên máy này"; render(); } }, 10000);
  try{
    const db = await window.claude.use("db");
    if (db){
      S.db = db; S.sync = "Đang đồng bộ…"; render();
      COLS.forEach(c => {
        db.collection(c).onSnapshot(snap => {
          const o = {}; snap.docs.forEach(d => { o[d.id] = d.data(); });
          if (c === "settings") S.settings = Object.assign({rate:T.rate, budget:0, plans:{}}, (o.main||{}));
          else { if (c === "beats") Object.keys(o).forEach(k => { if (S.beats[k] && S.beats[k]._open) o[k] = Object.assign({}, o[k], {_open:true}); }); S[c] = o; }
          if (!snap.metadata.fromCache){ clearTimeout(timer); S.sync = "Đã đồng bộ"; }
          renderSoon();
        }, () => { S.sync = "Mất kết nối dữ liệu"; render(); });
      });
    } else { S.sync = "Lưu trên máy này"; render(); }
  }catch(e){ S.sync = "Lưu trên máy này"; render(); }
  try{ S.assets = await window.claude.use("assets"); }catch(e){}
  try{ S.sample = await window.claude.use("sample"); }catch(e){}
  try{ S.dictation = await window.claude.use("dictation"); }catch(e){}
  try{ S.downloads = await window.claude.use("downloads"); }catch(e){}
  render();
}
const rate = () => Number(S.settings.rate || T.rate);

/* ---------- ngày ---------- */
function todayISO(){ const d = new Date(); return new Date(d.getTime() - d.getTimezoneOffset()*60000).toISOString().slice(0,10); }
function isoOfDay(n){ const d = new Date(T.start+"T00:00:00"); d.setDate(d.getDate()+n-1); return d; }
function realTripDay(){ return Math.round((new Date(todayISO()+"T00:00:00") - new Date(T.start+"T00:00:00"))/86400000) + 1; }
const tripDay = () => S.previewDay ? Number(S.previewDay) : realTripDay();
const dayObj = d => T.days.find(x => x.d === d);
const stObj = n => T.stages.find(s => s.n === n);
const ddmm = dt => `${dt.getDate()}/${dt.getMonth()+1}`;
const WD = ["CN","T2","T3","T4","T5","T6","T7"];
/* ---------- kịch bản ---------- */
const HOW = "“Nói tại chỗ” là câu Pum nói lúc cầm máy, đọc lướt cho nhớ ý rồi nói bằng giọng mình. Chỗ trong ngoặc tròn là phản ứng thật, thấy sao nói vậy. “Lồng tiếng” thu sau khi về phòng, sửa theo chuyện thật đã xảy ra. Chỗ ___ là số thật, quay xong mới điền. “Quay thêm” là cảnh nền để lúc dựng có chỗ đặt lồng tiếng.";
async function loadScript(n){
  if (S.scripts[n]) return S.scripts[n];
  try{ const r = await fetch(`scripts/tap${n}.enc?v=${window.PUMV}`); if (!r.ok) throw 0; S.scripts[n] = parseScript(await window.PUMDEC(await r.arrayBuffer()), n); }
  catch(e){ S.scripts[n] = {error:true, sections:[], meta:{}, title:""}; }
  return S.scripts[n];
}
function inline(s){ s = esc(s); return s.replace(/\*\*(.+?)\*\*/g, "<b>$1</b>"); }
function parseScript(md, n){
  const out = {n, title:"", meta:{}, sections:[]}; let sec = null, beat = null;
  for (const raw of md.split("\n")){
    const l = raw.trim(); if (!l) continue;
    if (l.startsWith("# ")){ out.title = l.slice(2); continue; }
    if (l.startsWith("## ")){
      const t = l.slice(3), id = `t${n}s${out.sections.length}`;
      const dm = t.match(/^Ngày (\d+) · (.+?)\s+—\s+(.+)$/);
      if (dm) sec = {kind:"day", id, d:Number(dm[1]), when:dm[2], title:dm[3], q:"", beats:[]};
      else if (/^(Mở tập|Cuối tập)/.test(t)) sec = {kind:"part", id, when:"", title:t, q:"", beats:[]};
      else if (/^Chương \d+/.test(t)){ const pm = t.match(/\(([^)]*)\)\s*$/); sec = {kind:"part", ch:true, id, when:pm?pm[1]:"", title:t, q:"", beats:[]}; }
      else sec = {kind:"list", id, title:t, list:[]};
      out.sections.push(sec); beat = null; continue;
    }
    if (!sec){ const m = l.match(/^\*\*(.+?):\*\*\s*(.*)$/); if (m) out.meta[m[1]] = m[2]; continue; }
    if (sec.kind === "list"){ sec.list.push(l.replace(/^- /,"")); continue; }
    if (/^\*[^*].*\*$/.test(l)){ sec.q = l.slice(1,-1).replace(/^Câu hỏi của ngày:\s*/,""); sec.q = sec.q.charAt(0).toUpperCase() + sec.q.slice(1); continue; }
    const bm = l.match(/^\*\*([^*]+)\*\*$/);
    if (bm){ beat = {title:bm[1], items:[], key:`${sec.id}b${sec.beats.length}`}; sec.beats.push(beat); continue; }
    if (l.startsWith("- ") && beat){ const im = l.slice(2).match(/^\*\*(.+?):\*\*\s*(.*)$/); beat.items.push(im ? {k:im[1], v:im[2]} : {k:"", v:l.slice(2)}); }
  }
  if (!out.meta["Cách đọc"] || /như tập/.test(out.meta["Cách đọc"])) out.meta["Cách đọc"] = HOW;
  return out;
}
const listSec = (sc, re) => sc.sections.find(s => s.kind === "list" && re.test(s.title));

/* ---------- tiền ---------- */
const expenseList = () => Object.entries(S.expenses).map(([id,e]) => Object.assign({id}, e)).filter(e => typeof e.amt === "number");
const spentTotal = () => expenseList().reduce((a,e)=>a+e.amt,0);
const spentBy = c => expenseList().filter(e=>e.cat===c).reduce((a,e)=>a+e.amt,0);
const spentDay = d => expenseList().filter(e=>Number(e.day)===d).reduce((a,e)=>a+e.amt,0);
const planOf = k => { const p = (S.settings.plans||{})[k]; if (p != null && p !== "") return Number(p); const b = T.budgetLines.find(x=>x.k===k); return b && b.plan || 0; };

/* ---------- khung ---------- */
let toastTimer;
function toast(t){ let el = $("#toast"); if (!el){ el = document.createElement("div"); el.id="toast"; el.className="toast"; el.setAttribute("role","status"); document.body.appendChild(el); } el.textContent = t; el.style.display="block"; clearTimeout(toastTimer); toastTimer = setTimeout(()=>el.style.display="none", 2600); }
function route(){ const h = location.hash.replace(/^#\/?/,"") || "hom-nay"; const [k, a, b] = h.split("/"); return {k, a, b}; }
function renderShell(){
  const r = route();
  const cur = r.k === "hieu-ung" ? "kenh" : r.k;
  const items = ROUTES.map(x => `<a href="#/${x.k}" ${cur===x.k?'aria-current="page"':''}>${x.icon}<span>${x.name}</span></a>`).join("");
  $("#nav").innerHTML = items; $("#tabbar").innerHTML = ROUTES.map(x => `<a href="#/${x.k}" ${cur===x.k?'aria-current="page"':''}>${x.icon}<span>${x.tab||x.name}</span></a>`).join("");
  const d = tripDay();
  $("#railFoot").innerHTML = `<img src="brand/hello.png" alt=""><b>Thái Lan</b> · 7/12/2026 – 3/1/2027<br>${esc(S.sync)}`;
  $("#syncTop").textContent = d < 1 ? `còn ${1-d} ngày` : (d <= 28 ? `ngày ${d}/28` : "đã về");
}
let lastRouteKey = null, relaxT = null, rsT = null;
function renderSoon(){ if (rsT) return; rsT = requestAnimationFrame(() => { rsT = null; render(); }); }
function render(){
  renderShell();
  const r = route(), v = $("#view");
  const rk = location.hash, same = rk === lastRouteKey; lastRouteKey = rk;
  const y = window.scrollY;
  if (same){ v.style.minHeight = v.offsetHeight + "px"; clearTimeout(relaxT); relaxT = setTimeout(() => { v.style.minHeight = ""; }, 800); }
  const fn = {"hom-nay":vToday, "lich-trinh":vTrip, "chi-tieu":vMoney, "san-xuat":vProd, "kenh":vBrand, "hieu-ung":(v)=>vBrand(v,{k:"kenh",a:"hieu-ung"})}[r.k] || vToday;
  const active = document.activeElement && document.activeElement.id; const keepVal = active && document.activeElement.value;
  fn(v, r);
  if (active){ const el = document.getElementById(active); if (el && el !== document.activeElement){ if (keepVal != null && "value" in el && el.dataset.keep !== "0") el.value = keepVal; el.focus({preventScroll:true}); } }
  if (same && Math.abs(window.scrollY - y) > 1) window.scrollTo(0, y);
}
window.addEventListener("hashchange", () => { closeSheet(); clearTimeout(stay.t); $("#view").style.minHeight = ""; window.scrollTo(0,0); render(); });
const postcard = (k, cap) => k ? `<figure class="post"><img src="${img(k)}" alt="${esc(cap)}"><figcaption>${esc(cap)}</figcaption></figure>` : `<figure class="post plain"><img src="brand/camera.png" alt=""></figure>`;

/* ---------- Hôm nay ---------- */
const PREP = [
  ["binhchon","Đăng 9 câu bình chọn (Cẩm nang › Trước chuyến), chụp lại kết quả trước 7/12"],
  ["hochieu","Hộ chiếu còn hạn tới ít nhất tháng 6/2027"],
  ["ve","Vé máy bay đi Chiang Mai 7/12, về từ Bangkok"],
  ["dich","Cài Google Dịch, tải gói tiếng Thái để dùng khi không có mạng"],
  ["sotay","Lưu sổ tay tiếng Thái (Cẩm nang › Trước chuyến) vào điện thoại, dùng riêng"],
  ["hop","Mang một chiếc hộp nhỏ làm hộp kỷ niệm"],
  ["hoavan","Lưu hình hoa văn thắng bình chọn để đưa thợ vẽ ô ở Bo Sang"],
  ["thac","Đặt xe có tài xế hoặc tour nửa ngày đi thác Bua Thong 11/12"],
  ["giaothua","Xem chương trình giao thừa 31/12 ở ICONSIAM"],
  ["do","Đồ theo bình chọn: bộ lên đồi trà, đồ sáng lạnh ở Pai, bộ giao thừa"],
  ["leo","Quần áo mau khô để leo thác"],
  ["tdac","Khai TDAC trong 3 ngày trước khi bay"],
  ["baohiem","Mua bảo hiểm du lịch"]
];
function dayCard(o){
  return `<dl class="facts">
    <dt>Làm gì</dt><dd>${esc(o.todo)}</dd>
    ${o.move?`<dt>Đi lại</dt><dd>${esc(o.move)}</dd>`:""}
    ${o.see?`<dt>Sẽ thấy</dt><dd>${esc(o.see)}</dd>`:""}
    ${o.cost?`<dt>Giá</dt><dd>${esc(o.cost)}</dd>`:""}
    ${o.note?`<dt>Lưu ý</dt><dd>${esc(o.note)}</dd>`:""}
    ${o.map?`<dt>Bản đồ</dt><dd><a class="lnkbtn" style="background:var(--blush)" href="https://www.google.com/maps/search/?api=1&query=${encodeURIComponent(o.map)}" target="_blank" rel="noopener">Mở Google Maps</a></dd>`:""}
  </dl><a class="vchip" href="#/san-xuat/${o.st}/d${o.d}"><b>Tập ${o.st} · ${esc(stObj(o.st).place)}</b><small>Kịch bản ngày ${o.d}: quay gì, nói gì tại chỗ, lồng tiếng gì</small><span class="go">Mở</span></a>`;
}
function vToday(v){
  const d = tripDay();
  const pick = `<details class="prev"><summary>Xem thử như đang ở một ngày khác</summary><label class="f small" style="max-width:300px">Ngày
    <select id="preview"><option value="">Hôm nay thật</option>${T.days.map(x=>`<option value="${x.d}" ${Number(S.previewDay)===x.d?"selected":""}>Ngày ${x.d} · ${x.date}</option>`).join("")}</select></label></details>`;
  if (d < 1){
    const done = PREP.filter(([k])=>S.prep[k] && S.prep[k].done).length, nx = PREP.find(([k])=>!(S.prep[k] && S.prep[k].done));
    v.innerHTML = `
    <section class="banner"><img src="img/bosang.jpg" alt=""><div class="in"><p class="k">Trước chuyến đi · bay thứ Hai 7/12</p><h1 class="disp num">Còn ${1-d} ngày</h1><p class="c">28 ngày ở Thái, 7 tập YouTube</p></div></section>
    ${nx?`<section class="sec next" style="margin-top:18px"><div><span class="k">Việc tiếp theo · ${done}/${PREP.length} xong</span><b>${esc(nx[1])}</b></div><button class="btn" data-donenext="${nx[0]}">Xong</button></section>`
      :`<section class="sec next" style="margin-top:18px"><div><span class="k">${PREP.length}/${PREP.length} xong</span><b>Đã sẵn sàng bay.</b></div></section>`}
    ${T.test?`<section class="sec next testcard" style="margin-top:18px"><div><span class="k">Quay thử trước chuyến</span><b>${esc(T.test.tab)}: một ngày, tập quay và thu lồng tiếng</b></div><a class="btn" href="#/san-xuat/test">Mở</a></section>`:""}
    <section class="sec" style="margin-top:28px"><div class="quick">
      <a href="#/lich-trinh"><b>Lịch trình</b><span>28 ngày, 7 tập</span></a>
      <a href="#/san-xuat/1"><b>Kịch bản tập 1</b><span>Chiang Mai · ngày 1–5</span></a>
      <a href="#/kenh/truoc"><b>Bình chọn</b><span>9 câu đăng trước 7/12</span></a>
    </div></section>
    <section class="sec">
      <div class="sec-head"><h2 class="disp h-sec">Việc trước khi bay</h2><span class="muted num" style="font-weight:800">${done}/${PREP.length}</span></div>
      <div class="progress" style="margin-bottom:8px"><i style="width:${done/PREP.length*100}%"></i></div>
      <ul class="check">${PREP.map(([k,t])=>{const ok=S.prep[k]&&S.prep[k].done;return `<li class="${ok?"done":""}"><input type="checkbox" id="prep-${k}" data-prep="${k}" ${ok?"checked":""}><label for="prep-${k}"><span>${esc(t)}</span></label></li>`}).join("")}</ul>
    </section>
    ${pick}`;
  } else if (d > 28){
    v.innerHTML = `<section class="banner"><img src="img/fireworks.jpg" alt=""><div class="in"><p class="k">Đã về</p><h1 class="disp">Xong chuyến Thái</h1><p class="c">Tổng chi ${fmtVND(spentTotal())}</p></div></section>
    <section class="sec next"><div><span class="k">Việc tiếp theo</span><b>Dựng và đăng các tập</b></div><a class="btn" href="#/san-xuat/1">Mở</a></section>${pick}`;
  } else {
    const o = dayObj(d), st = stObj(o.st), next = dayObj(d+1), sp = spentDay(d), im = o.img || st.img;
    v.innerHTML = `
    <section class="banner ${im?"":"noimg"}">${im?`<img src="${img(im)}" alt="">`:""}<div class="in"><p class="k">${esc(o.date)} · Tập ${o.st}</p><h1 class="disp num">Ngày ${d}</h1><p class="c">${esc(o.city)}</p></div></section>
    <section class="sec card" style="margin-top:18px">
      <p class="lead" style="font-weight:800">${esc(o.todo)}</p>
      ${o.move?`<p style="margin-top:10px"><b>Đi lại.</b> ${esc(o.move)}</p>`:""}
      ${o.cost?`<p style="margin-top:6px"><b>Giá.</b> ${esc(o.cost)}</p>`:""}
      ${o.note?`<p style="margin-top:6px"><b>Lưu ý.</b> ${esc(o.note)}</p>`:""}
      <div class="row mapbtn">${o.map?`<a class="btn small rose" href="https://www.google.com/maps/search/?api=1&query=${encodeURIComponent(o.map)}" target="_blank" rel="noopener">Mở bản đồ</a>`:""}<button class="btn small ghost" data-day="${d}">Chi tiết và nhật ký</button></div>
    </section>
    <div class="bhead"><h2 class="disp">Hôm nay quay</h2><a class="lnkbtn" href="#/san-xuat/${o.st}/d${d}">Mở trong tập ${o.st}</a></div>
    <div id="todayBeats" class="muted">Đang mở kịch bản…</div>
    <section class="sec strip">
      <div class="sec-head" style="margin-bottom:10px"><h2 class="disp" style="font-size:24px">Tiêu hôm nay</h2><span class="num" style="font-weight:900">${fmtVND(sp)}</span></div>
      ${addExpenseForm(d)}
    </section>
    ${next?`<section class="sec card"><p class="eyebrowless">Ngày mai · ${esc(next.date)} · ${esc(next.city)}</p><p class="lead" style="margin-top:6px">${esc(next.todo)}</p>${next.move?`<p class="muted" style="margin-top:6px">Đi lại: ${esc(next.move)}</p>`:""}</section>`:""}
    ${pick}`;
  }
  bindCommon(v);
  const sel = $("#preview"); if (sel) sel.onchange = () => { S.previewDay = sel.value || null; LS.set("previewDay", S.previewDay); render(); };
  v.querySelectorAll("[data-prep]").forEach(c => c.onchange = () => put("prep", c.dataset.prep, {done:c.checked}));
  v.querySelectorAll("[data-donenext]").forEach(b => b.onclick = () => put("prep", b.dataset.donenext, {done:true}));
  v.querySelectorAll("[data-day]").forEach(b => b.onclick = () => openDay(Number(b.dataset.day)));
  if (d >= 1 && d <= 28){ const o = dayObj(d); loadScript(o.st).then(sc => {
    const box = $("#todayBeats"); if (!box || route().k !== "hom-nay") return;
    const sec = sc.sections.find(s => s.kind === "day" && s.d === d);
    if (!sec){ box.innerHTML = sc.error ? "Chưa mở được kịch bản." : "Hôm nay không có cảnh trong kịch bản. Nghỉ hoặc quay thêm cảnh nền."; return; }
    S.curScript = sc; box.classList.remove("muted");
    const dn = sec.beats.filter(b=>S.beats[b.key]&&S.beats[b.key].shot).length;
    box.innerHTML = `<p class="promise" style="margin-bottom:6px"><b>${esc(sec.title)}.</b> ${esc(sec.q)} <span class="muted num">· ${dn}/${sec.beats.length} cảnh</span></p>` + sec.beats.map(b => beatHTML(b)).join("");
    bindBeats(box);
  }); }
}

/* ---------- Lịch trình ---------- */
function vTrip(v){
  const d = tripDay();
  v.innerHTML = `
  <section><h1 class="disp h-hero">Lịch trình</h1>
    <p class="lead" style="margin-top:14px;max-width:60ch">28 ngày, chia theo 7 tập YouTube. Bấm vào một ngày để xem đi đâu, giá, và ghi nhật ký.</p></section>
  ${T.stages.map(st => `
  <section class="st-block">
    <div class="st-title"><h2 class="disp" style="font-size:30px">Tập ${st.n} · ${esc(st.place)}</h2><a class="lnkbtn" href="#/san-xuat/${st.n}">Kịch bản tập</a><p>${esc(st.line)}</p></div>
    ${T.days.filter(x=>x.st===st.n).map(x=>{
      const cls = x.d===d?"is-today":(x.d<d?"past":""); const note = S.days[x.d] && S.days[x.d].note;
      return `<button class="day-row ${cls}" data-day="${x.d}">
        <span class="d disp num">${x.d}<small>${esc(x.date.split(" ").slice(-1)[0])}</small></span>
        <span><span class="t" style="font-weight:900">${esc(x.city)}</span>${x.d===d?'<span class="tag">hôm nay</span>':''}${note?'<span class="tag soft">có nhật ký</span>':''}<br><span class="muted">${esc(x.todo)}</span></span>
        ${x.img?`<img src="${img(x.img)}" alt="" loading="lazy">`:'<span></span>'}
      </button>`;}).join("")}
  </section>`).join("")}`;
  v.querySelectorAll("[data-day]").forEach(b => b.onclick = () => openDay(Number(b.dataset.day)));
}
function openPic(k, cap){
  const sh = $("#sheet");
  sh.innerHTML = `<button class="btn small close" id="closeSheet">Đóng</button><img class="cover" style="height:auto;max-height:70vh;object-fit:contain;background:#2b1f25" src="${img(k)}" alt="${esc(cap)}"><div class="in"><p class="lead" style="font-weight:800">${esc(cap)}</p><p class="small muted" style="margin-top:10px">Ảnh mẫu để biết chỗ đó, món đó trông ra sao, không dùng trong video.${T.credits[k]?` Ảnh: ${esc(T.credits[k])}, Wikimedia Commons.`:""}</p></div>`;
  sh.classList.add("open"); $("#sheetBg").classList.add("open");
  $("#closeSheet").onclick = closeSheet; $("#sheetBg").onclick = closeSheet; $("#closeSheet").focus();
}
function closeSheet(){ $("#sheet").classList.remove("open"); $("#sheetBg").classList.remove("open"); }
function openDay(d){
  const o = dayObj(d), note = (S.days[d] && S.days[d].note) || "", sh = $("#sheet");
  sh.innerHTML = `
    <button class="btn small close" id="closeSheet">Đóng</button>
    ${o.img?`<img class="cover" src="${img(o.img)}" alt="${esc(o.city)}">`:""}
    <div class="in">
      <p class="muted" style="font-weight:800">${esc(o.date)} · Tập ${o.st}</p>
      <h2 class="disp" style="font-size:52px;margin:8px 0 6px">Ngày ${d}</h2>
      <p class="lead" style="margin-bottom:24px;font-weight:800">${esc(o.city)}</p>
      ${dayCard(o)}
      <label class="f" style="margin-top:28px">Nhật ký ngày này
        <textarea id="dayNote" placeholder="Chuyện xảy ra, giá thật, câu Pum đã nói, điều bất ngờ…">${esc(note)}</textarea></label>
      <div class="row" style="margin-top:10px"><button class="btn" id="saveNote">Lưu nhật ký</button>${dictBtn("dayNote")}</div>
      ${o.img&&T.credits[o.img]?`<p class="small muted" style="margin-top:24px">Ảnh tham khảo: ${esc(T.credits[o.img])}, Wikimedia Commons</p>`:""}
    </div>`;
  sh.classList.add("open"); $("#sheetBg").classList.add("open");
  $("#closeSheet").onclick = closeSheet; $("#sheetBg").onclick = closeSheet;
  $("#saveNote").onclick = async () => { await put("days", String(d), {note: $("#dayNote").value}); toast("Đã lưu nhật ký ngày "+d); };
  bindDict(sh); $("#closeSheet").focus();
}
document.addEventListener("keydown", e => { if (e.key === "Escape") closeSheet(); });

/* ---------- Chi tiêu ---------- */
let unit = LS.get("unit","baht");
function addExpenseForm(day){
  const d = day ?? Math.max(0, Math.min(28, tripDay()));
  return `<form class="add-grid" id="expForm">
    <label class="f">Số tiền<input type="number" inputmode="decimal" id="expAmt" min="0" step="any" required placeholder="${unit==="baht"?"150":"120000"}"></label>
    <div class="unit" role="group" aria-label="Đơn vị"><button type="button" data-unit="baht" aria-pressed="${unit==="baht"}">฿</button><button type="button" data-unit="vnd" aria-pressed="${unit==="vnd"}">đ</button></div>
    <label class="f">Khoản<select id="expCat">${T.budgetLines.map(b=>`<option value="${b.k}" ${b.k==="an"?"selected":""}>${esc(b.name)}</option>`).join("")}</select></label>
    <label class="f">Ngày<select id="expDay"><option value="0" ${d<1?"selected":""}>Trước chuyến</option>${T.days.map(x=>`<option value="${x.d}" ${x.d===d?"selected":""}>Ngày ${x.d}</option>`).join("")}</select></label>
    <label class="f note">Ghi chú<input type="text" id="expNote" placeholder="Xôi xoài ở chợ đêm Chang Phueak"></label>
    <button class="btn rose wide" type="submit">Ghi khoản này</button>
  </form>`;
}
function bindCommon(root){
  root.querySelectorAll("[data-unit]").forEach(b => b.onclick = () => { unit = b.dataset.unit; LS.set("unit", unit); root.querySelectorAll("[data-unit]").forEach(x=>x.setAttribute("aria-pressed", x.dataset.unit===unit)); });
  const f = root.querySelector("#expForm");
  if (f) f.onsubmit = async ev => {
    ev.preventDefault();
    const raw = Number($("#expAmt").value); if (!raw) return;
    const amt = unit === "baht" ? raw*rate() : raw;
    const id = "e" + Date.now().toString(36) + Math.random().toString(36).slice(2,6);
    const doc = {amt, baht: unit==="baht"?raw:null, cat:$("#expCat").value, day:Number($("#expDay").value), note:$("#expNote").value.trim(), at:Date.now()};
    $("#expAmt").value=""; $("#expNote").value="";
    await put("expenses", id, doc); toast("Đã ghi " + fmtVND(amt));
  };
}
function vMoney(v){
  const total = spentTotal(), list = expenseList().sort((a,b)=>b.day-a.day || b.at-a.at), budget = Number(S.settings.budget||0);
  const days = [...new Set(list.map(e=>e.day))];
  v.innerHTML = `
  <section>
    <p class="muted" style="font-weight:800">Pum đã tiêu</p>
    <h1 class="disp big-money num" style="margin-top:6px">${fmtVND(total)}</h1>
    ${budget?`<p class="lead" style="margin-top:10px">trên ngân sách ${fmtTr(budget)}. Còn ${fmtVND(budget-total)}.</p><div class="progress" style="margin-top:16px"><i class="${total>budget?"over":""}" style="width:${Math.min(100,total/budget*100)}%"></i></div>`
      :`<p class="lead" style="margin-top:10px">Chưa đặt ngân sách cho chuyến.</p>`}
    <label class="f" style="max-width:280px;margin-top:16px">Ngân sách cả chuyến (đồng)<input type="number" id="budget" value="${budget||""}" placeholder="ví dụ 18000000"></label>
  </section>
  <section class="sec strip">
    <h2 class="disp" style="font-size:24px;margin-bottom:14px">Ghi một khoản</h2>
    ${addExpenseForm()}
    <p class="small muted" style="margin-top:12px">Quy đổi 1 baht = <input type="number" id="rate" value="${rate()}" style="width:90px;min-height:34px;padding:4px 8px;display:inline-block" aria-label="Tỷ giá"> đồng. Đổi tỷ giá chỉ áp dụng cho khoản ghi sau.</p>
  </section>
  <section class="sec">
    <h2 class="disp h-sec" style="margin-bottom:6px">Theo khoản</h2>
    ${T.budgetLines.map(b=>{const s=spentBy(b.k), p=planOf(b.k);return `<div class="cat-row"><b>${esc(b.name)}</b><span class="num" style="text-align:right">${fmtVND(s)}<span class="muted"> / ${p?fmtTr(p):`<button class="linkbtn" data-plan="${b.k}" style="border:0;background:none;color:var(--berry);font-weight:800;cursor:pointer;padding:0">đặt mức</button>`}</span></span><div class="progress"><i class="${p&&s>p?"over":""}" style="width:${p?Math.min(100,s/p*100):0}%"></i></div></div>`}).join("")}
  </section>
  <section class="sec">
    <h2 class="disp h-sec" style="margin-bottom:6px">Giá các hoạt động</h2>
    <p class="muted" style="margin-bottom:8px">Giá tham khảo khi lên lịch (16/11/2026). Mức 2,5 triệu cho khoản “Hoạt động và vé” tính từ bảng này, chưa gồm chỗ ___.</p>
    ${T.activities.map(([n,p,u])=>`<div class="act"><span>${u?`<a href="${u}" target="_blank" rel="noopener">${esc(n)}</a>`:esc(n)}</span><b class="num">${esc(p)}</b></div>`).join("")}
  </section>
  <section class="sec">
    <h2 class="disp h-sec">Sổ chi</h2>
    ${list.length?days.map(d=>`<div class="exp-day"><h3><span>${d?`Ngày ${d} · ${esc(dayObj(d).city)}`:"Trước chuyến"}</span><span class="num muted">${fmtVND(spentDay(d))}</span></h3>
      ${list.filter(e=>e.day===d).map(e=>`<div class="exp"><span>${esc(e.note||T.budgetLines.find(b=>b.k===e.cat)?.name||"")}<br><span class="small muted">${esc(T.budgetLines.find(b=>b.k===e.cat)?.name||"")}${e.baht?` · ${e.baht.toLocaleString("vi-VN")} ฿`:""}</span></span><span class="num">${fmtVND(e.amt)}</span><button class="btn small ghost" data-del="${e.id}" aria-label="Xóa khoản này">Xóa</button></div>`).join("")}</div>`).join("")
      :`<p class="muted" style="margin-top:12px">Chưa có khoản nào.</p>`}
  </section>`;
  bindCommon(v);
  v.querySelectorAll("[data-del]").forEach(b => b.onclick = () => { if (confirm("Xóa khoản này?")) del("expenses", b.dataset.del); });
  const r = $("#rate"); r.dataset.keep="0"; r.onchange = () => { const x = Number(r.value); if (x>0) setSetting({rate:x}); };
  const bg = $("#budget"); bg.dataset.keep="0"; bg.onchange = () => setSetting({budget:Number(bg.value)||0});
  v.querySelectorAll("[data-plan]").forEach(b => b.onclick = () => { const x = prompt("Mức cho khoản này (đồng)"); if (x && Number(x) > 0) setSetting({plans:Object.assign({}, S.settings.plans||{}, {[b.dataset.plan]:Number(x)})}); });
}

/* ---------- Sản xuất ---------- */
let prodTab = LS.get("prodTab","quay"); if (prodTab !== "dang") prodTab = "quay";
function stStats(sc){ let tot=0, shot=0; sc.sections.forEach(s => (s.beats||[]).forEach(b => { tot++; if (S.beats[b.key] && S.beats[b.key].shot) shot++; })); return {tot, shot}; }
function vProd(v, r){
  const dNow = Math.max(1, Math.min(28, tripDay()));
  const isTest = r.a === "test" && !!T.test;
  const n = isTest ? "test" : (Number(r.a) || dayObj(dNow).st);
  const st = isTest ? T.test : (stObj(n) || stObj(1));
  const late = isTest && LS.get("testVer", "") === "muon", scN = late ? "testlate" : st.n; const focus = r.b && /^d\d+$/.test(r.b) ? r.b : null;
  if (focus) prodTab = "quay";
  const x = S.vids["ep"+st.n] || {};
  v.innerHTML = `
  <nav class="st-tabs" aria-label="Chọn tập">${T.test?`<a class="test" href="#/san-xuat/test" ${st.test?'aria-current="page"':''}>${esc(T.test.tab)}</a>`:""}${T.stages.map(s=>`<a href="#/san-xuat/${s.n}" ${s.n===st.n?'aria-current="page"':''}>Tập ${s.n} · ${esc(s.place.split(":")[0])}</a>`).join("")}</nav>
  ${st.test?`<p class="notice small testnote">Tập quay thử trước chuyến Thái: tập cách quay, cách nói tại chỗ và cách thu lồng tiếng sau. Mỗi cảnh có thêm mục <b>Bài tập</b>; cuối ngày điền phần <b>Bài test</b> trong mục Ghi chú.</p>
  <label class="vtoggle"><span class="vt-txt"><b>Bản dậy muộn</b><small>8 giờ dậy, 9 giờ mới đi. Chỉ đổi buổi sáng, chiều giữ nguyên.</small></span><input type="checkbox" id="lateTog" role="switch" ${late?"checked":""}><span class="sw" aria-hidden="true"></span></label>`:""}
  <section class="ephead">
    <img src="${img(st.img)}" alt="">
    <div>
      <p class="eyebrowless">${st.test?`Tập test · ${late?"bản dậy muộn":esc(st.when)} · ${esc(st.len)}`:`Tập ${st.n} · ngày ${st.days[0]}–${st.days[1]} · ${esc(st.len)} · đăng ${esc(x.postDate || st.post)}`}</p>
      <h1 class="disp">${esc(st.place)}</h1>
      <div id="stProg" class="muted small">Đang mở kịch bản…</div>
    </div>
  </section>
  <details class="about" id="about"><summary>${st.test?"Câu hỏi và sợi chỉ của tập":"Câu hỏi, sợi chỉ và luật bạn chọn của tập"}</summary><div id="epQ" class="card" style="margin-top:6px">${esc(st.line)}</div></details>
  <div class="seg" role="group" aria-label="Phần" style="margin-top:14px">
    <button data-tab="quay" aria-pressed="${prodTab!=="dang"}">Quay và kịch bản</button>
    <button data-tab="dang" aria-pressed="${prodTab==="dang"}">Dựng và đăng</button>
  </div>
  <div id="prodBody"></div>`;
  v.querySelectorAll("[data-tab]").forEach(b => b.onclick = () => { prodTab = b.dataset.tab; LS.set("prodTab", prodTab); render(); });
  const lt = v.querySelector("#lateTog"); if (lt) lt.onchange = () => { LS.set("testVer", lt.checked ? "muon" : ""); TTS.stop(); render(); };
  loadScript(scN).then(sc => {
    if (route().k !== "san-xuat") return;
    const body = $("#prodBody"); if (!body) return;
    if (sc.error){ body.innerHTML = `<p class="notice">Chưa mở được kịch bản tập này. Tải lại trang thử.</p>`; return; }
    const s = stStats(sc);
    $("#stProg").innerHTML = `<span class="num" style="font-weight:800;color:var(--ink)">${s.shot}/${s.tot} cảnh đã quay</span><div class="progress" style="margin-top:6px;max-width:320px"><i style="width:${s.tot?s.shot/s.tot*100:0}%"></i></div>`;
    if (sc.meta["Câu hỏi của tập"]) $("#epQ").innerHTML = `<p class="q">${esc(sc.meta["Câu hỏi của tập"])}</p><p class="muted">${esc((m=>m.charAt(0).toUpperCase()+m.slice(1))(sc.meta["Sợi chỉ"]||""))}</p>${sc.meta["Luật bạn chọn"]?`<span class="rule"><b>Luật bạn chọn.</b> ${esc(sc.meta["Luật bạn chọn"].replace(/^bình chọn trước chuyến:\s*/,""))}</span>`:""}`;
    S.curScript = sc;
    if (prodTab === "dang") renderPublish(body, sc, st);
    else renderShoot(body, sc, focus, st);
  });
}
/* ---------- đọc to: giọng Hoài My đọc sẵn (audio/), thiếu file thì dùng giọng của máy ---------- */
const SILENT = "data:audio/mpeg;base64,SUQzBAAAAAAAI1RTU0UAAAAPAAADTGF2ZjYwLjE2LjEwMAAAAAAAAAAAAAAA//NwwAAAAAAAAAAAAEluZm8AAAAPAAAABgAAAykAWlpaWlpaWlpaWlpaWlpaWnt7e3t7e3t7e3t7e3t7e3t7nJycnJycnJycnJycnJycnL29vb29vb29vb29vb29vb293t7e3t7e3t7e3t7e3t7e3t7/////////////////////AAAAAExhdmM2MC4zMQAAAAAAAAAAAAAAACQCowAAAAAAAAMpso+sIAAAAAAAAAAAAAAAAAD/80DEAAAAA0gAAAAATEFNRTMuMTAwVVVVVVVVVVVVVUxBTUUzLjEwMFVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVf/zQsRbAAADSAAAAABVVVVVVVVVVVVVVVVVVVVVVVVVVUxBTUUzLjEwMFVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVf/zQMSkAAADSAAAAABVVVVVVVVVVVVVVVVVVVVVVVVVTEFNRTMuMTAwVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVV//NCxKMAAANIAAAAAFVVVVVVVVVVVVVVVVVVVVVVVVVVTEFNRTMuMTAwVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVV//NAxKQAAANIAAAAAFVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVX/80LEowAAA0gAAAAAVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVU=";
const TTS = {
  rates:[1, 1.25, 1.5, 0.8], cur:null, voice:null, audio:null, url:null, tok:0,
  rate(){ const r = Number(LS.get("ttsRate", 1)); return this.rates.includes(r) ? r : 1; },
  rateLabel(){ return String(this.rate()).replace(".", ",") + "x"; },
  ok(){ return "speechSynthesis" in window && "SpeechSynthesisUtterance" in window; },
  pick(){
    const vs = (speechSynthesis.getVoices() || []).filter(v => /^vi(-|_|$)/i.test(v.lang));
    const pref = [/linh/i, /hoaimy|hoai my/i, /google/i, /female|nữ/i];
    for (const re of pref){ const v = vs.find(x => re.test(x.name)); if (v) return v; }
    return vs.find(v => v.localService) || vs[0] || null;
  },
  clean(t){ return t.replace(/\([^)]*\)/g, " ").replace(/_{2,}/g, " … ").replace(/[“”"«»]/g, "").replace(/\s+/g, " ").trim(); },
  async hash(t){ const b = await crypto.subtle.digest("SHA-1", new TextEncoder().encode(t)); return [...new Uint8Array(b)].map(x => x.toString(16).padStart(2, "0")).join("").slice(0, 16); },
  async clip(text){
    const h = await this.hash(text);
    if (window.PUMDECB){ const r = await fetch(`audio/${h}.enc`); if (!r.ok) throw 0; return new Blob([await window.PUMDECB(await r.arrayBuffer())], {type:"audio/mpeg"}); }
    const r = await fetch(`audio/${h}.mp3`); if (!r.ok) throw 0; return await r.blob();
  },
  mark(btn, on){ btn.classList.toggle("on", on); const sp = btn.querySelector("span"); if (sp) sp.textContent = on ? "Dừng" : "Nghe"; },
  stop(){
    this.tok++;
    try{ speechSynthesis.cancel(); }catch(e){}
    if (this.audio){ try{ this.audio.pause(); }catch(e){} }
    if (this.url){ URL.revokeObjectURL(this.url); this.url = null; }
    if (this.cur) this.mark(this.cur, false);
    this.cur = null;
  },
  play(btn){
    if (this.cur === btn){ this.stop(); return; }
    this.stop();
    const dd = btn.closest("dt").nextElementSibling; const text = this.clean(dd ? dd.textContent : ""); if (!text) return;
    if (!this.audio){ this.audio = new Audio(); this.audio.preload = "auto"; }
    const a = this.audio, tok = this.tok;
    /* iPhone chỉ cho phát tiếng trong lúc bấm, nên mở khóa ngay bằng một đoạn im lặng */
    try{ a.src = SILENT; const p = a.play(); if (p) p.catch(() => {}); }catch(e){}
    this.cur = btn; this.mark(btn, true);
    this.clip(text).then(blob => {
      if (tok !== this.tok) return;
      this.url = URL.createObjectURL(blob);
      a.src = this.url; a.playbackRate = this.rate(); try{ a.preservesPitch = true; a.webkitPreservesPitch = true; }catch(e){}
      a.onended = () => { if (tok === this.tok) this.stop(); };
      const p = a.play(); if (p) p.catch(() => { if (tok === this.tok) this.speak(btn, text, tok); });
    }).catch(() => { if (tok === this.tok) this.speak(btn, text, tok); });
  },
  speak(btn, text, tok){
    if (!this.ok()){ this.stop(); toast("Trình duyệt này chưa đọc được. Thử mở bằng Safari hoặc Chrome."); return; }
    this.voice = this.voice || this.pick();
    const parts = text.split(/(?<=[.!?…])\s+/).filter(x => x.trim());
    parts.forEach((t, i) => {
      const u = new SpeechSynthesisUtterance(t); u.lang = "vi-VN"; u.rate = this.rate(); u.pitch = 1; if (this.voice) u.voice = this.voice;
      if (i === parts.length - 1) u.onend = () => { if (tok === this.tok) this.stop(); };
      u.onerror = ev => { if (ev && (ev.error === "interrupted" || ev.error === "canceled")) return; if (tok === this.tok) this.stop(); };
      speechSynthesis.speak(u);
    });
  }
};
if (TTS.ok()){ try{ speechSynthesis.onvoiceschanged = () => { TTS.voice = TTS.pick(); }; TTS.voice = TTS.pick(); }catch(e){} }
document.addEventListener("click", e => {
  const b = e.target.closest("[data-tts]"); if (b){ TTS.play(b); return; }
  const r = e.target.closest("[data-ttsrate]"); if (!r) return;
  const rs = TTS.rates, n = rs[(rs.indexOf(TTS.rate()) + 1) % rs.length]; LS.set("ttsRate", n);
  document.querySelectorAll("[data-ttsrate]").forEach(x => x.textContent = TTS.rateLabel());
  if (TTS.cur && TTS.url && TTS.audio){ TTS.audio.playbackRate = n; }
  else if (TTS.cur){ const c = TTS.cur; TTS.stop(); TTS.play(c); }
});
window.addEventListener("hashchange", () => TTS.stop());
function refPics(v){ return v.split(" · ").map(x => { const m = x.trim().match(/^([a-z0-9_]+)\s*\((.+)\)$/); return m ? {k:m[1], cap:m[2]} : null; }).filter(Boolean); }
function itemsHTML(items){ return `<dl class="lines">${items.map(it=>{
  if (it.k === "Bản đồ"){ const ms = it.v.split(" · ").map(x => x.split(" | ")).filter(m => m.length === 2); return `<dt>Bản đồ</dt><dd class="maps">${ms.map(([lab,q])=>`<a class="lnkbtn" style="background:var(--blush)" href="https://www.google.com/maps/search/?api=1&query=${encodeURIComponent(q.trim())}" target="_blank" rel="noopener">${esc(lab.trim())}</a>`).join(" ")}</dd>`; }
  if (it.k === "Ảnh mẫu"){ const ps = refPics(it.v); return `<dt>Ảnh mẫu</dt><dd class="pics">${ps.map(p=>`<button type="button" class="pic" data-pic="${p.k}" data-cap="${esc(p.cap)}"><img src="${img(p.k)}" alt="${esc(p.cap)}" loading="lazy"><span>${esc(p.cap)}</span></button>`).join("")}</dd>`; }
  const lab = it.k==="Nói" ? "Nói tại chỗ" : it.k==="Nói thêm" ? "Nói thêm (nếu hứng)" : it.k==="Lồng tiếng" ? "Lồng tiếng (thu sau)" : (it.k||"·");
  const tts = /^(Nói|Lồng tiếng)/.test(it.k) ? `<span class="ttsbox"><button type="button" class="tts" data-tts aria-label="Đọc to đoạn này"><svg width="18" height="18" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2.2" stroke-linecap="round" stroke-linejoin="round" aria-hidden="true"><path d="M4 9v6h4l5 4V5L8 9z"/><path d="M16.5 8.5a5 5 0 0 1 0 7"/><path d="M19 6a8.5 8.5 0 0 1 0 12"/></svg><span>Nghe</span></button><button type="button" class="ttsr" data-ttsrate aria-label="Đổi tốc độ đọc">${TTS.rateLabel()}</button></span>` : "";
  return `<dt class="${/^Nói/.test(it.k)?"k-say":""}"><span>${esc(lab)}</span>${tts}</dt><dd class="${it.k==="Nói thêm"?"say alt":/^Nói/.test(it.k)?"say":/^Lồng tiếng/.test(it.k)?"vo":/^Chữ trên hình/.test(it.k)?"ost":""}">${inline(it.v)}</dd>`; }).join("")}</dl>`; }
function secKey(s){ return s.kind === "day" ? "d" + s.d : s.id; }
/* giữ nguyên chỗ đang xem khi bấm chọn: không nhảy dọc, thanh chọn ngang không tự trượt */
const hScroll = {};
function keepX(root, sel, key){
  const el = root.querySelector(sel); if (!el) return;
  if (hScroll[key] != null) el.scrollLeft = hScroll[key];
  const on = el.querySelector('[aria-pressed="true"]');
  if (on){ const er = el.getBoundingClientRect(), r = on.getBoundingClientRect();
    if (r.left < er.left) el.scrollLeft += r.left - er.left - 8;
    else if (r.right > er.right) el.scrollLeft += r.right - er.right + 8; }
  hScroll[key] = el.scrollLeft;
  el.addEventListener("scroll", () => { hScroll[key] = el.scrollLeft; }, {passive:true});
}
function stay(sel, fn){
  const v = $("#view"), old = document.querySelector(sel), y0 = old ? old.getBoundingClientRect().top : null;
  v.style.minHeight = v.offsetHeight + "px";
  fn();
  const nw = document.querySelector(sel);
  if (nw && y0 != null){ const d = nw.getBoundingClientRect().top - y0; if (Math.abs(d) > 1) window.scrollBy(0, d); }
  /* thả chiều cao giữ chỗ nhưng không để trang ngắn lại tới mức kéo màn hình đang xem đi chỗ khác */
  clearTimeout(stay.t); stay.t = setTimeout(() => { const need = Math.ceil(window.scrollY + innerHeight - (v.getBoundingClientRect().top + window.scrollY)); v.style.minHeight = need > 0 ? need + "px" : ""; }, 1200);
}
function toTop(sel){ const el = document.querySelector(sel); if (!el) return; const top = el.getBoundingClientRect().top + window.scrollY - (innerWidth < 900 ? 70 : 16); if (window.scrollY > top) window.scrollTo(0, top); }
function renderShoot(body, sc, focus, st){
  const parts = sc.sections.filter(s => s.kind !== "list"), lists = sc.sections.filter(s => s.kind === "list");
  const keys = parts.map(secKey).concat(lists.length ? ["ghichu"] : []);
  const store = "shootSec" + st.n;
  let cur = focus || LS.get(store, null);
  if (!keys.includes(cur)){ const t = tripDay(); const td = parts.find(p => p.kind === "day" && p.d === t); cur = td ? secKey(td) : keys[0]; }
  if (focus) LS.set(store, cur);
  const label = s => { if (s.kind === "day") return `Ngày ${s.d}<small>${esc(s.when.split(" ")[1]||"")}</small>`; const t = s.title.replace(/\s*\(.*\)$/,""); if (s.ch){ const m = t.match(/^(Chương \d+)\s*·\s*(.+)$/); return m ? `${esc(m[1])}<small>${esc(m[2])}</small>` : esc(t); } return `${esc(t)}<small>phần dựng</small>`; };
  const done = s => s.beats.length && s.beats.every(b => S.beats[b.key] && S.beats[b.key].shot);
  const idx = keys.indexOf(cur), sec = parts.find(p => secKey(p) === cur);
  const nameOf = k => { if (k === "ghichu") return st.test ? "Bài test và ghi chú" : "Sổ tiền và ghi chú"; const p = parts.find(x => secKey(x) === k); return p.kind === "day" ? `Ngày ${p.d} · ${p.title}` : p.title.replace(/\s*\(.*\)$/,""); };
  let html = `<nav class="daypick" aria-label="Chọn phần">${parts.map(p => `<button data-sec="${secKey(p)}" aria-pressed="${secKey(p)===cur}" class="${done(p)?"done":""}">${label(p)}</button>`).join("")}${lists.length?`<button data-sec="ghichu" aria-pressed="${cur==="ghichu"}">Ghi chú<small>${st.test?"bài test":"sổ tiền"}</small></button>`:""}</nav>`;
  if (sec){
    const n = sec.beats.filter(b=>S.beats[b.key]&&S.beats[b.key].shot).length, o = sec.kind==="day" ? dayObj(sec.d) : null;
    html += `<section class="vsec" style="border-top:0;margin-top:8px;padding-top:6px" id="${cur}">
      <p class="vid">${sec.kind==="day"?`${esc(sec.when)}${o?` · ${esc(o.city)}`:""}`:sec.ch?esc(sec.when):"Phần dựng"}</p>
      <h2 class="disp">${esc(sec.ch ? sec.title.replace(/\s*\(.*\)$/,"") : sec.title)}</h2>
      ${sec.q?`<p class="promise">${esc(sec.q)}</p>`:""}
      <div class="row" style="margin-top:12px"><span class="tag ${n===sec.beats.length?"":"soft"}" style="margin:0">${n}/${sec.beats.length} cảnh</span>${o&&o.map?`<a class="btn small ghost" href="https://www.google.com/maps/search/?api=1&query=${encodeURIComponent(o.map)}" target="_blank" rel="noopener">Bản đồ</a>`:""}${o?`<button class="btn small ghost" data-day="${o.d}">Lịch ngày này</button>`:""}</div>
      ${idx===0?`<p class="notice small" style="font-size:14px;margin-top:16px">${inline(sc.meta["Cách đọc"])}</p>`:""}
      ${sec.beats.map(b => beatHTML(b)).join("")}
    </section>`;
  } else {
    html += lists.map(s=>`<section class="sec card" style="margin-top:14px"><h2 class="disp" style="font-size:22px;margin-bottom:8px">${esc(s.title)}</h2><ul style="margin:0;padding-left:20px">${s.list.map(x=>`<li style="margin:6px 0">${inline(x)}</li>`).join("")}</ul></section>`).join("");
  }
  const pv = keys[idx-1], nx = keys[idx+1];
  html += `<div class="pager"><button data-sec="${pv||""}" ${pv?"":"disabled"}><small>Trước</small>${pv?esc(nameOf(pv)):""}</button><button class="nx" data-sec="${nx||""}" ${nx?"":"disabled"}><small>Tiếp theo</small>${nx?esc(nameOf(nx)):""}</button></div>`;
  body.innerHTML = html;
  bindBeats(body);
  body.querySelectorAll("[data-day]").forEach(b => b.onclick = () => openDay(Number(b.dataset.day)));
  body.querySelectorAll("[data-sec]").forEach(b => b.onclick = () => { if (!b.dataset.sec) return; LS.set(store, b.dataset.sec); if (/\/d\d+$/.test(location.hash)) history.replaceState(null, "", "#/san-xuat/" + st.n); const fromPager = b.closest(".pager"); if (fromPager){ renderShoot(body, sc, null, st); toTop(".daypick"); } else stay(".daypick", () => renderShoot(body, sc, null, st)); });
  keepX(body, ".daypick", "shoot" + st.n);
}
function beatHTML(b){
  const x = S.beats[b.key] || {}; const att = (x.clips||[]).length + (x.voices||[]).length;
  return `<div class="beat ${x.shot?"is-shot":""}" data-key="${b.key}">
    <div class="beat-h2"><span class="bt">${esc(b.title)}</span><button type="button" class="shotbtn" data-shot="${b.key}" aria-pressed="${!!x.shot}"><i aria-hidden="true"></i>${x.shot?"Đã quay":"Chưa quay"}</button></div>
    <div class="body">
      ${itemsHTML(b.items)}
      <details class="tools-d" ${x._open?"open":""}>
        <summary>Ghi chú, clip, giọng${x.note||att?` <span class="meta">· ${x.note?"có ghi chú":""}${x.note&&att?", ":""}${att?att+" tệp":""}</span>`:""}</summary>
        <div class="tools">
          <label class="f">Ghi chú hiện trường (giá thật, câu Pum đã nói, chỗ nên cắt)
            <textarea id="note-${b.key}">${esc(x.note||"")}</textarea></label>
          <div class="row"><button class="btn small" data-savenote="${b.key}">Lưu ghi chú</button>${dictBtn("note-"+b.key)}${S.sample&&b.items.some(i=>i.k==="Lồng tiếng")?`<button class="btn small ghost" data-vo="${b.key}">Nhờ Claude sửa lời lồng tiếng theo ghi chú</button>`:""}</div>
          ${x.voDraft?`<div class="draft"><p class="small muted" style="margin-bottom:6px;font-weight:800">Lời lồng tiếng sửa theo chuyện thật</p><p>${esc(x.voDraft)}</p></div>`:""}
          <div>
            <div class="att">${(x.clips||[]).map((c,i)=>`<span class="chip">Clip <a href="${esc(c.url)}" target="_blank" rel="noopener">${esc(c.name||c.url)}</a><button data-rm="${b.key}|clips|${i}" aria-label="Bỏ">×</button></span>`).join("")}
            ${(x.voices||[]).map((c,i)=>`<span class="chip">Giọng <audio controls preload="none" src="${esc(c.url)}" style="height:30px;max-width:200px"></audio><button data-rm="${b.key}|voices|${i}" aria-label="Bỏ">×</button></span>`).join("")}</div>
            <div class="row" style="margin-top:10px"><input type="url" id="link-${b.key}" placeholder="Dán link Google Drive của clip" style="flex:1;min-width:200px"><button class="btn small" data-addlink="${b.key}">Thêm link</button></div>
            ${S.assets?`<div class="row" style="margin-top:10px">
              <label class="btn small ghost">Tải clip ngắn (dưới 20 MB)<input type="file" accept="video/*,image/*" data-up="${b.key}|clips" class="hidden"></label>
              <label class="btn small ghost">Tải file ghi âm<input type="file" accept="audio/*" data-up="${b.key}|voices" class="hidden"></label>
              <button class="btn small ghost" data-rec="${b.key}">Thu giọng ngay</button></div>`
            :`<p class="small muted" style="margin-top:8px">Tải tệp lên chỉ dùng được khi mở trang trong Claude. Clip dài thì để trên Google Drive rồi dán link.</p>`}
          </div>
        </div>
      </details>
    </div>
  </div>`;
}
function bindBeats(body){
  body.querySelectorAll(".beat").forEach(d => { const t = d.querySelector("details.tools-d"); if (t) t.addEventListener("toggle", () => { const k=d.dataset.key; S.beats[k]=Object.assign({},S.beats[k]||{},{_open:t.open}); }); });
  body.querySelectorAll("[data-shot]").forEach(c => c.onclick = () => { const on = c.getAttribute("aria-pressed") !== "true"; put("beats", c.dataset.shot, {shot:on, shotAt: on?Date.now():null}); });
  body.querySelectorAll("[data-savenote]").forEach(b => b.onclick = async () => { const k=b.dataset.savenote; await put("beats", k, {note: document.getElementById("note-"+k).value, _open:true}); toast("Đã lưu ghi chú"); });
  body.querySelectorAll("[data-addlink]").forEach(b => b.onclick = async () => {
    const k=b.dataset.addlink, u=document.getElementById("link-"+k).value.trim(); if(!/^https?:\/\//.test(u)){ toast("Link cần bắt đầu bằng https://"); return; }
    const x=S.beats[k]||{}; await put("beats", k, {clips:[...(x.clips||[]), {url:u, name:u.replace(/^https?:\/\//,"").slice(0,40)}], _open:true});
  });
  body.querySelectorAll("[data-rm]").forEach(b => b.onclick = async () => { const [k,f,i]=b.dataset.rm.split("|"); const x=S.beats[k]||{}; const arr=[...(x[f]||[])]; arr.splice(Number(i),1); await put("beats", k, {[f]:arr, _open:true}); });
  body.querySelectorAll("[data-up]").forEach(inp => inp.onchange = async () => {
    const [k,f] = inp.dataset.up.split("|"); const file = inp.files[0]; if (!file) return;
    if (file.size > 20*1024*1024){ toast("Tệp quá 20 MB. Để trên Google Drive rồi dán link."); return; }
    await uploadTo(k, f, file, file.name);
  });
  body.querySelectorAll("[data-rec]").forEach(b => b.onclick = () => record(b, b.dataset.rec));
  body.querySelectorAll("[data-vo]").forEach(b => b.onclick = () => draftVO(b, b.dataset.vo));
  body.querySelectorAll("[data-pic]").forEach(b => b.onclick = () => openPic(b.dataset.pic, b.dataset.cap));
  bindDict(body);
}
async function draftVO(btn, k){
  const sc = S.curScript; let beat = null, sec = null;
  [S.curScript, ...Object.values(S.scripts)].filter(Boolean).forEach(c => (c.sections||[]).forEach(s => (s.beats||[]).forEach(b => { if (b.key === k){ beat = b; sec = s; } })));
  if (!beat) return; const x = S.beats[k] || {};
  btn.disabled = true; btn.textContent = "Claude đang viết…";
  const prompt = `Sửa lời lồng tiếng cho một cảnh trong tập YouTube dài (30–50 phút) của kênh "Thử đi cùng Pum", loạt "${T.series}". Pum xưng Pum, gọi người xem là bạn. Giọng nói chuyện, câu ngắn, dễ đọc thành tiếng, tò mò, tinh nghịch vừa đủ. Không dùng "tuyệt vời", "hành trình", "khám phá", "ngon nhất", không văn vẻ.
Đoạn: ${sec.kind==="day"?`Ngày ${sec.d} · `:""}${sec.title}. Câu hỏi của đoạn: ${sec.q||"(không có)"}
Cảnh: ${beat.title}
Kịch bản cảnh:
${beat.items.map(i=>`- ${i.k}: ${i.v}`).join("\n")}
Ghi chú thật từ hiện trường: ${x.note || "(chưa có)"}
Viết lại phần lồng tiếng 2–4 câu, nối mạch với cảnh trước và sau, khớp với chuyện thật trong ghi chú, điền số thật vào chỗ ___. Thiếu thông tin thì giữ ___, không bịa cảm nhận, giá hay chuyện chưa xảy ra. Chỉ trả về lời lồng tiếng.`;
  try{ const r = await S.sample(prompt, {modelTier:"default"}); await put("beats", k, {voDraft: r.text.trim(), _open:true}); }
  catch(e){ if (e && e.code === "not_granted"){ S.sample = null; render(); } else { toast("Claude chưa viết được, thử lại sau."); btn.disabled = false; btn.textContent = "Nhờ Claude sửa lời lồng tiếng theo ghi chú"; } }
}
async function uploadTo(k, f, blob, name){
  if (!S.assets) return; toast("Đang tải lên…");
  try{ const r = await S.assets.upload(blob); const x = S.beats[k]||{}; await put("beats", k, {[f]:[...(x[f]||[]), {url:r.url, id:r.id, name}], _open:true}); toast("Đã tải lên"); }
  catch(e){ toast("Chưa tải lên được: " + (e && e.message ? e.message : "lỗi")); }
}
let rec = null;
async function record(btn, k){
  if (rec){ rec.stop(); return; }
  if (!navigator.mediaDevices || !window.MediaRecorder){ toast("Trình duyệt này không thu âm được. Dùng nút tải file ghi âm."); return; }
  try{
    const stream = await navigator.mediaDevices.getUserMedia({audio:true}); const chunks = []; rec = new MediaRecorder(stream);
    rec.ondataavailable = e => chunks.push(e.data);
    rec.onstop = async () => { stream.getTracks().forEach(t=>t.stop()); const blob = new Blob(chunks, {type: rec.mimeType || "audio/webm"}); rec = null; btn.textContent = "Thu giọng ngay"; await uploadTo(k, "voices", blob, "giong-"+new Date().toLocaleTimeString("vi-VN")); };
    rec.start(); btn.textContent = "Dừng thu";
  }catch(e){ rec = null; toast("Không mở được micro ở đây. Thu bằng app ghi âm rồi tải file lên."); }
}
function chaptersFrom(sc){
  return sc.sections.filter(s=>s.kind!=="list").map((s,i) => `${i===0?"0:00":"__:__"} ${s.kind==="day"?`Ngày ${s.d} · ${s.title}`:s.title.replace(/\s*\(.*\)$/,"")}`).join("\n");
}
function renderPost(body, sc, st){
  const id = "ep"+st.n, x = S.vids[id] || {}, s = stStats(sc);
  const tk = listSec(sc, /^TikTok/), money = listSec(sc, /^Sổ tiền/), check = listSec(sc, /^Cần Pum/);
  const tiks = (tk ? tk.list : []), tx = x.tiktok || {};
  const tdone = tiks.filter((_,i)=>tx[i] && tx[i].url).length;
  const steps = [[s.shot===s.tot,"Quay đủ"],[!!ed(sc.n).draftV,"Có bản nháp"],[!!(x.title&&x.thumb),"Tên và thumbnail"],[!!x.chapters&&!/__:__/.test(x.chapters),"Chương"],[!!ed(sc.n).finalV,"Có bản cuối"],[!!x.posted,"Lên YouTube"],[tiks.length&&tdone===tiks.length,`TikTok ${tdone}/${tiks.length}`]];
  const th = x.thumbCity ? x : {thumbCity:st.city, thumbL1:st.labels[0], thumbL2:st.labels[1], thumbL3:st.labels[2]};
  body.innerHTML = `
  <div class="card"><p class="eyebrowless" style="margin-bottom:8px">Tiến độ đăng</p><div class="steps" style="margin:0">${steps.map(([ok,t])=>`<span class="${ok?"ok":""}">${t}</span>`).join("")}</div><p class="small muted" style="margin-top:10px">Ô nào điền xong tự lưu. Mô tả và chữ trên hình chỉ nói điều Pum đã làm thật, giá có nơi và ngày.</p></div>
  <div class="pubs">
  <section class="pub ${x.title?"ok":""}">
    <h3 class="disp">Tên tập và ngày đăng</h3>
    <div class="grid2" style="gap:14px">
      <label class="f">Ngày đăng<input type="text" id="pb-postDate" value="${esc(x.postDate||"")}" placeholder="${esc(st.post)}"></label>
    </div>
    <label class="f" style="margin-top:14px">Tên tập trên YouTube<input type="text" id="pb-title" value="${esc(x.title||"")}" placeholder="${esc(sc.meta["Tên tập"]||"")}"></label>
    ${!x.title&&sc.meta["Tên tập"]?`<button class="btn small ghost" style="margin-top:8px" data-fill="title">Dùng tên gợi ý trong kịch bản</button>`:""}
  </section>
  ${st.test?"":`<section class="pub">
    <h3 class="disp">Hiệu ứng của tập</h3>
    <p class="small muted" style="margin-bottom:12px">Nền xanh cho CapCut (Xóa nền › Phông xanh). Chuyển cảnh chung và cách dùng ở Cẩm nang › Hiệu ứng.</p>
    <div class="fxrow">${fxVid(`fx/youtube/mo_tap_${st.n}.webm`)}<div><b>Mở tập ${st.n}</b>${fxLinks([["Nền xanh",`fx/youtube/mo_tap_${st.n}_nenxanh.mp4`],["Nền trong",`fx/youtube/mo_tap_${st.n}.webm`]])}</div></div>
    <ul class="fxdays">${T.days.filter(d=>d.st===st.n).map(d=>{const n=String(d.d).padStart(2,"0");return `<li><span>Thẻ ngày ${d.d}</span>${fxLinks([["Nền xanh",`fx/youtube/the_ngay/the_ngay_${n}_nenxanh.mp4`],["Nền trong",`fx/youtube/the_ngay/the_ngay_${n}.webm`]])}</li>`}).join("")}</ul>
  </section>`}
  <section class="pub ${x.thumb?"ok":""}">
    <h3 class="disp">Thumbnail</h3>
    <p class="small muted" style="margin-bottom:12px">Một ảnh Pum ở giữa, tên nơi thật to, ba nhãn ngắn là ba điều có trong tập. Chọn ảnh có mặt Pum và cảnh nơi đó, không dùng ảnh người khác.</p>
    <div class="thumb" aria-label="Xem trước bố cục thumbnail"><b class="tc">${esc(th.thumbCity)}</b><span class="t1">${esc(th.thumbL1)}</span><span class="t2">${esc(th.thumbL2)}</span><span class="t3">${esc(th.thumbL3)}</span><img src="brand/camera.png" alt=""></div>
    <div class="grid2" style="gap:14px;margin-top:14px">
      <label class="f">Tên nơi<input type="text" id="pb-thumbCity" value="${esc(th.thumbCity)}"></label>
      <label class="f">Nhãn 1<input type="text" id="pb-thumbL1" value="${esc(th.thumbL1)}"></label>
      <label class="f">Nhãn 2<input type="text" id="pb-thumbL2" value="${esc(th.thumbL2)}"></label>
      <label class="f">Nhãn 3<input type="text" id="pb-thumbL3" value="${esc(th.thumbL3)}"></label>
    </div>
    <label class="f" style="margin-top:14px">Link ảnh thumbnail đã làm<input type="url" id="pb-thumb" value="${esc(x.thumb||"")}" placeholder="https://drive.google.com/…"></label>
  </section>
  <section class="pub ${x.desc&&x.chapters&&!/__:__/.test(x.chapters)?"ok":""}">
    <h3 class="disp">Mô tả và chương</h3>
    <label class="f">Chương (dựng xong mới điền giờ thật vào chỗ __:__)<textarea id="pb-chapters" style="min-height:220px;font-variant-numeric:tabular-nums">${esc(x.chapters || chaptersFrom(sc))}</textarea></label>
    <label class="f" style="margin-top:14px">Mô tả YouTube<textarea id="pb-desc" style="min-height:160px">${esc(x.desc||"")}</textarea></label>
    ${x.descDraft?`<div class="draft" style="margin-top:10px"><p class="small muted" style="margin-bottom:6px;font-weight:800">Claude gợi ý từ ghi chú hiện trường</p><p style="white-space:pre-line">${esc(x.descDraft)}</p><button class="btn small ghost" style="margin-top:8px" data-usedesc="1">Dùng bản này</button></div>`:""}
    <p class="small muted" style="margin-top:8px">Hashtag: #thudicungpum ${esc(T.tag)}</p>
    ${S.sample?`<button class="btn small ghost" style="margin-top:10px" data-desc="1">Nhờ Claude viết mô tả</button>`:""}
  </section>
  <section class="pub ${tiks.length&&tdone===tiks.length?"ok":""}">
    <h3 class="disp">TikTok cắt từ tập này</h3>
    <p class="small muted" style="margin-bottom:10px">Cắt sau khi tập dài đã lên. Mỗi clip 30–60 giây, chữ mở trên băng hồng, cuối clip nhắc “Tập đầy đủ trên YouTube”.</p>
    ${tiks.length?tiks.map((t,i)=>`<div class="tk"><span>${inline(t)}</span><input type="url" id="tk-${i}" value="${esc((tx[i]||{}).url||"")}" placeholder="Link TikTok khi đã đăng"></div>`).join(""):`<p class="muted">Kịch bản chưa có danh sách TikTok.</p>`}
  </section>
  ${money?`<section class="pub"><h3 class="disp">${esc(money.title)}</h3><ul style="margin:0;padding-left:20px">${money.list.map(t=>`<li>${inline(t)}</li>`).join("")}</ul><p class="small muted" style="margin-top:8px">Lấy số thật trong <a href="#/chi-tieu">Chi tiêu</a> để điền bảng chữ khi dựng.</p></section>`:""}
  ${check?`<section class="pub ${check.list.every((_,i)=>(x.checks||{})[i])?"ok":""}"><h3 class="disp">${esc(check.title)}</h3><ul class="check">${check.list.map((t,i)=>{const ok=(x.checks||{})[i];return `<li class="${ok?"done":""}"><input type="checkbox" id="ck-${i}" data-ck="${i}" ${ok?"checked":""}><label for="ck-${i}"><span>${inline(t)}</span></label></li>`}).join("")}</ul></section>`:""}
  <section class="pub ${x.posted?"ok":""}">
    <h3 class="disp">Đăng lên YouTube</h3>
    <label class="f">Link tập đã lên YouTube<input type="url" id="pb-posted" value="${esc(x.posted||"")}" placeholder="https://youtu.be/…"></label>
    <div class="row" style="margin-top:14px">
      <button class="btn" data-savepub="1">Lưu</button>
    </div>
  </section>
  </div>`;
  const F = ["postDate","title","thumbCity","thumbL1","thumbL2","thumbL3","thumb","chapters","desc","posted"];
  const collect = () => { const o = {}; F.forEach(f => { const el = document.getElementById("pb-"+f); if (el) o[f] = f==="chapters"||f==="desc" ? el.value : el.value.trim(); }); const t = {}; tiks.forEach((_,i)=>{ const u = (document.getElementById("tk-"+i)||{}).value; t[i] = {url:(u||"").trim()}; }); o.tiktok = t; return o; };
  const save = (extra={}) => put("vids", id, Object.assign(collect(), extra));
  body.querySelectorAll("[data-savepub]").forEach(b => b.onclick = async () => { await save(); toast("Đã lưu tập "+st.n); });
  body.querySelectorAll('input[id^="pb-"],textarea[id^="pb-"],input[id^="tk-"]').forEach(el => { el.dataset.keep = "0"; el.addEventListener("change", () => save()); });
  body.querySelectorAll("[data-fill]").forEach(b => b.onclick = async () => { await save({title: sc.meta["Tên tập"]}); });
  body.querySelectorAll("[data-usedesc]").forEach(b => b.onclick = async () => { await save({desc: x.descDraft}); });
  body.querySelectorAll("[data-ck]").forEach(c => c.onchange = async () => { await save({checks: Object.assign({}, x.checks||{}, {[c.dataset.ck]: c.checked})}); });
  body.querySelectorAll("[data-send]").forEach(b => b.onclick = async () => {
    const beats = {}; sc.sections.forEach(sec => (sec.beats||[]).forEach(bt => { const y = S.beats[bt.key]; if (y) beats[bt.key] = {part: sec.kind==="day"?`Ngày ${sec.d} · ${sec.title}`:sec.title, title:bt.title, shot:!!y.shot, note:y.note||"", voDraft:y.voDraft||"", clips:y.clips||[], voices:y.voices||[]}; }));
    await save({request:{at:Date.now(), status:"chờ dựng", script:`scripts/tap${st.n}.md`, beats}}); toast("Đã gửi phiếu dựng tập " + st.n);
  });
  body.querySelectorAll("[data-desc]").forEach(b => b.onclick = () => draftDesc(b, sc, st));
  fxWire(body);
}
/* ---------- Dựng: đi song song với kịch bản ---------- */
const IC = {
  play:'<svg width="24" height="24" viewBox="0 0 24 24" fill="currentColor" aria-hidden="true"><path d="M8 5.5v13l11-6.5z"/></svg>',
  note:'<svg width="24" height="24" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2.2" aria-hidden="true"><path d="M9 18V6l10-2v12"/><circle cx="6.5" cy="18" r="2.5"/><circle cx="16.5" cy="16" r="2.5"/></svg>',
  star:'<svg width="20" height="20" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linejoin="round" aria-hidden="true"><path d="M12 3.5l2.6 5.3 5.9.9-4.3 4.1 1 5.8L12 16.9l-5.2 2.7 1-5.8-4.3-4.1 5.9-.9z"/></svg>',
  starOn:'<svg width="20" height="20" viewBox="0 0 24 24" fill="currentColor" aria-hidden="true"><path d="M12 3.5l2.6 5.3 5.9.9-4.3 4.1 1 5.8L12 16.9l-5.2 2.7 1-5.8-4.3-4.1 5.9-.9z"/></svg>',
  check:'<svg width="16" height="16" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="3" stroke-linecap="round" stroke-linejoin="round" aria-hidden="true"><path d="M5 12.5l4.5 4.5L19 7"/></svg>',
  dot:'<svg width="16" height="16" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2.4" aria-hidden="true"><circle cx="12" cy="12" r="7"/></svg>',
  x:'<svg width="20" height="20" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2.4" stroke-linecap="round" aria-hidden="true"><path d="M6 6l12 12M18 6L6 18"/></svg>'
};
const KINDS = [["canh","Cảnh"],["noi","Nói tại chỗ"],["vo","Lồng tiếng"]];
const ESTAT = {gui:"Đã gửi cho AI", de_xuat:"AI đã gửi hướng dựng", duyet:"Pum đã duyệt hướng dựng", dang_dung:"AI đang dựng", nhap:"Có bản nháp", sua:"AI đang sửa theo góp ý", chot:"AI đang xuất bản cuối", xong:"Đã có bản cuối"};
const NOTEK = {bo:"Bỏ đoạn này", ngan:"Cắt ngắn lại", take:"Đổi take khác", chu:"Sửa chữ trên hình", sub:"Sửa phụ đề", nhac:"Đổi nhạc", y:"Góp ý"};
const fmtT = s => { s = Math.max(0, Math.round(s||0)); return `${Math.floor(s/60)}:${String(s%60).padStart(2,"0")}`; };
const fmtSize = b => !b ? "" : b >= 1e9 ? (b/1e9).toFixed(1).replace(".",",")+" GB" : Math.max(1, Math.round(b/1e6))+" MB";
const WEBDUNG = () => !!window.PUMDECB;
/* clip và trạng thái dựng nằm trong kho vids: c_<cảnh> và e_<tập> */
const clipList = k => (S.vids["c_" + k] || {}).clips || [];
const clipDoc = k => S.vids["c_" + k] || {};
const uid = () => Math.random().toString(36).slice(2, 10);
const ed = n => S.vids["e_" + n] || {};
async function saveEd(n, o, mine = true){ await put("vids", "e_" + n, mine ? Object.assign({agentMsg:""}, o) : o); }
async function saveClips(k, n, clips, extra){ await put("vids", "c_" + k, Object.assign({ep:String(n), clips}, extra || {})); }

function probeFile(f){ return new Promise(res => {
  const audio = /^audio\//.test(f.type) || /\.(m4a|mp3|wav|aac|amr|ogg|opus)$/i.test(f.name);
  const el = document.createElement(audio ? "audio" : "video"); el.preload = audio ? "metadata" : "auto"; el.muted = true; el.playsInline = true; el.setAttribute("playsinline", "");
  const url = URL.createObjectURL(f); let done = false;
  const base = () => ({dur: isFinite(el.duration) ? el.duration : 0, w: el.videoWidth || 0, h: el.videoHeight || 0, audio});
  const fin = o => { if (done) return; done = true; try{ URL.revokeObjectURL(url); }catch(e){} res(o); };
  el.onloadedmetadata = () => { if (audio || !el.videoWidth) return fin(Object.assign(base(), {thumb:""})); try{ el.currentTime = Math.min(1, (el.duration || 2) * 0.2); }catch(e){ fin(Object.assign(base(), {thumb:""})); } };
  el.onseeked = () => { try{ const c = document.createElement("canvas"), w = 160, h = Math.round(w * el.videoHeight / el.videoWidth); c.width = w; c.height = h; c.getContext("2d").drawImage(el, 0, 0, w, h); fin(Object.assign(base(), {thumb:c.toDataURL("image/jpeg", .6)})); }catch(e){ fin(Object.assign(base(), {thumb:""})); } };
  el.onerror = () => fin({dur:0, w:0, h:0, audio, thumb:""});
  setTimeout(() => fin(Object.assign(base(), {thumb:""})), 9000);
  el.src = url;
});}

async function addFiles(files, key, n, extraKeep){
  const list = clipList(key).slice(); let i = 0;
  for (const f of files){
    i++; toast(`Đang đọc clip ${i}/${files.length}…`);
    const p = await probeFile(f), id = uid();
    if (p.thumb) LS.set("th:" + id, p.thumb);
    list.push({id, name:f.name, size:f.size, dur:Math.round((p.dur||0)*100)/100, w:p.w, h:p.h, mod:f.lastModified || 0,
      kind: p.audio ? "vo" : (p.w && p.h > p.w ? "noi" : "canh"), note:"", best:false, at:Date.now()});
  }
  await saveClips(key, n, list, extraKeep);
  toast(`Đã gắn ${files.length} clip`);
}

function clipRow(c, key){
  const th = LS.get("th:" + c.id, "");
  return `<li class="clip" data-cid="${c.id}" data-key="${key}">
    <div class="cth ${c.kind==="vo"?"is-vo":""}">${th?`<img src="${th}" alt="">`:`${c.kind==="vo"?IC.note:IC.play}`}</div>
    <div class="cmain">
      <p class="cname"><b>${esc(c.name)}</b><span>${fmtT(c.dur)}${c.size?` · ${fmtSize(c.size)}`:""}${c.h>c.w&&c.w?" · dọc":""}</span></p>
      <div class="ckind" role="group" aria-label="Loại clip">${KINDS.map(([k,t])=>`<button type="button" data-kind="${k}" aria-pressed="${c.kind===k}">${t}</button>`).join("")}</div>
      <input type="text" class="cnote" data-note="1" value="${esc(c.note||"")}" placeholder="Ghi chú take" aria-label="Ghi chú cho clip ${esc(c.name)}">
    </div>
    <div class="cact">
      <button type="button" class="cbest" data-best="1" aria-pressed="${!!c.best}" aria-label="Take ưng nhất">${c.best?IC.starOn:IC.star}<small>Ưng</small></button>
      <button type="button" class="cdel" data-delclip="1" aria-label="Bỏ clip ${esc(c.name)}">${IC.x}</button>
    </div>
  </li>`;
}
/* mỗi cảnh: kịch bản cần những clip gì, đã có chưa */
const NEEDK = [["Hình","canh","Cảnh quay"],["Quay thêm","canh","Cảnh thêm"],["Nói","noi","Pum nói tại chỗ"],["Nói thêm","noi","Nói thêm (nếu hứng)"],["Lồng tiếng","vo","Lồng tiếng thu sau"]];
function needsHTML(b, cl){
  const rows = []; NEEDK.forEach(([k, kind, lab]) => { const it = b.items.find(x => x.k.split(" (")[0] === k); if (it && it.v) rows.push({kind, lab, v:it.v.replace(/\*\*/g, "")}); });
  if (!rows.length) return "";
  return `<ul class="needs">${rows.map(r => { const ok = cl.some(c => c.kind === r.kind); return `<li class="${ok?"ok":""}"><span class="nk">${ok?IC.check:IC.dot}${esc(r.lab)}</span><p>${esc(r.v)}</p></li>`; }).join("")}</ul>`;
}
const REASONS = ["Gặp người thú vị", "Cảnh đẹp bất ngờ", "Phản ứng thật, buồn cười", "Món hoặc chỗ không có trong kịch bản", "Mẹo hay cho người xem", "Quay dự phòng để nối cảnh"];
function clipBox(key, label, n){
  const cl = clipList(key);
  return `<ul class="clips">${cl.map(c => clipRow(c, key)).join("")}</ul>
    <label class="btn small ghost addclip"><input type="file" multiple accept="video/*,audio/*" data-addkey="${key}" hidden>+ Thêm clip${cl.length?"":` cho ${esc(label)}`}</label>`;
}

function bindClips(root, n){
  root.querySelectorAll("[data-addkey]").forEach(inp => inp.onchange = async () => {
    const files = [...inp.files]; if (!files.length) return;
    const k = inp.dataset.addkey, keep = k.endsWith("x") ? {reason: clipDoc(k).reason || ""} : null;
    await addFiles(files, k, n, keep); inp.value = "";
  });
  const upd = async (li, fn) => { const k = li.dataset.key, cl = clipList(k).map(c => c.id === li.dataset.cid ? fn(Object.assign({}, c)) : c).filter(Boolean); const x = clipDoc(k); await saveClips(k, n, cl, k.endsWith("x") ? {reason:x.reason||""} : null); };
  root.querySelectorAll(".clip").forEach(li => {
    li.querySelectorAll("[data-kind]").forEach(b => b.onclick = () => upd(li, c => (c.kind = b.dataset.kind, c)));
    li.querySelector("[data-best]").onclick = () => upd(li, c => (c.best = !c.best, c));
    li.querySelector("[data-delclip]").onclick = () => { if (confirm("Bỏ clip này khỏi cảnh? File trên điện thoại vẫn còn.")) upd(li, () => null); };
    const nt = li.querySelector("[data-note]"); nt.dataset.keep = "0"; nt.onchange = () => upd(li, c => (c.note = nt.value.trim(), c));
  });
  root.querySelectorAll("[data-reason]").forEach(ta => { ta.dataset.keep = "0"; ta.onchange = async () => { const k = ta.dataset.reason; await saveClips(k, n, clipList(k), {reason: ta.value}); toast("Đã lưu lý do"); }; });
}

function dungStats(sc){
  const parts = sc.sections.filter(s => s.kind !== "list"); let beats = 0, withClip = 0, clips = 0, dur = 0, size = 0, extra = 0;
  parts.forEach(p => { p.beats.forEach(b => { beats++; const c = clipList(b.key); if (c.length) withClip++; c.forEach(x => { clips++; dur += x.dur||0; size += x.size||0; }); });
    clipList(p.id + "x").forEach(x => { clips++; extra++; dur += x.dur||0; size += x.size||0; }); });
  return {beats, withClip, clips, dur, size, extra};
}

function stepOf(e, st){
  if (["xong"].includes(e.status)) return 5;
  if (e.draftV) return 4;
  if (e.boardV) return 3;
  if (e.status === "gui") return 2;
  return 1;
}

async function encJSON(path){ const r = await fetch(path, {cache:"no-store"}); if (!r.ok) throw 0; return JSON.parse(await window.PUMDEC(await r.arrayBuffer())); }

function renderPublish(body, sc, st){
  const n = sc.n, e = ed(n), stats = dungStats(sc);
  if (!WEBDUNG()){
    body.innerHTML = `<p class="notice">Phần dựng cùng AI chạy trên <a href="https://pum.cherie.io.vn/#/san-xuat/${esc(String(st.n))}" target="_blank" rel="noopener"><b>pum.cherie.io.vn</b></a>, vì bản nháp video nằm ở đó. Phần đăng vẫn ở dưới.</p><div id="postBox"></div>`;
    renderPost($("#postBox"), sc, st); return;
  }
  const auto = stepOf(e, st), sk = "dungStep" + n; let cur = Number(LS.get(sk, 0)) || auto;
  const names = [["Gắn clip", `${stats.withClip}/${stats.beats} cảnh`], ["Gửi AI", e.sentAt ? "đã gửi" : "chưa gửi"], ["Hướng dựng", e.boardV ? (e.feedback && e.feedback.approved ? "đã duyệt" : "chờ Pum") : "chờ AI"], ["Bản nháp", e.draftV ? `v${e.draftV}` : "chờ AI"], ["Đăng", e.finalV ? "bản cuối" : ""]];
  body.innerHTML = `
  ${e.status ? `<p class="estat" role="status"><b>${esc(ESTAT[e.status] || e.status)}</b>${e.agentMsg ? ` · ${esc(e.agentMsg)}` : ""}</p>` : ""}
  <nav class="stepper" aria-label="Các bước dựng">${names.map(([t, s], i) => `<button type="button" data-step="${i+1}" aria-pressed="${cur===i+1}" class="${i+1<auto?"done":""}"><b>${i+1}. ${t}</b><small>${esc(s)}</small></button>`).join("")}</nav>
  <div id="stepBody"></div>`;
  body.querySelectorAll("[data-step]").forEach(b => b.onclick = () => { LS.set(sk, Number(b.dataset.step)); stay(".stepper", () => renderPublish(body, sc, st)); });
  keepX(body, ".stepper", "step" + n);
  const sb = $("#stepBody");
  ({1:stepClips, 2:stepSend, 3:stepBoard, 4:stepDraft, 5:stepPost})[cur](sb, sc, st, e, stats);
}

function stepClips(sb, sc, st, e, stats){
  const n = sc.n, parts = sc.sections.filter(s => s.kind !== "list");
  const store = "shootSec" + st.n; let cur = LS.get(store, null);
  if (!parts.some(p => secKey(p) === cur)) cur = secKey(parts[0]);
  const sec = parts.find(p => secKey(p) === cur);
  const lab = s => { const t = s.title.replace(/\s*\(.*\)$/,""); const m = t.match(/^(Chương \d+)\s*·\s*(.+)$/); const c = s.beats.filter(b => clipList(b.key).length).length; return `${esc(m ? m[1] : (s.kind==="day" ? "Ngày " + s.d : t))}<small>${c}/${s.beats.length} cảnh có clip</small>`; };
  const full = s => s.beats.length && s.beats.every(b => clipList(b.key).length);
  const ex = clipDoc(sec.id + "x");
  sb.innerHTML = `
  <p class="small muted dhelp">Mỗi cảnh ghi sẵn kịch bản cần những clip gì; gắn đủ loại nào thì loại đó hiện dấu tích. Gắn bao nhiêu clip cũng được: các lần quay lại, cảnh không lời, cảnh Pum nói, file lồng tiếng. Take nào ưng thì chạm sao, take nào hỏng thì ghi chú để AI bỏ qua. Clip vẫn nằm trên điện thoại, app chỉ ghi tên file.</p>
  <nav class="daypick" aria-label="Chọn chương">${parts.map(p => `<button data-dsec="${secKey(p)}" aria-pressed="${secKey(p)===cur}" class="${full(p)?"done":""}">${lab(p)}</button>`).join("")}</nav>
  <section class="vsec" style="border-top:0;margin-top:8px;padding-top:6px">
    <h2 class="disp">${esc(sec.title.replace(/\s*\(.*\)$/,""))}</h2>
    ${sec.beats.map(b => { const x = S.beats[b.key] || {}, cl = clipList(b.key); return `<article class="dbeat ${cl.length?"has":""}">
      <header><h3>${esc(b.title)}</h3><span class="tag ${cl.length?"":"soft"}">${cl.length ? cl.length + " clip" : "chưa có clip"}</span>${x.shot?`<span class="tag ok">đã quay</span>`:""}</header>
      ${needsHTML(b, cl)}
      ${x.note?`<p class="small dnote"><b>Ghi chú lúc quay:</b> ${esc(x.note)}</p>`:""}
      ${clipBox(b.key, "cảnh này", n)}
    </article>`; }).join("")}
    <article class="dbeat extra">
      <header><h3>Quay ngoài kịch bản</h3><span class="tag soft">${clipList(sec.id+"x").length} clip</span></header>
      <p class="small muted">Có cảnh hay mà kịch bản chưa có? Gắn vào đây, chạm gợi ý hoặc tự ghi vì sao quay và muốn AI đặt cảnh đó ở đâu.</p>
      <div class="rchips" role="group" aria-label="Gợi ý lý do">${REASONS.map(r => `<button type="button" data-rchip="rs-${sec.id}">${esc(r)}</button>`).join("")}</div>
      <label class="f">Vì sao quay, ý tưởng của Pum<textarea id="rs-${sec.id}" data-reason="${sec.id}x" placeholder="Ví dụ: gặp cô bán hàng vui tính, muốn chèn vào trước lúc ăn bánh canh">${esc(ex.reason||"")}</textarea></label>
      ${dictBtn("rs-" + sec.id)}
      ${clipBox(sec.id + "x", "phần này", n)}
    </article>
  </section>
  <div class="row" style="margin-top:20px"><button class="btn" data-step="2">Xong, qua bước gửi AI</button></div>`;
  sb.querySelectorAll("[data-dsec]").forEach(b => b.onclick = () => { LS.set(store, b.dataset.dsec); stay("#stepBody .daypick", () => stepClips(sb, sc, st, e, stats)); });
  sb.querySelectorAll("[data-step]").forEach(b => b.onclick = () => { LS.set("dungStep" + n, 2); render(); toTop(".stepper"); });
  bindClips(sb, n); bindDict(sb);
  sb.querySelectorAll("[data-rchip]").forEach(b => b.onclick = async () => { const ta = document.getElementById(b.dataset.rchip); if (!ta) return; ta.value = (ta.value.trim() ? ta.value.trim() + ". " : "") + b.textContent + ": "; ta.focus(); ta.setSelectionRange(ta.value.length, ta.value.length); });
  keepX(sb, ".daypick", "dung" + n);
}

function manifestText(sc){
  const lines = [`${sc.title}`];
  sc.sections.filter(s => s.kind !== "list").forEach(p => {
    const rows = []; p.beats.forEach(b => clipList(b.key).forEach(c => rows.push(`  ${b.title}: ${c.name} (${fmtT(c.dur)}, ${KINDS.find(k=>k[0]===c.kind)[1]}${c.best?", ưng":""})`)));
    clipList(p.id + "x").forEach(c => rows.push(`  Ngoài kịch bản: ${c.name} (${fmtT(c.dur)})`));
    if (rows.length) lines.push(p.title.replace(/\s*\(.*\)$/,""), ...rows);
  });
  return lines.join("\n");
}

function stepSend(sb, sc, st, e, stats){
  const n = sc.n, parts = sc.sections.filter(s => s.kind !== "list");
  const missing = []; parts.forEach(p => p.beats.forEach(b => { if (!clipList(b.key).length) missing.push(`${p.title.replace(/\s*\(.*\)$/,"").replace(/^Chương \d+ · /,"")} · ${b.title}`); }));
  const msg = `Dựng tập ${n === "testlate" ? "test (bản dậy muộn)" : n === "test" ? "test" : n} từ Pum Studio`;
  sb.innerHTML = `
  <section class="pub">
    <h3 class="disp">Gửi cho AI xem</h3>
    <div class="kpis"><div><b class="num">${stats.clips}</b><span>clip</span></div><div><b class="num">${fmtT(stats.dur)}</b><span>tổng thời lượng</span></div><div><b class="num">${stats.withClip}/${stats.beats}</b><span>cảnh có clip</span></div><div><b class="num">${fmtSize(stats.size) || "0 MB"}</b><span>dung lượng</span></div></div>
    ${missing.length ? `<details class="miss"><summary>${missing.length} cảnh chưa có clip</summary><ul>${missing.map(m => `<li>${esc(m)}</li>`).join("")}</ul><p class="small muted">Vẫn gửi được. AI sẽ dựng với những gì có và báo chỗ nào thiếu.</p></details>` : `<p class="ok-line">Cảnh nào cũng đã có clip.</p>`}
    <ol class="howto">
      <li><b>Bấm “Gửi cho AI”</b> để AI biết clip nào thuộc cảnh nào.</li>
      <li><b>Mở chat Claude trong project Pum Content Studio</b>, đính kèm đúng các file đã gắn (danh sách ở dưới).</li>
      <li><b>Nhắn câu này:</b> <code>${esc(msg)}</code></li>
    </ol>
    <div class="row"><button class="btn rose" data-sendai="1" ${stats.clips ? "" : "disabled"}>${e.sentAt ? "Gửi lại cho AI" : "Gửi cho AI"}</button><button class="btn ghost" data-copymsg="1">Chép câu nhắn</button><button class="btn ghost" data-copylist="1" ${stats.clips ? "" : "disabled"}>Chép danh sách file</button></div>
    ${e.sentAt ? `<p class="small muted" style="margin-top:10px">Đã gửi lúc ${new Date(e.sentAt).toLocaleString("vi-VN")}.</p>` : ""}
    <details class="miss" style="margin-top:14px"><summary>Danh sách file theo chương</summary><pre class="mf">${esc(manifestText(sc))}</pre></details>
  </section>`;
  const copy = t => (navigator.clipboard ? navigator.clipboard.writeText(t) : Promise.reject()).then(() => toast("Đã chép"), () => toast("Chưa chép được, giữ lâu để chép tay"));
  sb.querySelector("[data-copymsg]").onclick = () => copy(msg);
  sb.querySelector("[data-copylist]").onclick = () => copy(manifestText(sc));
  sb.querySelector("[data-sendai]").onclick = async () => { await saveEd(n, {status:"gui", sentAt:Date.now(), script:`scripts/tap${n}.enc`}); toast("Đã gửi. Giờ qua chat Claude gửi file nha."); };
}

function boardHTML(bd){
  const th = id => { const t = LS.get("th:" + id, ""); return t ? `<img src="${t}" alt="">` : ""; };
  return `
  <div class="bsum"><p>${esc(bd.summary || "")}</p>${bd.length?`<p class="small muted">Dài dự kiến: ${esc(bd.length)}${bd.music && bd.music.length ? ` · Nhạc: ${bd.music.map(m => esc(m.title || m.track)).join(", ")}` : ""}</p>`:""}</div>
  ${(bd.chapters || []).map(c => `<section class="bch"><h4>${esc(c.title)}${c.sec?` <span class="muted small">· khoảng ${fmtT(c.sec)}</span>`:""}</h4>${c.plan?`<p class="small">${esc(c.plan)}</p>`:""}
    <ol class="bsegs">${(c.segs || []).map(s => `<li><div class="bth">${th(s.take || (s.clips||[])[0])}</div><div><p><b>${esc(s.label || "")}</b>${s.sec?` <span class="muted small">${s.sec}s</span>`:""}</p>
      ${s.use?`<p class="small">${esc(s.use)}</p>`:""}
      <p class="bmeta">${s.voice?`<span class="tag soft">${esc(s.voice)}</span>`:""}${s.text?`<span class="tag soft">Chữ: ${esc(s.text)}</span>`:""}${s.fx?`<span class="tag soft">${esc(s.fx)}</span>`:""}</p></div></li>`).join("")}</ol></section>`).join("")}
  ${bd.extras && bd.extras.length ? `<section class="bch"><h4>Cảnh ngoài kịch bản</h4><ul>${bd.extras.map(x => `<li>${esc(x.idea || x)}</li>`).join("")}</ul></section>` : ""}
  ${bd.missing && bd.missing.length ? `<section class="bch warn"><h4>Còn thiếu</h4><ul>${bd.missing.map(x => `<li>${esc(x)}</li>`).join("")}</ul></section>` : ""}
  ${bd.questions && bd.questions.length ? `<section class="bch ask"><h4>AI cần Pum trả lời</h4><ol>${bd.questions.map(x => `<li>${esc(x)}</li>`).join("")}</ol></section>` : ""}`;
}

function stepBoard(sb, sc, st, e){
  const n = sc.n;
  if (!e.boardV){ sb.innerHTML = `<section class="pub"><h3 class="disp">Hướng dựng</h3><p class="muted">AI chưa gửi hướng dựng. Sau khi gửi file trong chat, AI xem hết clip rồi đưa hướng dựng lên đây.</p></section>`; return; }
  const fb = e.feedback || {};
  sb.innerHTML = `<section class="pub"><h3 class="disp">Hướng dựng AI đề xuất <span class="tag soft">bản ${e.boardV}</span></h3><div id="bdBox"><p class="muted">Đang mở…</p></div></section>
  <section class="pub">
    <h3 class="disp">Góp ý của Pum</h3>
    <label class="f">Muốn đổi gì, thêm gì, bỏ gì? Trả lời luôn câu hỏi của AI ở đây.<textarea id="fbText" style="min-height:150px" placeholder="Ví dụ: mở bằng cảnh dậy muộn, bỏ đoạn đi bộ dài ở buôn, nhạc chương 3 vui hơn">${esc(fb.text || "")}</textarea></label>
    ${dictBtn("fbText")}
    <div class="row" style="margin-top:14px"><button class="btn ghost" data-fbsave="1">Lưu góp ý</button><button class="btn rose" data-fbok="1">${fb.approved ? "Đã duyệt · gửi lại" : "Duyệt, cho AI dựng"}</button></div>
    ${fb.approved ? `<p class="small muted" style="margin-top:10px">Đã duyệt lúc ${new Date(fb.at).toLocaleString("vi-VN")}. Nhắn Claude trong chat: <code>Dựng tiếp tập ${esc(String(n))}</code></p>` : ""}
  </section>`;
  const ta = $("#fbText"); ta.dataset.keep = "0";
  sb.querySelector("[data-fbsave]").onclick = async () => { await saveEd(n, {feedback:{text:ta.value, at:Date.now(), approved:!!fb.approved, v:e.boardV}}); toast("Đã lưu góp ý"); };
  sb.querySelector("[data-fbok]").onclick = async () => { await saveEd(n, {feedback:{text:ta.value, at:Date.now(), approved:true, v:e.boardV}, status:"duyet"}); toast("Đã duyệt. Nhắn Claude: Dựng tiếp tập " + n); };
  bindDict(sb);
  encJSON(`drafts/${n}/board.enc?v=${e.boardV}`).then(bd => { const b = $("#bdBox"); if (b) b.innerHTML = boardHTML(bd); }).catch(() => { const b = $("#bdBox"); if (b) b.innerHTML = `<p class="notice">Chưa mở được hướng dựng. Bấm Tải lại trên cùng thử.</p>`; });
}

let draftURL = {};
function stepDraft(sb, sc, st, e){
  const n = sc.n;
  if (!e.draftV){ sb.innerHTML = `<section class="pub"><h3 class="disp">Bản nháp</h3><p class="muted">Chưa có bản nháp. Duyệt hướng dựng xong, nhắn Claude để AI dựng.</p></section>`; return; }
  const v = e.draftV, notes = (e.notes || []).filter(x => x.v === v), k = `${n}:${v}`;
  sb.innerHTML = `
  <section class="pub draftbox">
    <h3 class="disp">Bản nháp v${v} ${e.draftDur ? `<span class="tag soft">${fmtT(e.draftDur)}</span>` : ""}</h3>
    <div class="player" id="plWrap">${draftURL[k] ? `<video id="dv" controls playsinline src="${draftURL[k]}"></video>` : `<button class="btn rose" id="openDraft">Mở bản nháp${e.draftSize ? ` (${fmtSize(e.draftSize)})` : ""}</button><p class="small muted">Nên mở bằng wifi. Đây là bản nhẹ để xem; bản đẹp 1080p AI gửi trong chat khi chốt.</p>`}</div>
    <div class="tlhead"><span class="small muted">Chạm vào một hình để tua tới và góp ý</span><span class="zoom"><button type="button" data-z="-1" aria-label="Thu nhỏ dòng thời gian">−</button><button type="button" data-z="1" aria-label="Phóng to dòng thời gian">+</button></span></div>
    <p class="tllegend" aria-hidden="true"><span><i style="background:var(--ink)"></i>Hình</span><span><i style="background:var(--tape)"></i>Chữ trên hình</span><span><i style="background:var(--blush)"></i>Lồng tiếng</span><span><i style="background:#EFE6EA"></i>Nhạc</span></p>
    <div class="tl" id="tl"><p class="muted small" style="padding:12px">Đang mở dòng thời gian…</p></div>
    <div id="segAct"></div>
    <div class="row" style="margin-top:12px"><button class="btn ghost" data-noteat="1">Góp ý tại giây đang xem</button></div>
  </section>
  <section class="pub">
    <h3 class="disp">Góp ý trên bản nháp <span class="tag ${notes.length?"":"soft"}">${notes.length}</span></h3>
    ${notes.length ? `<ul class="notes">${notes.map(x => `<li><button type="button" class="tbtn" data-seek="${x.t||0}">${fmtT(x.t)}</button><div><b>${esc(NOTEK[x.kind] || "Góp ý")}</b>${x.seg ? ` · ${esc(x.segLabel || "")}` : ""}<p>${esc(x.text || "")}</p></div><button type="button" class="cdel" data-delnote="${x.id}" aria-label="Xoá góp ý">${IC.x}</button></li>`).join("")}</ul>` : `<p class="muted">Chưa có góp ý nào. Xem bản nháp, chạm vào đoạn muốn sửa.</p>`}
    <details class="miss" id="subBox"><summary>Phụ đề (sửa chữ nghe sai)</summary><div id="subList"><p class="small muted">Mở bản nháp để xem phụ đề.</p></div></details>
    <div class="row" style="margin-top:14px"><button class="btn rose" data-fix="1" ${notes.length ? "" : "disabled"}>Gửi góp ý cho AI sửa</button><button class="btn" data-final="1">Ưng rồi, xuất bản cuối</button></div>
    ${e.status === "sua" || e.status === "chot" ? `<p class="small muted" style="margin-top:10px">Nhắn Claude trong chat: <code>${e.status === "sua" ? "Sửa bản nháp tập " + esc(String(n)) : "Xuất bản cuối tập " + esc(String(n))}</code></p>` : ""}
  </section>`;
  let TL = null, z = Number(LS.get("tlz", 14));
  const addNote = async o => { const all = (e.notes || []).slice(); all.push(Object.assign({id:uid(), v, at:Date.now()}, o)); await saveEd(n, {notes: all}); toast("Đã ghi góp ý"); };
  const vid = () => $("#dv");
  const drawTL = () => {
    if (!TL) return; const box = $("#tl"); z = Math.max(z, (box.clientWidth - 8) / TL.dur); const W = TL.dur * z;
    const blk = (a, b, cls, inner, attrs="") => `<div class="tb ${cls}" style="left:${a*z}px;width:${Math.max(cls==="vs"?44:6,(b-a)*z-2)}px" ${attrs}>${inner}</div>`;
    const ticks = []; const step = z >= 12 ? 5 : z >= 6 ? 10 : z >= 3 ? 30 : 60; for (let t = 0; t <= TL.dur; t += step) ticks.push(`<span style="left:${t*z}px">${fmtT(t)}</span>`);
    const texts = [], vos = []; TL.segments.forEach(s => { (s.text||[]).forEach(t => texts.push(blk(s.start, s.end, "tx", esc(t)))); if (s.vo) vos.push(blk(s.start, s.end, "vo", "Lồng tiếng")); });
    box.innerHTML = `<div class="tlin" style="width:${W}px"><div class="ruler">${ticks.join("")}</div>
      <div class="trk vids">${TL.segments.map((s, i) => blk(s.start, s.end, "vs", `${s.thumb ? `<img src="${s.thumb}" alt="">` : ""}<span>${esc(s.label || "")}</span>`, `data-si="${i}" role="button" tabindex="0" aria-label="Đoạn ${esc(s.label||"")} từ ${fmtT(s.start)}"`)).join("")}</div>
      <div class="trk">${texts.join("")}</div><div class="trk">${vos.join("")}</div>
      <div class="trk">${(TL.music || []).map(m => blk(m.start, m.end, "mu", "Nhạc · " + esc(m.title || m.track))).join("")}</div>
      <i class="ph" id="ph"></i></div>`;
    box.querySelectorAll("[data-si]").forEach(b => { const go = () => selSeg(Number(b.dataset.si)); b.onclick = go; b.onkeydown = ev => { if (ev.key === "Enter" || ev.key === " "){ ev.preventDefault(); go(); } }; });
    syncPH();
  };
  const syncPH = () => { const p = $("#ph"), v2 = vid(); if (p && v2) p.style.left = (v2.currentTime * z) + "px"; };
  const selSeg = i => {
    const s = TL.segments[i]; const v2 = vid(); if (v2){ v2.currentTime = s.start + 0.05; }
    $("#tl").querySelectorAll(".vs").forEach((b, j) => b.classList.toggle("sel", j === i));
    const box = $("#segAct");
    box.innerHTML = `<div class="segact"><p><b>${esc(s.label || "Đoạn " + (i+1))}</b> <span class="muted small">${fmtT(s.start)}–${fmtT(s.end)}</span></p>
      <div class="acts">${["bo","ngan","take","chu","nhac","y"].map(k => `<button type="button" class="btn small ghost" data-act="${k}">${NOTEK[k]}</button>`).join("")}</div>
      <div id="actForm"></div></div>`;
    box.querySelectorAll("[data-act]").forEach(b => b.onclick = () => {
      const kk = b.dataset.act;
      if (kk === "bo"){ addNote({kind:"bo", seg:s.id, segLabel:s.label, t:s.start, text:"Bỏ đoạn này"}); return; }
      const ph = {ngan:"Ngắn lại còn bao lâu, giữ phần nào?", take:"Muốn dùng take nào, hoặc tả take đó", chu:"Chữ trên hình mới", nhac:"Nhạc vui hơn, nhẹ hơn, hay bỏ nhạc?", y:"Góp ý cho đoạn này"}[kk];
      $("#actForm").innerHTML = `<label class="f" style="margin-top:10px">${NOTEK[kk]}<textarea id="actTa" placeholder="${ph}">${kk === "chu" ? esc((s.text||[]).join(" / ")) : ""}</textarea></label><div class="row" style="margin-top:8px"><button class="btn small" id="actOk">Ghi góp ý</button></div>`;
      $("#actOk").onclick = () => addNote({kind:kk, seg:s.id, segLabel:s.label, t:s.start, text:$("#actTa").value.trim()});
      $("#actTa").focus();
    });
    box.scrollIntoView({block:"nearest"});
  };
  const subList = () => {
    const box = $("#subList"); if (!box || !TL) return;
    box.innerHTML = `<p class="small muted">Phụ đề lấy từ lời Pum nói, máy nghe có thể sai. Sửa xong ô nào là tự ghi thành góp ý.</p><ol class="subs">${TL.subs.map((s2, i) => `<li><button type="button" class="tbtn" data-seek="${s2[0]}">${fmtT(s2[0])}</button><input type="text" value="${esc(s2[2])}" data-sub="${i}" aria-label="Phụ đề lúc ${fmtT(s2[0])}"></li>`).join("")}</ol>`;
    box.querySelectorAll("[data-sub]").forEach(inp => { inp.dataset.keep = "0"; inp.onchange = () => { const s2 = TL.subs[Number(inp.dataset.sub)]; addNote({kind:"sub", t:s2[0], text:`“${s2[2]}” → “${inp.value.trim()}”`}); }; });
    bindSeek(box);
  };
  const bindSeek = root => root.querySelectorAll("[data-seek]").forEach(b => b.onclick = () => { const v2 = vid(); if (v2){ v2.currentTime = Number(b.dataset.seek); v2.play().catch(()=>{}); v2.scrollIntoView({block:"center"}); } else toast("Mở bản nháp trước nha"); });
  bindSeek(sb);
  sb.querySelectorAll("[data-z]").forEach(b => b.onclick = () => { z = Math.max(1.5, Math.min(24, z * (b.dataset.z === "1" ? 1.6 : 1/1.6))); LS.set("tlz", z); drawTL(); });
  sb.querySelectorAll("[data-delnote]").forEach(b => b.onclick = async () => { await saveEd(n, {notes:(e.notes||[]).filter(x => x.id !== b.dataset.delnote)}); });
  sb.querySelector("[data-noteat]").onclick = () => { const v2 = vid(); const t = v2 ? v2.currentTime : 0; const s = TL && TL.segments.find(x => t >= x.start && t < x.end);
    $("#segAct").innerHTML = `<div class="segact"><label class="f">Góp ý tại ${fmtT(t)}<textarea id="atTa" placeholder="Ví dụ: chỗ này nhạc to quá, chen thêm cảnh tô bánh canh"></textarea></label><div class="row" style="margin-top:8px"><button class="btn small" id="atOk">Ghi góp ý</button></div></div>`;
    $("#atOk").onclick = () => addNote({kind:"y", t, seg:s ? s.id : "", segLabel:s ? s.label : "", text:$("#atTa").value.trim()}); $("#atTa").focus(); };
  sb.querySelector("[data-fix]").onclick = async () => { await saveEd(n, {status:"sua", fixAt:Date.now()}); toast("Đã gửi. Nhắn Claude: Sửa bản nháp tập " + n); };
  sb.querySelector("[data-final]").onclick = async () => { if (!confirm("Chốt bản nháp này để AI xuất bản cuối 1080p?")) return; await saveEd(n, {status:"chot", finalAsk:Date.now()}); toast("Đã chốt. Nhắn Claude: Xuất bản cuối tập " + n); };
  const ob = $("#openDraft");
  if (ob) ob.onclick = async () => {
    ob.disabled = true; ob.textContent = "Đang tải bản nháp…";
    try{ const r = await fetch(`drafts/${n}/v${v}.mp4.enc`); if (!r.ok) throw 0; const buf = await window.PUMDECB(await r.arrayBuffer());
      draftURL[k] = URL.createObjectURL(new Blob([buf], {type:"video/mp4"}));
      $("#plWrap").innerHTML = `<video id="dv" controls playsinline src="${draftURL[k]}"></video>`; hookVid(); subList();
    }catch(err){ ob.disabled = false; ob.textContent = "Mở lại bản nháp"; toast("Chưa tải được bản nháp, thử lại nha"); }
  };
  const hookVid = () => { const v2 = vid(); if (v2) v2.ontimeupdate = syncPH; };
  hookVid();
  encJSON(`drafts/${n}/v${v}.json.enc`).then(j => { TL = j; drawTL(); if (vid()) subList(); }).catch(() => { $("#tl").innerHTML = `<p class="notice small">Chưa mở được dòng thời gian.</p>`; });
}

function stepPost(sb, sc, st, e){
  sb.innerHTML = `${e.finalV ? `<section class="pub ok"><h3 class="disp">Bản cuối</h3><p>AI đã gửi file 1080p trong chat Claude. Tải về rồi đăng.</p>${e.credits ? `<label class="f" style="margin-top:12px">Ghi công nhạc (dán vào cuối mô tả YouTube và caption TikTok)<textarea readonly style="min-height:120px">${esc(e.credits)}</textarea></label>` : ""}</section>` : ""}<div id="postBox"></div>`;
  renderPost($("#postBox"), sc, st);
}

async function draftDesc(btn, sc, st){
  const notes = []; sc.sections.forEach(sec => (sec.beats||[]).forEach(b => { const y = S.beats[b.key]; if (y && y.note) notes.push(`- ${sec.kind==="day"?"Ngày "+sec.d+" · ":""}${b.title}: ${y.note}`); }));
  btn.disabled = true; btn.textContent = "Claude đang viết…";
  const prompt = `Viết mô tả YouTube tiếng Việt cho một tập dài của kênh "Thử đi cùng Pum", loạt "${T.series}". Pum xưng Pum, gọi người xem là bạn. Giọng: câu ngắn, gần gũi, tinh nghịch vừa đủ. Không dùng "ngon nhất", "tuyệt vời", "hành trình", "khám phá", "chữa lành", "trải nghiệm đáng nhớ". Không emoji ở đầu dòng.
Tập ${st.n}: ${sc.meta["Tên tập"]||st.place}
Câu hỏi của tập: ${sc.meta["Câu hỏi của tập"]||""}
Ghi chú thật từ hiện trường:
${notes.join("\n") || "(chưa có)"}
Cấu trúc: 2–3 câu mở kể tập này có gì, một dòng trống, danh sách các nơi trong tập (chỉ tên nơi có trong kịch bản hoặc ghi chú), một câu hỏi mời bình luận. Chỉ dùng giá, tên món, cảm nhận có trong ghi chú; thiếu thì để ___. Không viết chương, không viết hashtag. Chỉ trả về mô tả.`;
  try{ const r = await S.sample(prompt, {modelTier:"default"}); await put("vids", "ep"+st.n, {descDraft: r.text.trim()}); }
  catch(e){ if (e && e.code === "not_granted"){ S.sample = null; render(); } else { toast("Claude chưa viết được, thử lại sau."); btn.disabled = false; btn.textContent = "Nhờ Claude viết mô tả"; } }
}


/* ---------- hiệu ứng ---------- */
const FX = [
  ["chop_kem","Chớp kem","0,7 giây. Dùng khi đổi nơi hoặc đổi ngày. Cắt cảnh ở giây 0,3, lúc màn hình kem phủ kín."],
  ["bang_hong","Băng hồng quét","1 giây. Dùng giữa hai phần lớn trong ngày, ví dụ từ chợ sang quán cà phê. Cắt cảnh ở giây 0,5."],
  ["tim","Tim nở","1 giây. Dùng một lần mỗi tập, ngay trước kết quả bạn chọn. Cắt cảnh ở giây 0,5."],
  ["trang_giay","Trang giấy","0,9 giây. Dùng trước bảng chữ: sổ tiền, hộp kỷ niệm, chín lần bạn chọn. Cắt cảnh ở giây 0,4."]
];
const FXBG = ["bosang","chatuchak","maeklong","chouifong","indigo","paiwalk","mekong2","iconsiam","srisuphan","bangkrachao","amphawa","singha"];
let fxbgI = 0;
function fxVid(src, tall){ const bg = FXBG[(fxbgI++) % FXBG.length]; const pv = /\.webm$/.test(src) ? "fx/preview/" + src.slice(3).replace(/\//g, "__").replace(/\.webm$/, ".mp4") : src; return `<button type="button" class="fxv ${tall?"tall":""}" style="background-image:url(img/${bg}.jpg)" aria-label="Xem to"><video data-src="${pv}" muted playsinline preload="none"></video></button>`; }
function fxLinks(arr){ return `<p class="fxl">${arr.map(([t,u])=>`<button type="button" data-dl="${u}">${t}</button>`).join("")}</p>`; }
document.addEventListener("click", async e => {
  const b = e.target.closest("[data-dl]"); if (!b) return;
  const dl = S.downloads, u = b.dataset.dl;
  if (!dl){ const a = document.createElement("a"); a.href = u; a.download = "pum_" + u.split("/").pop(); document.body.appendChild(a); a.click(); a.remove(); return; }
  b.disabled = true;
  try{ const r = await fetch(u); if (!r.ok) throw 0; await dl.save({filename: "pum_" + u.split("/").pop(), data: await r.blob()}); }
  catch(err){ if (err && err.code === "declined") {} else if (err && err.code === "rate_limited") toast("Đang mở một tệp khác, thử lại sau chút."); else toast("Chưa tải được tệp này."); }
  b.disabled = false;
});


function fxCard(src, title, desc, links, tall){
  return `<div class="fxc">${fxVid(src, tall)}<b>${title}</b>${desc?`<span>${desc}</span>`:""}${fxLinks(links)}</div>`;
}
function vFx(v, embed){
  const eps = T.stages; fxbgI = 0;
  v.innerHTML = `
  <section><p class="lead" style="max-width:62ch">Phần lớn tập dài là cắt thẳng theo hành động. Hiệu ứng chỉ dùng ở chỗ đổi nơi, đổi ngày, mở tập và cuối tập. Bấm vào một hiệu ứng để xem to.</p></section>
  <nav class="fxjump"><div class="seg" style="margin:0"><a href="#fx-cc">Chuyển cảnh</a><a href="#fx-mo">Mở tập</a><a href="#fx-ngay">Thẻ ngày</a><a href="#fx-cuoi">Cuối tập</a></div></nav>
  <section class="sec strip">
    <h2 class="disp" style="font-size:24px;margin-bottom:12px">Dùng trong CapCut</h2>
    <ol class="steps3">
      <li><b>Tải bản nền xanh</b><span>Bấm nút “nền xanh” dưới hiệu ứng, lưu vào máy.</span></li>
      <li><b>Đặt lên trên clip</b><span>Thêm vào lớp phủ (Overlay), kéo cho chỗ cắt cảnh nằm đúng điểm nối hai clip.</span></li>
      <li><b>Xóa nền xanh</b><span>Chọn Xóa nền, Phông xanh (Chroma key), chấm vào màu xanh, kéo cường độ tới khi hết viền xanh.</span></li>
    </ol>
    <p class="small muted" style="margin-top:10px">Bản “nền trong” (.webm) dùng cho trình dựng đọc được nền trong suốt, như DaVinci Resolve.</p>
  </section>
  <section class="sec">
    <h2 class="disp h-sec" id="fx-cc" style="margin-bottom:14px;scroll-margin-top:130px">Chuyển cảnh</h2>
    <div class="fxgrid">${FX.map(([k,n,d])=>fxCard(`fx/youtube/chuyen_canh_${k}.webm`, n, d, [["YouTube nền xanh",`fx/youtube/chuyen_canh_${k}_nenxanh.mp4`],["TikTok nền xanh",`fx/tiktok/chuyen_canh_${k}_nenxanh.mp4`],["Nền trong",`fx/youtube/chuyen_canh_${k}.webm`]])).join("")}</div>
  </section>
  <section class="sec">
    <h2 class="disp h-sec" id="fx-mo" style="margin-bottom:6px;scroll-margin-top:130px">Mở tập</h2>
    <p class="muted" style="margin-bottom:14px">4 giây. Đặt ngay sau phần mở bằng câu hỏi, trên cảnh Pum đầu tiên.</p>
    <div class="fxgrid">${eps.map(e=>fxCard(`fx/youtube/mo_tap_${e.n}.webm`, `Tập ${e.n} · ${esc(e.place)}`, "", [["Nền xanh",`fx/youtube/mo_tap_${e.n}_nenxanh.mp4`],["Nền trong",`fx/youtube/mo_tap_${e.n}.webm`]])).join("")}</div>
  </section>
  <section class="sec">
    <h2 class="disp h-sec" id="fx-ngay" style="margin-bottom:6px;scroll-margin-top:130px">Thẻ ngày</h2>
    <p class="muted" style="margin-bottom:14px">2,5 giây. Đặt ở cảnh đầu mỗi ngày. Tên ngày lấy theo kịch bản.</p>
    ${eps.map(e=>`<h3 class="fxh">Tập ${e.n} · ${esc(e.place)}</h3><div class="fxgrid days">${T.days.filter(d=>d.st===e.n).map(d=>{const n=String(d.d).padStart(2,"0");return fxCard(`fx/youtube/the_ngay/the_ngay_${n}.webm`, `Ngày ${d.d} · ${esc(d.date)}`, "", [["Nền xanh",`fx/youtube/the_ngay/the_ngay_${n}_nenxanh.mp4`],["Nền trong",`fx/youtube/the_ngay/the_ngay_${n}.webm`]])}).join("")}</div>`).join("")}
  </section>
  <section class="sec">
    <h2 class="disp h-sec" id="fx-cuoi" style="margin-bottom:14px;scroll-margin-top:130px">Cuối tập và cuối clip</h2>
    <div class="fxgrid">
      ${fxCard("fx/youtube/ket_tap_youtube.mp4","Kết tập YouTube","8 giây, nền kem. Hai ô hồng và vòng tròn là chỗ đặt màn hình kết thúc của YouTube (video tiếp theo, nút đăng ký).",[["Tải về","fx/youtube/ket_tap_youtube.mp4"]])}
      ${fxCard("fx/tiktok/tiktok_ket.webm","Cuối clip TikTok","2,5 giây, dọc. Ghép vào cuối mỗi clip TikTok cắt từ tập dài.",[["Nền xanh","fx/tiktok/tiktok_ket_nenxanh.mp4"],["Nền trong","fx/tiktok/tiktok_ket.webm"]],true)}
    </div>
  </section>`;
  v.querySelectorAll(".fxjump a").forEach(a => a.onclick = e => { e.preventDefault(); const el = document.getElementById(a.getAttribute("href").slice(1)); if (el) el.scrollIntoView({behavior:"smooth"}); });
  fxWire(v);
}
let fxIO = null;
function fxWire(root){
  if (fxIO) fxIO.disconnect();
  fxIO = "IntersectionObserver" in window ? new IntersectionObserver(es => es.forEach(e => { const vd = e.target; if (e.isIntersecting){ if (!vd.src) vd.src = vd.dataset.src; vd.play().catch(()=>{}); } else vd.pause(); }), {rootMargin:"100px"}) : null;
  root.querySelectorAll(".fxv video").forEach(vd => { vd.onended = () => setTimeout(() => { if (vd.isConnected){ vd.currentTime = 0; vd.play().catch(()=>{}); } }, 900); if (fxIO) fxIO.observe(vd); else vd.src = vd.dataset.src; });
  root.querySelectorAll(".fxv").forEach(b => b.onclick = () => {
    const src = b.querySelector("video").dataset.src, tall = b.classList.contains("tall"), sh = $("#sheet");
    sh.innerHTML = `<button class="btn small close" id="closeSheet">Đóng</button><div class="in"><div class="fxv big ${tall?"tall":""}"><video src="${src}" autoplay muted playsinline controls></video></div></div>`;
    sh.classList.add("open"); $("#sheetBg").classList.add("open");
    const bv = sh.querySelector("video"); bv.onended = () => setTimeout(() => { if (bv.isConnected){ bv.currentTime = 0; bv.play().catch(()=>{}); } }, 900);
    $("#closeSheet").onclick = closeSheet; $("#sheetBg").onclick = closeSheet;
  });
}

/* ---------- nói thay gõ ---------- */
function dictBtn(target){ return S.dictation ? `<button class="btn small ghost" type="button" data-dict="${target}">Nói thay gõ</button>` : ""; }
let dictOn = null;
function bindDict(root){
  root.querySelectorAll("[data-dict]").forEach(b => b.onclick = () => {
    const d = S.dictation, ta = document.getElementById(b.dataset.dict); if (!d || !ta) return;
    if (dictOn){ d.stop(); return; }
    const base = ta.value ? ta.value.replace(/\s*$/," ") : ""; let acc = "";
    d.onPartial(({text}) => { ta.value = base + acc + text; });
    d.onFinal(({text}) => { acc += text + " "; ta.value = base + acc; });
    d.onState(({state}) => { if (state === "idle"){ dictOn = null; b.textContent = "Nói thay gõ"; } else { dictOn = true; b.textContent = "Dừng nghe"; } });
    d.start().catch(e => { dictOn = null; b.textContent = "Nói thay gõ"; if (e && e.code === "not_granted"){ S.dictation = null; render(); } });
  });
}

/* ---------- Kênh ---------- */
const GUIDE = [["","Cách làm"],["truoc","Trước chuyến"],["hieu-ung","Hiệu ứng"],["thuong-hieu","Thương hiệu"]];
function vBrand(v, r){
  const sub = (r && r.a) || "";
  const head = `<section><h1 class="disp h-hero">Cẩm nang</h1></section><nav class="seg" aria-label="Phần" style="margin-top:20px">${GUIDE.map(([k,n])=>`<a href="#/kenh${k?"/"+k:""}" ${k===sub?'aria-current="page"':''}>${n}</a>`).join("")}</nav>`;
  if (sub === "hieu-ung"){ const box = document.createElement("div"); vFx(box, true); v.innerHTML = head; v.appendChild(box); return; }
  vBrandAll(v);
  const tags = ["th","cach","truoc","truoc","x","cach","cach","th","th","th","th","th"];
  const want = {"":"cach","truoc":"truoc","thuong-hieu":"th"}[sub] || "cach";
  [...v.children].forEach((el, i) => { if (tags[i] !== want) el.remove(); });
  v.insertAdjacentHTML("afterbegin", head);
  const first = v.children[2]; if (first) first.style.marginTop = "8px";
}
function vBrandAll(v){
  v.innerHTML = `
  <section class="hero">
    <div><img src="brand/logo.png" alt="Pum" style="height:96px;width:auto;display:block">
      <h1 class="disp" style="font-size:clamp(40px,6vw,64px);margin-top:20px">Thử đi cùng Pum</h1>
      <p class="lead" style="margin-top:14px"><span class="tape">Bạn chọn, Pum thử.</span></p>
      <p style="margin-top:14px;max-width:52ch">Pum thử thật, kể thật, và rủ bạn đi cùng. Chuyến này là loạt “${esc(T.series)}”: 7 tập YouTube dài, TikTok cắt từ từng tập, hashtag #thudicungpum ${esc(T.tag)}.</p></div>
    <figure class="post plain" style="transform:rotate(-2deg)"><img src="brand/hello.png" alt="Mini Pum vẫy tay"></figure>
  </section>
  <section class="sec">
    <h2 class="disp h-sec" style="margin-bottom:8px">Ba sợi chỉ của Pum</h2>
    <p class="lead" style="max-width:62ch;margin-bottom:18px">Pum không kể lịch sử, không phỏng vấn ai, không quay đoạn nói chuyện với người lạ. Mỗi tập chạy trên ba sợi chỉ này, mỗi nơi chỉ nói một câu về nơi đó.</p>
    <ol class="howto">${[
      ["Bạn chọn, Pum thử","Chín lựa chọn lấy từ bình chọn thật trước chuyến: màu đồ, hoa văn, mức cay, 500 baht mua gì. Nói rõ số bình chọn. Không đủ bình chọn thì nói Pum tự chọn."],
      ["Gu con gái của Pum","Bộ đồ của ngày, một quán cà phê Pum tự chọn, tủ 7-Eleven, một món đồ dễ thương, làm tóc, làm móng."],
      ["Hộp kỷ niệm","Mỗi thành phố Pum bỏ một món nhỏ vào hộp. Giữa chuyến mở ra xem, tập cuối bày hết ra kể từng món."],
      ["Mở tập bằng lời thú nhận","1 phút đầu: cắt nhanh cảnh hay nhất, lồng tiếng câu hỏi của tập và luật bạn chọn."],
      ["Phản ứng thật trên máy","Bật máy trước khi việc xảy ra: miếng đầu, lúc mặc đồ xong, lúc mở ô, lúc tàu tới. Mua đồ thì chỉ tay hoặc đưa hình, chỉ quay tay và món."],
      ["Cuối tập đếm lại","Kết quả bạn chọn, món mới trong hộp kỷ niệm, một câu Pum tự nói. Hé tập sau, hỏi người xem một câu."]
    ].map(([a,b])=>`<li><b>${a}</b><span>${b}</span></li>`).join("")}</ol>
  </section>
  <section class="sec">
    <h2 class="disp h-sec" style="margin-bottom:8px">Bình chọn trước chuyến</h2>
    <p style="max-width:62ch;margin-bottom:12px">Đăng trên TikTok hoặc story trước 7/12, chụp lại kết quả. Các tập dùng đúng số này.</p>
    <ul class="check">${[
      "Bộ đồ Lanna: tông hồng hay tông tím? (tập 1)",
      "Hoa văn vẽ lên ô Bo Sang: hoa, con mèo hay tên Pum? (tập 1)",
      "Lên đồi trà: váy trắng nhẹ hay đồ thể thao? (tập 2)",
      "Phố đêm Pai: món nhìn lạ nhất hay món có hàng dài nhất? (tập 3)",
      "Sáng lạnh ở Pai: một áo khoác dày hay nhiều lớp mỏng? (tập 3)",
      "Gỏi đu đủ: không cay, cay chút xíu hay cay như người địa phương? (tập 4)",
      "Khăn chàm đêm Noel: quàng cổ, buộc tóc hay khoác vai? (tập 5)",
      "500 baht ở Chatuchak: chỉ mua đồ mặc hay đồ ăn? (tập 6)",
      "Đêm giao thừa: váy hồng hay đồ trắng? (tập 7)"
    ].map(t=>`<li><span>${t}</span></li>`).join("")}</ul>
  </section>
  <section class="sec">
    <h2 class="disp h-sec" style="margin-bottom:8px">Sổ tay tiếng Thái</h2>
    <p style="max-width:62ch;margin-bottom:12px"><b>Dùng riêng khi đi, không đưa vào video.</b> Lưu vào điện thoại, cần thì đưa màn hình chữ Thái cho người bán. Cách đọc là gần đúng. Bấm nghe Google Dịch đọc vài lần rồi bắt chước. Con gái nói “kha” ở cuối câu, câu hỏi thì “khá”.</p>
    <div class="phr">${[
      ["1","สวัสดีค่ะ","xa-oát-đi kha","xin chào"],["2","ขอบคุณค่ะ","khọp-khun kha","cảm ơn"],["3","เอาอันนี้ค่ะ","ao an ní kha","lấy cái này"],["4","สวยไหมคะ","xuổi mái khá","đẹp không?"],["5","เท่าไหร่คะ","thâu-rài khá","bao nhiêu tiền?"],["6","ลดหน่อยได้ไหมคะ","lột nòi đai mái khá","bớt chút được không?"],["7","ลำ","lăm","ngon (miền Bắc)"],["8","ขอโทษค่ะ","khỏ-thốt kha","xin lỗi"],["9","เหนื่อยมาก","nười mác","mệt quá"],["10","น่ารัก","nả-rắc","dễ thương"],["11","นี่คืออะไรคะ","ni khư a-rai khá","cái này là gì?"],["12","หนาว","nảo","lạnh"],["13","ไม่เผ็ด","mây phết","không cay"],["14","เผ็ดนิดหน่อย","phết nít nòi","cay chút xíu"],["15","แซ่บ","xẹp","ngon (kiểu Isan)"],["16","สีนี้","xỉ ní","màu này"],["17","เมอร์รี่คริสต์มาส","mơ-ri khrít-mát","Giáng sinh vui vẻ"],["18","ห้องน้ำอยู่ที่ไหนคะ","hông-nám yù thì nải khá","nhà vệ sinh ở đâu?"],["19","รถไฟ","rốt-phai","tàu hỏa"],["20","จักรยาน","chắc-ra-yan","xe đạp"],["21","เอาแบบนี้ค่ะ","ao bẹp ní kha","lấy kiểu này"],["22","สวัสดีปีใหม่","xa-oát-đi pi mài","chúc mừng năm mới"]
    ].map(([n,t,r,v])=>`<div><span class="n num">${n}</span><b>${r}</b><span>${v}</span><small lang="th">${t}</small></div>`).join("")}</div>
  </section>
  <section class="sec notice"><b>Hiệu ứng và chuyển cảnh</b> nằm ở mục <a href="#/hieu-ung">Hiệu ứng</a>: xem chạy thử, cách dùng và tải về.</section>
  <section class="sec grid2">
    <div>
      <h2 class="disp h-sec" style="margin-bottom:12px">Tên tập và thumbnail</h2>
      <dl class="facts" style="grid-template-columns:96px minmax(0,1fr)">
        <dt>Tên</dt><dd>${esc(T.series)} #số | Nơi: điều 1, điều 2 & điều 3</dd>
        <dt>Thumbnail</dt><dd>Tên nơi thật to, ba nhãn ngắn (một nhãn là điều bạn chọn), Pum ở giữa nhìn vào máy</dd>
        <dt>Chương</dt><dd>Mở tập, từng ngày, cuối tập. Điền giờ thật sau khi dựng</dd>
        <dt>TikTok</dt><dd>Cắt 4–5 clip từ tập đã đăng, mỗi clip một cảnh có phản ứng thật</dd>
      </dl>
    </div>
    <div>
      <h2 class="disp h-sec" style="margin-bottom:12px">Lúc quay</h2>
      <ul class="check">${["Bật máy trước khi việc xảy ra: tàu tới, mở nắp, miếng đầu tiên.","Mỗi nơi quay thêm 2–3 phút cảnh nền để lồng tiếng.","Xin phép trước khi quay rõ mặt người lạ. Không được thì quay tay và món.","Tối nào cũng ghi giá và câu đã nói vào ghi chú cảnh.","Không dùng cảnh hay nhạc của người khác khi chưa có quyền."].map(t=>`<li><span>${t}</span></li>`).join("")}</ul>
    </div>
  </section>
  <section class="sec">
    <h2 class="disp h-sec" style="margin-bottom:10px">Năm tuyến trong chuyến này</h2>
    <ul class="pillars">${[["Đi thử một nơi","Đi đâu thử đó","Baan Kang Wat, cầu tre, chợ đường tàu"],["Ăn thử một món","Món này thử nha","Món lạ ở Pai, mức cay bạn chọn, tủ 7-Eleven"],["Thử một điều mới","Lần đầu của Pum","Leo thác chân trần, chợ đường tàu, giao thừa bên sông"],["Thử một phiên bản Pum","Đổi chút cùng Pum","Đồ Lanna, khăn chàm, đồ giao thừa bạn chọn"],["Thử rồi, kể bạn nghe","Thử rồi nói thật","Nửa chuyến, 28 ngày hết bao nhiêu"]].map(([a,b,c])=>`<li><b>${a}</b><small>Series “${b}” · ${c}</small></li>`).join("")}</ul>
  </section>
  <section class="sec grid2">
    <div>
      <h2 class="disp h-sec" style="margin-bottom:12px">Giọng Pum</h2>
      <dl class="facts" style="grid-template-columns:96px minmax(0,1fr)">
        <dt>Xưng</dt><dd>Pum, mình; gọi bạn, bọn mình</dd>
        <dt>Nhịp</dt><dd>Câu ngắn, lời mời tự nhiên, tinh nghịch vừa đủ</dd>
        <dt>Tránh</dt><dd>“ngon nhất đời”, “100% hợp mọi người”, “chữa lành”, giả làm chuyên gia</dd>
        <dt>Lồng tiếng</dt><dd>Như kể cho bạn nghe tối hôm đó, không đọc như bài thuyết minh</dd>
      </dl>
    </div>
    <div>
      <h2 class="disp h-sec" style="margin-bottom:12px">Luật thật</h2>
      <ul class="check">${["Không bịa giá, cảm nhận, “lần đầu”, lời người khác.","Phụ đề chỉ lấy từ lời Pum nói trong clip.","Giá ghi kèm nơi và ngày, cả baht lẫn đồng.","Không chê người bán, không đoán chuyện vệ sinh.","Hỏi trước khi quay cận mặt người lạ."].map(t=>`<li><span>${t}</span></li>`).join("")}</ul>
    </div>
  </section>
  <section class="sec grid2">
    <div>
      <h2 class="disp h-sec" style="margin-bottom:12px">Màu và chữ</h2>
      <div class="swatch"><div style="background:#E85C91;color:#fff">Rose<br>#E85C91</div><div style="background:#FFD0E3">Tape<br>#FFD0E3</div><div style="background:#392630;color:#FFF8F5">Cocoa<br>#392630</div><div style="background:#FFF8F5;outline:1px solid var(--line);outline-offset:-1px">Cream<br>#FFF8F5</div></div>
      <p style="margin-top:14px">Hook và tiêu đề: <b class="disp" style="font-size:20px">Inter 900 nghiêng</b>. Nhãn, lời mời: <b>Nunito</b>. Phụ đề: Be Vietnam Pro 800, trắng viền cocoa.</p>
    </div>
    <div>
      <h2 class="disp h-sec" style="margin-bottom:12px">Chữ trên hình</h2>
      <dl class="facts" style="grid-template-columns:110px minmax(0,1fr)">
        <dt><span class="tape" style="font-size:14px">Băng hồng</span></dt><dd>Hook mở đầu, kết luận</dd>
        <dt>Bưu thiếp</dt><dd>Nơi, ngày, giá</dd>
        <dt>Nhãn</dt><dd>Bước, mốc, A/B</dd>
        <dt>Hộp câu hỏi</dt><dd>Lời mời cuối, kèm một Mini Pum</dd>
      </dl>
    </div>
  </section>
  <section class="sec">
    <h2 class="disp h-sec" style="margin-bottom:14px">Mini Pum</h2>
    <div class="minis">${[["hello","Chào"],["camera","Máy ảnh"],["love","Tim"],["wow","Wow"],["coffee","Cà phê"]].map(([k,t])=>`<figure><img src="brand/${k}.png" alt="Mini Pum ${t}">${t}</figure>`).join("")}</div>
    <p class="small muted" style="margin-top:10px">Tối đa một Mini Pum mỗi khung, thường ở lời mời cuối. Dùng đúng tệp gốc, không vẽ lại.</p>
  </section>
  <section class="sec">
    <h2 class="disp h-sec" style="margin-bottom:10px">Nguồn giá và giờ mở cửa</h2>
    <ul class="srcs">${T.sources.map(([l,u])=>`<li><a href="${u}" target="_blank" rel="noopener">${esc(l)}</a></li>`).join("")}</ul>
  </section>
  <section class="sec notice"><b>Dữ liệu lưu ở đâu?</b> Chi tiêu, nhật ký, cảnh đã quay và phiếu dựng lưu cùng trang này, mở trên điện thoại hay máy tính đều thấy. ${esc(S.sync)}.</section>`;
}
boot();
