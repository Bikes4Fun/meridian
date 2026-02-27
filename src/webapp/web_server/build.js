const fs = require('fs');
const path = require('path');

const apiUrl = process.env.API_URL || 'http://localhost:8080';
const root = __dirname;
const webClient = path.join(root, '..', 'web_client');

const html = fs.readFileSync(path.join(webClient, 'checkin.html'), 'utf8');
const dist = path.join(root, 'dist');
if (!fs.existsSync(dist)) fs.mkdirSync(dist, { recursive: true });
fs.writeFileSync(path.join(dist, 'index.html'), html);

const checkinJsPath = path.join(webClient, 'checkin.js');
if (fs.existsSync(checkinJsPath)) {
    const checkinJs = fs.readFileSync(checkinJsPath, 'utf8');
    fs.writeFileSync(path.join(dist, 'checkin.js'), checkinJs.replace(/__API_URL__/g, apiUrl));
}
