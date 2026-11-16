(function(){
"use strict";
const SB = "https://lpiwmdomdzebzhmxzesn.supabase.co", KEY = "sb_publishable_6H1om-emHz6RrLBy1guQfg_PfGyseKE", SALT = "60370fbbacf66f1f564f02b04b4a86ad", ITER = 310000;
const hex = h => new Uint8Array(h.match(/../g).map(x => parseInt(x, 16)));
let PASS = null, AES = null;
async function rpc(fn, args){
  const r = await fetch(`${SB}/rest/v1/rpc/${fn}`, {method:"POST", headers:{"apikey":KEY, "Content-Type":"application/json"}, body:JSON.stringify(args)});
  if (!r.ok){ const e = new Error("rpc " + r.status); e.status = r.status; throw e; }
  const t = await r.text(); return t ? JSON.parse(t) : null;
}
async function deriveKey(p){
  const base = await crypto.subtle.importKey("raw", new TextEncoder().encode(p), "PBKDF2", false, ["deriveKey"]);
  return crypto.subtle.deriveKey({name:"PBKDF2", salt:hex(SALT), iterations:ITER, hash:"SHA-256"}, base, {name:"AES-GCM", length:256}, false, ["decrypt"]);
}
async function dec(buf){
  const u = new Uint8Array(buf);
  const pt = await crypto.subtle.decrypt({name:"AES-GCM", iv:u.slice(0,12)}, AES, u.slice(12));
  return new TextDecoder().decode(pt);
}
window.PUMDEC = dec;

/* db giống giao diện của Claude, chạy trên Supabase */
const listeners = {}, lastSig = {}; let pollTimer = null, polling = null, lastOk = 0;
async function poll(){
  if (polling) return polling;
  polling = (async () => {
    try{
      const rows = await rpc("pum_list", {p:PASS}) || [];
      const by = {}; rows.forEach(r => { if (!r.deleted) (by[r.col] = by[r.col] || []).push(r); });
      Object.keys(listeners).forEach(c => {
        const sig = JSON.stringify((by[c] || []).map(r => [r.id, r.updated_at]));
        if (lastSig[c] === sig) return; lastSig[c] = sig;
        const docs = (by[c] || []).map(r => ({id:r.id, data:() => r.data}));
        listeners[c].forEach(l => { try{ l.cb({docs, metadata:{fromCache:false}}); }catch(e){ console.error(e); } });
      });
      lastOk = Date.now();
    }catch(e){
      Object.values(listeners).flat().forEach(l => l.err && l.err(e));
      if (e.status === 400 || e.status === 401){ try{ localStorage.removeItem("pum:pass"); }catch(_){} }
    }finally{ polling = null; }
  })();
  return polling;
}
let soonT = null; const soon = () => { clearTimeout(soonT); soonT = setTimeout(poll, 400); };
const db = Object.freeze({
  collection: c => ({ onSnapshot(cb, err){ (listeners[c] = listeners[c] || []).push({cb, err}); delete lastSig[c]; soon(); return () => { listeners[c] = listeners[c].filter(x => x.cb !== cb); }; } }),
  doc: path => { const [c, ...rest] = path.split("/"); const id = rest.join("/");
    return { set: async data => { await rpc("pum_put", {p:PASS, c, i:id, d:data}); soon(); },
             delete: async () => { await rpc("pum_del", {p:PASS, c, i:id}); soon(); } }; }
});
window.claude = Object.freeze({ use: async name => name === "db" ? db : null });
document.addEventListener("visibilitychange", () => { if (!document.hidden) poll(); });

async function enter(p, remember){
  const ok = await rpc("pum_check", {p});
  if (!ok) return false;
  PASS = p; AES = await deriveKey(p);
  const r = await fetch("trip.enc?v=" + window.PUMV); const js = await dec(await r.arrayBuffer());
  (new Function(js))();
  if (remember){ try{ localStorage.setItem("pum:pass", p); }catch(_){} }
  document.getElementById("gate").classList.add("hide");
  const s = document.createElement("script"); s.src = "app.js?v=" + window.PUMV; document.body.appendChild(s);
  pollTimer = setInterval(() => { if (!document.hidden) poll(); }, 10000);
  return true;
}
const form = document.getElementById("gateForm"), msg = document.getElementById("gateMsg"), btn = document.getElementById("gateBtn");
form.onsubmit = async ev => {
  ev.preventDefault(); btn.disabled = true; msg.textContent = "Đang kiểm tra…";
  const pv = document.getElementById("gatePass").value.trim();
  if (!pv){ msg.textContent = "Nhập mật khẩu trước nha."; document.getElementById("gatePass").focus(); btn.disabled = false; return; }
  try{ if (!(await enter(pv, true))){ msg.textContent = "Sai mật khẩu, thử lại nha."; const g = document.getElementById("gate"); g.classList.remove("shake"); void g.offsetWidth; g.classList.add("shake"); document.getElementById("gatePass").select(); } }
  catch(e){ msg.textContent = "Chưa kết nối được. Kiểm tra mạng rồi thử lại."; }
  btn.disabled = false;
};
const eye = document.getElementById("gateEye"), pin = document.getElementById("gatePass");
eye.onclick = () => { const show = pin.type === "password"; pin.type = show ? "text" : "password"; eye.textContent = show ? "Ẩn" : "Hiện"; eye.setAttribute("aria-label", show ? "Ẩn mật khẩu" : "Hiện mật khẩu"); pin.focus(); };
(() => { const n = Math.round((new Date("2026-12-07T00:00:00") - new Date(new Date().toDateString())) / 864e5); if (n > 0) document.getElementById("gateSub").textContent = `Còn ${n} ngày nữa là bay`; })();
let saved = null; try{ saved = localStorage.getItem("pum:pass"); }catch(_){}
if (saved){ msg.textContent = "Đang mở…"; enter(saved, false).then(ok => { if (!ok){ msg.textContent = ""; try{ localStorage.removeItem("pum:pass"); }catch(_){} } }).catch(() => { msg.textContent = "Chưa kết nối được. Kiểm tra mạng rồi thử lại."; }); }
else document.getElementById("gatePass").focus();
})();
