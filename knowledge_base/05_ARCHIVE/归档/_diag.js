const fs = require('fs');
const path = require('path');

// Try multiple paths
const paths = [
  'D:/工作文件/小说/novel-studio/novel-studio.html',
  'D:\\工作文件\\小说\\novel-studio\\novel-studio.html',
];

let html = null;
let foundPath = null;
for (const p of paths) {
  try {
    if (fs.existsSync(p)) {
      html = fs.readFileSync(p, 'utf-8');
      foundPath = p;
      break;
    }
  } catch(e) {}
}

if (!html) {
  fs.writeFileSync('error.txt', 'File not found');
  process.exit(1);
}

const script = html.match(/<script>([\s\S]*?)<\/script>/)[1];
const lines = script.split('\n');

let output = `File: ${foundPath}\nLines: ${lines.length}\n\n=== Lines 1-10 ===\n`;
for (let i = 0; i < 10; i++) output += `${i+1}: ${lines[i]}\n`;
output += '\n=== Lines 270-285 ===\n';
for (let i = 269; i < 285 && i < lines.length; i++) output += `${i+1}: ${lines[i]}\n`;

fs.writeFileSync('result.txt', output, 'utf-8');
console.log('Done - see result.txt');