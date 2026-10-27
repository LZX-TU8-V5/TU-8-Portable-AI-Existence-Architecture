const fs = require('fs');
const html = fs.readFileSync('D:\\工作文件\\小说\\novel-studio\\novel-studio.html', 'utf-8');
const match = html.match(/<script>([\s\S]*?)<\/script>/);
const script = match[1];
const lines = script.split('\n');

// Only track curly braces, ignore parens
// But handle IIFE pattern: (() => { ... })();
// Opening: ( ( + ( ( + { = +3 opens
// Closing: } + ) + ) = -3 closes
// Net: 0

let braceDepth = 0;
let parenDepth = 0;
let inString = false;
let stringChar = '';
let inComment = false;
let inBlockComment = false;
let inTemplate = false;

for (let i = 0; i < 10 && i < lines.length; i++) {
  const line = lines[i];
  console.log(`\nLine ${i+1} BEFORE: brace=${braceDepth}, paren=${parenDepth}`);
  console.log(`  ${line}`);
  
  let j = 0;
  while (j < line.length) {
    const c = line[j];
    const prev = j > 0 ? line[j-1] : '';
    
    if (c === '\n' || c === '\r') { inComment = false; j++; continue; }
    if (prev === '\\') { j++; continue; }
    
    if (inComment) { j++; continue; }
    if (inBlockComment) {
      if (c === '*' && line[j+1] === '/') inBlockComment = false;
      j++; continue;
    }
    if (c === '/' && line[j+1] === '/') { inComment = true; j++; continue; }
    if (c === '/' && line[j+1] === '*') { inBlockComment = true; j+=2; continue; }
    
    // Template literals
    if (!inString && c === '`') { inTemplate = !inTemplate; j++; continue; }
    if (inTemplate) { j++; continue; }
    
    // Strings
    if (!inString && (c === '"' || c === "'" || c === '`')) {
      inString = true; stringChar = c; j++; continue;
    }
    if (inString) {
      if (c === stringChar) inString = false;
      j++; continue;
    }
    
    // Track only braces
    if (c === '{') {
      braceDepth++;
      console.log(`    @${j}: OPEN { -> brace=${braceDepth}`);
    } else if (c === '}') {
      braceDepth--;
      console.log(`    @${j}: CLOSE } -> brace=${braceDepth}`);
      if (braceDepth < 0) {
        console.log(`    *** NEGATIVE BRACE DEPTH! ***`);
      }
    }
    j++;
  }
  
  console.log(`Line ${i+1} AFTER: brace=${braceDepth}, paren=${parenDepth}`);
}

console.log('\n=== Summary of first 10 lines ===');
console.log('If braceDepth goes negative at line 5, it means something opened brace earlier without closing');
console.log('Or the file itself has an extra } somewhere before line 5');