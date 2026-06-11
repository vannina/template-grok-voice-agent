// Client navigateur — Démo Agent Vocal Corsica Studio (Margot, LOU PATIO).
// - Charge /config (prompt + tools), mint /token (secret éphémère xAI).
// - Micro 24 kHz, frames PCM16 base64 en input_audio_buffer.append.
// - Affiche la conversation, gère les function tools côté client.
// Règle du template : chaque function de tools.json a un handler ici (navigateur)
// ET dans _server_tool_call de web/server.py (téléphone).

const SAMPLE_RATE = 24000;
const MODEL = "grok-voice-think-fast-1.0";
const VOICE = "69smp8rm";   // voix française « Camille » (bibliothèque Grok Voice)

const $toggle      = document.getElementById("toggle");
const $toggleLabel = $toggle.querySelector(".cta-label");
const $status      = document.getElementById("status");
const $chat        = document.getElementById("chat");
const $configInfo  = document.getElementById("config-info");
const $afterCall   = document.getElementById("after-call");

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

const setStatus = s => { $status.textContent = s; };

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
  window.scrollTo({ top: document.body.scrollHeight, behavior: "smooth" });
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
  const buf = audioCtx.createBuffer(1, float32.length, SAMPLE_RATE);
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
    return `🔎 Margot vérifie les disponibilités du ${args.date || ""} à ${args.time || ""}…`;
  }
  if (name === "book_reservation") {
    return `📅 Enregistrement de la réservation au nom de ${args.name || "…"} (${args.party_size || "?"} pers.)…`;
  }
  if (name === "get_restaurant_info") {
    return "📖 Margot consulte la carte et les informations du restaurant…";
  }
  if (name === "end_call") return "👋 Fin d'appel demandée.";
  return `→ ${name}`;
}

function toolBubbleEnd(name, result) {
  if (name === "book_reservation" && result && result.status === "confirmed") {
    return "✅ Réservation enregistrée dans l'agenda du restaurant.";
  }
  if (name === "book_reservation" && result && result.status === "full") {
    return "📋 Créneau complet — Margot propose une alternative.";
  }
  if (name === "check_availability" && result && typeof result.available !== "undefined") {
    return result.available
      ? `✅ Des tables sont disponibles (${result.tables_libres ?? "?"} libre(s) sur ce créneau).`
      : "📋 Créneau complet — Margot cherche une alternative.";
  }
  if (result && result.status === "error") {
    return "⚠️ Petit souci technique côté agenda — Margot s'adapte.";
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
  setStatus("préparation…");

  const micPromise    = navigator.mediaDevices.getUserMedia({
    audio: { channelCount: 1, sampleRate: SAMPLE_RATE, echoCancellation: true, noiseSuppression: true }
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

  audioCtx = new AudioContext({ sampleRate: SAMPLE_RATE });
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
    setStatus("en ligne — dites bonjour !");
    ws.send(JSON.stringify({
      type: "session.update",
      session: {
        voice: VOICE,
        instructions: config.instructions,
        tools: config.tools,
        turn_detection: { type: "server_vad" },
        input_audio_transcription: { model: "whisper-1" },
        audio: {
          input:  { format: { type: "audio/pcm", rate: SAMPLE_RATE } },
          output: { format: { type: "audio/pcm", rate: SAMPLE_RATE } }
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
      window.scrollTo({ top: document.body.scrollHeight });
      break;
    }
    case "response.audio_transcript.done":
    case "response.output_audio_transcript.done":
    case "response.done": {
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
      setStatus("petit souci technique — relancez l'appel");
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

async function stop() {
  running = false;
  $toggleLabel.textContent = "🎙️ Parler à Margot";
  $toggle.classList.remove("recording");
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
  if (running) stop().catch(e => console.error(e));
  else start().catch(e => { console.error("start failed:", e); setStatus("micro refusé ou indisponible"); stop(); });
});
