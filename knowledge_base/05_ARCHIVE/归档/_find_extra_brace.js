const fs = require('fs');
const main = fs.readFileSync('D:/工作文件/小说/novel-studio/novel-studio.html', 'utf-8');
const main_m = main.match(/<script>([\s\S]*?)<\/script>/);
const lines = main_m[1].split('\n');

// Track brace depth and find where it goes negative
let depth = 0;
let inString = false;
let stringChar = '';

for (let i = 0; i < lines.length; i++) {
  const line = lines[i];
  for (let j = 0; j < line.length; j++) {
    const c = line[j];
    const prev = j > 0 ? line[j-1] : '';
    
    // Handle strings
    if (!inString && (c === '"' || c === "'" || c === '`')) {
      inString = true;
      stringChar = c;
    } else if (inString && c === stringChar && prev !== '\\') {
      inString = false;
    } else if (!inString) {
      if (c === '{') depth++;
      if (c === '}') {
        depth--;
        if (depth < 0) {
          console.log('Extra } at script line', i+1, 'col', j+1);
          console.log('Line content:', line.substring(0, 80));
          // Show context
          for (let k = Math.max(0, i-3); k < Math.min(lines.length, i+3); k++) {
            console.log('  ', k+1, ':', lines[k].substring(0, 70));
          }
          process.exit(0);
        }
      }
    }
  }
}

console.log('Final depth:', depth);
if (depth !== 0) {
  console.log('Unbalanced braces, final depth should be 0');
}
