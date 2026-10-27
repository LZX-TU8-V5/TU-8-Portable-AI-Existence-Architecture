const fs = require('fs');

// Restore: copy standalone to main (standalone is syntactically valid)
// But first back up current main
const main = fs.readFileSync('D:/工作文件/小说/novel-studio/novel-studio.html', 'utf-8');
fs.writeFileSync('D:/工作文件/小说/novel-studio/novel-studio.html.bak2', main);
console.log('Backed up current main to .bak2');

// Now copy standalone to main
const stand = fs.readFileSync('D:/工作文件/小说/novel-studio/novel-studio-standalone.html', 'utf-8');

// But first update the standalone's title if needed
// Check current title
const titleMatch = stand.match(/<title>([\s\S]*?)<\/title>/);
console.log('Standalone title:', titleMatch ? titleMatch[1] : 'none');

// Check if standalone has the "创作工作台" title
// It should already be "《钢印》创作工作台" based on our earlier check
// If not, update it

// Write standalone content to main
fs.writeFileSync('D:/工作文件/小说/novel-studio/novel-studio.html', stand, 'utf-8');
console.log('Restored novel-studio.html from standalone');

// Verify
const newMain = fs.readFileSync('D:/工作文件/小说/novel-studio/novel-studio.html', 'utf-8');
const new_m = newMain.match(/<script>([\s\S]*?)<\/script>/);
if (new_m) {
  try {
    new Function(new_m[1]);
    console.log('RESTORED file syntax: VALID ✓');
  } catch(e) {
    console.log('RESTORED file syntax: ERROR -', e.message);
  }
}