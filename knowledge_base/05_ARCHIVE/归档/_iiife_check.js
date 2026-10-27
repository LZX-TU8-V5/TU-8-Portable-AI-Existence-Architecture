const fs = require('fs');
const main = fs.readFileSync('D:/工作文件/小说/novel-studio/novel-studio.html', 'utf-8');
const main_m = main.match(/<script>([\s\S]*?)<\/script>/);
const lines = main_m[1].split('\n');

// Check if the IIFE structure is now correct
console.log('Lines 1-7:');
for (let i = 0; i < 7; i++) console.log((i+1) + ': ' + lines[i].substring(0,80));

// Try first 5, 6, 7, 8, 10 lines
for (const n of [5, 6, 7, 8, 10, 15, 20, 30, 50, 75]) {
  try { new Function(lines.slice(0, n).join('\n')); console.log(n + ': OK'); }
  catch(e) { console.log(n + ': ' + e.message); }
}

// Check if maybe the IIFE is being treated differently because of how new Function parses
// Try with wrapping parens
const snippet = lines.slice(0, 7).join('\n');
console.log('\nSnippet to test:', JSON.stringify(snippet));

// Maybe the issue is the IIFE - ()=>{} with {} being object literal
// Let's try a variant
try {
  const wrapped = '(function(){' + snippet + '})()';
  new Function(wrapped);
  console.log('Wrapped IIFE: OK');
} catch(e) {
  console.log('Wrapped IIFE: ERROR -', e.message);
}