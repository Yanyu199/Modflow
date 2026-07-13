const fs = require('fs');
const path = require('path');
const zlib = require('zlib');

const distDir = path.resolve(__dirname, '..', 'dist');
const strict = String(process.env.FLOPY_BUNDLE_BUDGET_STRICT || '').toLowerCase() === 'true';
const initialGzipBudget = Number(process.env.FLOPY_INITIAL_JS_GZIP_BUDGET || 900 * 1024);
const asyncChunkGzipBudget = Number(process.env.FLOPY_ASYNC_CHUNK_GZIP_BUDGET || 700 * 1024);

function walk(dir) {
  if (!fs.existsSync(dir)) return [];
  return fs.readdirSync(dir, { withFileTypes: true }).flatMap((entry) => {
    const full = path.join(dir, entry.name);
    return entry.isDirectory() ? walk(full) : [full];
  });
}

const assets = walk(distDir)
  .filter((file) => file.endsWith('.js'))
  .map((file) => {
    const bytes = fs.readFileSync(file);
    const rel = path.relative(distDir, file).replace(/\\/g, '/');
    const gzipBytes = zlib.gzipSync(bytes).length;
    return {
      file: rel,
      raw_bytes: bytes.length,
      gzip_bytes: gzipBytes,
      kind: rel === 'main.js' ? 'initial' : 'async',
    };
  })
  .sort((a, b) => b.raw_bytes - a.raw_bytes);

const warnings = [];
for (const asset of assets) {
  const budget = asset.kind === 'initial' ? initialGzipBudget : asyncChunkGzipBudget;
  if (asset.gzip_bytes > budget) {
    warnings.push({
      file: asset.file,
      kind: asset.kind,
      gzip_bytes: asset.gzip_bytes,
      budget,
    });
  }
}

const report = {
  generated_at: new Date().toISOString(),
  budgets: {
    initial_js_gzip_bytes: initialGzipBudget,
    async_chunk_gzip_bytes: asyncChunkGzipBudget,
    strict,
  },
  totals: {
    js_raw_bytes: assets.reduce((sum, item) => sum + item.raw_bytes, 0),
    js_gzip_bytes: assets.reduce((sum, item) => sum + item.gzip_bytes, 0),
    initial_raw_bytes: assets.filter((item) => item.kind === 'initial').reduce((sum, item) => sum + item.raw_bytes, 0),
    initial_gzip_bytes: assets.filter((item) => item.kind === 'initial').reduce((sum, item) => sum + item.gzip_bytes, 0),
    async_raw_bytes: assets.filter((item) => item.kind === 'async').reduce((sum, item) => sum + item.raw_bytes, 0),
    async_gzip_bytes: assets.filter((item) => item.kind === 'async').reduce((sum, item) => sum + item.gzip_bytes, 0),
  },
  largest_assets: assets.slice(0, 10),
  warnings,
};

fs.writeFileSync(path.join(distDir, 'bundle-report.json'), JSON.stringify(report, null, 2));
console.log(JSON.stringify(report, null, 2));

if (strict && warnings.length > 0) {
  process.exitCode = 1;
}
