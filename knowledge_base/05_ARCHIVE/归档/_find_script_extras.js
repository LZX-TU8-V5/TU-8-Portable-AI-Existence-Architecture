const fs = require('fs');
const p = 'D:/工作文件/小说/novel-studio/novel-studio.html';
let html = fs.readFileSync(p, 'utf-8');
const lines = html.split('\n');

// Script starts at HTML line 572+ (script tag)
// Find standalone } in script section (between lines 572 and end of script)
const scriptStart = lines.findIndex(l => l.includes('<script>'));
console.log('Script start:', scriptStart + 1);

// Find script end
const scriptEnd = lines.findIndex((l, i) => i > scriptStart && l.includes('</script>'));
console.log('Script end:', scriptEnd + 1);

// Find standalone } in script (not part of HTML)
const scriptLines = lines.slice(scriptStart + 1, scriptEnd);
standaloneInScript = [];
for (let i = 0; i < scriptLines.length; i++) {
  const line = scriptLines[i].trim();
  if (line === '}') standaloneInScript.push(scriptStart + i + 2);
}
console.log('\nStandalone } in script:', standaloneInScript);