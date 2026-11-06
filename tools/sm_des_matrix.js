const mod = require('../work/sm/mod_0x5b.js');
const m = mod.default || mod;
const toHex = (s) => Buffer.from(s, 'binary').toString('hex');
const target = '21b4d8cc4254b4a0'; // Python: DES-ECB + PKCS7('hello'), key='e1024477'
console.log('target', target);
for (let mode = 0; mode <= 12; mode++) {
  for (let pad = 0; pad <= 4; pad++) {
    let r;
    try {
      r = m.DES('e1024477', 'hello', mode, pad);
    } catch (e) {
      continue;
    }
    if (typeof r !== 'string') continue;
    const h = toHex(r);
    const mark = h === target ? '  <<<< MATCH' : '';
    console.log(`mode=${mode} pad=${pad} len=${r.length} hex=${h}${mark}`);
  }
}
