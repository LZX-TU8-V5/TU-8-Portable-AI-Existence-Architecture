const fs = require('fs');
const main = fs.readFileSync('D:/工作文件/小说/novel-studio/novel-studio.html', 'utf-8');
const stand = fs.readFileSync('D:/工作文件/小说/novel-studio/novel-studio-standalone.html', 'utf-8');
const main_m = main.match(/<script>([\s\S]*?)<\/script>/);
const stand_m = stand.match(/<script>([\s\S]*?)<\/script>/);
if (!main_m || !stand_m) { console.log('No script'); process.exit(1); }

const mainLines = main_m[1].split('\n');
const standLines = stand_m[1].split('\n');
const minLen = Math.min(mainLines.length, standLines.length);

for (let i = 0; i < minLen; i++) {
  if (mainLines[i] !== standLines[i]) {
    console.log('DIFF at script line', i+1, '(HTML ~', 572+i+1, '):');
    console.log('  MAIN:  ', mainLines[i]);
    console.log('  STAND: ', standLines[i]);
  }
}
if (mainLines.length !== standLines.length) {
  console.log('LINE COUNT DIFF: main=' + mainLines.length + ', stand=' + standLines.length);
}