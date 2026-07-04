import fs from 'node:fs';
import path from 'node:path';
import { fileURLToPath } from 'node:url';

const __dirname = path.dirname(fileURLToPath(import.meta.url));
const root = path.resolve(__dirname, '..');
const pkg = JSON.parse(fs.readFileSync(path.join(root, 'package.json'), 'utf8'));
const version = String(pkg.version || '').trim();
if (!/^\d+\.\d+\.\d+$/.test(version)) {
  throw new Error(`package.json version must be X.Y.Z, got: ${version || '(empty)'}`);
}

const publicDir = path.join(root, 'public');
fs.writeFileSync(path.join(publicDir, 'app-version.json'), `${JSON.stringify({ version }, null, 2)}\n`);
const swPath = path.join(publicDir, 'sw.js');
let sw = fs.readFileSync(swPath, 'utf8');
sw = sw.replace(/const APP_VERSION = '[^']+';/, `const APP_VERSION = '${version}';`);
fs.writeFileSync(swPath, sw);
console.log(`Mini App version synchronized: ${version}`);
