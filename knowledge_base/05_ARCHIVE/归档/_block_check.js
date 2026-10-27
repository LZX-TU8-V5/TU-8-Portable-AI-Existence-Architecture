const fs = require('fs');
const html = fs.readFileSync('D:\\工作文件\\小说\\novel-studio\\novel-studio.html', 'utf-8');
const match = html.match(/<script>([\s\S]*?)<\/script>/);
const script = match[1];
const lines = script.split('\n');

// Try parsing with acorn-like error recovery
// Strategy: wrap in try-catch and test each "section" separated by blank lines
// Find function boundaries and test each function independently

// First, let's identify top-level functions/statements
let currentFunc = [];
let funcStart = 0;
let funcNum = 0;

for (let i = 0; i < lines.length; i++) {
  const line = lines[i];
  currentFunc.push(line);
  
  // Check if this line might end a top-level construct
  const stripped = line.trim();
  // A top-level statement ends with } followed by empty line or next statement
  if ((stripped === '}' || stripped === '};') && (i === lines.length - 1 || lines[i+1].trim() === '' || /^[a-z]/.test(lines[i+1].trim()))) {
    funcNum++;
    const code = currentFunc.join('\n');
    try {
      new Function(code);
      // OK
    } catch(e) {
      console.log(`\n=== ERROR in block #${funcNum} (lines ${funcStart+1}-${i+1}) ===`);
      console.log(`Error: ${e.message}`);
      console.log(`First line: ${lines[funcStart].trim().substring(0, 100)}`);
      console.log(`Last line: ${stripped.substring(0, 100)}`);
      
      // Show the full block
      console.log('\nFull block:');
      currentFunc.forEach((l, idx) => {
        console.log(`  ${funcStart + idx + 1}: ${l.substring(0, 150)}`);
      });
    }
    currentFunc = [];
    funcStart = i + 1;
  }
}

// Also check remaining
if (currentFunc.length > 0) {
  funcNum++;
  const code = currentFunc.join('\n');
  try {
    new Function(code);
  } catch(e) {
    console.log(`\n=== ERROR in final block #${funcNum} (lines ${funcStart+1}-${lines.length}) ===`);
    console.log(`Error: ${e.message}`);
  }
}
