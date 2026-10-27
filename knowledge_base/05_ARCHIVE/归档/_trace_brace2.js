const fs = require('fs');
const html = fs.readFileSync('D:\\工作文件\\小说\\novel-studio\\novel-studio.html', 'utf-8');
const match = html.match(/<script>([\s\S]*?)<\/script>/);
const script = match[1];
const lines = script.split('\n');

// State machine for parsing JS tokens
let depth = 0;
let minDepth = 0;
let minDepthLine = 0;
let inTemplate = false;  // inside backtick string
let inExpr = false;      // inside ${...} inside template
let exprDepth = 0;        // brace depth inside ${...}
let inString = false;
let stringChar = '';

for (let i = 0; i < lines.length; i++) {
  const line = lines[i];
  for (let j = 0; j < line.length; j++) {
    const c = line[j];
    const prev = j > 0 ? line[j-1] : '';
    const prev2 = j > 1 ? line[j-2] : '';
    
    // Escape sequence - skip next char
    if (prev === '\\') continue;
    
    // Template literal start/end
    if (!inString && c === '`') {
      inTemplate = !inTemplate;
      continue;
    }
    
    // Inside template literal
    if (inTemplate) {
      // Check for ${ ... } expressions
      if (c === '$' && line[j+1] === '{') {
        inExpr = true;
        exprDepth = 0;
        j++; // skip {
        continue;
      }
      if (inExpr) {
        if (c === '{') { exprDepth++; }
        else if (c === '}') { exprDepth--; }
        if (exprDepth === 0) {
          inExpr = false;
        }
        continue;
      }
      continue;
    }
    
    // Inside regular string
    if (inString) {
      if (c === stringChar) { inString = false; }
      continue;
    }
    
    // String start
    if (c === '"' || c === "'") {
      inString = true;
      stringChar = c;
      continue;
    }
    
    // Skip // comments
    if (c === '/' && prev === '') continue;
    
    // Track braces
    if (c === '{') { depth++; }
    else if (c === '}') {
      depth--;
      if (depth < minDepth) {
        minDepth = depth;
        minDepthLine = i + 1;
      }
    }
  }
}

console.log('Final depth:', depth, '(should be 0)');
console.log('Min depth:', minDepth, 'at line', minDepthLine);
console.log('\n=== Context around problem line', minDepthLine, '===');
for (let i = Math.max(0, minDepthLine-5); i < Math.min(lines.length, minDepthLine+5); i++) {
  const marker = i === minDepthLine-1 ? '>>>' : '   ';
  console.log(`${marker} ${i+1}: ${lines[i]}`);
}