// Browser client for the xAI Voice Agent realtime API.
// - Loads /config (system prompt + tools), mints /token (ephemeral secret).
// - Captures mic at 24 kHz, ships PCM16 base64 frames as input_audio_buffer.append.
// - Renders a chat: user transcripts, assistant transcripts, tool calls.
// - Handles client-side function tools (mock implementations below).

const SAMPLE_RATE = 24000;
const MODEL = "grok-voice-think-fast-1.0";
const VOICE = "69smp8rm";   // Composio voice library id — French speaker

const $toggle      = document.getElementById("toggle");
const $toggleLabel = $toggle.querySelector(".cta-label");
const $status      = document.getElementById("status");
const $chat        = document.getElementById("chat");
const $configInfo  = document.getElementById("config-info");

let running = false;
let ws = null;
let audioCtx = null;
let micStream = null;
let micNode = null;
let playhead = 0;
let earlyBuffer = [];
let wsOpen = false;

let assistantBubble = null;   // current streaming assistant bubble
let userBubble = null;        // current streaming user transcript bubble
let pendingEndCall = false;   // set by end_call tool, acted on at response.done

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

// ---- mock client-side function implementations ----------------------------
// These run in the browser. In a real app they'd call your backend / DB.
// Add a handler whenever you add a `function` tool in tools.json.

const FUNCTIONS = {
  book_reservation: async (args) => {
    const r = await fetch("/api/calendar/book", {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify(args),
    });
    return await r.json();
  },
  get_restaurant_hours: async () => ({
    monday:    "closed",
    tuesday:   "17:00-22:00",
    wednesday: "17:00-22:00",
    thursday:  "17:00-22:00",
    friday:    "17:00-23:00",
    saturday:  "11:00-23:00",
    sunday:    "11:00-21:00",
  }),
  end_call: async () => {
    // Don't stop right now — Margot may still be speaking. Flag it; the
    // response.done handler will drain the audio buffer and then call stop().
    pendingEndCall = true;
    return { status: "ok", message: "Hang-up scheduled after current utterance." };
  },
};

// ---- main ------------------------------------------------------------------

async function start() {
  running = true;
  $toggleLabel.textContent = "Stop";
  $toggle.classList.add("recording");
  setStatus("requesting mic + token + config…");

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
    addBubble("system", "Unexpected /token response: " + JSON.stringify(tokenResp));
    throw new Error("no ephemeral secret");
  }

  $configInfo.textContent = `tools: ${config.tools.length} • prompt: ${config.instructions.length} chars`;
  const toolSummary = config.tools.map(t => t.type === "mcp" ? `mcp:${t.server_label}` : t.type).join(", ");
  addBubble("system", `Session opening — voice "${VOICE}", ${config.tools.length} tool(s) loaded from /config: ${toolSummary}.`);

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

  setStatus("connecting to xAI…");
  ws = new WebSocket(
    `wss://api.x.ai/v1/realtime?model=${encodeURIComponent(MODEL)}`,
    [`xai-client-secret.${secret}`]
  );

  ws.onopen = () => {
    wsOpen = true;
    setStatus("connected");
    ws.send(JSON.stringify({
      type: "session.update",
      session: {
        voice: VOICE,
        instructions: config.instructions,
        tools: config.tools,
        turn_detection: { type: "server_vad" },
        // Ask the API to transcribe the user's audio so we can show it in chat.
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
    // Deep debug: every event lands in the JS console. Filter in DevTools by "[ws]".
    if (event.type !== "response.audio.delta" && event.type !== "response.output_audio.delta") {
      console.log("[ws]", event.type, event);
    }
    handleEvent(event);
  };

  ws.onerror = e => addBubble("system", "ws error: " + (e?.message || "unknown"));
  ws.onclose = e => { wsOpen = false; setStatus("closed: " + (e.reason || e.code)); };
}

function handleEvent(event) {
  switch (event.type) {
    // ---------- assistant audio + transcript --------------------------------
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
        // Wait for the queued audio to finish playing so we don't cut off
        // Margot's "au revoir" mid-word. playhead is the audioCtx time of
        // the last scheduled chunk's end; add a small safety margin.
        const drainMs = Math.max(0, (playhead - audioCtx.currentTime) * 1000) + 400;
        addBubble("system", `Margot raccroche dans ${Math.round(drainMs)} ms…`);
        setTimeout(() => stop(), drainMs);
      }
      break;
    }

    // ---------- user transcript --------------------------------------------
    case "conversation.item.input_audio_transcription.completed": {
      const text = event.transcript || "";
      if (text.trim()) addBubble("user", text, "You");
      break;
    }

    // ---------- VAD events --------------------------------------------------
    case "input_audio_buffer.speech_started":
      setStatus("you're speaking…");
      break;
    case "input_audio_buffer.speech_stopped":
      setStatus("thinking…");
      break;

    // ---------- tool calls --------------------------------------------------
    case "response.function_call_arguments.done":
      handleFunctionCall(event);
      break;

    case "session.created":
    case "response.created":
      // quiet
      break;

    case "session.updated": {
      // Echo the tools xAI actually registered — if MCP tool was rejected,
      // it will be missing from session.tools and we'll see it here.
      const tools = (event.session && event.session.tools) || [];
      addBubble("system",
        `session.updated — ${tools.length} tool(s) accepted by xAI:\n` +
        tools.map(t => `  • ${t.type}${t.server_label ? ` (${t.server_label})` : ""}${t.name ? ` (${t.name})` : ""}`).join("\n"));
      break;
    }

    case "error":
      addBubble("system", "ERROR: " + JSON.stringify(event.error || event));
      break;

    default:
      // Bubble anything tool-/mcp-/error-related so we don't need DevTools
      // to debug. Everything else still lands in the JS console.
      if (/mcp|tool|fail|error/i.test(event.type)) {
        const compact = JSON.stringify(event, null, 2);
        addBubble("tool", `[${event.type}]\n${compact.length > 1200 ? compact.slice(0, 1200) + "…" : compact}`);
      }
      break;
  }
}

async function handleFunctionCall(event) {
  const name = event.name;
  const callId = event.call_id;
  let args = {};
  try { args = JSON.parse(event.arguments || "{}"); } catch {}

  addBubble("tool", `→ ${name}(${JSON.stringify(args)})`);

  const handler = FUNCTIONS[name];
  let result;
  if (handler) {
    try { result = await handler(args); }
    catch (e) { result = { error: String(e) }; }
  } else {
    result = { error: `No client handler for tool "${name}"` };
  }

  addBubble("tool", `← ${name} → ${JSON.stringify(result)}`);

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
  $toggleLabel.textContent = "Start conversation";
  $toggle.classList.remove("recording");
  setStatus("stopping…");
  try { ws?.close(); } catch {}
  try { micNode?.disconnect(); } catch {}
  try { micStream?.getTracks().forEach(t => t.stop()); } catch {}
  try { await audioCtx?.close(); } catch {}
  ws = null; micNode = null; micStream = null; audioCtx = null;
  wsOpen = false; earlyBuffer = []; playhead = 0;
  assistantBubble = null; userBubble = null;
  setStatus("idle");
}

$toggle.addEventListener("click", () => {
  if (running) stop().catch(e => addBubble("system", String(e)));
  else start().catch(e => { addBubble("system", "start failed: " + (e.message || e)); stop(); });
});
