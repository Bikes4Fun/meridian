(function () {
    'use strict';
    var API_URL = (typeof __API_URL__ !== 'undefined' && __API_URL__.indexOf('http') === 0) ? __API_URL__ : '';
    var statusEl = document.getElementById('status');
    var meetingEl = document.getElementById('dyte-meeting');

    function setStatus(msg) {
        if (statusEl) statusEl.textContent = msg;
    }

    function showMeeting() {
        if (statusEl) statusEl.style.display = 'none';
        if (meetingEl) meetingEl.style.display = 'block';
    }

    fetch(API_URL + '/api/video/participant-token', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        credentials: 'include'
    })
        .then(function (r) {
            if (!r.ok) return r.json().then(function (d) { throw new Error(d.error || r.status); });
            return r.json();
        })
        .then(function (data) {
            var token = data && data.authToken;
            if (!token) throw new Error('No token');
            return DyteClient.init({ authToken: token, defaults: { audio: true, video: true } });
        })
        .then(function (meeting) {
            if (meetingEl) meetingEl.meeting = meeting;
            showMeeting();
        })
        .catch(function (e) {
            setStatus('Video error: ' + (e.message || e));
        });
})();
