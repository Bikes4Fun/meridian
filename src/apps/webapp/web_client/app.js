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
        if (document.getElementById('loginForm')) initLogin();
        if (document.getElementById('checkinBtn')) initCheckin();
        if (document.getElementById('openChatBtn')) initOpenChat();
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
                var base = (apiBase ? apiBase.replace(/\/$/, '') : '');
                window.location.href = base ? base + '/' : '/';
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
                fetch(API_URL + '/api/family_circles/' + fcId + '/checkin', {
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
                    window.location.href = apiBase ? apiBase + '/login.html' : '/login.html';
                    return null;
                }
                return r.ok ? r.json() : null;
            })
            .then(function (session) {
                if (!session || !session.family_circle_id) return;
                _familyCircleId = session.family_circle_id;
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
        loadFamilyMembers();
    }

    function initOpenChat() {
        var btn = document.getElementById('openChatBtn');
        var statusEl = document.getElementById('openChatStatus');
        if (!btn) return;
        btn.addEventListener('click', function () {
            btn.disabled = true;
            if (statusEl) statusEl.textContent = 'Opening chat…';
            var base = (API_URL || '').replace(/\/$/, '');
            fetch(base + '/api/chat/chat-session-url', { credentials: 'include' })
                .then(function (r) {
                    if (!r.ok) return r.json().then(function (d) { throw new Error(d.error || 'Failed to get chat URL'); });
                    return r.json();
                })
                .then(function (data) {
                    if (data && data.url) {
                        window.open(data.url, 'chat', 'width=800,height=600');
                        if (statusEl) statusEl.textContent = '';
                    } else throw new Error('No URL returned');
                })
                .catch(function (err) {
                    if (statusEl) statusEl.textContent = 'Error: ' + (err.message || 'Could not open chat');
                })
                .finally(function () { btn.disabled = false; });
        });
    }

    function initChat() {
        var messagesEl = document.getElementById('messages') || document.getElementById('chatMessages');
        var sendRow = document.getElementById('sendRow') || document.getElementById('chatSendRow');
        var msgInput = document.getElementById('msgInput') || document.getElementById('chatMsgInput');
        var sendBtn = document.getElementById('sendBtn') || document.getElementById('chatSendBtn');
        var statusEl = document.getElementById('chatMessages') ? document.getElementById('chatStatus') : document.getElementById('status');
        var loggedInEl = document.getElementById('chatMessages') ? document.getElementById('chatLoggedIn') : document.getElementById('loggedInAs');

        function setStatus(msg, className) {
            if (statusEl) {
                statusEl.textContent = msg;
                statusEl.className = className || 'info';
            }
        }

        function appendMessage(text, isSelf) {
            if (!messagesEl) return;
            var p = document.createElement('p');
            p.textContent = text;
            p.style.fontWeight = isSelf ? 'bold' : 'normal';
            messagesEl.appendChild(p);
            messagesEl.scrollTop = messagesEl.scrollHeight;
        }

        function loadConfig() {
            return fetch(API_URL + '/api/chat/config', { credentials: 'include' })
                .then(function (r) {
                    if (!r.ok) throw new Error('Config failed: ' + r.status);
                    return r.json();
                });
        }

        function loadToken() {
            return fetch(API_URL + '/api/chat/token', {
                method: 'POST',
                headers: { 'Content-Type': 'application/json' },
                credentials: 'include',
                body: JSON.stringify({})
            }).then(function (r) {
                if (!r.ok) {
                    return r.json().then(function (d) {
                        var msg = d.error || 'Token failed';
                        if (d.detail) msg += ' (' + d.detail + ')';
                        throw new Error(msg);
                    });
                }
                return r.json();
            });
        }

        function loadRecipient() {
            return fetch(API_URL + '/api/chat/recipient', { credentials: 'include' })
                .then(function (r) {
                    if (!r.ok) return r.json().then(function (d) { throw new Error(d.error || 'Recipient failed'); });
                    return r.json();
                });
        }

        function getRecipientFromUrl() {
            var params = new URLSearchParams(window.location.search);
            var sb = (params.get('sendbird_user_id') || '').trim();
            var name = (params.get('display_name') || '').trim();
            if (sb) return Promise.resolve({ sendbird_user_id: sb, name: name || sb });
            return loadRecipient();
        }

        if (!messagesEl) return;

        setStatus('Fetching config and token…', 'info');
        Promise.all([loadConfig(), loadToken(), getRecipientFromUrl()])
            .then(function (results) {
                var config = results[0];
                var tokenData = results[1];
                var recipientData = results[2];
                var sendbirdUserId = tokenData.sendbird_user_id;
                if (!config.app_id || !sendbirdUserId || !tokenData.session_token) {
                    setStatus('Missing app_id, sendbird_user_id or session_token.', 'error');
                    return;
                }
                if (!recipientData || !recipientData.sendbird_user_id) {
                    setStatus('No recipient configured (SENDBIRD_DEFAULT_RECIPIENT_ID).', 'error');
                    return;
                }
                if (loggedInEl) loggedInEl.textContent = 'Logged in as ' + (tokenData.display_name || tokenData.sendbird_user_id || 'You') + '. ';
                setStatus('Initializing Sendbird…', 'info');
                return initSendbird(config.app_id, sendbirdUserId, tokenData.session_token, recipientData.sendbird_user_id);
            })
            .catch(function (err) {
                setStatus('Error: ' + (err && err.message ? err.message : String(err)), 'error');
            });

        function initSendbird(appId, sendbirdUserId, sessionToken, recipientSendbirdUserId) {
            var sdkUrl = 'https://cdn.jsdelivr.net/npm/@sendbird/chat@4/+esm';
            var groupUrl = 'https://cdn.jsdelivr.net/npm/@sendbird/chat@4/groupChannel/+esm';
            var sb = null;
            var currentChannel = null;

            return import(sdkUrl)
                .then(function (chatMod) {
                    return import(groupUrl).then(function (groupMod) {
                        var SendbirdChat = chatMod.default;
                        sb = SendbirdChat.init({
                            appId: appId,
                            modules: [new groupMod.GroupChannelModule()]
                        });
                        return sb.connect(sendbirdUserId, sessionToken);
                    });
                })
                .then(function () {
                    setStatus((sendbirdUserId || 'You') + ' is opening conversation with ' + (recipientSendbirdUserId || 'recipient') + '…', 'success');
                    return sb.groupChannel.createChannel({
                        invitedUserIds: [recipientSendbirdUserId],
                        isDistinct: true,
                        name: 'Family'
                    });
                })
                .catch(function (err) {
                    if (err && err.code === 800220) {
                        return sb.groupChannel.getChannel(recipientSendbirdUserId);
                    }
                    throw err;
                })
                .then(function (channel) {
                    currentChannel = channel;
                    if (sendRow) sendRow.style.display = 'flex';
                    return channel.getMessageList ? channel.getMessageList({ prevResultSize: 50, nextResultSize: 0 }) : channel.getMessagesByTimestamp(0, { prevResultSize: 50, nextResultSize: 0 });
                })
                .then(function (list) {
                    var messages = (list && list.messages) ? list.messages : (list || []);
                    for (var i = 0; i < messages.length; i++) {
                        var m = messages[i];
                        var sender = (m.sender && m.sender.nickname) ? m.sender.nickname : ((m.sender && m.sender.userId) || '?');
                        appendMessage(sender + ': ' + (m.message || ''), m.sender && m.sender.userId === sb.currentUser.userId);
                    }
                    setStatus('1:1 chat. You can send messages below.', 'success');

                    if (sendBtn) sendBtn.addEventListener('click', sendMessage);
                    if (msgInput) msgInput.addEventListener('keydown', function (e) { if (e.key === 'Enter') sendMessage(); });
                })
                .catch(function (err) {
                    setStatus('Channel error: ' + (err && err.message ? err.message : String(err)), 'error');
                });

            function sendMessage() {
                var text = (msgInput && msgInput.value || '').trim();
                if (!text || !currentChannel) return;
                sendBtn.disabled = true;
                currentChannel.sendUserMessage({ message: text })
                    .onSucceeded(function () {
                        appendMessage('You: ' + text, true);
                        if (msgInput) msgInput.value = '';
                    })
                    .onFailed(function (err) {
                        setStatus('Send failed: ' + (err && err.message || err), 'error');
                    })
                    .finally(function () { sendBtn.disabled = false; });
            }
        }
    }

    if (document.readyState === 'loading') {
        document.addEventListener('DOMContentLoaded', init);
    } else {
        init();
    }
})();
