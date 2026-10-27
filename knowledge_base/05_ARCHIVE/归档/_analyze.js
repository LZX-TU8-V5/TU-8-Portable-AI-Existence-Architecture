const fs = require('fs');
const main = fs.readFileSync('D:/工作文件/小说/novel-studio/novel-studio.html', 'utf-8');
const stand = fs.readFileSync('D:/工作文件/小说/novel-studio/novel-studio-standalone.html', 'utf-8');
const main_m = main.match(/<script>([\s\S]*?)<\/script>/);
const stand_m = stand.match(/<script>([\s\S]*?)<\/script>/);
if (!main_m || !stand_m) { process.exit(1); }

// Line count diff
console.log('MAIN script lines:', main_m[1].split('\n').length);
console.log('STAND script lines:', stand_m[1].split('\n').length);
console.log('');

// Find 'return' statements that are at top level (not in a function or arrow function body)
const mainLines = main_m[1].split('\n');
let inFunction = 0; // brace depth inside { }
let inArrow = false;

for (let i = 0; i < mainLines.length; i++) {
  const line = mainLines[i];
  const trimmed = line.trim();
  
  // Detect function declarations
  if (/^function\s+\w+/.test(trimmed)) inFunction++;
  // Detect async function
  if (/^async\s+function\s+\w+/.test(trimmed)) inFunction++;
  
  // Count braces (but skip object literals)
  for (const ch of line) {
    if (ch === '{') {
      // Simple heuristic: if we're in a function and see {, we're in block
      if (inFunction > 0) {}
      // Just track globally
    }
  }
  
  // Check for return at top level
  if (trimmed.startsWith('return ') && inFunction === 0 && !inArrow) {
    console.log('TOP-LEVEL return at script line', i+1, ':', trimmed.substring(0, 80));
  }
}

// Count functions vs code in main
const fnCount = (main_m[1].match(/^function\s+\w+/gm) || []).length;
const asyncFnCount = (main_m[1].match(/^async\s+function\s+\w+/gm) || []).length;
console.log('\nFunctions in MAIN script:', fnCount, 'sync +', asyncFnCount, 'async =', fnCount + asyncFnCount);

const fnCountS = (stand_m[1].match(/^function\s+\w+/gm) || []).length;
const asyncFnCountS = (stand_m[1].match(/^async\s+function\s+\w+/gm) || []).length;
console.log('Functions in STAND script:', fnCountS, 'sync +', asyncFnCountS, 'async =', fnCountS + asyncFnCountS);