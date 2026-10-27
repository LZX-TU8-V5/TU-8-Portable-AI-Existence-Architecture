const fs = require('fs');
const p = 'D:/工作文件/小说/novel-studio/novel-studio.html';
const html = fs.readFileSync(p, 'utf-8');
const m = html.match(/<script>([\s\S]*?)<\/script>/);
const script = m[1];
const lines = script.split('\n');

// Find lines with 'return' that aren't part of 'return (' or 'return' inside a function
for (let i = 0; i < lines.length; i++) {
  const line = lines[i];
  if (line.includes('return') && !line.includes('=>') && !line.includes('function')) {
    console.log('Line', i+1 + ':', line.trim().substring(0, 80));
  }
}