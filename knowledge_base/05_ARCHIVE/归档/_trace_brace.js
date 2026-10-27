const fs = require('fs');
const html = fs.readFileSync('D:\\工作文件\\小说\\novel-studio\\novel-studio.html', 'utf-8');
const match = html.match(/<script>([\s\S]*?)<\/script>/);
const script = match[1];
const lines = script.split('\n');

// Track braces more carefully - skip content inside template literals
let depth = 0;
let inTemplate = false;
let templateDepth = 0;
let minDepth = 0;
let minDepthLine = 0;
let inString = false;
let stringChar = '';

for (let i = 0; i < lines.length; i++) {
  const line = lines[i];
  
  // Check each character
  for (let j = 0; j < line.length; j++) {
    const c = line[j];
    const prevC = j > 0 ? line[j-1] : '';
    
    // Skip escape sequences
    if (prevC === '\\') continue;
    
    // Handle template literals
    if (!inString && c === '`') {
      inTemplate = !inTemplate;
      continue;
    }
    if (inTemplate) continue;
    
    // Handle strings
    if (!inString && (c === '"' || c === "'")) {
      inString = true;
      stringChar = c;
      continue;
    }
    if (inString && c === stringChar) {
      inString = false;
      continue;
    }
    if (inString) continue;
    
    // Track braces
    if (c === '{') {
      depth++;
    } else if (c === '}') {
      depth--;
      if (depth < minDepth) {
        minDepth = depth;
        minDepthLine = i + 1;
      }
    }
  }
}

console.log('Final depth:', depth);
console.log('Min depth:', minDepth, 'at line', minDepthLine);
console.log('Lines around min depth:');
for (let i = Math.max(0, minDepthLine-3); i < Math.min(lines.length, minDepthLine+3); i++) {
  const marker = i === minDepthLine-1 ? '>>>' : '   ';
  console.log(`${marker} ${i+1}: ${lines[i]}`);
}