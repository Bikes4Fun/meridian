/**
 * Sendbird Chat PoC – minimal client.
 * Uses session: GET /api/chat/config, POST /api/chat/token, then Sendbird JS SDK to connect and chat.
 * API_URL is replaced by the server (same as checkin.js).
 */
(function () {
    'use strict';

    var _u = '__API_URL__';
    var API_URL = (_u.startsWith('http') ? _u : '');

    var statusEl = document.getElementById('status');
    var messagesEl = document.getElementById('messages');
    var sendRow = document.getElementById('sendRow');
    var msgInput = document.getElementById('msgInput');
    var sendBtn = document.getElementById('sendBtn');

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
            if (!r.ok) return r.json().then(function (d) { throw new Error(d.error || 'Token failed'); });
            return r.json();
        });
    }

    function run() {
        setStatus('Fetching config and token…', 'info');
        Promise.all([loadConfig(), loadToken()])
            .then(function (results) {
                var config = results[0];
                var tokenData = results[1];
                if (!config.app_id || !tokenData.user_id || !tokenData.session_token) {
                    setStatus('Missing app_id, user_id or session_token.', 'error');
                    return;
                }
                setStatus('Initializing Sendbird…', 'info');
                return initSendbird(config.app_id, tokenData.user_id, tokenData.session_token);
            })
            .then(function () {
                setStatus('Connected. Loading or creating channel…', 'success');
            })
            .catch(function (err) {
                setStatus('Error: ' + (err && err.message ? err.message : String(err)), 'error');
            });
    }

    function initSendbird(appId, userId, sessionToken) {
        // Load Sendbird SDK from CDN (ESM). Need base + groupChannel + openChannel for open channel.
        var sdkUrl = 'https://cdn.jsdelivr.net/npm/@sendbird/chat@4/+esm';
        var groupUrl = 'https://cdn.jsdelivr.net/npm/@sendbird/chat@4/groupChannel/+esm';
        var openUrl = 'https://cdn.jsdelivr.net/npm/@sendbird/chat@4/openChannel/+esm';
        var sb = null;
        var currentChannel = null;
        var OPEN_CHANNEL_URL = 'meridian-poc-open';

        return import(sdkUrl)
            .then(function (chatMod) {
                return Promise.all([import(groupUrl), import(openUrl)]).then(function (mods) {
                    var GroupChannelModule = mods[0].GroupChannelModule;
                    var OpenChannelModule = mods[1].OpenChannelModule;
                    var SendbirdChat = chatMod.default;
                    sb = SendbirdChat.init({
                        appId: appId,
                        modules: [new GroupChannelModule(), new OpenChannelModule()]
                    });
                    return sb.connect(userId, sessionToken);
                });
            })
            .then(function () {
                setStatus('Connected as ' + userId + '. Opening channel…', 'success');
                return sb.openChannel.getChannel(OPEN_CHANNEL_URL);
            })
            .catch(function (err) {
                if (err && (err.code === 800220 || (err.message && err.message.indexOf('channel') !== -1))) {
                    return sb.openChannel.createChannel({
                        name: 'Meridian PoC',
                        channelUrl: OPEN_CHANNEL_URL
                    });
                }
                throw err;
            })
            .then(function (channel) {
                currentChannel = channel;
                return channel.enter();
            })
            .then(function () {
                sendRow.style.display = 'flex';
                return currentChannel.getMessageList({ prevResultSize: 50, nextResultSize: 0 });
            })
            .then(function (list) {
                var messages = list.messages || [];
                for (var i = 0; i < messages.length; i++) {
                    var m = messages[i];
                    var sender = (m.sender && m.sender.nickname) ? m.sender.nickname : ((m.sender && m.sender.userId) || '?');
                    appendMessage(sender + ': ' + (m.message || ''), m.sender && m.sender.userId === sb.currentUser.userId);
                }
                setStatus('In channel. You can send messages below.', 'success');

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
                    appendMessage('You: ' + text, true);
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
