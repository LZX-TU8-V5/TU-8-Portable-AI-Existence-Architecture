const fs = require('fs');
const main = fs.readFileSync('D:/工作文件/小说/novel-studio/novel-studio.html', 'utf-8');
const main_m = main.match(/<script>([\s\S]*?)<\/script>/);
if (!main_m) { process.exit(1); }
const lines = main_m[1].split('\n');

// Check line 3 exactly
console.log('Line 3:', JSON.stringify(lines[2]));
console.log('Line 3 length:', lines[2].length);
console.log('Line 4:', JSON.stringify(lines[3]));
console.log('Line 5:', JSON.stringify(lines[4]));
console.log('Line 6:', JSON.stringify(lines[5]));

// Try the first 10 lines as a Function
const test = lines.slice(0, 10).join('\n');
try {
  new Function(test);
  console.log('First 10 lines: OK');
} catch(e) {
  console.log('First 10 lines: ERROR -', e.message);
}

// Try first 20 lines
const test2 = lines.slice(0, 20).join('\n');
try {
  new Function(test2);
  console.log('First 20 lines: OK');
} catch(e) {
  console.log('First 20 lines: ERROR -', e.message);
}

// Try first 50 lines
const test5 = lines.slice(0, 50).join('\n');
try {
  new Function(test5);
  console.log('First 50 lines: OK');
} catch(e) {
  console.log('First 50 lines: ERROR -', e.message);
}

// Try first 70 lines
const test7 = lines.slice(0, 70).join('\n');
try {
  new Function(test7);
  console.log('First 70 lines: OK');
} catch(e) {
  console.log('First 70 lines: ERROR -', e.message);
}

// Try first 76 lines
const test76 = lines.slice(0, 76).join('\n');
try {
  new Function(test76);
  console.log('First 76 lines: OK');
} catch(e) {
  console.log('First 76 lines: ERROR -', e.message);
}

// Try first 77 lines
const test77 = lines.slice(0, 77).join('\n');
try {
  new Function(test77);
  console.log('First 77 lines: OK');
} catch(e) {
  console.log('First 77 lines: ERROR -', e.message);
}