/**
 * Chatapp client – chat only. Used by webapp, kiosk, mobile.
 * API_URL replaced at build (__API_URL__).
 */
(function () {
    'use strict';

    var _u = '__API_URL__';
    var API_URL = (_u.startsWith('http') ? _u : '');

    function setStatus(msg, className) {
        var el = document.getElementById('status');
        if (el) { el.textContent = msg; el.className = className || 'info'; }
    }

    function appendMessage(text, isSelf) {
        var el = document.getElementById('messages');
        if (!el) return;
        var p = document.createElement('p');
        p.textContent = text;
        p.style.fontWeight = isSelf ? 'bold' : 'normal';
        el.appendChild(p);
        el.scrollTop = el.scrollHeight;
    }

    function loadConfig() {
        return fetch((API_URL || '').replace(/\/$/, '') + '/api/chat/config', { credentials: 'include' })
            .then(function (r) { if (!r.ok) throw new Error('Config failed: ' + r.status); return r.json(); });
    }

    function loadToken() {
        return fetch((API_URL || '').replace(/\/$/, '') + '/api/chat/token', {
            method: 'POST',
            headers: { 'Content-Type': 'application/json' },
            credentials: 'include',
            body: JSON.stringify({})
        }).then(function (r) {
            if (!r.ok) return r.json().then(function (d) {
                var msg = (d && d.error) || 'Token failed';
                if (d && d.detail) msg += ' (' + d.detail + ')';
                throw new Error(msg);
            });
            return r.json();
        });
    }

    function loadRecipient() {
        return fetch((API_URL || '').replace(/\/$/, '') + '/api/chat/recipient', { credentials: 'include' })
            .then(function (r) {
                if (!r.ok) return r.json().then(function (d) { throw new Error((d && d.error) || 'Recipient failed'); });
                return r.json();
            });
    }

    function createChannel(recipientSendbirdUserId) {
        var body = {};
        if (recipientSendbirdUserId) body.recipient_sendbird_user_id = recipientSendbirdUserId;
        return fetch((API_URL || '').replace(/\/$/, '') + '/api/chat/channel', {
            method: 'POST',
            headers: { 'Content-Type': 'application/json' },
            credentials: 'include',
            body: JSON.stringify(body)
        }).then(function (r) {
            if (!r.ok) return r.json().then(function (d) { throw new Error((d && d.error) || (d && d.detail) || 'Create channel failed'); });
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

    function initSendbird(appId, sendbirdUserId, sessionTokenVal, channelUrl, recipientName, tokenData) {
        var sdkUrl = 'https://cdn.jsdelivr.net/npm/@sendbird/chat@4/+esm';
        var groupUrl = 'https://cdn.jsdelivr.net/npm/@sendbird/chat@4/groupChannel/+esm';
        var sb = null;
        var currentChannel = null;
        var sendRow = document.getElementById('sendRow');
        var msgInput = document.getElementById('msgInput');
        var sendBtn = document.getElementById('sendBtn');
        var youName = document.getElementById('youName');
        var themName = document.getElementById('themName');
        var headerEl = document.getElementById('chatHeader');
        var youDisplay = (tokenData && tokenData.display_name) ? tokenData.display_name : (sendbirdUserId || 'You');
        var themDisplay = recipientName || '…';
        if (youName) youName.textContent = youDisplay;
        if (themName) themName.textContent = themDisplay;
        if (headerEl) headerEl.textContent = 'Chat with ' + themDisplay;
        if (document.title === 'Family Chat') document.title = 'Chat with ' + themDisplay;
        setStatus('Initializing Sendbird…', 'info');

        return import(sdkUrl)
            .then(function (chatMod) {
                return import(groupUrl).then(function (groupMod) {
                    var SendbirdChat = chatMod.default;
                    sb = SendbirdChat.init({
                        appId: appId,
                        modules: [new groupMod.GroupChannelModule()]
                    });
                    return sb.connect(sendbirdUserId, sessionTokenVal);
                });
            })
            .catch(function (err) { err._step = 'connect'; throw err; })
            .then(function () {
                setStatus((recipientName || 'Opening conversation') + '…', 'success');
                return sb.groupChannel.getChannel(channelUrl);
            })
            .catch(function (err) { if (!err._step) err._step = 'getChannel'; throw err; })
            .then(function (channel) {
                currentChannel = channel;
                if (sendRow) sendRow.style.display = 'flex';
                return channel.getMessageList ? channel.getMessageList({ prevResultSize: 50, nextResultSize: 0 }) : channel.getMessagesByTimestamp(0, { prevResultSize: 50, nextResultSize: 0 });
            })
            .catch(function (err) { if (!err._step) err._step = 'getMessages'; throw err; })
            .then(function (list) {
                var messages = (list && list.messages) ? list.messages : (list || []);
                for (var i = 0; i < messages.length; i++) {
                    var m = messages[i];
                    var sender = (m.sender && m.sender.nickname) ? m.sender.nickname : ((m.sender && m.sender.userId) || '?');
                    appendMessage(sender + ': ' + (m.message || ''), m.sender && m.sender.userId === sb.currentUser.userId);
                }
                setStatus('1:1 chat. You can send messages below.', 'success');

                function sendMessage() {
                    var text = (msgInput && msgInput.value || '').trim();
                    if (!text || !currentChannel) return;
                    if (sendBtn) sendBtn.disabled = true;
                    currentChannel.sendUserMessage({ message: text })
                        .onSucceeded(function () {
                            appendMessage('You: ' + text, true);
                            if (msgInput) msgInput.value = '';
                        })
                        .onFailed(function (err) {
                            setStatus('Send failed: ' + (err && err.message || err), 'error');
                        })
                        .finally(function () { if (sendBtn) sendBtn.disabled = false; });
                }
                if (sendBtn) sendBtn.addEventListener('click', sendMessage);
                if (msgInput) msgInput.addEventListener('keydown', function (e) { if (e.key === 'Enter') sendMessage(); });
            })
            .catch(function (err) {
                var step = err && err._step ? err._step + ': ' : '';
                var msg = (err && err.message ? err.message : String(err));
                setStatus('Channel error: ' + step + msg, 'error');
            });
    }

    function init() {
        var messagesEl = document.getElementById('messages');
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
                    setStatus('No recipient configured.', 'error');
                    return;
                }
                var youDisplay = (tokenData.display_name) ? tokenData.display_name : (sendbirdUserId || 'You');
                var themDisplay = recipientData.name || recipientData.sendbird_user_id || '…';
                var headerEl = document.getElementById('chatHeader');
                var youName = document.getElementById('youName');
                var themName = document.getElementById('themName');
                if (headerEl) headerEl.textContent = 'Chat with ' + themDisplay;
                if (youName) youName.textContent = youDisplay;
                if (themName) themName.textContent = themDisplay;
                if (document.title === 'Family Chat') document.title = 'Chat with ' + themDisplay;
                setStatus('Creating channel…', 'info');
                return createChannel(recipientData.sendbird_user_id)
                    .then(function (data) {
                        var channelUrl = (data && data.channel_url) || '';
                        if (!channelUrl) throw new Error('No channel_url in response');
                        return initSendbird(config.app_id, sendbirdUserId, tokenData.session_token, channelUrl, recipientData.name, tokenData);
                    });
            })
            .catch(function (err) {
                setStatus('Error: ' + (err && err.message ? err.message : String(err)), 'error');
            });
    }

    if (document.readyState === 'loading') {
        document.addEventListener('DOMContentLoaded', init);
    } else {
        init();
    }
})();
