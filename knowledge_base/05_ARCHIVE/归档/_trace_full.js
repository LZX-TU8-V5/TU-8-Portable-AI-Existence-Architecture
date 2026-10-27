const fs = require('fs');
const p = 'D:/工作文件/小说/novel-studio/novel-studio.html';

const html = fs.readFileSync(p, 'utf-8');
const m = html.match(/<script>([\s\S]*?)<\/script>/);
const script = m[1];
const lines = script.split('\n');

// Track brace depth through ENTIRE script
let depth = 0;
let minDepth = 0;
let minLine = 0;

// Skip strings/comments - simpler approach
for (let i = 0; i < lines.length; i++) {
  const line = lines[i];
  let inString = false;
  let stringChar = '';
  
  for (let j = 0; j < line.length; j++) {
    const c = line[j];
    const prev = j > 0 ? line[j-1] : '';
    
    // Skip escaped
    if (prev === '\\') continue;
    
    // String handling
    if (!inString && (c === '"' || c === "'" || c === '`')) {
      inString = true;
      stringChar = c;
      continue;
    }
    if (inString) {
      if (c === stringChar) inString = false;
      continue;
    }
    
    // Skip comments
    if (c === '/' && line[j+1] === '/') break;
    
    // Track braces - only count { and }
    if (c === '{') depth++;
    else if (c === '}') {
      depth--;
      if (depth < minDepth) {
        minDepth = depth;
        minLine = i + 1;
      }
    }
  }
}

console.log('Final depth:', depth);
console.log('Min depth:', minDepth, 'at line', minLine);

if (minLine > 0) {
  console.log('\n=== Context around line', minLine, '===');
  for (let k = Math.max(0, minLine-4); k < Math.min(lines.length, minLine+3); k++) {
    const marker = k+1 === minLine ? '>>>' : '   ';
    console.log(marker + ' ' + (k+1) + ': ' + lines[k]);
  }
}