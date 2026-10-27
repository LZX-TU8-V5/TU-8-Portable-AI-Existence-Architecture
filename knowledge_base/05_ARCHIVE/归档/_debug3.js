const fs = require('fs');
const main = fs.readFileSync('D:/工作文件/小说/novel-studio/novel-studio.html', 'utf-8');
const main_m = main.match(/<script>([\s\S]*?)<\/script>/);
if (!main_m) { process.exit(1); }
const lines = main_m[1].split('\n');

// Check lines around 78
console.log('=== Lines 76-82 ===');
for (let i = 75; i < 82; i++) console.log((i+1) + ': ' + lines[i]);

// Try up to line 76
try { new Function(lines.slice(0, 76).join('\n')); console.log('76: OK'); }
catch(e) { console.log('76: ERROR -', e.message); }

// Try up to line 77
try { new Function(lines.slice(0, 77).join('\n')); console.log('77: OK'); }
catch(e) { console.log('77: ERROR -', e.message); }

// Try up to line 78
try { new Function(lines.slice(0, 78).join('\n')); console.log('78: OK'); }
catch(e) { console.log('78: ERROR -', e.message); }

// Try up to line 79
try { new Function(lines.slice(0, 79).join('\n')); console.log('79: OK'); }
catch(e) { console.log('79: ERROR -', e.message); }

// The issue might be that switchBook is called BEFORE it's defined, or has await inside
// Let's find all await statements
console.log('\n=== await statements ===');
for (let i = 0; i < lines.length; i++) {
  if (/\bawait\b/.test(lines[i])) {
    console.log('Line', i+1, ':', lines[i].trim().substring(0,80));
  }
}

// Let's also find async function declarations
console.log('\n=== async function declarations ===');
for (let i = 0; i < lines.length; i++) {
  if (/async\s+function/.test(lines[i])) {
    console.log('Line', i+1, ':', lines[i].trim().substring(0,80));
  }
}