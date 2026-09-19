/**
 * Self-test for the Telegram VoIP crypto (Sprint 11.4).
 * Verifies the DH key exchange produces the SAME shared key on both sides,
 * and that g_a_hash is a SHA-256 of the padded public value.
 *
 *   node test-crypto.js
 */
'use strict';

const assert = require('assert');
const crypto = require('crypto');
const { dhGenerate, dhShared, modpow, G, DH_PRIME, bigintToBytes } = require('./lib/crypto.js');

// Both sides pick private exponents.
const alice = dhGenerate();
const bob = dhGenerate();

// Each computes their public value g^x mod p (padded to 256 bytes).
const gA_bytes = bigintToBytes(modpow(G, alice.a, DH_PRIME), 256);
const gB_bytes = bigintToBytes(modpow(G, bob.a, DH_PRIME), 256);

// g_a_hash must be SHA-256 of the padded public value.
const expectHash = crypto.createHash('sha256').update(gA_bytes).digest();
assert(alice.g_a_hash.equals(expectHash), 'g_a_hash != sha256(padded g^a)');

// Each derives the shared key from the OTHER's public value + own exponent.
const sharedA = dhShared(gB_bytes, alice.a);   // Alice: (g^b)^a
const sharedB = dhShared(gA_bytes, bob.a);     // Bob:   (g^a)^b

assert(Buffer.compare(sharedA.shared, sharedB.shared) === 0, 'shared keys differ!');
assert(typeof sharedA.key_fingerprint === 'bigint', 'fingerprint not bigint');

console.log('crypto self-test PASS');
console.log('  g_a_hash:', alice.g_a_hash.toString('hex').slice(0, 16) + '…');
console.log('  shared key (256B):', sharedA.shared.slice(0, 8).toString('hex') + '…');
console.log('  key_fingerprint:', sharedA.key_fingerprint.toString(16).slice(0, 16) + '…');