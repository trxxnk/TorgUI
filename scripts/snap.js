// Lossless screenshot of the page for docs/demo.gif. Run scripts/frame_receiver.py, open the app
// with ?dpr=2, paste this file into the browser console (or run it from an agent), then:  await snap('01')
// The page is cloned into an SVG <foreignObject>, drawn on a canvas at 2x and POSTed to the receiver as PNG.
// Browser-pane screenshots are no good for this: they are downscaled to 800 px and JPEG-compressed.
window.snap = async (name, opt = {}) => {
  const scale = opt.scale || 2, W = innerWidth, H = innerHeight;
  // The WebGL buffer is readable only right after the app's own render, so read it in the same frame.
  const gl = document.getElementById('gl');
  const glURL = await new Promise(r => requestAnimationFrame(() => r(gl.toDataURL('image/png'))));
  const clone = document.documentElement.cloneNode(true);
  clone.querySelectorAll('script,link').forEach(e => e.remove());
  // form values live in properties, not in markup: copy them over
  const src = [...document.querySelectorAll('textarea,input')], dst = [...clone.querySelectorAll('textarea,input')];
  src.forEach((e, k) => { if (e.tagName === 'TEXTAREA') dst[k].textContent = e.value; else dst[k].setAttribute('value', e.value); });
  const img3d = document.createElement('img');
  img3d.setAttribute('src', glURL); img3d.setAttribute('style', 'display:block;width:100%;height:100%');
  clone.querySelector('#gl').replaceWith(img3d);
  // a clone forgets scroll offsets: shift the sidebar content instead
  const side = document.querySelector('.side'), side2 = clone.querySelector('.side');
  if (side.scrollTop) { side2.style.overflow = 'hidden'; side2.firstElementChild.style.marginTop = -side.scrollTop + 'px'; }
  // keep the viewer's own saved listings out of a public picture
  if (opt.hide) {
    clone.querySelectorAll('.savedItem').forEach(e => { if (opt.hide.test(e.textContent)) e.remove(); });
    if (!clone.querySelector('.savedItem')) clone.querySelector('#savedWrap').setAttribute('hidden', '');
  }
  // an image loads nothing from the network: inline the stylesheet and the fonts, and pin the theme tokens
  const css = await (await fetch('styles.css')).text(), cs = getComputedStyle(document.documentElement);
  const vars = [...new Set(css.match(/--[a-z0-9-]+(?=:)/g))].map(v => `${v}:${cs.getPropertyValue(v)}`).join(';');
  const st = document.createElement('style');
  st.textContent = `${await snapFonts()}\n${css}\n:root:root:root{${vars};color-scheme:${cs.colorScheme || 'light'}}`;
  clone.querySelector('head').append(st);
  const svg = `<svg xmlns="http://www.w3.org/2000/svg" width="${W * scale}" height="${H * scale}" viewBox="0 0 ${W} ${H}">` +
    `<foreignObject x="0" y="0" width="${W}" height="${H}">${new XMLSerializer().serializeToString(clone)}</foreignObject></svg>`;
  const img = new Image();
  await new Promise((ok, no) => { img.onload = ok; img.onerror = () => no(new Error('svg load failed')); img.src = 'data:image/svg+xml;charset=utf-8,' + encodeURIComponent(svg); });
  const cv = document.createElement('canvas'); cv.width = W * scale; cv.height = H * scale;
  const ctx = cv.getContext('2d');
  ctx.drawImage(img, 0, 0, cv.width, cv.height);          // first draw warms up the embedded fonts
  await new Promise(r => setTimeout(r, 250));
  ctx.clearRect(0, 0, cv.width, cv.height); ctx.drawImage(img, 0, 0, cv.width, cv.height);
  const blob = await new Promise(r => cv.toBlob(r, 'image/png'));
  await fetch('http://localhost:8099/' + name, { method: 'POST', mode: 'no-cors', body: blob });
  return blob.size;
};
// Google Fonts CSS with the Cyrillic and Latin font files embedded as data URIs (fetched once).
window.snapFonts = async () => {
  if (window.__snapFonts) return window.__snapFonts;
  const link = document.querySelector('link[href*="fonts.googleapis"]');
  if (!link) return '';
  let css = (await (await fetch(link.href)).text()).split('/*').slice(1).filter(b => /^ (cyrillic|latin) \*\//.test(b)).map(b => '/*' + b).join('');
  for (const u of new Set(css.match(/https:[^)]+/g))) {
    const blob = await (await fetch(u)).blob();
    const data = await new Promise(r => { const fr = new FileReader(); fr.onload = () => r(fr.result); fr.readAsDataURL(blob); });
    css = css.split(u).join(data);
  }
  return window.__snapFonts = css;
};
