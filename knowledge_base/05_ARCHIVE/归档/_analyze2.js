const fs = require('fs');

// Let's be more careful. First, let's look at the server injection
const main = fs.readFileSync('D:/工作文件/小说/novel-studio/novel-studio.html', 'utf-8');
const stand = fs.readFileSync('D:/工作文件/小说/novel-studio/novel-studio-standalone.html', 'utf-8');
const main_m = main.match(/<script>([\s\S]*?)<\/script>/);
const stand_m = stand.match(/<script>([\s\S]*?)<\/script>/);
const mainLines = main_m[1].split('\n');
const standLines = stand_m[1].split('\n');

console.log('MAIN has embedded-data lines:');
for (let i = 0; i < mainLines.length; i++) {
  if (mainLines[i].includes('embedded') || mainLines[i].includes('embedded-data')) {
    console.log('  Line', i+1, ':', mainLines[i].substring(0,80));
  }
}

console.log('\nSTAND has embedded-data lines:');
for (let i = 0; i < standLines.length; i++) {
  if (standLines[i].includes('embedded') || standLines[i].includes('embedded-data')) {
    console.log('  Line', i+1, ':', standLines[i].substring(0,80));
  }
}

// Check how many lines are different (just the embedded part)
let diffCount = 0;
const maxI = Math.max(mainLines.length, standLines.length);
for (let i = 0; i < maxI; i++) {
  const m = mainLines[i] || '';
  const s = standLines[i] || '';
  if (m !== s) diffCount++;
}
console.log('\nTotal different lines:', diffCount);

// Best approach: fix the brace balance in main
// Main has brace imbalance at line 76 (extra })
// We know standalone line 76 = "}" and main line 76 = "}" too...
// Wait, check the balance more carefully
// After line 75 in MAIN: balance = 1 (extra })
// After line 75 in STAND: balance = 0

// The difference in lines 73-78 between MAIN and STAND suggests
// the MAIN version is MISSING some lines
// Let me find what's missing

// Find where MAIN diverges from STAND at line 73
console.log('\n=== Line-by-line from line 70 ===');
for (let i = 69; i < 85; i++) {
  const m = mainLines[i] || '<MISSING>';
  const s = standLines[i] || '<MISSING>';
  if (m !== s || i >= mainLines.length || i >= standLines.length) {
    console.log('DIFF at line', i+1);
    console.log('  MAIN: ', m.substring(0,80));
    console.log('  STAND:', s.substring(0,80));
  }
}