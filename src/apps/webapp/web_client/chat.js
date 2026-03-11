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

    function run() {
        setStatus('Fetching config and token…', 'info');
        Promise.all([loadConfig(), loadToken()])
            .then(function (results) {
                var config = results[0];
                var tokenData = results[1];
                if (!config.app_id || !tokenData.user_id || !tokenData.session_token || !tokenData.chat_with_user_id) {
                    setStatus('Missing app_id, user_id, session_token or chat_with_user_id.', 'error');
                    return;
                }
                setStatus('Initializing Sendbird…', 'info');
                return initSendbird(config.app_id, tokenData.user_id, tokenData.session_token, tokenData.chat_with_user_id);
            })
            .then(function () {
                setStatus('Connected. Loading or creating channel…', 'success');
            })
            .catch(function (err) {
                setStatus('Error: ' + (err && err.message ? err.message : String(err)), 'error');
            });
    }

    function initSendbird(appId, userId, sessionToken, chatWithUserId) {
        // 1:1 chat: group channel with exactly two users (patient and e.g. daughter). No open channel.
        var sdkUrl = 'https://cdn.jsdelivr.net/npm/@sendbird/chat@4/+esm';
        var groupUrl = 'https://cdn.jsdelivr.net/npm/@sendbird/chat@4/groupChannel/+esm';
        var sb = null;
        var currentChannel = null;

        return import(sdkUrl)
            .then(function (chatMod) {
                return import(groupUrl).then(function (groupMod) {
                    var SendbirdChat = chatMod.default;
                    var GroupChannelModule = groupMod.GroupChannelModule;
                    sb = SendbirdChat.init({
                        appId: appId,
                        modules: [new GroupChannelModule()]
                    });
                    return sb.connect(userId, sessionToken);
                });
            })
            .then(function () {
                setStatus('Connected. Opening 1:1 chat with ' + chatWithUserId + '…', 'success');
                return sb.groupChannel.createChannel({
                    invitedUserIds: [chatWithUserId],
                    isDistinct: true,
                    name: 'Family'
                });
            })
            .then(function (channel) {
                currentChannel = channel;
                sendRow.style.display = 'flex';
                return channel.getMessageList({ prevResultSize: 50, nextResultSize: 0 });
            })
            .then(function (list) {
                var messages = list.messages || [];
                for (var i = 0; i < messages.length; i++) {
                    var m = messages[i];
                    var sender = (m.sender && m.sender.nickname) ? m.sender.nickname : ((m.sender && m.sender.userId) || '?');
                    appendMessage(sender + ': ' + (m.message || ''), m.sender && m.sender.userId === sb.currentUser.userId);
                }
                setStatus('Chat with family. You can send messages below.', 'success');

                sendBtn.addEventListener('click', sendMessage);
                msgInput.addEventListener('keydown', function (e) { if (e.key === 'Enter') sendMessage(); });
            })
            .catch(function (err) {
                setStatus('Chat error: ' + (err && err.message ? err.message : String(err)), 'error');
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
