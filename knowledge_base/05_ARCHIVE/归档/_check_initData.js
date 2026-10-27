const fs = require('fs');
const main = fs.readFileSync('D:/工作文件/小说/novel-studio/novel-studio.html', 'utf-8');
const main_m = main.match(/<script>([\s\S]*?)<\/script>/);
const lines = main_m[1].split('\n');

// Find initData function boundaries
let initDataStart = -1;
let initDataEnd = -1;

for (let i = 0; i < lines.length; i++) {
  if (/async function initData\(\)/.test(lines[i])) {
    initDataStart = i;
    console.log('initData starts at line', i+1);
  }
  if (initDataStart > 0 && initDataEnd < 0 && lines[i].trim() === '}') {
    // Check if this is the closing of initData by counting braces
    let braceCount = 0;
    for (let j = initDataStart; j <= i; j++) {
      for (const c of lines[j]) {
        if (c === '{') braceCount++;
        if (c === '}') braceCount--;
      }
    }
    if (braceCount === 0) {
      initDataEnd = i;
      console.log('initData ends at line', i+1);
      break;
    }
  }
}

// Show initData structure
if (initDataStart >= 0 && initDataEnd >= 0) {
  console.log('\n=== initData structure ===');
  let depth = 0;
  for (let i = initDataStart; i <= initDataEnd; i++) {
    const line = lines[i];
    const open = (line.match(/{/g) || []).length;
    const close = (line.match(/}/g) || []).length;
    depth += open - close;
    if (open > 0 || close > 0) {
      console.log('Line', i+1, 'depth', depth, ':', line.trim().substring(0, 50));
    }
  }
}
