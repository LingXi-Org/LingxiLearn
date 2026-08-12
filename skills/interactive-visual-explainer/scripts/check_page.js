#!/usr/bin/env node
/* LingXi 单文件讲解页体检器
 *   node scripts/check_page.js <page.html> [--allow-cdn]
 * 静态检查 20 项硬约束。FAIL 必须修完才能交付；WARN 需要在交付说明里解释为何保留。
 * 只做静态检查：运行时才生成的 DOM 不在检查范围内，所以它不替代「渲染后肉眼看一遍」。
 */
'use strict';
const fs = require('fs');

const args = process.argv.slice(2);
const file = args.find((a) => !a.startsWith('--'));
const allowCdn = args.includes('--allow-cdn');
if (!file) {
  console.error('用法: node scripts/check_page.js <page.html> [--allow-cdn]');
  process.exit(2);
}
const src = fs.readFileSync(file, 'utf8');
const bytes = Buffer.byteLength(src);

const CDN = ['cdnjs.cloudflare.com', 'cdn.jsdelivr.net', 'unpkg.com', 'esm.sh'];
const out = [];
const add = (level, name, msg) => out.push({ level, name, msg: msg || '' });
const trunc = (a, n = 4) => {
  const u = [...new Set(a)];
  return u.slice(0, n).join(', ') + (u.length > n ? ` …(+${u.length - n})` : '');
};

/* 剥掉注释与 :root/@media 令牌块，避免误报 */
const tokenBlocks = [];
let deTokened = src.replace(/:root\s*\{[\s\S]*?\}/g, (m) => { tokenBlocks.push(m); return ''; });
deTokened = deTokened.replace(/@media\s*\(prefers-color-scheme[\s\S]*?\}\s*\}/g, (m) => { tokenBlocks.push(m); return ''; });
deTokened = deTokened.replace(/@media\s+print\s*\{[\s\S]*?\}\s*\}/g, (m) => { tokenBlocks.push(m); return ''; });
const scripts = [...src.matchAll(/<script\b[^>]*>([\s\S]*?)<\/script>/gi)].map((m) => m[1]).join('\n');

/* 1. 自包含 */
const ext = [...src.matchAll(/(?:src|href)\s*=\s*["'](https?:)?\/\/([^/"']+)/gi)].map((m) => m[2])
  .concat([...src.matchAll(/@import\s+(?:url\()?["']?(?:https?:)?\/\/([^/"')]+)/gi)].map((m) => m[1]))
  .concat([...src.matchAll(/url\(\s*["']?(?:https?:)?\/\/([^/"')]+)/gi)].map((m) => m[1]));
if (ext.length === 0) add('PASS', '自包含', '零外部请求，可离线打开');
else if (!allowCdn) add('FAIL', '自包含', `发现 ${ext.length} 处外部引用: ${trunc(ext)} — 默认要求零依赖，确需外链请加 --allow-cdn 并写明降级方案`);
else {
  const bad = ext.filter((h) => !CDN.includes(h.toLowerCase()));
  bad.length ? add('FAIL', '自包含', `域名不在白名单: ${trunc(bad)}`)
             : add('WARN', '自包含', `依赖 CDN: ${trunc(ext)} — 断网即降级，必须提供无脚本兜底`);
}

/* 2. 文档骨架 */
const skel = [
  [/<!doctype\s+html/i, '<!doctype html>'],
  [/<html[^>]*\slang\s*=/i, '<html lang>'],
  [/<meta[^>]*charset/i, '<meta charset>'],
  [/<meta[^>]*name\s*=\s*["']viewport/i, '<meta viewport>'],
  [/<title>[^<]+<\/title>/i, '<title>'],
].filter(([re]) => !re.test(src)).map(([, n]) => n);
skel.length ? add('FAIL', '文档骨架', `缺少 ${skel.join('、')}`) : add('PASS', '文档骨架');

/* 3. 最小字号 */
const tiny = [...src.matchAll(/font-size\s*:\s*(\d+(?:\.\d+)?)px/gi)].map((m) => +m[1]).filter((v) => v < 11);
tiny.length ? add('FAIL', '最小字号', `${tiny.length} 处小于 11px: ${trunc(tiny.map(String))}`) : add('PASS', '最小字号');

/* 4. 字重 */
const heavy = [...src.matchAll(/font-weight\s*:\s*(\d{3}|bold|bolder)/gi)].map((m) => m[1])
  .filter((v) => v === 'bold' || v === 'bolder' || +v >= 600);
heavy.length ? add('WARN', '字重', `出现 ${trunc(heavy)} — 只用 400/500，重字重在正文里显脏`) : add('PASS', '字重');

/* 5. position: fixed */
/fixed/.test(src) && /position\s*:\s*fixed/i.test(src)
  ? add('WARN', '定位', 'position: fixed 会脱离文档流，长页面滚动时容易遮挡图形')
  : add('PASS', '定位');

/* 6. emoji */
const emo = src.match(/[\u{1F300}-\u{1FAFF}\u{2600}-\u{27BF}\u{FE0F}]/gu) || [];
emo.length ? add('WARN', '图标', `发现 ${emo.length} 个 emoji: ${trunc(emo, 6)} — 改用 SVG 图形或色块`) : add('PASS', '图标');

/* 7. 装饰效果 */
const deco = [];
if (/(linear|radial|conic)-gradient/i.test(deTokened)) deco.push('渐变');
if (/box-shadow\s*:\s*(?!none)/i.test(deTokened.replace(/box-shadow\s*:\s*0\s+0\s+0\s+\d+px[^;]*/gi, ''))) deco.push('阴影');
if (/filter\s*:\s*(blur|drop-shadow)/i.test(deTokened)) deco.push('模糊');
if (/text-shadow\s*:\s*(?!none)/i.test(deTokened)) deco.push('文字阴影');
deco.length ? add('WARN', '装饰效果', `${deco.join('、')} — 学术风要求平面，除非它编码了信息`) : add('PASS', '装饰效果');

/* 8. 暗色模式 */
/prefers-color-scheme/i.test(src) || /color-scheme\s*:/i.test(src)
  ? add('PASS', '暗色模式')
  : add('FAIL', '暗色模式', '既无 prefers-color-scheme 也无 color-scheme，暗背景下必然有文字读不出来');

/* 9. 硬编码颜色 */
const hard = [...deTokened.matchAll(/(?:color|background|background-color|fill|stroke)\s*[:=]\s*["']?(#[0-9a-f]{3,8})\b/gi)].map((m) => m[1]);
hard.length ? add('WARN', '硬编码颜色', `${hard.length} 处写死颜色: ${trunc(hard)} — 除物理写实场景外一律走 var(--…)`) : add('PASS', '硬编码颜色');

/* 10-11. SVG */
const svgs = [...src.matchAll(/<svg\b([^>]*)>([\s\S]*?)<\/svg>/gi)];
if (!svgs.length) add('WARN', 'SVG', '页面里没有 SVG — 讲解页通常需要至少一张结构图');
else {
  const noClass = [];
  const noBox = [];
  const overflow = [];
  const noLabel = [];
  svgs.forEach((s, i) => {
    const [, attrs, body] = s;
    for (const t of body.matchAll(/<text\b([^>]*)>/gi)) {
      if (!/class\s*=/i.test(t[1])) noClass.push(`#${i + 1}`);
    }
    if (!/<title\b/i.test(body) && !/aria-label\s*=/i.test(attrs)) noLabel.push(`#${i + 1}`);
    const vb = /viewBox\s*=\s*["']\s*([-\d.]+)\s+([-\d.]+)\s+([\d.]+)\s+([\d.]+)/i.exec(attrs);
    if (!vb) { noBox.push(`#${i + 1}`); return; }
    const W = +vb[3], H = +vb[4];
    let mx = 0, my = 0;
    for (const m of body.matchAll(/<rect\b[^>]*>/gi)) {
      const g = (k) => { const r = new RegExp(k + '\\s*=\\s*["\']([-\\d.]+)').exec(m[0]); return r ? +r[1] : 0; };
      mx = Math.max(mx, g('x') + g('width')); my = Math.max(my, g('y') + g('height'));
    }
    for (const m of body.matchAll(/<circle\b[^>]*>/gi)) {
      const g = (k) => { const r = new RegExp(k + '\\s*=\\s*["\']([-\\d.]+)').exec(m[0]); return r ? +r[1] : 0; };
      mx = Math.max(mx, g('cx') + g('r')); my = Math.max(my, g('cy') + g('r'));
    }
    for (const m of body.matchAll(/<(?:text|line)\b[^>]*>/gi)) {
      const g = (k) => { const r = new RegExp('\\b' + k + '\\s*=\\s*["\']([-\\d.]+)').exec(m[0]); return r ? +r[1] : 0; };
      mx = Math.max(mx, g('x'), g('x1'), g('x2')); my = Math.max(my, g('y'), g('y1'), g('y2'));
    }
    if (mx > W + 0.5 || my > H + 0.5) overflow.push(`#${i + 1} 内容到 (${Math.round(mx)},${Math.round(my)}) 超出 viewBox ${W}×${H}`);
  });
  noBox.length ? add('FAIL', 'SVG viewBox', `缺 viewBox: ${trunc(noBox)}`) : add('PASS', 'SVG viewBox');
  noClass.length ? add('FAIL', 'SVG 文本类名', `${noClass.length} 个 <text> 没有 t/ts/th/tn 类 — 暗色下会渲染成黑字`) : add('PASS', 'SVG 文本类名');
  overflow.length ? add('WARN', 'SVG 边界', overflow.join('; ')) : add('PASS', 'SVG 边界', `${svgs.length} 张图静态元素均在框内`);
  noLabel.length ? add('WARN', 'SVG 可访问名', `${trunc(noLabel)} 缺 <title> 或 aria-label`) : add('PASS', 'SVG 可访问名');
}

/* 12. 表单可访问性 */
const inputs = [...src.matchAll(/<(input|select|textarea)\b[^>]*>/gi)];
const labeled = (tag) => /aria-label/i.test(tag) || (/(?:^|\s)id\s*=\s*["']([^"']+)/i.exec(tag) &&
  new RegExp(`<label[^>]*for\\s*=\\s*["']${/(?:^|\s)id\s*=\s*["']([^"']+)/i.exec(tag)[1]}["']`, 'i').test(src));
const unlabeled = inputs.filter((m) => !labeled(m[0]));
if (!inputs.length) add('FAIL', '交互控件', '没有任何 input/select/button — 交互讲解页必须有可操作的控件');
else if (unlabeled.length) add('WARN', '控件标签', `${unlabeled.length} 个控件没有 label/aria-label`);
else add('PASS', '控件标签', `${inputs.length} 个控件均有标签`);

/* 13. 控件位置：必须在它所控制的图形下方 */
const ctlPos = [...src.matchAll(/class\s*=\s*["'][^"']*\bcontrols\b/gi)].map((m) => m.index);
const figPos = [...src.matchAll(/<(svg|canvas)\b/gi)].map((m) => m.index);
if (!ctlPos.length) {
  const loose = [...src.matchAll(/<input\b[^>]*type\s*=\s*["'](range|checkbox|radio)/gi)].map((m) => m.index);
  const early = loose.filter((i) => !figPos.some((f) => f < i));
  early.length ? add('FAIL', '控件位置', `${early.length} 个控件出现在所有图形之前 — 控件必须放在它所控制的图形下方`)
               : add('WARN', '控件位置', '未找到 .controls 容器，无法逐组核对；请人工确认每组控件都在对应图形下方');
} else {
  const bad = ctlPos.filter((i) => !figPos.some((f) => f < i));
  bad.length ? add('FAIL', '控件位置', `${bad.length} 组 .controls 前面没有任何图形 — 控件必须紧跟在它所控制的 </figure> 之后`)
             : add('PASS', '控件位置', `${ctlPos.length} 组控件均位于图形之后`);
}

/* 14. 文字替代 */
/aria-live/i.test(src) ? add('PASS', '文字替代') : add('WARN', '文字替代', '缺 aria-live 区域 — 状态变化后读屏用户与不渲染的客户端拿不到结论');

/* 15. 动效降级 */
const anim = /@keyframes|animation\s*:|transition\s*:/i.test(src);
if (!anim) add('PASS', '动效降级', '未使用动画');
else /prefers-reduced-motion/i.test(src) ? add('PASS', '动效降级') : add('WARN', '动效降级', '用了动画但没有 prefers-reduced-motion 兜底');

/* 16. 数字取整 */
if (!scripts.trim()) add('FAIL', '脚本', '没有 <script>，页面不可能交互');
else {
  const rounds = /toFixed|Math\.round|toLocaleString|Intl\.NumberFormat/.test(scripts);
  const writes = /(textContent|innerHTML|innerText)\s*=/.test(scripts);
  writes && !rounds
    ? add('WARN', '数字取整', '脚本向 DOM 写值但未见 toFixed/Math.round — 浮点尾巴会漏到屏幕上')
    : add('PASS', '数字取整');
  /addEventListener|on(input|click|change)\s*=/.test(scripts + src)
    ? add('PASS', '事件绑定')
    : add('FAIL', '事件绑定', '找不到事件监听，控件是死的');
}

/* 17. 体积 */
bytes > 500 * 1024 ? add('WARN', '体积', `${(bytes / 1024).toFixed(0)} KB，超过 500 KB`) : add('PASS', '体积', `${(bytes / 1024).toFixed(0)} KB`);

const fails = out.filter((o) => o.level === 'FAIL');
const warns = out.filter((o) => o.level === 'WARN');
console.log(`\nLingXi 体检 · ${file}`);
for (const o of out) console.log(`  [${o.level}]`.padEnd(9) + o.name.padEnd(14) + o.msg);
console.log(`\n  → ${fails.length ? `未通过：${fails.length} 项 FAIL，${warns.length} 项 WARN` : (warns.length ? `通过，但有 ${warns.length} 项 WARN 需在交付说明中解释` : '全部通过')}`);
console.log('  提示：静态检查看不见运行时生成的 DOM，交付前仍需渲染截图肉眼过一遍。\n');
process.exit(fails.length ? 1 : 0);
