// Runs at Vercel build time. Reads SUPABASE_URL / SUPABASE_ANON_KEY from
// Vercel's Environment Variables (never committed to git) and writes them
// into a small generated file the static page loads at runtime.
const fs = require('fs');
const path = require('path');

const url = process.env.SUPABASE_URL || '';
const key = process.env.SUPABASE_ANON_KEY || '';

if (!url || !key) {
  console.warn(
    '[build.js] SUPABASE_URL and/or SUPABASE_ANON_KEY are not set. ' +
    'The deployed page will show the "not configured" state until they are ' +
    'added in Vercel Project Settings -> Environment Variables.'
  );
}

const out = `window.__ESYS_CONFIG__ = ${JSON.stringify({
  SUPABASE_URL: url,
  SUPABASE_ANON_KEY: key,
})};\n`;

fs.writeFileSync(path.join(__dirname, 'public', 'config.js'), out);
console.log('[build.js] wrote public/config.js');
