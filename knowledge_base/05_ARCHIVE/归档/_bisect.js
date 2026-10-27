const fs = require('fs');
const stand = fs.readFileSync('D:/工作文件/小说/novel-studio/novel-studio-standalone.html', 'utf-8');
const main = fs.readFileSync('D:/工作文件/小说/novel-studio/novel-studio.html', 'utf-8');
const stand_m = stand.match(/<script>([\s\S]*?)<\/script>/);
const main_m = main.match(/<script>([\s\S]*?)<\/script>/);

const sLines = stand_m[1].split('\n');
const mLines = main_m[1].split('\n');

console.log('Standalone total lines:', sLines.length);
console.log('Main total lines:', mLines.length);

// Binary search for the syntax error location
function bisectForError(lines) {
  let lo = 0, hi = lines.length;
  while (hi - lo > 50) {
    const mid = Math.floor((lo + hi) / 2);
    const chunk = lines.slice(0, mid).join('\n');
    try {
      new Function(chunk);
      lo = mid;
    } catch(e) {
      hi = mid;
    }
  }
  // Now check from lo to hi
  for (let i = lo; i < hi; i++) {
    const chunk = lines.slice(0, i+1).join('\n');
    try {
      new Function(chunk);
    } catch(e) {
      return { line: i+1, error: e.message };
    }
  }
  return { line: -1, error: 'not found' };
}

console.log('\nSearching main for error...');
const mainResult = bisectForError(mLines);
console.log('First error in MAIN at script line:', mainResult.line, '-', mainResult.error);

// Now check what's around that line in both files
if (mainResult.line > 0) {
  const ctx = 3;
  const start = Math.max(0, mainResult.line - ctx - 1);
  console.log('\n=== Main script around error ===');
  for (let i = start; i < Math.min(mLines.length, mainResult.line + ctx); i++) {
    console.log((i+1) + ': ' + mLines[i].substring(0,100));
  }
  
  // Find corresponding area in standalone
  if (mainResult.line <= sLines.length) {
    console.log('\n=== Standalone same area ===');
    for (let i = start; i < Math.min(sLines.length, mainResult.line + ctx); i++) {
      console.log((i+1) + ': ' + sLines[i].substring(0,100));
    }
  }
}