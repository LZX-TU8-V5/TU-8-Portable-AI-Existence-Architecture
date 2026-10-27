const fs = require('fs');
const p = 'D:/工作文件/小说/novel-studio/novel-studio.html';

try {
  const html = fs.readFileSync(p, 'utf-8');
  const m = html.match(/<script>([\s\S]*?)<\/script>/);
  if (!m) { console.log('No script found'); process.exit(1); }
  const script = m[1];
  const lines = script.split('\n');
  
  console.log('=== Lines 1-10 ===');
  for (let i = 0; i < 10; i++) {
    console.log((i+1) + ': ' + (lines[i] || ''));
  }
  
  console.log('\n=== Lines 270-285 ===');
  for (let i = 269; i < 285 && i < lines.length; i++) {
    console.log((i+1) + ': ' + (lines[i] || ''));
  }
} catch(e) {
  console.log('Error:', e.message);
}