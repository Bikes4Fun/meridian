/**
 * Build webapp + chatapp for Railway deploy.
 * API_URL empty = same-origin (webapp/chatapp served from same server as API).
 */
const { spawnSync } = require('child_process');
const path = require('path');

const root = __dirname;
const webappDir = path.join(root, 'apps', 'webapp', 'web_server');
const chatappDir = path.join(root, 'apps', 'chatapp', 'chat_server');

process.env.API_URL = process.env.API_URL || '';

function run(cwd, cmd, args = []) {
  const r = spawnSync(cmd, args, { cwd, stdio: 'inherit', env: { ...process.env } });
  if (r.status !== 0) process.exit(r.status || 1);
}

console.log('Building webapp...');
run(webappDir, 'node', ['build.js']);

console.log('Building chatapp...');
run(chatappDir, 'node', ['build.js']);

console.log('Build complete.');
