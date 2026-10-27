const fs = require('fs');

const stand = fs.readFileSync('D:/工作文件/小说/novel-studio/novel-studio-standalone.html', 'utf-8');
const main = fs.readFileSync('D:/工作文件/小说/novel-studio/novel-studio.html', 'utf-8');

// Extract scripts
const stand_m = stand.match(/<script>([\s\S]*?)<\/script>/);
const main_m = main.match(/<script>([\s\S]*?)<\/script>/);

console.log('STANDALONE script lines:', stand_m[1].split('\n').length);
console.log('MAIN script lines:', main_m[1].split('\n').length);
console.log('');

// The main file has the server-side injection. Let's check what makes it different.
console.log('=== MAIN first 3 lines ===');
main_m[1].split('\n').slice(0,3).forEach((l,i) => console.log(i+1+': '+l.substring(0,80)));

// Find return at top level in main
console.log('\n=== Top-level returns in MAIN script ===');
const mainLines = main_m[1].split('\n');
let braceDepth = 0;
let fnDepth = 0;
let inMultiLineString = false;

for (let i = 0; i < mainLines.length; i++) {
  let changed = false;
  for (const ch of mainLines[i]) {
    if (ch === "'" || ch === '"' || ch === '`') inMultiLineString = !inMultiLineString;
  }
  const t = mainLines[i].trim();
  if (t.startsWith('function ') || t.startsWith('async function ')) fnDepth++;
  if (t === '}' && fnDepth > 0) fnDepth--;
  if (t.startsWith('return ') && fnDepth === 0 && !inMultiLineString) {
    console.log('Script line', i+1, ':', t.substring(0,80));
  }
}