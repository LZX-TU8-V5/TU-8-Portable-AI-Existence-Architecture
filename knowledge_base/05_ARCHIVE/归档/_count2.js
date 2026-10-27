const fs = require('fs');
const html = fs.readFileSync('D:/工作文件/小说/novel-studio/novel-studio.html', 'utf-8');
const m = html.match(/<script>([\s\S]*?)<\/script>/);
const script = m[1];
const lines = script.split('\n');

function countBraces(arr) {
  let o = 0, c = 0;
  for (const line of arr) {
    for (const ch of line) {
      if (ch === '{') o++;
      if (ch === '}') c++;
    }
  }
  return o - c;
}

console.log('203-218:', countBraces(lines.slice(202, 218)));
console.log('219-275:', countBraces(lines.slice(218, 275)));
console.log('Total:', countBraces(lines));