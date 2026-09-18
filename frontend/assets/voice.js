/* Voice mode — mic input (server STT) and spoken replies (server TTS).
   The APK WebView has no SpeechRecognition, so audio goes through
   MediaRecorder → /api/v1/voice/stt, and replies play from /api/v1/voice/tts.
   Works identically in the PWA. */

import { $, apiUrl, getApiKey, toast } from './core.js';
import { sendMessage } from './chat.js';

const VOICE_REPLY_KEY = 'jarvis.voiceReply';

let recorder = null;
let recording = false;
let currentAudio = null;

export function voiceReplyEnabled() {
  try { return localStorage.getItem(VOICE_REPLY_KEY) === 'true'; } catch { return false; }
}

function setVoiceReply(on) {
  try { localStorage.setItem(VOICE_REPLY_KEY, on ? 'true' : 'false'); } catch { /* ignore */ }
  renderVoiceToggle();
  if (!on) stopPlayback();
}

function renderVoiceToggle() {
  const btn = $('#voiceToggle');
  if (btn) {
    btn.textContent = voiceReplyEnabled() ? '🔊' : '🔇';
    btn.title = voiceReplyEnabled() ? 'Spoken replies on (tap to mute)' : 'Spoken replies off (tap for voice mode)';
  }
}

function authHeaders() {
  const key = getApiKey();
  return key ? { Authorization: `Bearer ${key}` } : {};
}

/* Strip markdown cruft so the spoken reply sounds natural. */
function speakable(text) {
  return String(text || '')
    .replace(/```[\s\S]*?```/g, ' code omitted ')
    .replace(/`([^`]+)`/g, '$1')
    .replace(/^#{1,6}\s+/gm, '')
    .replace(/\*\*([^*]+)\*\*/g, '$1')
    .replace(/\[([^\]]+)\]\([^)]+\)/g, '$1')
    .replace(/\n{2,}/g, '. ')
    .replace(/\n/g, ' ')
    .trim()
    .slice(0, 2000);
}

export function stopPlayback() {
  try {
    if (currentAudio) { currentAudio.pause(); currentAudio = null; }
  } catch { /* ignore */ }
}

export async function speakReply(text) {
  if (!voiceReplyEnabled()) return;
  const clean = speakable(text);
  if (!clean) return;
  stopPlayback();
  try {
    const res = await fetch(apiUrl('/api/v1/voice/tts'), {
      method: 'POST',
      headers: { 'Content-Type': 'application/json', ...authHeaders() },
      body: JSON.stringify({ text: clean }),
    });
    if (!res.ok) throw new Error(`TTS ${res.status}`);
    const blob = await res.blob();
    const audio = new Audio(URL.createObjectURL(blob));
    currentAudio = audio;
    audio.onended = () => { if (currentAudio === audio) currentAudio = null; };
    await audio.play();
  } catch (err) {
    toast(`Voice reply failed: ${err.message}`, 'err');
  }
}

async function toggleRecording() {
  const btn = $('#micBtn');
  if (recording) {
    try { recorder?.stop(); } catch { /* ignore */ }
    return;
  }
  if (!navigator.mediaDevices?.getUserMedia) {
    toast('Microphone not available in this browser', 'err');
    return;
  }
  try {
    const stream = await navigator.mediaDevices.getUserMedia({ audio: true });
    const mime = MediaRecorder.isTypeSupported('audio/webm') ? 'audio/webm' : '';
    recorder = new MediaRecorder(stream, mime ? { mimeType: mime } : undefined);
    const chunks = [];
    recorder.ondataavailable = (e) => { if (e.data.size) chunks.push(e.data); };
    recorder.onstop = async () => {
      recording = false;
      if (btn) { btn.textContent = '🎤'; btn.classList.remove('recording'); }
      stream.getTracks().forEach((t) => t.stop());
      if (!chunks.length) return;
      await transcribeAndSend(new Blob(chunks, { type: mime || 'audio/webm' }));
    };
    recorder.start();
    recording = true;
    stopPlayback();
    if (btn) { btn.textContent = '⏹'; btn.classList.add('recording'); }
    toast('Listening… tap again to send');
  } catch (err) {
    toast(`Microphone blocked: ${err.message}`, 'err');
  }
}

async function transcribeAndSend(blob) {
  toast('Transcribing…');
  try {
    const fd = new FormData();
    fd.append('audio', blob, 'voice.webm');
    const key = getApiKey();
    const res = await fetch(apiUrl('/api/v1/voice/stt'), {
      method: 'POST',
      ...(key ? { headers: { Authorization: `Bearer ${key}` } } : {}),
      body: fd,
    });
    const data = await res.json();
    if (!res.ok) throw new Error(data.detail || `STT ${res.status}`);
    const text = (data.text || '').trim();
    if (!text) { toast('Heard nothing — try again'); return; }
    const input = $('#composerInput');
    if (input) {
      input.value = text;
      input.style.height = 'auto';
      input.dispatchEvent(new Event('input'));
    }
    // Hands-free: send immediately so a voice turn is one tap.
    await sendMessage();
  } catch (err) {
    toast(`Transcription failed: ${err.message}`, 'err');
  }
}

export function initVoice() {
  renderVoiceToggle();
  $('#micBtn')?.addEventListener('click', toggleRecording);
  $('#voiceToggle')?.addEventListener('click', () => setVoiceReply(!voiceReplyEnabled()));
}
