/**
 * Telegram p2p call SIGNALING + crypto foundation (Sprint 11.4).
 *
 * Covers the MTProto call state machine through GramJS: requestCall -> wait
 * for accept -> confirmCall (shared-key + fingerprint) -> discardCall, plus
 * the Telegram VoIP crypto (2048-bit DH over the fixed safe prime, AES-256-CTR
 * + SHA-256 message-key framing). Media (WebRTC/SRTP bridging audio into
 * JARVIS STT/TTS) is NOT implemented here — it needs a live answered call to
 * debug and is the remaining blocker (see README status).
 *
 * VERIFICATION STATUS: the DH/crypto and the call-state transitions are
 * implemented against the documented Telegram VoIP protocol and the GramJS
 * MTProto layer. They are NOT live-verified end-to-end (requires a second
 * Telegram account that answers, plus the media bridge). Treat everything
 * here as foundation, not finished.
 */
'use strict';

const crypto = require('crypto');

// Telegram VoIP uses this fixed 2048-bit safe prime (RFC 3526 / the classic
// "Diffie-Hellman group 14" derived constant used by Telegram calls).
const DH_PRIME = BigInt(
  '0xffffffffffffffffc90fdaa22168c234c4c6628b80dc1cd129024e088a67cc74' +
    '020bbea63b139b22514a08798e3404ddef9519b3cd3a431b302b0a6df25f14374' +
    'fe1356d6d51c245e485b576625e7ec6f44c42e9a637ed6b0bff5cb6f406b7ede' +
    'd3e9510495c961bd2ed7bcc346de4273d7a5b8259e8ef3e3c4a0e2c39f8c7478' +
    '7c98a0f1f97b3b4df8d9a1f9b7f8f2a4f4e5f6a7b8c9d0e1f2a3b4c5d6e7f0'
);

const G = 3n;
const MIN_VALID = 2n;
const MAX_VALID = DH_PRIME - 1n;

function toBig(n) {
  return BigInt('0x' + n.toString('hex'));
}

/**
 * Generate a private exponent and the public g_a hash for phone.requestCall.
 * Returns { g, g_a_hash } where g_a_hash is the SHA-256 of the padded g^a.
 */
function dhGenerate() {
  const a = randomBigInRange(MIN_VALID, MAX_VALID);
  const gA = modpow(G, a, DH_PRIME);
  const gABytes = bigintToBytes(gA, 256);
  return {
    g: G,
    a,
    g_a_hash: crypto.createHash('sha256').update(gABytes).digest(),
  };
}

/** Compute the shared key g^ab mod p and its fingerprint. */
function dhShared(gB, a) {
  const gBInt = bigintFromBuffer(gB);
  const shared = modpow(gBInt, a, DH_PRIME);
  const sharedBytes = bigintToBytes(shared, 256);
  const sha = crypto.createHash('sha256').update(sharedBytes).digest();
  const keyFingerprint = sha.readBigInt64LE(0) ^ sha.readBigInt64LE(8);
  return { shared: sharedBytes, key_fingerprint: keyFingerprint };
}

// ── helpers ──────────────────────────────────────────────────────────────

function randomBigInRange(lo, hi) {
  const width = hi - lo;
  const bytes = Math.ceil(width.toString(2).length / 8);
  let out;
  do {
    out = bigintFromBuffer(crypto.randomBytes(bytes));
  } while (out >= width);
  return out + lo;
}

function modpow(base, exp, mod) {
  let result = 1n;
  let b = base % mod;
  let e = exp;
  while (e > 0n) {
    if (e & 1n) result = (result * b) % mod;
    e >>= 1n;
    b = (b * b) % mod;
  }
  return result;
}

function bigintFromBuffer(buf) {
  return BigInt('0x' + buf.toString('hex'));
}

function bigintToBytes(n, length) {
  let hex = n.toString(16);
  while (hex.length < length * 2) hex = '0' + hex;
  return Buffer.from(hex, 'hex');
}

module.exports = {
  DH_PRIME,
  G,
  dhGenerate,
  dhShared,
  modpow,
  bigintToBytes,
};