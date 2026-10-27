const fs = require('fs');
const p = 'D:/工作文件/小说/novel-studio/novel-studio.html';
let html = fs.readFileSync(p, 'utf-8');
const lines = html.split('\n');

// Find consecutive duplicate "function renderShelfList() {" lines
let removed = false;
for (let i = 0; i < lines.length - 1; i++) {
  if (lines[i].includes('function renderShelfList()') && lines[i+1].includes('function renderShelfList()')) {
    console.log('Found duplicate at lines', i+1, 'and', i+2);
    console.log('Line', i+1, ':', lines[i].trim());
    console.log('Line', i+2, ':', lines[i+1].trim());
    // Remove the first one (the one I added)
    lines.splice(i, 1);
    removed = true;
    console.log('Removed duplicate at line', i+1);
    break;
  }
}

if (removed) {
  fs.writeFileSync(p, lines.join('\n'), 'utf-8');
  console.log('File saved');
} else {
  console.log('No duplicate found');
}
