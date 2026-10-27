const fs = require('fs');
const main = fs.readFileSync('D:/工作文件/小说/novel-studio/novel-studio.html', 'utf-8');
const main_m = main.match(/<script>([\s\S]*?)<\/script>/);
const lines = main_m[1].split('\n');

// Find where renderShelf function starts and ends
for (let i = 0; i < lines.length; i++) {
  const t = lines[i].trim();
  if (t.startsWith('function renderShelf') || t.startsWith('function openShelf') || t.includes('shelf-item')) {
    console.log('Line', i+1, ':', t.substring(0,80));
  }
}

// Check standalone for the same section
const stand = fs.readFileSync('D:/工作文件/小说/novel-studio/novel-studio-standalone.html', 'utf-8');
const stand_m = stand.match(/<script>([\s\S]*?)<\/script>/);
const sLines = stand_m[1].split('\n');

console.log('\n=== STANDALONE lines 65-82 ===');
for (let i = 64; i < 82; i++) console.log((i+1) + ': ' + sLines[i].substring(0,80));

console.log('\n=== MAIN lines 65-82 ===');
for (let i = 64; i < 82; i++) console.log((i+1) + ': ' + lines[i].substring(0,80));