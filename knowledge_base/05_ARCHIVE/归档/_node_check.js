const fs = require('fs');
const html = fs.readFileSync('D:\\工作文件\\小说\\novel-studio\\novel-studio.html', 'utf-8');
// Extract script content
const match = html.match(/<script>([\s\S]*?)<\/script>/);
if (!match) { console.log('No script found'); process.exit(1); }
const script = match[1];
console.log('Script length:', script.length);

try {
  new Function(script);
  console.log('SYNTAX OK - no errors found');
} catch(e) {
  console.log('=== SYNTAX ERROR ===');
  console.log('Message:', e.message);
  
  // Try to find the error location
  const lines = script.split('\n');
  const errStr = e.message;
  console.log('\nFull error:', e.stack || e.toString());
}
