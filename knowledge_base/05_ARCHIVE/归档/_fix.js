const fs = require('fs');
const p = 'D:/工作文件/小说/novel-studio/novel-studio.html';
let html = fs.readFileSync(p, 'utf-8');
const lines = html.split('\n');

// Find where to add the missing }
console.log('Lines around 215-220:');
for (let i = 214; i < 220; i++) console.log(i + 1 + ': ' + lines[i]);

// Add one extra } after line 217
lines.splice(217, 0, '    }');
console.log('Added extra } at line 218');

fs.writeFileSync(p, lines.join('\n'), 'utf-8');