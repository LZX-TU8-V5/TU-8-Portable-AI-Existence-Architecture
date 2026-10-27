const fs = require('fs');

const standPath = 'D:/工作文件/小说/novel-studio/novel-studio-standalone.html';
const mainPath = 'D:/工作文件/小说/novel-studio/novel-studio.html';

// Read standalone
const stand = fs.readFileSync(standPath, 'utf-8');

// Backup current main
const main = fs.readFileSync(mainPath, 'utf-8');
fs.writeFileSync(mainPath + '.bak3', main);
console.log('Backed up current main to .bak3');

// Copy standalone to main
fs.writeFileSync(mainPath, stand, 'utf-8');
console.log('Restored main from standalone');

// Verify
const newMain = fs.readFileSync(mainPath, 'utf-8');
const m = newMain.match(/<script>([\s\S]*?)<\/script>/);
if (m) {
  try {
    new Function(m[1]);
    console.log('Syntax check: VALID ✓');
  } catch(e) {
    console.log('Syntax check: ERROR -', e.message);
  }
}

// Check title
const titleMatch = newMain.match(/<title>([\s\S]*?)<\/title>/);
console.log('Title:', titleMatch ? titleMatch[1] : 'not found');
