const fs = require('fs');
const p = 'D:/工作文件/小说/novel-studio/novel-studio.html';

const html = fs.readFileSync(p, 'utf-8');
const m = html.match(/<script>([\s\S]*?)<\/script>/);
const script = m[1];
const lines = script.split('\n');

console.log('=== Lines 238-262 ===');
for (let i = 237; i < 262 && i < lines.length; i++) {
  console.log((i+1) + ': ' + lines[i]);
}