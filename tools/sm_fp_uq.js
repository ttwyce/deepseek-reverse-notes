// 用 Node 精确复刻数美 uq 签名：md5(canon(obj))，并逐字段打印 canon 片段。
const fs = require('fs');
const crypto = require('crypto');

const plain = JSON.parse(fs.readFileSync('work/sm/fp/plain.json', 'utf8'))[0].str;
const obj = JSON.parse(plain);
const target = obj.uq;
delete obj.uq;

function canon(x) {
  if (Object.prototype.toString.call(x) === '[object Object]') {
    const out = [];
    Object.keys(x).sort().forEach(k => {
      const v = x[k];
      out.push(typeof v === 'number' ? canon('' + (10000 * v)) : canon('' + v));
    });
    return out.join('');
  }
  return x ? x.toString() : '';
}

const s = canon(obj);
const md5 = crypto.createHash('md5').update(Buffer.from(s, 'utf8')).digest('hex');
console.log('canon len', s.length);
console.log('head', JSON.stringify(s.slice(0, 160)));
console.log('computed', md5);
console.log('target  ', target);
console.log(md5 === target ? 'MATCH' : 'MISMATCH');

// 逐字段前 40 字符
Object.keys(obj).sort().forEach(k => {
  const v = obj[k];
  const c = typeof v === 'number' ? canon('' + (10000 * v)) : canon('' + v);
  console.log(k.padStart(16), '=', JSON.stringify(c.slice(0, 60)));
});
