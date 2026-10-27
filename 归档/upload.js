const fs = require('fs');
const https = require('https');

const filepath = 'C:\\Users\\qq366410837\\.qclaw\\workspace\\knowledge\\TU-8\\TU-8-Package-v1.0.zip';
const filename = 'TU-8-Package-v1.0.zip';

const boundary = '----TU8Upload' + Date.now();

const header = Buffer.from(
  `--${boundary}\r\n` +
  `Content-Disposition: form-data; name="file"; filename="${filename}"\r\n` +
  `Content-Type: application/zip\r\n\r\n`
);

const footer = Buffer.from(`\r\n--${boundary}--\r\n`);
const fileBuffer = fs.readFileSync(filepath);
const body = Buffer.concat([header, fileBuffer, footer]);

const options = {
  hostname: 'file.io',
  path: '/',
  method: 'POST',
  headers: {
    'Content-Type': `multipart/form-data; boundary=${boundary}`,
    'Content-Length': body.length
  }
};

console.log('Uploading...');
const req = https.request(options, (res) => {
  let data = '';
  res.on('data', chunk => data += chunk);
  res.on('end', () => {
    console.log('STATUS:', res.statusCode);
    console.log('RESPONSE:', data);
  });
});

req.on('error', e => console.log('ERROR:', e.message));
req.write(body);
req.end();