const fs = require('fs');
const stand = fs.readFileSync('D:/工作文件/小说/novel-studio/novel-studio-standalone.html', 'utf-8');
const main = fs.readFileSync('D:/工作文件/小说/novel-studio/novel-studio.html', 'utf-8');
const stand_m = stand.match(/<script>([\s\S]*?)<\/script>/);
const main_m = main.match(/<script>([\s\S]*?)<\/script>/);
const sLines = stand_m[1].split('\n');
const mLines = main_m[1].split('\n');

// Check for function declarations in both around line 64-68
console.log('=== Looking for function declarations around shelf ===');
for (let i = 0; i < sLines.length; i++) {
  if (/function\s+(renderShelf|openShelf|closeShelf)/.test(sLines[i])) {
    console.log('STAND function at line', i+1, ':', sLines[i].trim().substring(0,80));
  }
}
for (let i = 0; i < mLines.length; i++) {
  if (/function\s+(renderShelf|openShelf|closeShelf)/.test(mLines[i])) {
    console.log('MAIN function at line', i+1, ':', mLines[i].trim().substring(0,80));
  }
}

// Check what's before line 65 in MAIN
console.log('\n=== MAIN before line 65 ===');
for (let i = 60; i < 68; i++) console.log((i+1) + ': ' + mLines[i].substring(0,80));

// Check what's before line 67 in STAND
console.log('\n=== STAND before line 67 ===');
for (let i = 62; i < 70; i++) console.log((i+1) + ': ' + sLines[i].substring(0,80));

// The fix: insert 'function renderShelfList() {' before MAIN script line 65 (HTML line ~637)
// Find the right position in HTML (script starts at HTML line 572)
// MAIN script line 65 = HTML line 572 + 65 - 1 = 636
console.log('\nFix: Insert "function renderShelfList() {" at HTML line', 572 + 65 - 1);