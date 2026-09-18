/**
 * JARVIS Telegram call sidecar (Node 18 runtime — see README note on wrtc).
 *
 * What it does: logs in as YOU (userbot session), calls your own account so
 * the phone rings, then runs a turn loop entirely through JARVIS HTTP:
 *   call audio in  -> POST /api/v1/voice/stt  -> text
 *   text            -> POST /api/chat          -> reply (fast model)
 *   reply           -> POST /api/v1/voice/tts  -> mp3 -> played into the call
 *
 * Signaling + media: GramJS (telegram) + gram-tgcalls (tgcalls/werift media).
 * This file wires the loop; the exact VoiceCall attach call is pinned by
 * `node check-api.js` (run it first — tgcalls APIs drift between versions).
 *
 * Env:
 *   TG_API_ID / TG_API_HASH   from https://my.telegram.org
 *   TG_SESSION                session file (default ../../data/tgcall.session)
 *   JARVIS_URL                e.g. http://127.0.0.1:8000
 *   JARVIS_API_KEY            console key
 *   CALL_TARGET               default 'me' (call yourself)
 *   LISTEN_SEC                seconds recorded per turn (default 8)
 *   MAX_TURNS                 safety cap on turns (default 10)
 */
'use strict';

const { TelegramClient } = require('telegram');
const { StringSession } = require('telegram/sessions');

const API_ID = Number(process.env.TG_API_ID || 0);
const API_HASH = process.env.TG_API_HASH || '';
const SESSION_PATH = process.env.TG_SESSION || __dirname + '/../../data/tgcall.session';
const JARVIS_URL = (process.env.JARVIS_URL || 'http://127.0.0.1:8000').replace(/\/+$/, '');
const JARVIS_KEY = process.env.JARVIS_API_KEY || '';
const CALL_TARGET = process.env.CALL_TARGET || 'me';
const LISTEN_SEC = Number(process.env.LISTEN_SEC || 8);
const MAX_TURNS = Number(process.env.MAX_TURNS || 10);

if (!API_ID || !API_HASH) {
  console.error('TG_API_ID / TG_API_HASH required (https://my.telegram.org).');
  process.exit(2);
}

const fs = require('fs');

function loadSession() {
  try {
    return new StringSession(fs.readFileSync(SESSION_PATH, 'utf8').trim());
  } catch {
    return new StringSession('');
  }
}

function saveSession(client) {
  fs.mkdirSync(require('path').dirname(SESSION_PATH), { recursive: true });
  fs.writeFileSync(SESSION_PATH, client.session.save(), { mode: 0o600 });
}

async function jarvis(path, opts = {}) {
  const res = await fetch(JARVIS_URL + path, {
    ...opts,
    headers: {
      Authorization: `Bearer ${JARVIS_KEY}`,
      ...(opts.headers || {}),
    },
  });
  if (!res.ok) throw new Error(`${path} -> HTTP ${res.status}`);
  return res;
}

async function main() {
  const client = new TelegramClient(loadSession(), API_ID, API_HASH, {
    connectionRetries: 5,
  });
  await client.start({
    phoneNumber: async () => {
      throw new Error('No session yet: run `node login.js` first (needs the login code).');
    },
    password: async () => '',
    phoneCode: async () => {
      throw new Error('No session yet: run `node login.js` first.');
    },
    onError: (err) => console.error('login error:', err.message),
  });
  saveSession(client);
  console.log('Logged in as', (await client.getMe()).username);

  // The call attach (signaling + media) lives in lib/call.js so the loop
  // below stays readable. It throws with a pointer to check-api.js output
  // when the installed gram-tgcalls version differs.
  const { placeCall } = require('./lib/call.js');
  const call = await placeCall(client, CALL_TARGET);
  console.log('Call established.');

  const { listenOnce, playBuffer, hangup } = call;
  try {
    for (let turn = 1; turn <= MAX_TURNS; turn++) {
      console.log(`--- turn ${turn}: listening ${LISTEN_SEC}s ---`);
      const wav = await listenOnce(LISTEN_SEC * 1000);
      const form = new FormData();
      form.append('audio', new Blob([wav], { type: 'audio/wav' }), 'turn.wav');
      const stt = await jarvis('/api/v1/voice/stt', { method: 'POST', body: form });
      const { text } = await stt.json();
      console.log('heard:', text);
      if (!text || !text.trim()) {
        await playBuffer(await tts('I did not catch that. Could you repeat?'));
        continue;
      }
      if (/good ?bye|hang ?up|that'?s all|done/i.test(text)) {
        await playBuffer(await tts('Goodbye.'));
        break;
      }
      const chat = await jarvis('/api/chat', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({
          message: text,
          model: { provider: 'groq', id: '' },
          session_id: 'tgcall',
          memory_enabled: true,
        }),
      });
      const { response } = await chat.json();
      await playBuffer(await tts(response || '...'));
    }
  } finally {
    await hangup();
    await client.disconnect();
  }
}

async function tts(text) {
  const res = await jarvis('/api/v1/voice/tts', {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify({ text: String(text).slice(0, 2000) }),
  });
  return Buffer.from(await res.arrayBuffer());
}

main().catch((err) => {
  console.error('call failed:', err.message);
  process.exit(1);
});
