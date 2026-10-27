const fs = require('fs');
const p = 'D:/工作文件/小说/novel-studio/novel-studio.html';
let html = fs.readFileSync(p, 'utf-8');
const lines = html.split('\n');

// Find the merged line (comment + const _ls on same line)
const scriptStartIdx = lines.findIndex(l => l.includes('<script>'));
let found = false;
for (let i = scriptStartIdx; i < scriptStartIdx + 10 && i < lines.length; i++) {
  const t = lines[i].trim();
  if (t.includes('localStorage') && t.includes('const _ls') && t.startsWith('//')) {
    console.log('Found merged line at HTML line', i+1, ':', lines[i].substring(0,80));
    // Split: keep the comment part, move const _ls to next line
    const line = lines[i];
    const commentEnd = line.indexOf('// ==========');
    const secondCommentEnd = line.lastIndexOf('//');
    // Find where the non-comment code starts
    const codeStart = line.indexOf('const _ls');
    if (codeStart > 0) {
      const comment = line.substring(0, codeStart);
      const code = line.substring(codeStart);
      lines[i] = comment;
      lines.splice(i+1, 0, code);
      console.log('Fixed: split into two lines');
      found = true;
      break;
    }
  }
}

if (found) {
  fs.writeFileSync(p, lines.join('\n'), 'utf-8');
  console.log('File saved');
} else {
  console.log('Line not found, trying alternate approach');
}