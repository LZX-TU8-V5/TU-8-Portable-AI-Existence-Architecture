const fs = require('fs');
const html = fs.readFileSync('D:\\工作文件\\小说\\novel-studio\\novel-studio.html', 'utf-8');
const match = html.match(/<script>([\s\S]*?)<\/script>/);
const script = match[1];

// Try different parsers
try {
  // Method 1: Try to parse with Function constructor
  new Function(script);
  console.log('Function constructor: OK');
} catch(e) {
  console.log('Function constructor ERROR:', e.message);
}

// Method 2: Use node's syntax checker via child_process
const { execSync } = require('child_process');
const path = require('path');

// Write to temp file
const tmpPath = path.join(process.env.TEMP || '/tmp', 'novel_test.js');
fs.writeFileSync(tmpPath, script, 'utf-8');

try {
  const result = execSync(`node --check "${tmpPath}" 2>&1`, {encoding: 'utf-8'});
  console.log('node --check: OK');
} catch(e) {
  const output = e.stdout + e.stderr;
  console.log('node --check output:', output);
}

// Try to extract line number from error
const nodeCheckOutput = execSync(`node --check "${tmpPath}" 2>&1`, {encoding: 'utf-8', encoding: 'utf8'});
} catch(e) {
  // This is actually executed if there's an error
  const output = e.stdout ? e.stdout.toString() : '';
  console.log('ERROR OUTPUT:', output);
  
  // Try to parse line number from the output
  const match = output.match(/line (\d+)/);
  if (match) {
    const lineNum = parseInt(match[1]);
    console.log(`Error at line: ${lineNum}`);
    const lines = script.split('\n');
    for (let i = Math.max(0, lineNum - 3); i < Math.min(lines.length, lineNum + 3); i++) {
      const marker = i === lineNum - 1 ? '>>>' : '   ';
      console.log(`${marker} ${i+1}: ${lines[i].substring(0, 150)}`);
    }
  }
}