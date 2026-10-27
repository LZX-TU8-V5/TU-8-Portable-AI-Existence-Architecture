const fs = require('fs');
const p = 'D:/工作文件/小说/novel-studio/novel-studio.html';

const html = fs.readFileSync(p, 'utf-8');
const m = html.match(/<script>([\s\S]*?)<\/script>/);
const script = m[1];
const lines = script.split('\n');

console.log('=== Lines 215-219 EXACT ===');
for (let i = 214; i < 219 && i < lines.length; i++) {
  const line = lines[i];
  console.log((i+1) + ' len=' + line.length + ': [' + line + ']');
}