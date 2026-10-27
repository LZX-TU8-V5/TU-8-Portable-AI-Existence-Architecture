const fs = require('fs');
const p = 'D:/工作文件/小说/novel-studio/novel-studio.html';

const html = fs.readFileSync(p, 'utf-8');
const m = html.match(/<script>([\s\S]*?)<\/script>/);
const script = m[1];
const lines = script.split('\n');

// Find where the initData function starts
console.log('=== Looking for initData function ===');
for (let i = 180; i < 225 && i < lines.length; i++) {
  if (lines[i].includes('function') || lines[i].includes('async')) {
    console.log((i+1) + ': ' + lines[i]);
  }
}