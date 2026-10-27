const fs = require('fs');
const p = 'D:/工作文件/小说/novel-studio/novel-studio.html';

const html = fs.readFileSync(p, 'utf-8');
const m = html.match(/<script>([\s\S]*?)<\/script>/);
const script = m[1];
const lines = script.split('\n');

// Count braces in lines 203-218
let open = 0, close = 0;
for (let i = 202; i < 218; i++) {
  const line = lines[i];
  for (const c of line) {
    if (c === '{') open++;
    if (c === '}') close++;
  }
}
console.log('Lines 203-218: open=' + open + ', close=' + close);

// Now 219-275
open = 0; close = 0;
for (let i = 218; i < 275; i++) {
  const line = lines[i];
  for (const c of line) {
    if (c === '{') open++;
    if (c === '}') close++;
  }
}
console.log('Lines 219-275: open=' + open + ', close=' + close);