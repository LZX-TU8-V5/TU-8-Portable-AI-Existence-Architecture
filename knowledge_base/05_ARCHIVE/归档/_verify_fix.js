const fs = require('fs');
const main = fs.readFileSync('D:/工作文件/小说/novel-studio/novel-studio.html', 'utf-8');
const main_m = main.match(/<script>([\s\S]*?)<\/script>/);

if (!main_m) {
  console.log('No script found');
  process.exit(1);
}

const script = main_m[1];
const lines = script.split('\n');

// Check for the function we added
let foundRenderShelf = false;
for (let i = 0; i < lines.length; i++) {
  if (lines[i].includes('function renderShelfList()')) {
    console.log('Found renderShelfList at script line', i+1);
    foundRenderShelf = true;
    // Show context
    for (let j = Math.max(0, i-2); j < Math.min(lines.length, i+5); j++) {
      console.log('  ', j+1, ':', lines[j].substring(0,70));
    }
    break;
  }
}

if (!foundRenderShelf) {
  console.log('ERROR: renderShelfList not found!');
}

// Check brace balance
let braceCount = 0;
for (const line of lines) {
  for (const c of line) {
    if (c === '{') braceCount++;
    if (c === '}') braceCount--;
  }
}
console.log('\nBrace balance:', braceCount, '(should be 0)');

// Try syntax check with a wrapper that allows top-level await
try {
  // Wrap in async IIFE to allow await
  const wrapped = '(async function(){' + script + '})()';
  new Function(wrapped);
  console.log('Syntax check (wrapped): VALID');
} catch(e) {
  console.log('Syntax check (wrapped): ERROR -', e.message);
}

// Also try the raw check
try {
  new Function(script);
  console.log('Syntax check (raw): VALID');
} catch(e) {
  console.log('Syntax check (raw):', e.message);
}
