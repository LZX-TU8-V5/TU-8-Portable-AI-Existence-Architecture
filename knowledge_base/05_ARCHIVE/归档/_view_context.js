const fs = require('fs');
const main = fs.readFileSync('D:/工作文件/小说/novel-studio/novel-studio.html', 'utf-8');
const main_m = main.match(/<script>([\s\S]*?)<\/script>/);
const lines = main_m[1].split('\n');

console.log('=== Lines 270-285 ===');
for (let i = 269; i < 285; i++) {
  console.log((i+1) + ': ' + lines[i]);
}

// Also check what function this is in
console.log('\n=== Finding enclosing function ===');
for (let i = 275; i >= 0; i--) {
  if (/function\s+\w+\s*\(/.test(lines[i])) {
    console.log('Function at line', i+1, ':', lines[i].trim().substring(0, 60));
    break;
  }
}
