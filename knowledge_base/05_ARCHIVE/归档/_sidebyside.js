const fs = require('fs');
const stand = fs.readFileSync('D:/工作文件/小说/novel-studio/novel-studio-standalone.html', 'utf-8');
const stand_m = stand.match(/<script>([\s\S]*?)<\/script>/);
const sLines = stand_m[1].split('\n');

console.log('=== STANDALONE lines 50-82 ===');
for (let i = 49; i < 82; i++) console.log((i+1) + ': ' + sLines[i].substring(0,80));

console.log('\n=== MAIN lines 50-82 ===');
const main = fs.readFileSync('D:/工作文件/小说/novel-studio/novel-studio.html', 'utf-8');
const main_m = main.match(/<script>([\s\S]*?)<\/script>/);
const mLines = main_m[1].split('\n');
for (let i = 49; i < 82; i++) console.log((i+1) + ': ' + mLines[i].substring(0,80));