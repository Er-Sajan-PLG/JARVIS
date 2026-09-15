/* Parse-check every frontend ES module by actually importing it under a
   minimal DOM shim. Catches syntax errors, bad import specifiers and
   top-level crashes without needing a browser. */

import { readFileSync, readdirSync } from 'node:fs';
import { pathToFileURL } from 'node:url';
import { resolve } from 'node:path';

const DIR = resolve('frontend/assets');

/* ── Minimal DOM shim ─────────────────────────────────────────────────── */

class ClassList {
  constructor() { this.set = new Set(); }
  add(...c) { c.forEach((x) => this.set.add(x)); }
  remove(...c) { c.forEach((x) => this.set.delete(x)); }
  contains(c) { return this.set.has(c); }
  toggle(c, force) {
    const on = force === undefined ? !this.set.has(c) : force;
    on ? this.set.add(c) : this.set.delete(c);
    return on;
  }
}

class Node {
  constructor(tag = 'div') {
    this.tagName = String(tag).toUpperCase();
    this.children = [];
    this.classList = new ClassList();
    this.dataset = {};
    this.style = {};
    this.attributes = {};
    this.listeners = {};
    this.value = '';
    this.textContent = '';
    this.type = '';
    this.disabled = false;
    this.checked = false;
  }
  appendChild(c) { this.children.push(c); return c; }
  removeChild(c) { this.children = this.children.filter((x) => x !== c); return c; }
  remove() {}
  replaceWith() {}
  setAttribute(k, v) { this.attributes[k] = v; if (k === 'class') this.className = v; }
  getAttribute(k) { return this.attributes[k] ?? null; }
  addEventListener(t, fn) { (this.listeners[t] ||= []).push(fn); }
  removeEventListener() {}
  querySelector() { return null; }
  querySelectorAll() { return []; }
  focus() {}
  select() {}
  blur() {}
  click() {}
  get innerHTML() { return ''; }
  set innerHTML(v) { this.children = []; }
  get scrollHeight() { return 0; }
}

const document = {
  documentElement: new Node('html'),
  body: new Node('body'),
  createElement: (t) => new Node(t),
  createTextNode: (t) => ({ nodeType: 3, textContent: t }),
  querySelector: () => null,
  querySelectorAll: () => [],
  addEventListener: () => {},
  getElementById: () => null,
};

const localStorage = {
  _d: {},
  getItem(k) { return this._d[k] ?? null; },
  setItem(k, v) { this._d[k] = String(v); },
  removeItem(k) { delete this._d[k]; },
};

globalThis.document = document;
globalThis.window = {
  matchMedia: () => ({ matches: false, addEventListener: () => {} }),
  localStorage,
};
globalThis.localStorage = localStorage;
globalThis.confirm = () => true;
globalThis.fetch = async () => ({
  ok: true, status: 200,
  text: async () => '{"providers":[]}',
  json: async () => ({ providers: [] }),
});

/* ── Import each module ───────────────────────────────────────────────── */

const files = readdirSync(DIR).filter((f) => f.endsWith('.js')).sort();
let failures = 0;

for (const f of files) {
  const url = pathToFileURL(resolve(DIR, f)).href;
  try {
    const mod = await import(url);
    const names = Object.keys(mod);
    console.log(`OK    ${f.padEnd(14)} exports: ${names.length ? names.join(', ') : '(side-effect only)'}`);
  } catch (err) {
    failures++;
    console.log(`FAIL  ${f}`);
    console.log(`      ${err.message.split('\n')[0]}`);
  }
}

console.log(`\n${files.length - failures}/${files.length} modules imported cleanly`);
process.exit(failures ? 1 : 0);