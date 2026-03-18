/**
 * Webapp client – single JS file. Handles login, check-in, and chat.
 * API_URL replaced by server (__API_URL__).
 */
(function () {
    'use strict';

    var _u = '__API_URL__';
    var API_URL = (_u.startsWith('http') ? _u : '');
    var _familyCircleId = null;

    function init() {
        if (document.getElementById('loginForm')) {
            initLogin();
            return;
        }
        if (document.getElementById('checkinBtn')) {
            var apiBase = (API_URL || '').replace(/\/$/, '');
            fetch(apiBase + '/api/session', { credentials: 'include' })
                .then(function (r) {
                    if (r.status === 401) {
                        window.location.href = '/login.html';
                        return null;
                    }
                    return r.ok ? r.json() : null;
                })
                .then(function (session) {
                    if (!session || !session.family_circle_id) {
                        window.location.href = '/login.html';
                        return;
                    }
                    document.body.classList.remove('pending');
                    initCheckin();
                    initLogoutLink();
                })
                .catch(function () { window.location.href = '/login.html'; });
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
            var apiBase = API_URL || '';
            fetch((apiBase ? apiBase.replace(/\/$/, '') : '') + '/api/login', {
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
                window.location.href = '/';
            })
            .catch(function (err) {
                alert(err.message || 'Login failed');
            });
        });
    }

    function showStatus(message, type) {
        var container = document.getElementById('status');
        if (!container) return;
        var box = document.createElement('div');
        box.className = type;
        box.textContent = message;
        container.appendChild(box);
    }

    function checkIn() {
        var userId = document.getElementById('familyMemberSelect').value;
        var notes = document.getElementById('notes').value;
        var btn = document.getElementById('checkinBtn');

        if (!userId) {
            showStatus('Please select who to check in!', 'error');
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
                fetch(API_URL + '/api/family_circles/' + fcId + '/create_checkin', {
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

    function loadFamilyMembers() {
        var apiBase = (API_URL || '').replace(/\/$/, '');
        fetch(apiBase + '/api/session', { credentials: 'include' })
            .then(function (r) {
                if (r.status === 401) {
                    window.location.href = '/login.html';
                    return null;
                }
                return r.ok ? r.json() : null;
            })
            .then(function (session) {
                if (!session || !session.family_circle_id) return;
                _familyCircleId = session.family_circle_id;
                if (document.getElementById('logoutLink')) document.getElementById('logoutLink').style.display = '';
                if (document.getElementById('contactsGrid')) initChatContacts();
                if (document.getElementById('eventsList')) loadEvents();
                return fetch(API_URL + '/api/family_circles/' + session.family_circle_id + '/family-members', {
                    credentials: 'include'
                });
            })
            .then(function (r) { return r && r.ok ? r.json() : null; })
            .then(function (data) {
                var sel = document.getElementById('familyMemberSelect');
                if (!sel || !data || !data.data) return;
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
        fetch(API_URL + '/api/emergency/alert', {
            method: 'POST',
            headers: { 'Content-Type': 'application/json' },
            credentials: 'include',
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
        fetch(API_URL + '/api/emergency/alert', {
            method: 'POST',
            headers: { 'Content-Type': 'application/json' },
            credentials: 'include',
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

    function initCheckin() {
        var btn = document.getElementById('checkinBtn');
        if (btn) btn.addEventListener('click', checkIn);
        var alertBtn = document.getElementById('alertBtn');
        if (alertBtn) alertBtn.addEventListener('click', activateAlert);
        var cancelBtn = document.getElementById('cancelAlertBtn');
        if (cancelBtn) cancelBtn.addEventListener('click', cancelAlert);
        if (document.getElementById('addEventBtn')) initEvents();
        loadFamilyMembers();
    }

    function loadEvents() {
        var list = document.getElementById('eventsList');
        if (!list || !_familyCircleId) return;
        var today = new Date().toISOString().slice(0, 10);
        var apiBase = (API_URL || '').replace(/\/$/, '');
        fetch(apiBase + '/api/family_circles/' + _familyCircleId + '/calendar/events?date=' + today, { credentials: 'include' })
            .then(function (r) { return r.ok ? r.json() : null; })
            .then(function (data) {
                if (!list) return;
                if (!data || !data.data || data.data.length === 0) {
                    list.innerHTML = '<p style="color: #666; margin: 0;">No events today</p>';
                    return;
                }
                list.innerHTML = '<ul style="margin: 0; padding-left: 20px;">' +
                    data.data.map(function (e) { return '<li>' + (e.display || e.title || '') + '</li>'; }).join('') +
                    '</ul>';
            })
            .catch(function () { if (list) list.innerHTML = '<p style="color: #999;">Could not load events</p>'; });
    }

    function initEvents() {
        var addBtn = document.getElementById('addEventBtn');
        var modal = document.getElementById('eventFormModal');
        var form = document.getElementById('eventForm');
        var cancelBtn = document.getElementById('eventFormCancel');
        if (!addBtn || !modal || !form) return;

        addBtn.addEventListener('click', function () {
            var today = new Date().toISOString().slice(0, 10);
            document.getElementById('eventTitle').value = '';
            document.getElementById('eventDate').value = today;
            document.getElementById('eventStartTime').value = '09:00';
            document.getElementById('eventEndTime').value = '';
            document.getElementById('eventLocation').value = '';
            document.getElementById('eventDescription').value = '';
            modal.style.display = 'flex';
        });

        cancelBtn.addEventListener('click', function () { modal.style.display = 'none'; });
        modal.addEventListener('click', function (e) { if (e.target === modal) modal.style.display = 'none'; });

        form.addEventListener('submit', function (e) {
            e.preventDefault();
            var title = document.getElementById('eventTitle').value.trim();
            var date = document.getElementById('eventDate').value;
            var startTime = document.getElementById('eventStartTime').value;
            var endTime = document.getElementById('eventEndTime').value;
            var location = document.getElementById('eventLocation').value.trim();
            var description = document.getElementById('eventDescription').value.trim();
            if (!title || !date || !startTime) {
                showStatus('Title, date, and start time required', 'error');
                return;
            }
            var startDateTime = date + 'T' + startTime + ':00';
            var payload = { title: title, start_time: startDateTime, location: location || undefined, description: description || undefined };
            if (endTime) payload.end_time = date + 'T' + endTime + ':00';

            var apiBase = (API_URL || '').replace(/\/$/, '');
            fetch(apiBase + '/api/family_circles/' + _familyCircleId + '/calendar/events', {
                method: 'POST',
                headers: { 'Content-Type': 'application/json' },
                credentials: 'include',
                body: JSON.stringify(payload)
            })
                .then(function (r) {
                    if (r.ok) {
                        modal.style.display = 'none';
                        showStatus('\u2713 Event added', 'success');
                        loadEvents();
                    } else return r.json().then(function (d) { throw new Error(d.error || 'Failed to add event'); });
                })
                .catch(function (err) {
                    showStatus('\u2717 ' + err.message, 'error');
                });
        });
    }

    function initChatContacts() {
        var grid = document.getElementById('contactsGrid');
        var statusEl = document.getElementById('openChatStatus');
        if (!grid || !_familyCircleId) return;
        var apiBase = (API_URL || '').replace(/\/$/, '');
        fetch(apiBase + '/api/family_circles/' + _familyCircleId + '/contacts', { credentials: 'include' })
            .then(function (r) { return r.ok ? r.json() : null; })
            .then(function (data) {
                if (!data || !data.data) return;
                var chatContacts = data.data.filter(function (c) { return (c.sendbird_user_id || '').trim(); });
                if (chatContacts.length === 0) {
                    grid.innerHTML = '<p style="font-size: 13px; color: #666;">No contacts with chat.</p>';
                    return;
                }
                grid.innerHTML = '';
                chatContacts.forEach(function (c) {
                    var name = c.display_name || c.id || 'Contact';
                    var sb = (c.sendbird_user_id || '').trim();
                    var tile = document.createElement('div');
                    tile.className = 'contact-tile';
                    tile.style.display = 'flex';
                    tile.style.flexDirection = 'column';
                    tile.style.alignItems = 'center';
                    var avatarSize = 96;
                    var avatar = document.createElement('div');
                    avatar.className = 'contact-avatar';
                    avatar.style.width = avatarSize + 'px';
                    avatar.style.height = avatarSize + 'px';
                    avatar.style.borderRadius = '50%';
                    avatar.style.marginBottom = '10px';
                    avatar.style.display = 'flex';
                    avatar.style.alignItems = 'center';
                    avatar.style.justifyContent = 'center';
                    avatar.style.backgroundColor = '#b0b0b0';
                    avatar.style.color = '#fff';
                    avatar.style.fontSize = '40px';
                    avatar.style.fontWeight = 'bold';
                    avatar.textContent = (name || '?').charAt(0).toUpperCase();
                    if (c.user_id) {
                        var img = document.createElement('img');
                        img.src = apiBase + '/api/users/' + c.user_id + '/photo';
                        img.alt = name;
                        img.style.position = 'absolute';
                        img.style.top = '0';
                        img.style.left = '0';
                        img.style.width = '100%';
                        img.style.height = '100%';
                        img.style.objectFit = 'cover';
                        img.onerror = function () { img.style.display = 'none'; };
                        avatar.style.position = 'relative';
                        avatar.style.overflow = 'hidden';
                        avatar.appendChild(img);
                    }
                    tile.appendChild(avatar);
                    var label = document.createElement('span');
                    label.className = 'contact-name';
                    label.style.fontSize = '20px';
                    label.textContent = name;
                    tile.appendChild(label);
                    tile.addEventListener('click', function () {
                        if (statusEl) statusEl.textContent = 'Opening chat…';
                        var qs = '?recipient_sendbird_user_id=' + encodeURIComponent(sb) + '&recipient_display_name=' + encodeURIComponent(name);
                        fetch(apiBase + '/api/chat/chat-session-url' + qs, { credentials: 'include' })
                            .then(function (r) {
                                if (!r.ok) return r.json().then(function (d) { throw new Error(d.error || 'Failed to get chat URL'); });
                                return r.json();
                            })
                            .then(function (res) {
                                if (res && res.url) {
                                    window.open(res.url, 'chat_' + sb, 'width=800,height=600');
                                    if (statusEl) statusEl.textContent = '';
                                } else throw new Error('No URL returned');
                            })
                            .catch(function (err) {
                                if (statusEl) statusEl.textContent = 'Error: ' + (err.message || 'Could not open chat');
                            });
                    });
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
            var apiBase = (API_URL || '').replace(/\/$/, '');
            fetch(apiBase + '/api/logout', { method: 'POST', credentials: 'include' })
                .then(function () { window.location.href = '/login.html'; })
                .catch(function () { window.location.href = '/login.html'; });
        });
    }

    if (document.readyState === 'loading') {
        document.addEventListener('DOMContentLoaded', init);
    } else {
        init();
    }
})();
