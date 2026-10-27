const fs = require('fs');
const html = fs.readFileSync('D:\\工作文件\\小说\\novel-studio\\novel-studio.html', 'utf-8');
const match = html.match(/<script>([\s\S]*?)<\/script>/);
const script = match[1];
const lines = script.split('\n');

console.log('Total script lines:', lines.length);

// Strategy: progressively include lines from the start until we hit an error
let lastGood = 0;
for (let i = 1; i <= lines.length; i++) {
  const subset = lines.slice(0, i).join('\n');
  try {
    new Function(subset);
    lastGood = i;
  } catch(e) {
    // Error found! Show where
    console.log(`\n=== ERROR first appears when including up to line ${i} ===`);
    console.log(`Last good line: ${lastGood}`);
    console.log(`\nLine ${i} (problematic):`);
    console.log(lines[i-1]);
    console.log(`\nLine ${lastGood} (last OK):`);
    if (lastGood > 0) console.log(lines[lastGood-1]);
    
    // Show context
    console.log(`\n=== Context: lines ${Math.max(1,i-3)} to ${Math.min(lines.length, i+3)} ===`);
    for (let j = Math.max(0, i-4); j < Math.min(lines.length, i+3); j++) {
      const marker = j === i-1 ? '>>>' : (j === lastGood-1 ? '<<<' : '   ');
      console.log(`${marker} ${j+1}: ${lines[j].trim().substring(0, 150)}`);
    }
    break;
  }
}

if (lastGood === lines.length) {
  console.log('No error found in incremental check (error might need full context)');
}
