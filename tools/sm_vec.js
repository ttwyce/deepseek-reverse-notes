const fs = require('fs');
const m = require('../work/sm/mod_0x5b.js').default;
const salts = ['e1024477', '803d9d10', 'e6c8d743', 'd809f47c', '210a5a6d', '24fd4665',
  'f2858cfa', 'df29aa2d', '9728245c', '3ae79dfa', 'fa1b1f22', '10c0600a', '53cda785'];
const vals = ['', 'a', 'hello', 'abcdefgh', 'abcdefghi', '1234567890', '1', '11',
  'P9usCUBauxft8eAmUXaZ', 'default', 'zh-cn', '[{"x":100,"y":50}]', 'web', '1.0.4', '1.1.3'];
const out = [];
for (const s of salts) {
  for (const v of vals) {
    let b64 = null, err = null;
    try {
      b64 = m.base64Encode(m.DES(s, v, 9, 0));
    } catch (e) { err = String(e && e.message); }
    out.push({ salt: s, val: v, b64, err });
  }
}
fs.writeFileSync('work/sm/vectors.json', JSON.stringify(out, null, 0));
console.log('cases', out.length);
console.log(JSON.stringify(out.slice(0, 6), null, 1));
