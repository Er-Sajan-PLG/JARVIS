/**
 * First-time login: creates the userbot session file.
 *
 *   TG_API_ID=.. TG_API_HASH=.. node login.js
 *
 * Telegram sends a login code to your app — paste it at the prompt. The
 * session (data/tgcall.session, mode 600) persists, so this runs once.
 * From then on call.js starts without interaction.
 */
'use strict';

const readline = require('readline');
const { TelegramClient } = require('telegram');
const { StringSession } = require('telegram/sessions');

const API_ID = Number(process.env.TG_API_ID || 0);
const API_HASH = process.env.TG_API_HASH || '';
const SESSION_PATH = process.env.TG_SESSION || __dirname + '/../data/tgcall.session';

if (!API_ID || !API_HASH) {
  console.error('TG_API_ID / TG_API_HASH required (https://my.telegram.org).');
  process.exit(2);
}

const ask = (q) =>
  new Promise((resolve) => {
    const rl = readline.createInterface({ input: process.stdin, output: process.stdout });
    rl.question(q, (ans) => {
      rl.close();
      resolve(ans.trim());
    });
  });

(async () => {
  const client = new TelegramClient(new StringSession(''), API_ID, API_HASH, {
    connectionRetries: 5,
  });
  await client.start({
    phoneNumber: () => ask('Phone number (international format): '),
    password: () => ask('2FA password (empty if none): '),
    phoneCode: () => ask('Login code from Telegram: '),
    onError: (err) => console.error('login error:', err.message),
  });
  const fs = require('fs');
  fs.mkdirSync(require('path').dirname(SESSION_PATH), { recursive: true });
  fs.writeFileSync(SESSION_PATH, client.session.save(), { mode: 0o600 });
  console.log('Session saved. You will not need the code again.');
  await client.disconnect();
})().catch((err) => {
  console.error('login failed:', err.message);
  process.exit(1);
});
