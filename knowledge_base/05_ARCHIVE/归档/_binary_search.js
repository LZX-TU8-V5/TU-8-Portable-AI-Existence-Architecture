const fs = require('fs');
const html = fs.readFileSync('D:\\工作文件\\小说\\novel-studio\\novel-studio.html', 'utf-8');
const match = html.match(/<script>([\s\S]*?)<\/script>/);
const script = match[1];
const lines = script.split('\n');

function checkRange(start, end) {
  const subset = lines.slice(start, end).join('\n');
  try {
    new Function(subset);
    return true;
  } catch(e) {
    return false;
  }
}

// Binary search for the error
let lo = 0, hi = lines.length;
while (lo < hi) {
  const mid = Math.floor((lo + hi) / 2);
  console.log(`Checking lines ${lo+1}-${mid}...`);
  if (!checkRange(lo, mid)) {
    hi = mid;
  } else {
    lo = mid + 1;
  }
}
console.log(`\nError is at or near line ${lo+1}`);
console.log(`Content: ${lines[lo].trim().substring(0, 120)}`);

// Show context
console.log('\n=== Context (5 lines before and after) ===');
for (let i = Math.max(0, lo-5); i <= Math.min(lines.length-1, lo+5); i++) {
  const marker = i === lo ? '>>>' : '   ';
  console.log(`${marker} ${i+1}: ${lines[i].trim().substring(0, 150)}`);
}
