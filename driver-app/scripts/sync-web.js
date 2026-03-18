#!/usr/bin/env node
/**
 * Sync driver portal assets from ../web into driver-app/www.
 * Run before cap sync so the native app has the latest driver portal and login.
 */
const fs = require('fs');
const path = require('path');

const ROOT = path.join(__dirname, '..');
const WEB = path.join(ROOT, '..', 'web');
const WWW = path.join(ROOT, 'www');

const FILES = [
  { src: 'driver.html', dest: 'index.html' },
  { src: 'login.html', dest: 'login.html' },
  { src: 'css/style.css', dest: 'css/style.css' },
  { src: 'js/config.js', dest: 'js/config.js' },
  { src: 'js/auth.js', dest: 'js/auth.js' },
  { src: 'js/driver-portal.js', dest: 'js/driver-portal.js' },
];

function ensureDir(dir) {
  if (!fs.existsSync(dir)) fs.mkdirSync(dir, { recursive: true });
}

ensureDir(WWW);
ensureDir(path.join(WWW, 'css'));
ensureDir(path.join(WWW, 'js'));

for (const { src, dest } of FILES) {
  const srcPath = path.join(WEB, src);
  const destPath = path.join(WWW, dest);
  if (!fs.existsSync(srcPath)) {
    console.warn('Skip (missing):', src);
    continue;
  }
  let content = fs.readFileSync(srcPath, 'utf8');
  if (dest === 'index.html') {
    content = content.replace(/window\.location\.href = '\/login\.html'/g, "window.location.href = 'login.html'");
    content = content.replace(/window\.location\.href = "\/login\.html"/g, 'window.location.href = "login.html"');
  }
  if (dest === 'js/auth.js') {
    content = content.replace(/window\.location\.href = '\/driver\.html'/g, "window.location.href = 'index.html'");
    content = content.replace(/window\.location\.href = "\/driver\.html"/g, 'window.location.href = "index.html"');
    content = content.replace(/window\.location\.href = '\/login\.html'/g, "window.location.href = 'login.html'");
    content = content.replace(/window\.location\.href = "\/login\.html"/g, 'window.location.href = "login.html"');
    content = content.replace(/window\.location\.href = '\/index\.html'/g, "window.location.href = (window.GEOMAPPER_DISPATCH_URL || 'index.html')");
    content = content.replace(/window\.location\.href = "\/index\.html"/g, 'window.location.href = (window.GEOMAPPER_DISPATCH_URL || "index.html")');
  }
  fs.writeFileSync(destPath, content);
  console.log('Synced:', dest);
}

console.log('Done. Run npx cap sync to update native projects.');
