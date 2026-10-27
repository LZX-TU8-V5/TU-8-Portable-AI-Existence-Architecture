const fs = require('fs');
const p = 'D:/工作文件/小说/novel-studio/novel-studio.html';

const html = fs.readFileSync(p, 'utf-8');
const m = html.match(/<script>([\s\S]*?)<\/script>/);
const script = m[1];
const lines = script.split('\n');

console.log('=== Lines 200-220 (function start) ===');
for (let i = 199; i < 220 && i < lines.length; i++) {
  console.log((i+1) + ': ' + lines[i]);
}