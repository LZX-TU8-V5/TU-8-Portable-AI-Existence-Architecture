const fs = require('fs');
const p = 'D:/工作文件/小说/novel-studio/novel-studio.html';
let html = fs.readFileSync(p, 'utf-8');
const lines = html.split('\n');

// Insert extra } at line 790 (after the if block closes)
lines.splice(789, 0, '  }');
console.log('Added extra } at HTML line 790');

fs.writeFileSync(p, lines.join('\n'), 'utf-8');
console.log('File updated');