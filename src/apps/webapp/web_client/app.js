/**
 * Webapp client – single JS file. Handles login, check-in, and chat.
 * __API_URL__ replaced at build. The first IIFE defines shared meridian* helpers (login redirect, API base, escaping) for this file, events.js, medications.js, ice_editor.js (no separate meridian_api_base.js).
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
    global.meridianApiBaseNormalize = function (url) {
        return String(url || '').replace(/\/$/, '');
    };
    global.meridianEscapeHtml = function (s) {
        return String(s || '').replace(/</g, '&lt;').replace(/>/g, '&gt;');
    };
    global.meridianEscapeAttr = function (s) {
        return String(s || '').replace(/&/g, '&amp;').replace(/"/g, '&quot;');
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

(function () {
    'use strict';

    var _u = '__API_URL__';
    var API_BASE = meridianApiBaseForFetch(_u.startsWith('http') ? _u : '');
    var _familyCircleId = null;
    var _userId = null;
    var _mobileChatLoaded = false;

    function init() {
        if (document.getElementById('loginForm')) {
            initLogin();
            return;
        }
        if (document.getElementById('appNav')) {
            function finishDashboardInit() {
                document.body.classList.remove('pending');
                var topLogin = document.querySelector('.app-topbar-login');
                if (topLogin) topLogin.style.display = 'none';
                if (document.getElementById('logoutLink')) document.getElementById('logoutLink').style.display = 'inline';
                initNav();
                initKioskAlertShortcut();
                initHealthShortcuts();
                initHealthFoldFromHash();
                initCheckin();
                initLogoutLink();
                initIdleLogout();
                var apiRoot = API_BASE || '';
                if (window.MeridianMedications) {
                    MeridianMedications.init(apiRoot, _familyCircleId, showStatus);
                }
            }
            function applySessionPayload(session) {
                if (!session || !session.family_circle_id || !session.user_id) {
                    return false;
                }
                _familyCircleId = session.family_circle_id;
                _userId = session.user_id;
                return true;
            }
            var boot = typeof window.__MERIDIAN_SESSION__ !== 'undefined' ? window.__MERIDIAN_SESSION__ : null;
            if (boot && boot.user_id && boot.family_circle_id) {
                if (applySessionPayload(boot)) {
                    finishDashboardInit();
                } else {
                    window.location.href = meridianLoginPageWithReturn();
                }
                return;
            }
            var apiBase = API_BASE || '';
            fetch(apiBase + '/api/session', { credentials: 'include' })
                .then(function (r) {
                    if (r.status === 401) {
                        window.location.href = meridianLoginPageWithReturn();
                        return null;
                    }
                    if (!r.ok) return null;
                    return r.json().catch(function () { return null; });
                })
                .then(function (session) {
                    if (!applySessionPayload(session)) {
                        window.location.href = meridianLoginPageWithReturn();
                        return;
                    }
                    finishDashboardInit();
                })
                .catch(function () { window.location.href = meridianLoginPageWithReturn(); });
            return;
        }
        initLogoutLink();
    }

    function initLogin() {
        document.getElementById('loginForm').addEventListener('submit', function (e) {
            e.preventDefault();
            var familyCircleId = document.getElementById('familyCircleId').value.trim();
            var userId = document.getElementById('userId').value.trim();
            if (!familyCircleId || !userId) return;
            var apiBase = API_BASE || '';
            fetch(apiBase + '/api/login', {
                method: 'POST',
                headers: { 'Content-Type': 'application/json' },
                credentials: 'include',
                body: JSON.stringify({ user_id: userId, family_circle_id: familyCircleId })
            })
            .then(function (r) {
                if (r.ok) return r.json();
                return r.json().then(function (d) { throw new Error(d.error || 'Login failed'); });
            })
            .then(function () {
                window.location.href = meridianPostLoginRedirectTarget();
            })
            .catch(function (err) {
                alert(err.message || 'Login failed');
            });
        });
    }

    function showStatus(message, type) {
        var container = document.getElementById('status');
        if (!container) return;
        if (type === 'success') {
            var olds = container.querySelectorAll('div.success');
            for (var i = 0; i < olds.length; i++) olds[i].remove();
        }
        var box = document.createElement('div');
        box.className = type;
        box.textContent = message;
        container.appendChild(box);
        while (container.children.length > 5) {
            container.removeChild(container.firstChild);
        }
    }

    function checkIn() {
        var userId = _userId;
        var notes = document.getElementById('notes').value;
        var btn = document.getElementById('checkinBtn');

        if (!userId) {
            showStatus('Session expired. Please log in again.', 'error');
            return;
        }

        btn.disabled = true;
        showStatus('Getting your location...', 'info');

        if (!navigator.geolocation) {
            showStatus('GPS not supported on this device!', 'error');
            btn.disabled = false;
            return;
        }

        navigator.geolocation.getCurrentPosition(
            function (position) {
                var latitude = position.coords.latitude;
                var longitude = position.coords.longitude;

                showStatus('Found location: ' + latitude.toFixed(4) + ', ' + longitude.toFixed(4) + '. Sending...', 'info');

                var fcId = _familyCircleId;
                if (!fcId) {
                    showStatus('Session expired. Please log in again.', 'error');
                    btn.disabled = false;
                    return;
                }
                fetch((API_BASE || '') + '/api/family_circles/' + fcId + '/create_checkin', {
                    method: 'POST',
                    headers: { 'Content-Type': 'application/json' },
                    credentials: 'include',
                    body: JSON.stringify({
                        user_id: userId,
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
                var msg = 'Could not get location. ';
                if (error.code === 1) msg += 'Permission denied.';
                else if (error.code === 2) msg += 'Position unavailable.';
                else if (error.code === 3) msg += 'Timeout.';
                showStatus(msg, 'error');
                btn.disabled = false;
            },
            { enableHighAccuracy: true, timeout: 10000, maximumAge: 0 }
        );
    }

    function activateAlert() {
        var url = (API_BASE || '') + '/api/emergency/alert';
        fetch(url, {
            method: 'POST',
            headers: { 'Content-Type': 'application/json' },
            credentials: 'include',
            body: JSON.stringify({ activated: true })
        })
            .then(function (r) {
                return r.json().then(function (data) {
                    if (!r.ok) throw new Error(data.error || 'Request failed');
                    return data;
                });
            })
            .then(function () {
                showStatus('Alert mode activated. The kiosk should show the emergency screen.', 'success');
            })
            .catch(function (err) {
                showStatus('Alert failed: ' + (err.message || String(err)), 'error');
            });
    }

    function cancelAlert() {
        var url = (API_BASE || '') + '/api/emergency/alert';
        fetch(url, {
            method: 'POST',
            headers: { 'Content-Type': 'application/json' },
            credentials: 'include',
            body: JSON.stringify({ activated: false })
        })
            .then(function (r) {
                return r.json().then(function (data) {
                    if (!r.ok) throw new Error(data.error || 'Request failed');
                    return data;
                });
            })
            .then(function () {
                showStatus('Alert cancelled.', 'success');
            })
            .catch(function (err) {
                showStatus('Cancel failed: ' + (err.message || String(err)), 'error');
            });
    }

    function initNav() {
        var nav = document.getElementById('appNav');
        if (!nav) return;
        nav.addEventListener('click', function (e) {
            var raw = e.target;
            var el = raw.nodeType === 1 ? raw : raw.parentElement;
            if (!el || !el.closest) return;
            var btn = el.closest('.nav-btn');
            if (!btn) return;
            var pageId = btn.getAttribute('data-page') || '';
            var targetId = btn.getAttribute('data-target-id');
            if (!targetId) return;
            [].forEach.call(nav.querySelectorAll('.nav-btn'), function (b) { b.classList.remove('active'); });
            [].forEach.call(document.querySelectorAll('.page'), function (p) { p.classList.remove('active'); });
            btn.classList.add('active');
            var target = document.getElementById(targetId);
            if (target) target.classList.add('active');
            document.body.classList.toggle('dashboard-view--info', pageId === 'info');
            var apiRoot = API_BASE || '';
            if (pageId === 'events' && window.MeridianEvents) {
                MeridianEvents.init(apiRoot, _familyCircleId, showStatus);
            }
            if (
                (pageId === 'health' || pageId === 'settings') &&
                window.MeridianMedications
            ) {
                MeridianMedications.init(apiRoot, _familyCircleId, showStatus);
            }
            if (pageId === 'mobile' && !_mobileChatLoaded) {
                _mobileChatLoaded = true;
                initChatContacts();
            }
            if (pageId === 'health' || pageId === 'settings') {
                setTimeout(syncFoldDetailsFromHash, 0);
            }
        });
    }

    function initKioskAlertShortcut() {
        var shortcut = document.getElementById('kioskAlertShortcutBtn');
        if (!shortcut) return;
        shortcut.addEventListener('click', function () {
            var nav = document.getElementById('appNav');
            var settingsBtn = nav && nav.querySelector('.nav-btn[data-page="settings"]');
            if (settingsBtn) settingsBtn.click();
            setTimeout(function () {
                var el = document.getElementById('settingsKioskAlert');
                if (el) el.scrollIntoView({ behavior: 'smooth', block: 'nearest' });
            }, 50);
        });
    }

    function syncFoldDetailsFromHash() {
        var id = (location.hash || '').replace(/^#/, '');
        if (!id) return;
        var el = document.getElementById(id);
        if (el && el.tagName === 'DETAILS') el.open = true;
    }

    function initHealthFoldFromHash() {
        window.addEventListener('hashchange', syncFoldDetailsFromHash);
        syncFoldDetailsFromHash();
    }

    function openHealthMedicationList() {
        var nav = document.getElementById('appNav');
        var healthBtn = nav && nav.querySelector('.nav-btn[data-page="health"]');
        if (healthBtn) healthBtn.click();
        setTimeout(function () {
            var el = document.getElementById('health-section-medications');
            if (el && el.tagName === 'DETAILS') el.open = true;
            if (el) el.scrollIntoView({ behavior: 'smooth', block: 'nearest' });
        }, 50);
    }

    function openSettingsKioskControls() {
        var nav = document.getElementById('appNav');
        var settingsBtn = nav && nav.querySelector('.nav-btn[data-page="settings"]');
        if (settingsBtn) settingsBtn.click();
        setTimeout(function () {
            var el = document.getElementById('settingsKioskAlert');
            if (el) el.scrollIntoView({ behavior: 'smooth', block: 'nearest' });
        }, 50);
    }

    function initHealthShortcuts() {
        var nav = document.getElementById('appNav');
        if (!nav) return;
        var takeHost = document.getElementById('healthMedsTakeHost');
        if (takeHost) {
            takeHost.addEventListener('click', function (e) {
                if (e.target.closest('.health-meds-empty__cta')) {
                    e.preventDefault();
                    openHealthMedicationList();
                }
            });
        }
        var settingsMedsShortcut = document.getElementById('settingsMedicationListBtn');
        if (settingsMedsShortcut) {
            settingsMedsShortcut.addEventListener('click', function () {
                openHealthMedicationList();
            });
        }
        var settingsKioskBtn = document.getElementById('settingsKioskControlsBtn');
        if (settingsKioskBtn) {
            settingsKioskBtn.addEventListener('click', function () {
                openSettingsKioskControls();
            });
        }
    }

    function initCheckin() {
        var btn = document.getElementById('checkinBtn');
        if (btn) btn.addEventListener('click', checkIn);
        var alertBtn = document.getElementById('alertBtn');
        if (alertBtn) alertBtn.addEventListener('click', activateAlert);
        var cancelBtn = document.getElementById('cancelAlertBtn');
        if (cancelBtn) cancelBtn.addEventListener('click', cancelAlert);
    }

    function initChatContacts() {
        var grid = document.getElementById('contactsGrid');
        if (!grid || !_familyCircleId) return;
        var apiBase = API_BASE || '';
        fetch(apiBase + '/api/family_circles/' + _familyCircleId + '/contacts', { credentials: 'include' })
            .then(function (r) { return r.ok ? r.json() : null; })
            .then(function (data) {
                if (!data || !data.data) return;
                var chatContacts = data.data.filter(function (c) {
                    var relationship = (c.relationship || '').toLowerCase();
                    return relationship !== 'care recipient' && relationship !== 'care_recipient' && relationship !== 'patient';
                });
                if (chatContacts.length === 0) {
                    grid.innerHTML = '<p class="muted">No family contacts to show.</p>';
                    return;
                }
                grid.innerHTML = '';
                chatContacts.forEach(function (c) {
                    var name = c.display_name || c.id || 'Contact';
                    var tile = document.createElement('div');
                    tile.className = 'contact-tile';
                    var inner = document.createElement('div');
                    inner.className = 'contact-tile-inner';
                    var avatar = document.createElement('div');
                    avatar.className = 'contact-avatar';
                    avatar.textContent = (name || '?').charAt(0).toUpperCase();
                    if (c.user_id) {
                        var img = document.createElement('img');
                        img.src = apiBase + '/api/users/' + c.user_id + '/photo';
                        img.alt = name;
                        img.onerror = function () { img.style.display = 'none'; };
                        avatar.appendChild(img);
                    }
                    inner.appendChild(avatar);
                    var label = document.createElement('span');
                    label.className = 'contact-name';
                    label.textContent = name;
                    inner.appendChild(label);
                    tile.appendChild(inner);
                    grid.appendChild(tile);
                });
            })
            .catch(function () {});
    }

    function initLogoutLink() {
        var link = document.getElementById('logoutLink');
        if (!link) return;
        link.addEventListener('click', function (e) {
            e.preventDefault();
            var apiBase = API_BASE || '';
            fetch(apiBase + '/api/logout', { method: 'POST', credentials: 'include' })
                .then(function () { window.location.href = '/login.html'; })
                .catch(function () { window.location.href = '/login.html'; });
        });
    }

    function initIdleLogout() {
        var sec = typeof window.__MERIDIAN_IDLE_LOGOUT_SEC__ === 'number' ? window.__MERIDIAN_IDLE_LOGOUT_SEC__ : 1800;
        var idleMs = sec * 1000;
        if (idleMs <= 0) return;
        var timer = null;
        function doLogout() {
            var apiBase = API_BASE || '';
            fetch(apiBase + '/api/logout', { method: 'POST', credentials: 'include' })
                .then(function () { window.location.href = '/login.html'; })
                .catch(function () { window.location.href = '/login.html'; });
        }
        function reset() {
            if (timer) clearTimeout(timer);
            timer = setTimeout(doLogout, idleMs);
        }
        ['mousedown', 'keydown', 'touchstart', 'scroll'].forEach(function (ev) {
            document.addEventListener(ev, reset, { passive: true });
        });
        reset();
    }

    if (document.readyState === 'loading') {
        document.addEventListener('DOMContentLoaded', init);
    } else {
        init();
    }
})();
