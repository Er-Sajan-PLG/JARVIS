/**
 * Self-test: pins the installed gram-tgcalls API surface WITHOUT credentials.
 * Run before the first live call — tgcalls APIs drift between versions, and
 * lib/call.js asserts against what this reports.
 *
 *   node check-api.js
 */
'use strict';

const gram = require('gram-tgcalls');

console.log('gram-tgcalls exports:', Object.keys(gram).sort().join(', '));
for (const name of ['VoiceCall', 'GroupCall', 'CallsClient']) {
  if (gram[name]) {
    const proto = Object.getOwnPropertyNames(gram[name].prototype || {});
    console.log(`${name} methods:`, proto.filter((m) => m !== 'constructor').sort().join(', '));
  }
}
try {
  const pkg = require('gram-tgcalls/package.json');
  console.log('gram-tgcalls version:', pkg.version);
} catch { /* ignore */ }
try {
  console.log('tgcalls version:', require('tgcalls/package.json').version);
} catch { /* ignore */ }
