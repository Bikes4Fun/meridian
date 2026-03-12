const fs = require('fs');
const path = require('path');
const { resolveApiUrl } = require('../../../shared/resolve_api_url');

async function build() {
    const apiUrl = await resolveApiUrl();
    const root = __dirname;
    const webClient = path.join(root, '..', 'web_client');

    const dist = path.join(root, 'dist');
    if (!fs.existsSync(dist)) fs.mkdirSync(dist, { recursive: true });

    const replaceApi = (s) => s.replace(/__API_URL__/g, apiUrl);

    const loginHtml = fs.readFileSync(path.join(webClient, 'login.html'), 'utf8');
    fs.writeFileSync(path.join(dist, 'index.html'), replaceApi(loginHtml));
    fs.writeFileSync(path.join(dist, 'login.html'), replaceApi(loginHtml));

    const indexHtml = fs.readFileSync(path.join(webClient, 'index.html'), 'utf8');
    fs.writeFileSync(path.join(dist, 'checkin.html'), replaceApi(indexHtml));

    const appJs = fs.readFileSync(path.join(webClient, 'app.js'), 'utf8');
    fs.writeFileSync(path.join(dist, 'app.js'), replaceApi(appJs));
}

build().catch((e) => { console.error(e); process.exit(1); });
