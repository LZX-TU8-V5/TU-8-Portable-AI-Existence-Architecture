const fs = require('fs');
const main = fs.readFileSync('D:/工作文件/小说/novel-studio/novel-studio.html', 'utf-8');
const stand = fs.readFileSync('D:/工作文件/小说/novel-studio/novel-studio-standalone.html', 'utf-8');
const main_m = main.match(/<script>([\s\S]*?)<\/script>/);
const stand_m = stand.match(/<script>([\s\S]*?)<\/script>/);
const mLines = main_m[1].split('\n');
const sLines = stand_m[1].split('\n');

console.log('=== Lines 73-78 in BOTH ===');
for (let i = 72; i < 78; i++) {
  console.log('MAIN  line', i+1, ':', mLines[i]);
  console.log('STAND line', i+1, ':', sLines[i]);
  console.log('');
}

// Show the area where standalone error occurs (line 81 in standalone = line ~78 in main)
// Check what's around main script line 75
console.log('MAIN script line 75:', JSON.stringify(mLines[74]));
console.log('MAIN script line 76:', JSON.stringify(mLines[75]));

// Count braces in lines 1-75 of main
let b = 0;
for (let i = 0; i < 75; i++) {
  for (const c of mLines[i]) {
    if (c === '{') b++;
    if (c === '}') b--;
  }
}
console.log('\nBrace balance after line 75 in MAIN:', b);

// For comparison, count in standalone lines 1-80
let bs = 0;
for (let i = 0; i < 80; i++) {
  for (const c of sLines[i]) {
    if (c === '{') bs++;
    if (c === '}') bs--;
  }
}
console.log('Brace balance after line 80 in STAND:', bs);