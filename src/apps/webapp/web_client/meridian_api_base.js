/**
 * Shared webapp helpers. Load before app.js / ice_editor.js.
 */
(function (global) {
    'use strict';
    global.meridianLoginPageWithReturn = function () {
        return '/login.html?next=' + encodeURIComponent(global.location.pathname + global.location.search);
    };
    global.meridianPostLoginRedirectTarget = function () {
        var next = new URLSearchParams(global.location.search).get('next');
        if (!next || typeof next !== 'string') return '/';
        next = next.trim();
        if (!next || next.indexOf('//') === 0 || next.charAt(0) !== '/' || next.indexOf('://') >= 0) {
            return '/';
        }
        return next;
    };
    global.meridianApiBaseForFetch = function (configUrl) {
        var u = (configUrl || '').trim();
        if (!u.startsWith('http')) return '';
        try {
            var api = new URL(u);
            var win = global.location;
            if (api.origin === win.origin) return '';
            var loopbacks = { localhost: 1, '127.0.0.1': 1, '[::1]': 1 };
            if (
                loopbacks[api.hostname] &&
                loopbacks[win.hostname] &&
                api.protocol === win.protocol &&
                String(api.port) === String(win.port)
            ) {
                return '';
            }
            return u.replace(/\/$/, '');
        } catch (e) {
            return '';
        }
    };
})(typeof window !== 'undefined' ? window : this);
