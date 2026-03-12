/**
 * Resolve API URL for build scripts. Tries: 1) API_URL env, 2) Railway, 3) probe localhost ports.
 * Aligns with Python config (get_server_port, find_available_port). Default port 5000.
 */
function loadApiConfig() {
    const path = require('path');
    const fs = require('fs');
    const cfgPath = path.join(__dirname, 'api_config.json');
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
    if (!url) throw new Error('Railway API URL not configured.');
    return url;
}

async function probeLocalApi(startPort, maxTries = 20) {
    for (let i = 0; i < maxTries; i++) {
        const port = startPort + i;
        const url = `http://127.0.0.1:${port}/api/health`;
        try {
            const res = await fetch(url, { signal: AbortSignal.timeout(1500) });
            if (res.ok) return `http://127.0.0.1:${port}`;
        } catch (e) {}
    }
    return null;
}

async function resolveApiUrl() {
    if (process.env.API_URL) return process.env.API_URL.trim();
    try {
        const railwayUrl = getRailwayUrl();
        const res = await fetch(railwayUrl.replace(/\/$/, '') + '/api/health', {
            signal: AbortSignal.timeout(3000),
        });
        if (res.ok) return railwayUrl;
    } catch (e) {}
    const defaultPort = (loadApiConfig().local_api_port ?? 5000);
    const startPort = parseInt(process.env.PORT || String(defaultPort), 10);
    const local = await probeLocalApi(startPort);
    if (local) return local;
    console.log('No API reachable. Tried Railway and localhost:' + startPort + '..' + (startPort + 19) + '. Set API_URL or run main.py --local.');
    return `http://127.0.0.1:${startPort}`;
}

module.exports = { resolveApiUrl, getRailwayUrl, loadApiConfig };
