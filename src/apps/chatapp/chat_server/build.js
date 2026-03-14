const fs = require('fs');
const path = require('path');
const { resolveApiUrl } = require('../../../shared/resolve_api_url');

async function build() {
    const apiUrl = typeof process.env.API_URL === 'string' ? process.env.API_URL : await resolveApiUrl();
    const root = __dirname;
    const client = path.join(root, '..', 'chat_client');

    const dist = path.join(root, 'dist');
    if (!fs.existsSync(dist)) fs.mkdirSync(dist, { recursive: true });

    const replaceApi = (s) => s.replace(/__API_URL__/g, apiUrl);

    const chatHtml = fs.readFileSync(path.join(client, 'chat.html'), 'utf8');
    fs.writeFileSync(path.join(dist, 'index.html'), replaceApi(chatHtml));
    fs.writeFileSync(path.join(dist, 'chat.html'), replaceApi(chatHtml));

    const chatJs = fs.readFileSync(path.join(client, 'chat.js'), 'utf8');
    fs.writeFileSync(path.join(dist, 'chat.js'), replaceApi(chatJs));

    console.log('Chatapp built: index.html, chat.html, chat.js');
}

build().catch((e) => { console.error(e); process.exit(1); });
