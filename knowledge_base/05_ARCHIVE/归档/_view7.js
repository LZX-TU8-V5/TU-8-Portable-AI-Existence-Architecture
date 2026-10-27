const fs = require('fs');
const html = fs.readFileSync('D:/工作文件/小说/novel-studio/novel-studio.html', 'utf-8');
const lines = html.split('\n');

// Script starts at 572. Script lines 203-218 = HTML lines 774-789
// Need to add one } somewhere in this range
console.log('=== Lines 773-792 ===');
for (let i = 772; i < 792; i++) console.log((i+1) + ': ' + (lines[i] || '').substring(0, 80));