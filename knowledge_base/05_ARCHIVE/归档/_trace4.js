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
let inTemplate = false;
let templateDepth = 0;

for (let i = 0; i < lines.length; i++) {
  const line = lines[i];
  let j = 0;
  
  while (j < line.length) {
    const c = line[j];
    const prev = j > 0 ? line[j-1] : '';
    
    // End of line
    if (c === '\n' || c === '\r') {
      inComment = false;
      j++;
      continue;
    }
    
    // Skip escaped
    if (prev === '\\') { j++; continue; }
    
    // Comments
    if (inComment) { j++; continue; }
    if (inBlockComment) {
      if (c === '*' && line[j+1] === '/') { inBlockComment = false; j+=2; }
      else j++;
      continue;
    }
    if (c === '/' && line[j+1] === '/') { inComment = true; j++; continue; }
    if (c === '/' && line[j+1] === '*') { inBlockComment = true; j+=2; continue; }
    
    // Template literals - handle ${} expressions
    if (!inString && c === '`') {
      inTemplate = !inTemplate;
      j++;
      continue;
    }
    if (inTemplate) {
      // Check for ${...}
      if (c === '$' && line[j+1] === '{') {
        j++;
        templateDepth = 0;
        while (j < line.length) {
          const tc = line[j];
          if (tc === '{') { templateDepth++; }
          else if (tc === '}') { templateDepth--; if (templateDepth === 0) break; }
          j++;
        }
      }
      j++;
      continue;
    }
    
    // String handling
    if (!inString && (c === '"' || c === "'")) {
      inString = true;
      stringChar = c;
      j++;
      continue;
    }
    if (inString) {
      if (c === stringChar) { inString = false; }
      j++;
      continue;
    }
    
    // Track braces
    if (c === '{') {
      depth++;
    } else if (c === '}') {
      depth--;
      if (depth < 0) {
        console.log(`\n=== NEGATIVE DEPTH at line ${i+1} (script line ${i+1}) ===`);
        console.log(`Line: ${line}`);
        for (let k = Math.max(0, i-3); k <= Math.min(lines.length-1, i+3); k++) {
          const marker = k === i ? '>>>' : '   ';
          console.log(`${marker} ${k+1}: ${lines[k]}`);
        }
        process.exit(1);
      }
    }
    j++;
  }
}

console.log('\nFinal depth:', depth);
if (depth === 0) console.log('Balanced!');
else console.log(`Imbalance: ${depth} more { than }`);