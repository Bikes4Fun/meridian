const fs = require('fs');
const path = require('path');

function loadApiConfig() {
    const cfgPath = path.join(__dirname, '..', '..', '..', 'shared', 'api_config.json');
    try {
        return JSON.parse(fs.readFileSync(cfgPath, 'utf8'));
    } catch (e) {
        return {};
    }
}

function getRailwayUrl() {
    if (process.env.RAILWAY_API_URL) return process.env.RAILWAY_API_URL.trim();
    const cfg = loadApiConfig();
    const url = (cfg.railway_api_url || '').trim();
    if (!url) {
        console.log('Railway API URL not configured. Set RAILWAY_API_URL or add railway_api_url to src/shared/api_config.json');
        throw new Error('Railway API URL not configured.');
    }
    return url;
}

async function resolveApiUrl() {
    if (process.env.API_URL) return process.env.API_URL.trim();
    const railwayUrl = getRailwayUrl();
    try {
        const res = await fetch(railwayUrl.replace(/\/$/, '') + '/api/health', { signal: AbortSignal.timeout(3000) });
        if (res.ok) return railwayUrl;
        console.log('Railway API health check failed:', res.status);
    } catch (e) {
        console.log('Railway API not reachable, using localhost:', e.message);
    }
    return 'http://localhost:8080';
}

async function build() {
    const apiUrl = await resolveApiUrl();
    const root = __dirname;
    const webClient = path.join(root, '..', 'web_client');

    const dist = path.join(root, 'dist');
    if (!fs.existsSync(dist)) fs.mkdirSync(dist, { recursive: true });

    const loginHtml = fs.readFileSync(path.join(webClient, 'login.html'), 'utf8');
    fs.writeFileSync(path.join(dist, 'index.html'), loginHtml.replace(/__API_URL__/g, apiUrl));
    fs.writeFileSync(path.join(dist, 'login.html'), loginHtml.replace(/__API_URL__/g, apiUrl));

    const checkinHtml = fs.readFileSync(path.join(webClient, 'checkin.html'), 'utf8');
    fs.writeFileSync(path.join(dist, 'checkin.html'), checkinHtml);

    const checkinJsPath = path.join(webClient, 'checkin.js');
    if (fs.existsSync(checkinJsPath)) {
        const checkinJs = fs.readFileSync(checkinJsPath, 'utf8');
        fs.writeFileSync(path.join(dist, 'checkin.js'), checkinJs.replace(/__API_URL__/g, apiUrl));
    }
}

build().catch((e) => { console.error(e); process.exit(1); });
