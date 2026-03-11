/**
 * Sendbird Chat PoC – minimal client.
 * Uses session: GET /api/chat/config, POST /api/chat/token, then Sendbird JS SDK to connect and chat.
 * API_URL is replaced by the server (same as checkin.js).
 */
(function () {
    'use strict';

    var _u = '__API_URL__';
    var API_URL = (_u.startsWith('http') ? _u : '');

    var embedded = !!document.getElementById('chatMessages');
    var statusEl = embedded ? document.getElementById('chatStatus') : document.getElementById('status');
    var messagesEl = document.getElementById('chatMessages') || document.getElementById('messages');
    var sendRow = document.getElementById('chatSendRow') || document.getElementById('sendRow');
    var msgInput = document.getElementById('chatMsgInput') || document.getElementById('msgInput');
    var sendBtn = document.getElementById('chatSendBtn') || document.getElementById('sendBtn');
    var contactsGridEl = document.getElementById('contactsGrid');

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
        if (embedded) {
            p.className = isSelf ? 'out' : 'in';
        } else {
            p.style.fontWeight = isSelf ? 'bold' : 'normal';
        }
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

    function loadSession() {
        return fetch(API_URL + '/api/session', { credentials: 'include' })
            .then(function (r) {
                if (!r.ok) throw new Error('Session failed');
                return r.json();
            });
    }

    function loadContacts(familyCircleId) {
        return fetch(API_URL + '/api/family_circles/' + encodeURIComponent(familyCircleId) + '/contacts', { credentials: 'include' })
            .then(function (r) {
                if (!r.ok) throw new Error('Contacts failed');
                return r.json();
            })
            .then(function (data) { return data.data || []; });
    }

    function loadRecipient() {
        return fetch(API_URL + '/api/chat/recipient', { credentials: 'include' })
            .then(function (r) {
                if (!r.ok) return r.json().then(function (d) { throw new Error(d.error || 'Recipient failed'); });
                return r.json();
            })
            .then(function (d) {
                return { sendbird_user_id: (d.sendbird_user_id || '').trim(), display_name: (d.name || d.sendbird_user_id || 'Contact').trim() };
            });
    }

    function renderContactsGrid(contacts) {
        if (!contactsGridEl) return;
        contactsGridEl.innerHTML = '';
        contacts.forEach(function (c) {
            var tile = document.createElement('div');
            tile.className = 'contact-tile';
            tile.setAttribute('data-sendbird-user-id', c.sendbird_user_id || '');
            tile.setAttribute('data-display-name', c.display_name || '');
            var nameEl = document.createElement('span');
            nameEl.className = 'name';
            nameEl.textContent = c.display_name || c.id || 'Contact';
            tile.appendChild(nameEl);
            tile.addEventListener('click', function () { onContactClick(c); });
            contactsGridEl.appendChild(tile);
        });
    }

    function onContactClick(contact) {
        var sendbirdUserId = (contact.sendbird_user_id || '').trim();
        if (!sendbirdUserId) {
            setStatus('Chat not available for ' + (contact.display_name || 'this contact') + '.', 'info');
            return;
        }
        setStatus('Connecting…', 'info');
        Promise.all([loadConfig(), loadToken()])
            .then(function (results) {
                var config = results[0];
                var tokenData = results[1];
                var loggedInEl = document.getElementById('loggedInAs');
                if (loggedInEl) loggedInEl.textContent = 'Logged in as ' + (tokenData.display_name || tokenData.sendbird_user_id || 'You') + '. ';
                if (!config.app_id || !tokenData.sendbird_user_id || !tokenData.session_token) {
                    setStatus('Missing app_id, sendbird_user_id or session_token.', 'error');
                    return;
                }
                setStatus('Opening chat with ' + (contact.display_name || sendbirdUserId) + '…', 'info');
                var chatLoggedIn = document.getElementById('chatLoggedIn');
                if (chatLoggedIn) chatLoggedIn.textContent = 'Logged in messaging as ' + (tokenData.display_name || tokenData.sendbird_user_id || '…');
                return initSendbird(config.app_id, tokenData.sendbird_user_id, tokenData.session_token, sendbirdUserId);
            })
            .catch(function (err) {
                setStatus('Error: ' + (err && err.message ? err.message : String(err)), 'error');
            });
    }

    function getQueryParams() {
        var params = {};
        var q = (window.location.search || '').replace(/^\?/, '').split('&');
        for (var i = 0; i < q.length; i++) {
            var kv = q[i].split('=');
            if (kv.length >= 2) params[decodeURIComponent(kv[0])] = decodeURIComponent(kv[1].replace(/\+/g, ' '));
        }
        return params;
    }

    function run() {
        if (!messagesEl) return;
        var q = getQueryParams();
        var presetSb = (q.sendbird_user_id || '').trim();
        var presetName = (q.display_name || '').trim();
        if (presetSb) {
            onContactClick({ sendbird_user_id: presetSb, display_name: presetName });
            return;
        }
        if (embedded) {
            setStatus('Loading…', 'info');
            loadSession().then(function (s) {
                var chatLoggedIn = document.getElementById('chatLoggedIn');
                if (chatLoggedIn && s && s.user_id) chatLoggedIn.textContent = 'Logged in messaging as ' + s.user_id + ' (resolving recipient…)';
            }).catch(function () {});
            loadRecipient()
                .then(function (contact) {
                    if (!contact.sendbird_user_id) {
                        setStatus('No chat recipient configured.', 'info');
                        return;
                    }
                    onContactClick(contact);
                })
                .catch(function (err) {
                    setStatus('Error: ' + (err && err.message ? err.message : String(err)), 'error');
                    loadSession().then(function (s) {
                        var chatLoggedIn = document.getElementById('chatLoggedIn');
                        if (chatLoggedIn && s && s.user_id) chatLoggedIn.textContent = 'Logged in messaging as ' + s.user_id;
                    }).catch(function () {});
                });
            return;
        }
        setStatus('Loading…', 'info');
        loadSession()
            .then(function (session) {
                var familyCircleId = session.family_circle_id;
                if (!familyCircleId) {
                    setStatus('Not in a family. Log in first.', 'error');
                    return;
                }
                // Webapp is logged in as Dylan (fm_005): open chat with patient (testpatient) directly.
                if (session.user_id === 'fm_005') {
                    var contactsSection = document.getElementById('contactsSection');
                    if (contactsSection) contactsSection.style.display = 'none';
                    onContactClick({ sendbird_user_id: 'testpatient', display_name: 'Marian Foster' });
                    return;
                }
                return loadContacts(familyCircleId).then(function (contacts) {
                    renderContactsGrid(contacts);
                    setStatus('Choose a contact to call.', 'success');
                });
            })
            .catch(function (err) {
                setStatus('Error: ' + (err && err.message ? err.message : String(err)), 'error');
            });
    }

    function initSendbird(appId, sendbirdUserId, sessionToken, recipientSendbirdUserId) {
        if (messagesEl) messagesEl.innerHTML = '';
        // 1:1 chat: distinct group channel between sender and recipient. No open channel.
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
                    var txt = (m.message || '').trim();
                    if (!txt) continue;
                    var isSelf = m.sender && m.sender.userId === sb.currentUser.userId;
                    var displayTxt = embedded ? txt : ((m.sender && m.sender.nickname) ? m.sender.nickname : ((m.sender && m.sender.userId) || '?')) + ': ' + txt;
                    appendMessage(displayTxt, isSelf);
                }
                setStatus(embedded ? '1:1 chat' : '1:1 chat. You can send messages below.', 'success');

                sendBtn.addEventListener('click', sendMessage);
                msgInput.addEventListener('keydown', function (e) { if (e.key === 'Enter') sendMessage(); });
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
                    appendMessage(embedded ? text : 'You: ' + text, true);
                    if (msgInput) msgInput.value = '';
                })
                .onFailed(function (err) {
                    setStatus('Send failed: ' + (err && err.message || err), 'error');
                })
                .finally(function () { sendBtn.disabled = false; });
        }
    }

    if (document.readyState === 'loading') {
        document.addEventListener('DOMContentLoaded', run);
    } else {
        run();
    }
})();
