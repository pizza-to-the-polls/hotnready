// Minimal DOM stub to smoke-test the two inline scripts (comp + e15) from the generated page.
const fs = require('fs');
const path = require('path');
const html = fs.readFileSync(process.argv[2] || path.join(__dirname, 'out/midterm-volume/index.html'), 'utf8');
const blocks = [...html.matchAll(/<script>\n([\s\S]*?)<\/script>/g)].map(m => m[1]);

function makeEl(tag) {
  return {
    tag, children: [], attrs: {}, style: {}, textContent: '', _handlers: {},
    setAttribute(k, v) { this.attrs[k] = String(v); },
    appendChild(c) { this.children.push(c); return c; },
    insertBefore(c) { this.children.unshift(c); return c; },
    removeChild(c) { const i = this.children.indexOf(c); if (i >= 0) this.children.splice(i, 1); },
    get firstChild() { return this.children[0] || null; },
    addEventListener(t, fn) { (this._handlers[t] = this._handlers[t] || []).push(fn); },
    dispatch(t, ev) { (this._handlers[t] || []).forEach(fn => fn(ev)); },
    getBoundingClientRect() { return { left: 0, top: 0, width: 1240, height: 640 }; },
    classList: { add() {}, remove() {}, toggle() {}, contains() { return false; } },
    querySelectorAll() { return []; },
    querySelector() { return null; },
    get offsetWidth() { return 200; }, get offsetHeight() { return 80; },
  };
}
const byId = {};
['comp', 'tip', 'compctl', 'e15', 'e15tip', 'e15ctl'].forEach(id => byId[id] = makeEl('div'));
global.document = {
  getElementById(id) { if (!byId[id]) byId[id] = makeEl('div'); return byId[id]; },
  createElement(t) { return makeEl(t); },
  createElementNS(ns, t) { return makeEl(t); },
};
global.window = global;

function countTree(el, pred, acc = 0) {
  if (pred(el)) acc++;
  el.children.forEach(c => { acc = countTree(c, pred, acc); });
  return acc;
}
function findCapture(el) {
  let found = null;
  (function walk(e) {
    e.children.forEach(c => { if (c.attrs && c.attrs.fill === 'transparent') found = c; walk(c); });
  })(el);
  return found;
}

if (blocks.length !== 2) throw new Error('expected 2 script blocks, got ' + blocks.length);
console.log('script blocks: 2 | comp lines:', blocks[0].split('\n').length, '| e15 lines:', blocks[1].split('\n').length);
blocks.forEach((b, i) => {
  new Function(b)(); // syntax + immediate run
  console.log('block', i, 'ran OK');
});

// comp chart
const compSvg = byId['comp'].children.filter(c => c.tag === 'svg')[0];
console.log('comp elements:', countTree(compSvg, () => true));
byId['compctl'].children.forEach((btn, j) => btn.onclick());
console.log('comp chips clicked:', byId['compctl'].children.length);
findCapture(compSvg).dispatch('mousemove', { clientX: 400, clientY: 200 });
console.log('comp tooltip len:', byId['tip'].innerHTML.length);

// e15 chart
const e15Svg = byId['e15'].children.filter(c => c.tag === 'svg')[0];
console.log('e15 elements:', countTree(e15Svg, () => true));
byId['e15ctl'].children.forEach(btn => btn.onclick());
console.log('e15 metric chips clicked:', byId['e15ctl'].children.length);
const cap = findCapture(e15Svg);
cap.dispatch('mousemove', { clientX: 300, clientY: 100 });
console.log('e15 tooltip len:', byId['e15tip'].innerHTML.length, '| display:', byId['e15tip'].style.display);
cap.dispatch('mousemove', { clientX: 1200, clientY: 100 });
cap.dispatch('mouseleave', {});
console.log('ALL OK');