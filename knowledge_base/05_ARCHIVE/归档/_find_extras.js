const fs = require('fs');
const p = 'D:/工作文件/小说/novel-studio/novel-studio.html';
let html = fs.readFileSync(p, 'utf-8');
const lines = html.split('\n');

// Remove ONE extra } from around lines 275-276 (where we see two in a row)
console.log('Lines around 274-278:');
for (let i = 273; i < 278; i++) console.log(i+1 + ': ' + lines[i]);

// Find lines with just }
const candidates = [];
for (let i = 0; i < lines.length; i++) {
  if (lines[i].trim() === '}') candidates.push(i+1);
}
console.log('\nAll standalone } lines:', candidates.slice(0, 20));