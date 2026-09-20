/**
 * Telegram p2p call STATE MACHINE over GramJS MTProto (Sprint 11.4).
 *
 * Drives: requestCall -> (wait for accepted) -> confirmCall -> discardCall.
 * Uses the crypto in ./crypto.js for the DH handshake. The media layer
 * (SRTP audio -> JARVIS STT/TTS) is NOT wired; see README verification status.
 */
'use strict';

const { Api } = require('telegram');

const PROTOCOL = new Api.PhoneCallProtocol({
  udpP2p: true,
  udpReflector: true,
  minLayer: 92,
  maxLayer: 92,
  libraryVersions: ['3.0.0'],
});

/**
 * Initiate a call to a user. Returns { call, a } where `a` is the private
 * exponent to complete the handshake when the peer accepts.
 */
async function requestCall(client, userId) {
  const { dhGenerate } = require('./crypto.js');
  const { g, a, g_a_hash } = dhGenerate();
  const randomId = Math.floor(Math.random() * 0x7fffffff);
  const result = await client.invoke(
    new Api.phone.RequestCall({
      userId: await client.getInputEntity(userId),
      randomId,
      gAHash: g_a_hash,
      protocol: PROTOCOL,
    })
  );
  return { call: result.call, a, randomId };
}

/**
 * Accept an incoming call (peer sent phoneCallRequested). Returns the
 * confirmed shared-key info once phone.confirmCall succeeds.
 */
async function acceptCall(client, peer, a, gB) {
  const { dhShared } = require('./crypto.js');
  const shared = dhShared(gB, a);
  await client.invoke(
    new Api.phone.AcceptCall({
      peer: new Api.InputPhoneCall({ id: peer.id, accessHash: peer.accessHash }),
      gB: bigintToBytes(shared.shared, 256),
      protocol: PROTOCOL,
    })
  );
  return shared;
}

async function confirmCall(client, peer, shared) {
  const { dhShared } = require('./crypto.js');
  await client.invoke(
    new Api.phone.ConfirmCall({
      peer: new Api.InputPhoneCall({ id: peer.id, accessHash: peer.accessHash }),
      gA: bigintToBytes(shared.shared, 256),
      keyFingerprint: shared.key_fingerprint,
      protocol: PROTOCOL,
    })
  );
}

async function discardCall(client, peer, reason = 'hangup') {
  const reasons = {
    hangup: new Api.PhoneCallDiscardReasonHangup(),
    disconnect: new Api.PhoneCallDiscardReasonDisconnect(),
    busy: new Api.PhoneCallDiscardReasonBusy(),
    missed: new Api.PhoneCallDiscardReasonMissed(),
  };
  await client.invoke(
    new Api.phone.DiscardCall({
      peer: new Api.InputPhoneCall({ id: peer.id, accessHash: peer.accessHash }),
      duration: 0,
      reason: reasons[reason] || reasons.hangup,
      connectionId: 0n,
    })
  );
}

function bigintToBytes(n, length) {
  let hex = n.toString(16);
  while (hex.length < length * 2) hex = '0' + hex;
  return Buffer.from(hex, 'hex');
}

module.exports = {
  PROTOCOL,
  requestCall,
  acceptCall,
  confirmCall,
  discardCall,
};