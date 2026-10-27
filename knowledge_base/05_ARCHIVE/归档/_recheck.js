const fs = require('fs');

function checkScript(path, label) {
  const content = fs.readFileSync(path, 'utf-8');
  const m = content.match(/<script>([\s\S]*?)<\/script>/);
  if (!m) { console.log(label + ': No script found'); return; }
  try {
    new Function(m[1]);
    console.log(label + ': VALID');
  } catch(e) {
    console.log(label + ': ERROR - ' + e.message);
  }
}

// Re-check all three
checkScript('D:/工作文件/小说/novel-studio/novel-studio.html', 'MAIN');
checkScript('D:/工作文件/小说/novel-studio/novel-studio-standalone.html', 'STANDALONE');
checkScript('D:/工作文件/小说/novel-studio/novel-studio.html.bak', 'BAK');

// Also check what the bisect2 found for standalone
const stand = fs.readFileSync('D:/工作文件/小说/novel-studio/novel-studio-standalone.html', 'utf-8');
const stand_m = stand.match(/<script>([\s\S]*?)<\/script>/);
const sLines = stand_m[1].split('\n');

function bisect(lines) {
  let lo = 0, hi = lines.length;
  while (hi - lo > 50) {
    const mid = Math.floor((lo + hi) / 2);
    try { new Function(lines.slice(0, mid).join('\n')); lo = mid; }
    catch(e) { hi = mid; }
  }
  for (let i = lo; i < hi; i++) {
    try { new Function(lines.slice(0, i+1).join('\n')); }
    catch(e) { return { line: i+1, error: e.message }; }
  }
  return { line: -1 };
}

const r = bisect(sLines);
console.log('\nStandalone bisect result: line', r.line, '-', r.error);