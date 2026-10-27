const fs = require('fs');
const main = fs.readFileSync('D:/工作文件/小说/novel-studio/novel-studio.html', 'utf-8');
const main_m = main.match(/<script>([\s\S]*?)<\/script>/);
if (!main_m) { console.log('no script'); process.exit(1); }

// Try to find the await issue with binary search
const lines = main_m[1].split('\n');

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
  for (let i = lo; i < hi; i++) {
    const chunk = lines.slice(0, i+1).join('\n');
    try {
      new Function(chunk);
    } catch(e) {
      return { line: i+1, error: e.message };
    }
  }
  return { line: -1, error: 'ok' };
}

const r = bisectForError(lines);
console.log('Error at script line:', r.line, '-', r.error);
if (r.line > 0) {
  const ctx = 5;
  for (let i = Math.max(0, r.line-ctx-1); i < Math.min(lines.length, r.line+ctx); i++) {
    console.log((i+1) + ': ' + lines[i].substring(0,100));
  }
}

// Also check standalone for comparison
const stand = fs.readFileSync('D:/工作文件/小说/novel-studio/novel-studio-standalone.html', 'utf-8');
const stand_m = stand.match(/<script>([\s\S]*?)<\/script>/);
const sLines = stand_m[1].split('\n');
const r2 = bisectForError(sLines);
console.log('\nStandalone error at script line:', r2.line, '-', r2.error);
if (r2.line > 0) {
  const ctx = 5;
  for (let i = Math.max(0, r2.line-ctx-1); i < Math.min(sLines.length, r2.line+ctx); i++) {
    console.log((i+1) + ': ' + sLines[i].substring(0,100));
  }
}