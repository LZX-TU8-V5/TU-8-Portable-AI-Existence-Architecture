const fs = require('fs');
const p = 'D:/工作文件/小说/novel-studio/novel-studio.html';

const html = fs.readFileSync(p, 'utf-8');
const m = html.match(/<script>([\s\S]*?)<\/script>/);
const script = m[1];
const lines = script.split('\n');

// Look at lines 260-290 with more context
console.log('=== Lines 260-295 ===');
for (let i = 259; i < 295 && i < lines.length; i++) {
  console.log((i+1) + ': ' + lines[i]);
}