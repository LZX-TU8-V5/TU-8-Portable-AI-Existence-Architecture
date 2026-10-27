const fs = require('fs');
const stand = fs.readFileSync('D:/工作文件/小说/novel-studio/novel-studio-standalone.html', 'utf-8');
const main = fs.readFileSync('D:/工作文件/小说/novel-studio/novel-studio.html', 'utf-8');
const stand_m = stand.match(/<script>([\s\S]*?)<\/script>/);
const main_m = main.match(/<script>([\s\S]*?)<\/script>/);

const sLines = stand_m[1].split('\n');
const mLines = main_m[1].split('\n');

// Show lines 1-6 of both
console.log('=== STANDALONE lines 1-6 ===');
for (let i = 0; i < 6; i++) console.log((i+1) + ': [' + sLines[i] + ']');
console.log('\n=== MAIN lines 1-6 ===');
for (let i = 0; i < 6; i++) console.log((i+1) + ': [' + mLines[i] + ']');

// Check line 4 in detail
console.log('\n=== LINE 4 ANALYSIS ===');
console.log('STAND:', JSON.stringify(sLines[3]));
console.log('MAIN: ', JSON.stringify(mLines[3]));

// Count chars
console.log('\nSTAND line 4 length:', sLines[3].length);
console.log('MAIN line 4 length:', mLines[3].length);

// Check if standalone line 4 is multi-line in source
console.log('\nSTAND has \\n in line 4?', sLines[3].includes('\n'));
console.log('MAIN has \\n in line 4?', mLines[3].includes('\n'));