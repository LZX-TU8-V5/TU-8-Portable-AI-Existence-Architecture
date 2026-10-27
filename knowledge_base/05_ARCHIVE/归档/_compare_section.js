const fs = require('fs');
const main = fs.readFileSync('D:/工作文件/小说/novel-studio/novel-studio.html', 'utf-8');
const stand = fs.readFileSync('D:/工作文件/小说/novel-studio/novel-studio-standalone.html', 'utf-8');
const main_m = main.match(/<script>([\s\S]*?)<\/script>/);
const stand_m = stand.match(/<script>([\s\S]*?)<\/script>/);
const mLines = main_m[1].split('\n');
const sLines = stand_m[1].split('\n');

// Find the section with the fallback UI in both
console.log('=== MAIN lines 270-285 ===');
for (let i = 269; i < 285; i++) {
  console.log((i+1) + ': ' + (mLines[i] || '<MISSING>').substring(0, 80));
}

console.log('\n=== STANDALONE lines 270-285 ===');
for (let i = 269; i < 285; i++) {
  console.log((i+1) + ': ' + (sLines[i] || '<MISSING>').substring(0, 80));
}

// Count lines in both
console.log('\nMain script total lines:', mLines.length);
console.log('Standalone script total lines:', sLines.length);
