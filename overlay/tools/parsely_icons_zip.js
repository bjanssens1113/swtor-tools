// Run this in the browser console while logged in on https://parsely.io (any page).
// It fetches every ability icon listed in overlay/data/parsely_icons.json (paste the slug list below or let it
// scrape the class pages), packs them into an uncompressed ZIP in memory, and downloads "parsely_icons.zip".
// Then run:  python overlay/tools/unpack_icons.py   to extract into overlay/data/icons/.
// Icons are game assets (EA/BioWare). They stay local and git-ignored.

(async () => {
  const classes = ['assassin','commando','guardian','gunslinger','juggernaut','marauder','mercenary','operative',
                   'powertech','sage','scoundrel','sentinel','shadow','sniper','sorcerer','vanguard'];
  const slugs = new Set();
  for (const c of classes) {
    const html = await fetch('/parser/abilities/' + c).then(r => r.text());
    const doc = new DOMParser().parseFromString(html, 'text/html');
    for (const img of doc.querySelectorAll('table img')) {
      const m = (img.getAttribute('src') || '').match(/\/img\/icons\/(.+)\.png$/);
      if (m) slugs.add(m[1]);
    }
  }
  console.log('icons to fetch:', slugs.size);

  // --- minimal ZIP writer (store method) --------------------------------------------------------
  const crcTable = new Uint32Array(256).map((_, n) => { let c = n; for (let k = 0; k < 8; k++) c = c & 1 ? 0xEDB88320 ^ (c >>> 1) : c >>> 1; return c >>> 0; });
  const crc32 = (u8) => { let c = 0xFFFFFFFF; for (const b of u8) c = crcTable[(c ^ b) & 0xFF] ^ (c >>> 8); return (c ^ 0xFFFFFFFF) >>> 0; };
  const le16 = (n) => [n & 255, (n >> 8) & 255];
  const le32 = (n) => [n & 255, (n >> 8) & 255, (n >> 16) & 255, (n >>> 24) & 255];
  const parts = [], central = []; let offset = 0, count = 0;
  const enc = new TextEncoder();
  for (const slug of slugs) {
    let data;
    try {
      const res = await fetch('/img/icons/' + slug + '.png');
      if (!res.ok) continue;
      data = new Uint8Array(await res.arrayBuffer());
    } catch (e) { continue; }
    const name = enc.encode(slug + '.png');
    const crc = crc32(data);
    const local = new Uint8Array([...le32(0x04034b50), ...le16(20), ...le16(0), ...le16(0), ...le16(0), ...le16(0),
      ...le32(crc), ...le32(data.length), ...le32(data.length), ...le16(name.length), ...le16(0), ...name]);
    parts.push(local, data);
    central.push(new Uint8Array([...le32(0x02014b50), ...le16(20), ...le16(20), ...le16(0), ...le16(0), ...le16(0), ...le16(0),
      ...le32(crc), ...le32(data.length), ...le32(data.length), ...le16(name.length), ...le16(0), ...le16(0), ...le16(0),
      ...le16(0), ...le32(0), ...le32(offset), ...name]));
    offset += local.length + data.length;
    count++;
    if (count % 100 === 0) console.log('fetched', count);
  }
  const cdSize = central.reduce((a, c) => a + c.length, 0);
  const end = new Uint8Array([...le32(0x06054b50), ...le16(0), ...le16(0), ...le16(count), ...le16(count),
    ...le32(cdSize), ...le32(offset), ...le16(0)]);
  const blob = new Blob([...parts, ...central, end], { type: 'application/zip' });
  const a = document.createElement('a');
  a.href = URL.createObjectURL(blob);
  a.download = 'parsely_icons.zip';
  document.body.appendChild(a);
  a.click();
  console.log('done:', count, 'icons,', (blob.size / 1e6).toFixed(1), 'MB');
})();
