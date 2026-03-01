
(function () {
    'use strict';

    var _u = '__API_URL__';
    var API_URL = (_u.startsWith('http') ? _u : '');

    function showStatus(message, type) {
        var container = document.getElementById('status');
        if (!container) return;
        var box = document.createElement('div');
        box.className = type;
        box.textContent = message;
        container.appendChild(box);
    }

    function checkIn() {
        var familyMemberId = document.getElementById('familyMemberSelect').value;
        var notes = document.getElementById('notes').value;
        var btn = document.getElementById('checkinBtn');

        if (!familyMemberId) {
            showStatus('Please select a family member!', 'error');
            return;
        }

        btn.disabled = true;
        showStatus('Getting your location...', 'info');

        if (!navigator.geolocation) {
            showStatus('GPS not supported on this device!', 'error');
            btn.disabled = false;
            return;
        }

        // #region agent log
        (function () {
            var isSecure = typeof window !== 'undefined' && window.isSecureContext;
            var origin = typeof location !== 'undefined' ? location.origin : '';
            var isIframe = typeof window !== 'undefined' && window.self !== window.top;
            fetch('http://127.0.0.1:7597/ingest/42253974-8a85-41c5-a6bf-91c1b0df07a4', { method: 'POST', headers: { 'Content-Type': 'application/json', 'X-Debug-Session-Id': '14aad6' }, body: JSON.stringify({ sessionId: '14aad6', location: 'checkin.js:before-getCurrentPosition', message: 'geolocation context', data: { isSecureContext: isSecure, origin: origin, isIframe: isIframe }, timestamp: Date.now(), hypothesisId: 'H1-H3' }) }).catch(function () {});
            if (navigator.permissions && navigator.permissions.query) {
                navigator.permissions.query({ name: 'geolocation' }).then(function (p) { fetch('http://127.0.0.1:7597/ingest/42253974-8a85-41c5-a6bf-91c1b0df07a4', { method: 'POST', headers: { 'Content-Type': 'application/json', 'X-Debug-Session-Id': '14aad6' }, body: JSON.stringify({ sessionId: '14aad6', location: 'checkin.js:permission-state', message: 'geolocation permission', data: { state: p.state }, timestamp: Date.now(), hypothesisId: 'H2' }) }).catch(function () {}); }).catch(function () {});
            }
        })();
        // #endregion

        navigator.geolocation.getCurrentPosition(
            function (position) {
                var latitude = position.coords.latitude;
                var longitude = position.coords.longitude;

                showStatus('Found location: ' + latitude.toFixed(4) + ', ' + longitude.toFixed(4) + '. Sending...', 'info');

                fetch(API_URL + '/api/location/checkin', {
                    method: 'POST',
                    headers: { 'Content-Type': 'application/json' },
                    credentials: 'same-origin',
                    body: JSON.stringify({
                        family_member_id: familyMemberId,
                        latitude: latitude,
                        longitude: longitude,
                        notes: notes || null
                    })
                })
                    .then(function (response) {
                        if (response.ok) {
                            showStatus('\u2713 Check-in successful!', 'success');
                            document.getElementById('notes').value = '';
                        } else {
                            return response.json().then(function (data) {
                                showStatus('\u2717 Error: ' + (data.error || 'Check-in failed'), 'error');
                            });
                        }
                    })
                    .catch(function (err) {
                        showStatus('\u2717 Network error: ' + err.message, 'error');
                    })
                    .then(function () {
                        btn.disabled = false;
                    });
            },
            function (error) {
                // #region agent log
                fetch('http://127.0.0.1:7597/ingest/42253974-8a85-41c5-a6bf-91c1b0df07a4', { method: 'POST', headers: { 'Content-Type': 'application/json', 'X-Debug-Session-Id': '14aad6' }, body: JSON.stringify({ sessionId: '14aad6', location: 'checkin.js:getCurrentPosition-error', message: 'geolocation error', data: { code: error.code, message: error.message }, timestamp: Date.now(), hypothesisId: 'H5' }) }).catch(function () {});
                // #endregion
                var msg = 'Could not get location. ';
                if (error.code === 1) msg += 'Permission denied.';
                else if (error.code === 2) msg += 'Position unavailable.';
                else if (error.code === 3) msg += 'Timeout.';
                showStatus(msg, 'error');
                btn.disabled = false;
            },
            {
                enableHighAccuracy: true,
                timeout: 10000,
                maximumAge: 0
            }
        );
    }

    function loadFamilyMembers() {
        fetch(API_URL + '/api/location/family-members', {
            credentials: 'same-origin'
        })
            .then(function (r) { return r.json(); })
            .then(function (data) {
                var sel = document.getElementById('familyMemberSelect');
                if (!sel || !data.data) return;
                data.data.forEach(function (fm) {
                    var opt = document.createElement('option');
                    opt.value = fm.id;
                    opt.textContent = fm.display_name;
                    sel.appendChild(opt);
                });
            })
            .catch(function () {});
    }

    function activateAlert() {
        fetch(API_URL + '/api/alert', {
            method: 'POST',
            headers: { 'Content-Type': 'application/json' },
            credentials: 'same-origin',
            body: JSON.stringify({ activated: true })
        })
            .then(function (r) { return r.json(); })
            .then(function (data) {
                showStatus('Alert mode activated. TV should switch to emergency screen.', 'success');
            })
            .catch(function (err) {
                showStatus('Alert failed: ' + err.message, 'error');
            });
    }

    function cancelAlert() {
        fetch(API_URL + '/api/alert', {
            method: 'POST',
            headers: { 'Content-Type': 'application/json' },
            credentials: 'same-origin',
            body: JSON.stringify({ activated: false })
        })
            .then(function (r) { return r.json(); })
            .then(function (data) {
                showStatus('Alert cancelled.', 'success');
            })
            .catch(function (err) {
                showStatus('Cancel failed: ' + err.message, 'error');
            });
    }

    function init() {
        var btn = document.getElementById('checkinBtn');
        if (btn) btn.addEventListener('click', checkIn);
        var alertBtn = document.getElementById('alertBtn');
        if (alertBtn) alertBtn.addEventListener('click', activateAlert);
        var cancelBtn = document.getElementById('cancelAlertBtn');
        if (cancelBtn) cancelBtn.addEventListener('click', cancelAlert);
        loadFamilyMembers();
    }

    if (document.readyState === 'loading') {
        document.addEventListener('DOMContentLoaded', init);
    } else {
        init();
    }
})();
