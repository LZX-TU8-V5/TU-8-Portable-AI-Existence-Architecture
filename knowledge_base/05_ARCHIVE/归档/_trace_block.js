const fs = require('fs');
const main = fs.readFileSync('D:/工作文件/小说/novel-studio/novel-studio.html', 'utf-8');
const main_m = main.match(/<script>([\s\S]*?)<\/script>/);
const lines = main_m[1].split('\n');

// Trace back from line 276 to find the matching {
let targetLine = 275; // 0-indexed = 276-1
let braceDepth = 1; // We found an extra } so we need to find what { it matches

for (let i = targetLine; i >= 0; i--) {
  const line = lines[i];
  for (let j = line.length - 1; j >= 0; j--) {
    const c = line[j];
    if (c === '}') braceDepth++;
    if (c === '{') {
      braceDepth--;
      if (braceDepth === 0) {
        console.log('Matching { found at line', i+1, 'col', j+1);
        console.log('Line content:', line.substring(0, 80));
        // Show context
        for (let k = Math.max(0, i-2); k < Math.min(lines.length, i+5); k++) {
          console.log('  ', k+1, ':', lines[k].substring(0, 70));
        }
        process.exit(0);
      }
    }
  }
}

console.log('Could not find matching {');
