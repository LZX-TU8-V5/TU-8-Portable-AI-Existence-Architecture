const fs = require('fs');
const html = fs.readFileSync('D:/工作文件/小说/novel-studio/novel-studio.html', 'utf-8');
const lines = html.split('\n');

// Script starts at line 573 (0-indexed = 572)
// Need to find script section (around line 573-600)
console.log('=== HTML lines 570-580 ===');
for (let i = 569; i < 580; i++) console.log(i + 1 + ': ' + (lines[i] || '').substring(0, 80));

// Find the script start
const scriptStart = lines.findIndex((l, i) => l.includes('<script>'));
console.log('\nScript starts at HTML line:', scriptStart + 1);

// Find initData area in script (around script line 203 = HTML line 573 + 203 - 1 = 775)
const initDataLine = scriptStart + 202;
console.log('initData function around HTML line:', initDataLine + 1);
console.log('\n=== Content at lines', initDataLine, '-', initDataLine+5, '===');
for (let i = initDataLine; i < initDataLine + 6; i++) console.log(i + 1 + ': ' + lines[i]);