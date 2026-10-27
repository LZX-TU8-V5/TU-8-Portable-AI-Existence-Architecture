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

checkScript('D:/工作文件/小说/novel-studio/novel-studio.html', 'MAIN');
checkScript('D:/工作文件/小说/novel-studio/novel-studio-standalone.html', 'STANDALONE');
checkScript('D:/工作文件/小说/novel-studio/novel-studio.html.bak', 'BAK');