const fs = require('fs');
const main = fs.readFileSync('D:/工作文件/小说/novel-studio/novel-studio.html', 'utf-8');
const main_m = main.match(/<script>([\s\S]*?)<\/script>/);
const lines = main_m[1].split('\n');

// Check lines 76-82
console.log('Lines 76-82:');
for (let i = 75; i < 82; i++) console.log((i+1) + ': ' + lines[i]);

// Try chunks
[76, 77, 78, 79].forEach(n => {
  try { new Function(lines.slice(0, n).join('\n')); console.log(n + ': OK'); }
  catch(e) { console.log(n + ': ERROR -', e.message); }
});

// Find await in script
console.log('\nawait statements:');
for (let i = 0; i < lines.length; i++) {
  if (/\bawait\b/.test(lines[i])) console.log('Line', i+1, ':', lines[i].trim().substring(0,80));
}

// Find async function
console.log('\nasync function:');
for (let i = 0; i < lines.length; i++) {
  if (/async\s+function/.test(lines[i])) console.log('Line', i+1, ':', lines[i].trim().substring(0,80));
}