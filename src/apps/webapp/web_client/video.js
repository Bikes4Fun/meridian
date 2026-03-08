(function () {
    'use strict';
    var params = new URLSearchParams(typeof location !== 'undefined' ? location.search : '');
    var joinId = params.get('join');
    var statusEl = document.getElementById('status');
    if (!joinId) {
        if (statusEl) statusEl.textContent = 'Open from kiosk to start a call.';
        return;
    }
    if (statusEl) statusEl.textContent = 'Joining...';
    var base = (typeof API_URL !== 'undefined' && API_URL) ? API_URL : '';
    fetch(base + '/api/video/join?join=' + encodeURIComponent(joinId))
        .then(function (r) {
            if (!r.ok) throw new Error('Invalid or expired link');
            return r.json();
        })
        .then(function (data) {
            if (!data.authToken) throw new Error('No token');
            return data.authToken;
        })
        .then(function (authToken) {
            return window.DyteClient.init({
                authToken: authToken,
                defaults: { audio: true, video: true }
            });
        })
        .then(function (meeting) {
            var el = document.getElementById('dyte-meeting');
            var container = document.getElementById('meeting-container');
            if (el) el.meeting = meeting;
            if (container) container.style.display = 'block';
            if (statusEl) statusEl.textContent = '';
        })
        .catch(function (e) {
            if (statusEl) statusEl.textContent = 'Could not join: ' + (e.message || 'error');
        });
})();
