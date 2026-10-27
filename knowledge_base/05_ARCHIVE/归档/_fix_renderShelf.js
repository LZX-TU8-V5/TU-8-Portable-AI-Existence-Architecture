const fs = require('fs');
const p = 'D:/工作文件/小说/novel-studio/novel-studio.html';
let html = fs.readFileSync(p, 'utf-8');
const lines = html.split('\n');

// Find the <script> tag
const scriptIdx = lines.findIndex(l => l.includes('<script>') && !l.includes('</script>'));
console.log('Script tag at HTML line:', scriptIdx + 1);

// Find where we need to insert "function renderShelfList() {"
// In the script, we need to find the pattern that indicates we're missing the function declaration
// Looking for: after "function closeShelf() {" ... "}" then the renderShelfList body starts

let closeShelfEnd = -1;
let renderShelfBodyStart = -1;

// Scan script content (after script tag)
for (let i = scriptIdx + 1; i < lines.length && i < scriptIdx + 100; i++) {
  const t = lines[i].trim();
  if (t === '}' && closeShelfEnd === -1) {
    // Check if this is the end of closeShelf function
    // Look back a few lines to see if we had closeShelf content
    closeShelfEnd = i;
  }
  if (t.startsWith('const shelf = getShelf()') && renderShelfBodyStart === -1) {
    renderShelfBodyStart = i;
    break;
  }
}

console.log('closeShelf end at HTML line:', closeShelfEnd + 1);
console.log('renderShelf body starts at HTML line:', renderShelfBodyStart + 1);

if (closeShelfEnd > 0 && renderShelfBodyStart > 0 && renderShelfBodyStart > closeShelfEnd) {
  // Insert "function renderShelfList() {" before renderShelfBodyStart
  lines.splice(renderShelfBodyStart, 0, 'function renderShelfList() {');
  console.log('Inserted "function renderShelfList() {" at HTML line', renderShelfBodyStart + 1);
  
  fs.writeFileSync(p, lines.join('\n'), 'utf-8');
  console.log('File saved');
} else {
  console.log('Could not find insertion point');
}
