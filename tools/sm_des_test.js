const mod = require('../work/sm/mod_0x5b.js');
const m = mod.default || mod;
console.log('keys', Object.keys(m));
try {
  const r = m.DES('e1024477', 'hello', 9, 0);
  console.log('DES typeof', typeof r, 'len', r && r.length);
  console.log('DES raw', JSON.stringify(r).slice(0, 200));
  console.log('DES b64', m.base64Encode(r));
} catch (e) {
  console.log('DES err', e && e.message);
}
console.log('b64 hello', m.base64Encode('hello'));
