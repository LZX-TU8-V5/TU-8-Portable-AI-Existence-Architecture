const fs = require('fs');
const path = 'D:\\工作文件\\小说\\novel-studio\\novel-studio.html';
const html = fs.readFileSync(path, 'utf-8');
const match = html.match(/<script>([\s\S]*?)<\/script>/);
if (!match) { console.log('No script found'); return; }
const script = match[1];
const lines = script.split('\n');

console.log('Total lines in script:', lines.length);

// Check the last few lines carefully
console.log('\n=== Last 10 lines (with char codes) ===');
for (let i = Math.max(0, lines.length - 10); i < lines.length; i++) {
  const line = lines[i];
  console.log(`\nLine ${i+1}:`);
  console.log(`  Raw: ${JSON.stringify(line)}`);
  console.log(`  Length: ${line.length}`);
  console.log(`  Display: ${line.substring(0, 200)}`);
  // Check for hidden chars
  for (let j = 0; j < line.length; j++) {
    const code = line.charCodeAt(j);
    if (code > 127 && code < 32) {
      console.log(`  WARNING: Hidden char at pos ${j}: ${code}`);
    }
  }
}

// Check for BOM
const firstChars = script.substring(0, 10);
console.log('\n=== First 10 chars ===');
for (let i = 0; i < Math.min(10, firstChars.length); i++) {
  console.log(`  '${firstChars[i]}' = ${firstChars.charCodeAt(i)}`);
}

// Check if script ends with </script> properly
const afterScript = html.match(/<\/script>([\s\S]*)/);
if (afterScript) {
  console.log('\n=== Content after </script> ===');
  console.log(afterScript[1].substring(0, 500));
}

// Check for extra content after </script>
console.log('\n=== Looking for script injection area ===');
const scriptMatch = html.match(/id="embedded-data"[^>]*>([\s\S]*?)<\/script>/);
if (scriptMatch) {
  console.log('Found embedded-data script');
  console.log('Content length:', scriptMatch[1].length);
  console.log('Content:', scriptMatch[1].substring(0, 500));
} else {
  console.log('No embedded-data script found');
}

// Check if there's more than one script block
const allScripts = html.match(/<script[^>]*>([\s\S]*?)<\/script>/g);
console.log('\n=== All script blocks ===');
console.log('Count:', allScripts ? allScripts.length : 0);
if (allScripts) {
  allScripts.forEach((s, i) => {
    const content = s.match(/<script[^>]*>([\s\S]*)/)[1].replace(/<\/script>/, '');
    console.log(`Script ${i+1}: ${content.length} chars (first 100: ${content.substring(0, 100)})`);
  });
}