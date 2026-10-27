const fs = require('fs');

// Try to find error using Node.js new Function
const p = 'D:/工作文件/小说/novel-studio/novel-studio.html';
const html = fs.readFileSync(p, 'utf-8');
const m = html.match(/<script>([\s\S]*?)<\/script>/);
if (!m) { console.log('No script found'); process.exit(1); }

const script = m[1];
try {
  new Function(script);
  console.log('Script is valid!');
} catch(e) {
  console.log('Error:', e.message);
  // Try to extract line number
  const match = e.message.match(/line (\d+)/);
  if (match) console.log('Error at line:', match[1]);
}