const fs = require('fs');
const html = fs.readFileSync('D:\\工作文件\\小说\\novel-studio\\novel-studio.html', 'utf-8');
const match = html.match(/<script>([\s\S]*?)<\/script>/);
const script = match[1];
const lines = script.split('\n');

let depth = 0;
let inString = false;
let stringChar = '';
let inComment = false;
let inBlockComment = false;

for (let i = 0; i < lines.length; i++) {
  const line = lines[i];
  let j = 0;
  
  while (j < line.length) {
    const c = line[j];
    const prev = j > 0 ? line[j-1] : '';
    
    // End of line - reset comment state
    if (c === '\n' || c === '\r') {
      inComment = false;
      j++;
      continue;
    }
    
    // Skip content after comment markers
    if (inComment || inBlockComment) {
      j++;
      continue;
    }
    
    // Skip escaped characters
    if (prev === '\\') {
      j++;
      continue;
    }
    
    // String handling
    if (!inString && (c === '"' || c === "'" || c === '`')) {
      inString = true;
      stringChar = c;
      j++;
      continue;
    }
    if (inString) {
      if (c === stringChar && prev !== '\\') {
        inString = false;
      }
      j++;
      continue;
    }
    
    // Comment detection
    if (c === '/' && line[j+1] === '/') {
      inComment = true;
      j++;
      continue;
    }
    if (c === '/' && line[j+1] === '*') {
      inBlockComment = true;
      j += 2;
      continue;
    }
    if (c === '*' && line[j+1] === '/') {
      inBlockComment = false;
      j += 2;
      continue;
    }
    
    // Template literal inside strings... handled above
    
    // Track braces
    if (c === '{') {
      depth++;
    } else if (c === '}') {
      depth--;
      if (depth < 0) {
        console.log(`\n=== DEPTH GOES NEGATIVE at line ${i+1} (HTML line ${573+i}) ===`);
        console.log(`Current depth: ${depth+1} → ${depth}`);
        console.log(`Line: ${line}`);
        // Show context
        for (let k = Math.max(0, i-5); k <= Math.min(lines.length-1, i+3); k++) {
          const marker = k === i ? '>>>' : '   ';
          console.log(`${marker} ${k+1}: ${lines[k]}`);
        }
        process.exit(1); // Stop at first negative
      }
    }
    
    j++;
  }
}

console.log('\n=== Script analysis ===');
console.log('Final depth:', depth, '(should be 0)');
if (depth !== 0) {
  console.log(`ERROR: Imbalance of ${-depth} closing braces`);
}