// Client navigateur — Démo Agent Vocal Corsica Studio (Margot, LOU PATIO).
// - Charge /config (prompt + tools), mint /token (secret éphémère xAI).
// - Micro 24 kHz, frames PCM16 base64 en input_audio_buffer.append.
// - Affiche la conversation, gère les function tools côté client.
// Règle du template : chaque function de tools.json a un handler ici (navigateur)
// ET dans _server_tool_call de web/server.py (téléphone).

// 24 kHz par défaut ; iOS Safari peut refuser un sampleRate forcé → on retombe
// sur le rate natif de l'appareil (souvent 48 kHz) et on le DÉCLARE à xAI.
const PREFERRED_RATE = 24000;
let sampleRate = PREFERRED_RATE;
const MODEL = "grok-voice-think-fast-1.0";
const VOICE = "69smp8rm";   // voix française « Camille » (bibliothèque Grok Voice)

const $toggle      = document.getElementById("toggle");
const $toggleLabel = $toggle.querySelector(".cta-label");
const $status      = document.getElementById("status");
const $chat        = document.getElementById("chat");
const $configInfo  = document.getElementById("config-info");
const $afterCall   = document.getElementById("after-call");
const $callCard    = document.getElementById("call-card");
const $callBar     = document.getElementById("call-bar");
const $callBarStatus = document.getElementById("call-bar-status");
const $hangup      = document.getElementById("hangup");
const $callTimer   = document.getElementById("call-timer");
const $phoneHangup = document.getElementById("phone-hangup");

// chrono de l'écran d'appel (mockup téléphone)
let callTimerInterval = null;
function startCallTimer() {
  const t0 = Date.now();
  if ($callTimer) $callTimer.textContent = "00:00";
  callTimerInterval = setInterval(() => {
    const s = Math.floor((Date.now() - t0) / 1000);
    const mm = String(Math.floor(s / 60)).padStart(2, "0");
    const ss = String(s % 60).padStart(2, "0");
    if ($callTimer) $callTimer.textContent = `${mm}:${ss}`;
  }, 1000);
}
function stopCallTimer() {
  clearInterval(callTimerInterval);
  callTimerInterval = null;
}

let running = false;
let ws = null;
let audioCtx = null;
let micStream = null;
let micNode = null;
let playhead = 0;
let earlyBuffer = [];
let wsOpen = false;

let assistantBubble = null;
let pendingEndCall = false;
let hadConversation = false;
let lastBooking = null;   // mémorise la dernière résa confirmée pour le récap de fin d'appel

// Filet de sécurité (même liste que le chemin Twilio dans server.py) :
// Margot dit souvent « au revoir » sans émettre end_call → on raccroche nous-mêmes.
const GOODBYES = [
  "au revoir", "bonne soirée", "bonne journée",
  "à très vite", "à bientôt", "bonne fin de",
  "merci d'avoir appelé", "à plus tard",
];

const setStatus = s => {
  $status.textContent = s;
  if ($callBarStatus) $callBarStatus.textContent = s;
};

// Auto-scroll DANS la carte conversation uniquement (jamais la page entière),
// et seulement si le lecteur est déjà près du bas (il peut relire sans être arraché).
function scrollChat(force = false) {
  const nearBottom = $chat.scrollHeight - $chat.scrollTop - $chat.clientHeight < 140;
  if (force || nearBottom) $chat.scrollTop = $chat.scrollHeight;
}

function addBubble(kind, text = "", labelText = null) {
  const row = document.createElement("div");
  row.className = "row " + kind;
  const role = document.createElement("div");
  role.className = "role";
  role.textContent = (labelText || kind).toUpperCase();
  const body = document.createElement("div");
  body.className = "text";
  body.textContent = text;
  row.appendChild(role);
  row.appendChild(body);
  $chat.appendChild(row);
  scrollChat();
  return body;
}

// ---- audio helpers ---------------------------------------------------------

function float32ToPCM16Base64(float32) {
  const pcm16 = new Int16Array(float32.length);
  for (let i = 0; i < float32.length; i++) {
    const s = Math.max(-1, Math.min(1, float32[i]));
    pcm16[i] = s < 0 ? s * 0x8000 : s * 0x7fff;
  }
  let binary = "";
  const bytes = new Uint8Array(pcm16.buffer);
  for (let i = 0; i < bytes.length; i++) binary += String.fromCharCode(bytes[i]);
  return btoa(binary);
}

function base64PCM16ToFloat32(b64) {
  const bin = atob(b64);
  const bytes = new Uint8Array(bin.length);
  for (let i = 0; i < bin.length; i++) bytes[i] = bin.charCodeAt(i);
  const pcm16 = new Int16Array(bytes.buffer);
  const f32 = new Float32Array(pcm16.length);
  for (let i = 0; i < pcm16.length; i++) f32[i] = pcm16[i] / 32768;
  return f32;
}

function schedulePlayback(float32) {
  if (!audioCtx) return;
  const buf = audioCtx.createBuffer(1, float32.length, sampleRate);
  buf.copyToChannel(float32, 0);
  const src = audioCtx.createBufferSource();
  src.buffer = buf;
  src.connect(audioCtx.destination);
  const now = audioCtx.currentTime;
  if (playhead < now) playhead = now;
  src.start(playhead);
  playhead += buf.duration;
}

// ---- function tools (chemin navigateur) ------------------------------------

const FUNCTIONS = {
  check_availability: async (args) => {
    const r = await fetch("/api/calendar/availability", {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify(args),
    });
    return await r.json();
  },
  book_reservation: async (args) => {
    const r = await fetch("/api/calendar/book", {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify(args),
    });
    return await r.json();
  },
  get_restaurant_info: async () => {
    const r = await fetch("/api/restaurant");
    return await r.json();
  },
  end_call: async () => {
    pendingEndCall = true;
    return { status: "ok", message: "Hang-up scheduled after current utterance." };
  },
};

// Bulles lisibles pour le grand public (le JSON brut reste en console).
function toolBubbleStart(name, args) {
  if (name === "check_availability") {
    return `Margot vérifie les disponibilités du ${args.date || ""} à ${args.time || ""}…`;
  }
  if (name === "book_reservation") {
    return `Enregistrement de la réservation au nom de ${args.name || "…"} (${args.party_size || "?"} pers.)…`;
  }
  if (name === "get_restaurant_info") {
    return "Margot consulte la carte et les informations du restaurant…";
  }
  if (name === "end_call") return "Fin d'appel demandée.";
  return `→ ${name}`;
}

function toolBubbleEnd(name, result) {
  if (name === "book_reservation" && result && result.status === "confirmed") {
    return "Réservation enregistrée dans l'agenda du restaurant.";
  }
  if (name === "book_reservation" && result && result.status === "full") {
    return "Créneau complet : Margot propose une alternative.";
  }
  if (name === "check_availability" && result && typeof result.available !== "undefined") {
    return result.available
      ? `Des tables sont disponibles (${result.tables_libres ?? "?"} libre(s) sur ce créneau).`
      : "Créneau complet : Margot cherche une alternative.";
  }
  if (result && result.status === "error") {
    return "Petit souci technique côté agenda : Margot s'adapte.";
  }
  return null; // pas de bulle de fin
}

// ---- main ------------------------------------------------------------------

async function start() {
  running = true;
  hadConversation = true;
  $toggleLabel.textContent = "Raccrocher";
  $toggle.classList.add("recording");
  $afterCall.classList.remove("visible");
  // Nouvelle conversation : carte visible et vidée, barre d'appel fixe affichée.
  $chat.innerHTML = "";
  lastBooking = null;
  const $recap = document.getElementById("recap");
  if ($recap) $recap.hidden = true;
  $callCard.hidden = false;
  $callCard.classList.remove("ended");
  $callBar.hidden = false;
  document.body.classList.add("on-call");
  startCallTimer();
  const callTarget = window.matchMedia("(max-width: 980px)").matches
    ? document.querySelector(".phone-left") : $callCard;
  (callTarget || $callCard).scrollIntoView({ behavior: "smooth", block: "center" });
  setStatus("préparation…");

  const micPromise    = navigator.mediaDevices.getUserMedia({
    audio: { channelCount: 1, echoCancellation: true, noiseSuppression: true }
  });
  const tokenPromise  = fetch("/token",  { method: "POST" }).then(r => { if (!r.ok) throw new Error("token "+r.status); return r.json(); });
  const configPromise = fetch("/config").then(r => { if (!r.ok) throw new Error("config "+r.status); return r.json(); });

  const [stream, tokenResp, config] = await Promise.all([micPromise, tokenPromise, configPromise]);
  micStream = stream;

  const secret =
    tokenResp?.client_secret?.client_secret?.value ||
    tokenResp?.client_secret?.value ||
    tokenResp?.client_secret;
  if (!secret || typeof secret !== "string") {
    console.error("Unexpected /token response:", tokenResp);
    addBubble("system", "La démo est momentanément indisponible. Réessayez dans un instant.");
    throw new Error("no ephemeral secret");
  }

  console.log(`[config] tools: ${config.tools.length} • prompt: ${config.instructions.length} chars`);

  // iOS Safari : un sampleRate forcé peut jeter une exception → fallback natif.
  try { audioCtx = new AudioContext({ sampleRate: PREFERRED_RATE }); }
  catch { audioCtx = new AudioContext(); }
  sampleRate = audioCtx.sampleRate;
  if (audioCtx.state === "suspended") { try { await audioCtx.resume(); } catch {} }
  console.log(`[audio] sampleRate=${sampleRate}`);
  const source = audioCtx.createMediaStreamSource(stream);
  micNode = audioCtx.createScriptProcessor(4096, 1, 1);
  source.connect(micNode);
  micNode.connect(audioCtx.destination);

  micNode.onaudioprocess = e => {
    const input = e.inputBuffer.getChannelData(0);
    const b64 = float32ToPCM16Base64(input);
    const msg = JSON.stringify({ type: "input_audio_buffer.append", audio: b64 });
    if (wsOpen) ws.send(msg);
    else earlyBuffer.push(msg);
  };

  setStatus("connexion…");
  ws = new WebSocket(
    `wss://api.x.ai/v1/realtime?model=${encodeURIComponent(MODEL)}`,
    [`xai-client-secret.${secret}`]
  );

  ws.onopen = () => {
    wsOpen = true;
    setStatus("en ligne, dites bonjour !");
    ws.send(JSON.stringify({
      type: "session.update",
      session: {
        voice: VOICE,
        instructions: config.instructions,
        tools: config.tools,
        turn_detection: { type: "server_vad" },
        input_audio_transcription: { model: "whisper-1" },
        audio: {
          input:  { format: { type: "audio/pcm", rate: sampleRate } },
          output: { format: { type: "audio/pcm", rate: sampleRate } }
        }
      }
    }));
    for (const m of earlyBuffer) ws.send(m);
    earlyBuffer = [];
  };

  ws.onmessage = ev => {
    let event;
    try { event = JSON.parse(ev.data); } catch { return; }
    if (event.type !== "response.audio.delta" && event.type !== "response.output_audio.delta") {
      console.log("[ws]", event.type, event);
    }
    handleEvent(event);
  };

  ws.onerror = e => { console.error("ws error", e); setStatus("connexion interrompue"); };
  ws.onclose = e => { wsOpen = false; if (running) setStatus("appel terminé"); };
}

function handleEvent(event) {
  switch (event.type) {
    case "response.output_audio.delta":
    case "response.audio.delta": {
      schedulePlayback(base64PCM16ToFloat32(event.delta));
      break;
    }
    case "response.audio_transcript.delta":
    case "response.output_audio_transcript.delta":
    case "response.text.delta":
    case "response.output_text.delta": {
      if (!assistantBubble) assistantBubble = addBubble("assistant", "", "Margot");
      assistantBubble.textContent += event.delta || "";
      scrollChat();
      break;
    }
    case "response.audio_transcript.done":
    case "response.output_audio_transcript.done":
    case "response.done": {
      // Auto-raccrochage : si l'au revoir est dans le transcript, on arme le hang-up
      // (même si le modèle oublie end_call). Déclenché à response.done, après drain audio.
      const spoken = (event.transcript || assistantBubble?.textContent || "").toLowerCase();
      if (!pendingEndCall && spoken && GOODBYES.some(g => spoken.includes(g))) {
        console.log("[call] auto-hangup armé (au revoir détecté)");
        pendingEndCall = true;
      }
      assistantBubble = null;
      if (event.type === "response.done" && pendingEndCall) {
        pendingEndCall = false;
        const drainMs = Math.max(0, (playhead - audioCtx.currentTime) * 1000) + 400;
        setTimeout(() => stop(), drainMs);
      }
      break;
    }

    case "conversation.item.input_audio_transcription.completed": {
      const text = event.transcript || "";
      if (text.trim()) addBubble("user", text, "Vous");
      break;
    }

    case "input_audio_buffer.speech_started":
      setStatus("vous parlez…");
      break;
    case "input_audio_buffer.speech_stopped":
      setStatus("Margot réfléchit…");
      break;

    case "response.function_call_arguments.done":
      handleFunctionCall(event);
      break;

    case "session.created":
    case "response.created":
    case "session.updated":
      // détail en console uniquement (public non technique)
      break;

    case "error":
      console.error("[xai] ERROR", event.error || event);
      setStatus("petit souci technique, relancez l'appel");
      break;

    default:
      if (/fail|error/i.test(event.type)) {
        console.error("[ws]", event.type, event);
      }
      break;
  }
}

async function handleFunctionCall(event) {
  const name = event.name;
  const callId = event.call_id;
  let args = {};
  try { args = JSON.parse(event.arguments || "{}"); } catch {}

  console.log(`[tool] → ${name}`, args);
  addBubble("tool", toolBubbleStart(name, args), "Agenda");

  const handler = FUNCTIONS[name];
  let result;
  if (handler) {
    try { result = await handler(args); }
    catch (e) { result = { error: String(e) }; }
  } else {
    result = { error: `No client handler for tool "${name}"` };
  }

  console.log(`[tool] ← ${name}`, result);
  if (name === "book_reservation" && result && result.status === "confirmed") {
    lastBooking = { ...args };   // pour le récap affiché après le raccrochage
  }
  const endText = toolBubbleEnd(name, result);
  if (endText) addBubble("tool", endText, "Agenda");

  ws.send(JSON.stringify({
    type: "conversation.item.create",
    item: {
      type: "function_call_output",
      call_id: callId,
      output: JSON.stringify(result),
    }
  }));
  ws.send(JSON.stringify({ type: "response.create" }));
}

// La conversation est effacée au raccrochage : seul un récap des infos
// importantes reste (réservation confirmée : couverts, date, heure, nom).
function showRecap() {
  const $recap = document.getElementById("recap");
  if (!$recap) return;
  if (!lastBooking) { $recap.hidden = true; return; }
  let when = lastBooking.date || "";
  try {
    const d = new Date(`${lastBooking.date}T${(lastBooking.time || "12:00")}:00`);
    when = d.toLocaleDateString("fr-FR", { weekday: "long", day: "numeric", month: "long" });
  } catch {}
  const heure = (lastBooking.time || "").replace(":", "h");
  $recap.classList.remove("error");
  $recap.innerHTML = `
    <span class="recap-check"><svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2.4" stroke-linecap="round" stroke-linejoin="round"><path d="M22 11.08V12a10 10 0 1 1-5.93-9.14"/><path d="m9 11 3 3L22 4"/></svg></span>
    <div>
      <b>Réservation confirmée</b> : table pour ${lastBooking.party_size || "?"},
      ${when} à ${heure}${lastBooking.name ? `, au nom de ${lastBooking.name}` : ""}.
      <span class="recap-note">Elle est déjà dans l'agenda du restaurant.</span>
    </div>`;
  $recap.hidden = false;
}

async function stop() {
  running = false;
  $toggleLabel.textContent = "Appeler le restaurant";
  $toggle.classList.remove("recording");
  // Raccrochage : la barre disparaît, la conversation est effacée,
  // seul le récap (si réservation) reste à l'écran.
  $callBar.hidden = true;
  $callCard.hidden = true;
  $callCard.classList.add("ended");
  $chat.innerHTML = "";
  document.body.classList.remove("on-call");
  stopCallTimer();
  showRecap();
  setStatus("appel terminé");
  try { ws?.close(); } catch {}
  try { micNode?.disconnect(); } catch {}
  try { micStream?.getTracks().forEach(t => t.stop()); } catch {}
  try { await audioCtx?.close(); } catch {}
  ws = null; micNode = null; micStream = null; audioCtx = null;
  wsOpen = false; earlyBuffer = []; playhead = 0;
  assistantBubble = null;
  if (hadConversation && $afterCall) $afterCall.classList.add("visible");
}

$toggle.addEventListener("click", () => {
  if (running) { stop().catch(e => console.error(e)); return; }
  start().catch(e => {
    console.error("start failed:", e);
    const msg = (e && (e.name === "NotAllowedError" || e.name === "SecurityError"))
      ? "micro refusé : autorise le micro pour parler à Margot (icône AA ou Réglages > Safari > Micro)"
      : "démarrage impossible : " + (e && e.message ? e.message : "réessaie dans un instant");
    stop().catch(() => {});
    setStatus(msg);
    const r = document.getElementById("recap");
    if (r) {
      r.innerHTML = `<span class="recap-check warn">!</span><div><b>L'appel n'a pas pu démarrer.</b> ${msg}.</div>`;
      r.hidden = false; r.classList.add("error");
    }
  });
});

$hangup.addEventListener("click", () => { if (running) stop().catch(e => console.error(e)); });
if ($phoneHangup) $phoneHangup.addEventListener("click", () => { if (running) stop().catch(e => console.error(e)); });

// ---- page resto : carte du menu + infos pratiques (depuis /api/restaurant) ---
// Une seule source de vérité : web/config/restaurant.json. Dupliquer le template
// pour un autre établissement = changer ce JSON, la page suit.

function menuItem(raw) {
  const [label, price] = raw.split(" — ");
  if (!price) return `<p class="menu-note">${raw}</p>`;
  return `<div class="menu-item"><span>${label}</span><span class="dots"></span><span class="price">${price}</span></div>`;
}

async function loadRestaurantPage() {
  let r;
  try { r = await (await fetch("/api/restaurant")).json(); }
  catch (e) { console.error("[resto] fiche indisponible", e); return; }

  const $menu = document.getElementById("menu-content");
  if ($menu && r.menus) {
    const fixed = r.menus.map(m => `
      <div class="menu-box">
        <h4>${m.nom}</h4>
        <span class="menu-price">${m.prix}${m.service && m.service !== "midi et soir" ? " · " + m.service : ""}</span>
        <p>${m.contenu.replaceAll(" · ", "<br/>")}</p>
        <span class="menu-wine">${m.accord_vins || ""}</span>
      </div>`).join("");
    const c = r.carte || {};
    const section = (titre, items) => items?.length
      ? `<div class="menu-section"><h4>${titre}</h4>${items.map(menuItem).join("")}</div>` : "";
    $menu.innerHTML = `
      <div class="menu-fixed">${fixed}</div>
      ${section("Entrées", c.entrees)}
      ${section("Plats", c.plats)}
      ${section("Pièces à partager", c.pieces_a_partager)}
      ${section("Desserts", c.desserts)}`;
  }

  // (les 3 cartes sous les téléphones sont commerciales et statiques :
  //  avantages, secteurs, offre — voir index.html, demande Vannina 11/06)
}

loadRestaurantPage();

// apparition en douceur des éléments .reveal (mockups téléphone…)
const revealObserver = new IntersectionObserver(entries => {
  for (const e of entries) {
    if (e.isIntersecting) { e.target.classList.add("visible"); revealObserver.unobserve(e.target); }
  }
}, { threshold: 0.18 });
document.querySelectorAll(".reveal").forEach(el => revealObserver.observe(el));
