const fs = require('fs');
const p = 'D:/工作文件/小说/novel-studio/novel-studio.html';

const html = fs.readFileSync(p, 'utf-8');
const m = html.match(/<script>([\s\S]*?)<\/script>/);
const script = m[1];
const lines = script.split('\n');

// Find the function that contains lines 260-275 - its opening brace
console.log('=== Lines 220-265 ===');
for (let i = 219; i < 265 && i < lines.length; i++) {
  console.log((i+1) + ': ' + lines[i]);
}