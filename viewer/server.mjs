// Zero-dependency static server for the sprite viewer.
//   /                    -> viewer/index.html (and other files in viewer/)
//   /dist/<file>         -> ../dist/<file>            (Aseprite exports: <name>_sheet.png / .json)
//   /vendor/pixi.mjs     -> node_modules/pixi.js/dist/pixi.min.mjs
//   /api/sprites         -> ["mummy", "player", ...]  (every dist/*_sheet.json)
// Usage: npm start   (PORT=5173 by default)
import http from 'node:http';
import { readFile, readdir } from 'node:fs/promises';
import { dirname, extname, join, normalize, sep } from 'node:path';
import { fileURLToPath } from 'node:url';

const here = dirname(fileURLToPath(import.meta.url));
const distDir = join(here, '..', 'dist');
const port = Number(process.env.PORT) || 5173;

const types = {
  '.html': 'text/html; charset=utf-8',
  '.js': 'text/javascript; charset=utf-8',
  '.mjs': 'text/javascript; charset=utf-8',
  '.json': 'application/json; charset=utf-8',
  '.png': 'image/png',
  '.css': 'text/css; charset=utf-8',
};

/** Resolve `rel` under `root`, refusing anything that escapes it. */
function inside(root, rel) {
  const full = normalize(join(root, rel));
  return full === root || full.startsWith(root + sep) ? full : null;
}

async function send(res, file) {
  try {
    const body = await readFile(file);
    res.writeHead(200, { 'Content-Type': types[extname(file)] ?? 'application/octet-stream', 'Cache-Control': 'no-store' });
    res.end(body);
  } catch {
    res.writeHead(404, { 'Content-Type': 'text/plain' });
    res.end('not found');
  }
}

http
  .createServer(async (req, res) => {
    const url = new URL(req.url ?? '/', 'http://localhost');
    const path = decodeURIComponent(url.pathname);
    if (path === '/api/sprites') {
      const names = (await readdir(distDir).catch(() => []))
        .filter((f) => f.endsWith('_sheet.json'))
        .map((f) => f.slice(0, -'_sheet.json'.length))
        .sort();
      res.writeHead(200, { 'Content-Type': types['.json'], 'Cache-Control': 'no-store' });
      return res.end(JSON.stringify(names));
    }
    if (path === '/vendor/pixi.mjs') return send(res, join(here, 'node_modules/pixi.js/dist/pixi.min.mjs'));
    if (path.startsWith('/dist/')) {
      const file = inside(distDir, path.slice('/dist/'.length));
      return file ? send(res, file) : send(res, '');
    }
    const file = inside(here, path === '/' ? 'index.html' : path.slice(1));
    return file && !file.includes(`${sep}node_modules${sep}`) ? send(res, file) : send(res, '');
  })
  .listen(port, () => console.log(`Sprite viewer: http://localhost:${port}/   (sheets from ${distDir})`));
