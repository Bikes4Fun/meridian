/**
 * Chatapp client – proxy approach. No Sendbird SDK.
 * Uses /api/chat/send and /api/chat/messages (polling).
 * Used by webapp, kiosk, mobile.
 * API_URL replaced at build (__API_URL__).
 */
(function () {
    'use strict';

    var _u = '__API_URL__';
    var API_URL = (_u.startsWith('http') ? _u : '').replace(/\/$/, '');

    var channelUrl = null;
    var mySendbirdUserId = null;
    var seenMessageIds = {};
    var pollInterval = null;

    function api(path) {
        return (API_URL || window.location.origin).replace(/\/$/, '') + path;
    }

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

    function renderMessages(data) {
        var list = Array.isArray(data) ? data : (data && data.messages ? data.messages : []);
        for (var i = 0; i < list.length; i++) {
            var m = list[i];
            var mid = m.message_id || m.id;
            if (mid && seenMessageIds[mid]) continue;
            if (mid) seenMessageIds[mid] = true;
            var sender = (m.user && (m.user.nickname || m.user.user_id))
                || (m.sender && (m.sender.nickname || m.sender.userId)) || '?';
            var uid = (m.user && m.user.user_id) || (m.sender && m.sender.userId);
            var text = m.message || '';
            if (!text) continue;
            appendMessage(sender + ': ' + text, uid === mySendbirdUserId);
        }
    }

    function loadToken() {
        return fetch(api('/api/chat/token'), {
            method: 'POST',
            headers: { 'Content-Type': 'application/json' },
            credentials: 'include',
            body: '{}'
        }).then(function (r) {
            if (r.status === 401) throw new Error('Not logged in.');
            return r.json();
        });
    }

    function getRecipientFromUrl() {
        var params = new URLSearchParams(window.location.search);
        var sb = (params.get('sendbird_user_id') || '').trim();
        var name = (params.get('display_name') || '').trim();
        if (sb) return Promise.resolve({ sendbird_user_id: sb, name: name || sb });
        return fetch(api('/api/chat/recipient'), { credentials: 'include' })
            .then(function (r) {
                if (!r.ok) throw new Error('Could not load recipient.');
                return r.json();
            });
    }

    function createChannel(recipientSendbirdUserId) {
        var body = {};
        if (recipientSendbirdUserId) body.recipient_sendbird_user_id = recipientSendbirdUserId;
        return fetch(api('/api/chat/channel'), {
            method: 'POST',
            headers: { 'Content-Type': 'application/json' },
            credentials: 'include',
            body: JSON.stringify(body)
        }).then(function (r) {
            return r.json().then(function (d) {
                if (!r.ok) throw new Error((d && d.error) || 'Create channel failed');
                return d;
            });
        });
    }

    function pollMessages() {
        if (!channelUrl) return;
        fetch(api('/api/chat/messages?channel_url=' + encodeURIComponent(channelUrl)), { credentials: 'include' })
            .then(function (r) { return r.json(); })
            .then(function (data) {
                if (!data.error) renderMessages(data.messages || data);
            })
            .catch(function () {});
    }

    function sendMessage() {
        var msgInput = document.getElementById('msgInput');
        var sendBtn = document.getElementById('sendBtn');
        var text = (msgInput && msgInput.value || '').trim();
        if (!text || !channelUrl) return;
        if (sendBtn) sendBtn.disabled = true;
        fetch(api('/api/chat/send'), {
            method: 'POST',
            headers: { 'Content-Type': 'application/json' },
            credentials: 'include',
            body: JSON.stringify({ channel_url: channelUrl, message: text })
        })
            .then(function (r) { return r.json(); })
            .then(function (data) {
                if (data.error) throw new Error(data.detail || data.error);
                appendMessage('You: ' + text, true);
                if (msgInput) msgInput.value = '';
            })
            .catch(function (err) {
                setStatus('Send failed: ' + (err && err.message || err), 'error');
            })
            .finally(function () { if (sendBtn) sendBtn.disabled = false; });
    }

    function init() {
        var messagesEl = document.getElementById('messages');
        if (!messagesEl) return;

        var sendRow = document.getElementById('sendRow');
        var msgInput = document.getElementById('msgInput');
        var sendBtn = document.getElementById('sendBtn');

        setStatus('Loading…', 'info');

        Promise.all([loadToken(), getRecipientFromUrl()])
            .then(function (results) {
                var tokenData = results[0];
                var recipientData = results[1];

                if (!tokenData.sendbird_user_id) {
                    setStatus(tokenData.error || 'No Sendbird user linked.', 'error');
                    return;
                }
                if (!recipientData || !recipientData.sendbird_user_id) {
                    setStatus('No recipient configured.', 'error');
                    return;
                }

                mySendbirdUserId = tokenData.sendbird_user_id;
                var youDisplay = tokenData.display_name || mySendbirdUserId;
                var themDisplay = recipientData.name || recipientData.sendbird_user_id;
                var headerEl = document.getElementById('chatHeader');
                var youName = document.getElementById('youName');
                var themName = document.getElementById('themName');
                if (headerEl) headerEl.textContent = 'Chat with ' + themDisplay;
                if (youName) youName.textContent = youDisplay;
                if (themName) themName.textContent = themDisplay;
                if (document.title === 'Family Chat') document.title = 'Chat with ' + themDisplay;

                setStatus('Opening conversation…', 'info');
                return createChannel(recipientData.sendbird_user_id)
                    .then(function (data) {
                        if (!data.channel_url) throw new Error('No channel_url in response');
                        channelUrl = data.channel_url;
                        return fetch(api('/api/chat/messages?channel_url=' + encodeURIComponent(channelUrl)), { credentials: 'include' })
                            .then(function (r) { return r.json(); });
                    })
                    .then(function (data) {
                        if (data.error) throw new Error(data.error);
                        renderMessages(data.messages || data);
                        setStatus('Connected. Say hello!', 'success');
                        if (sendRow) sendRow.style.display = 'flex';
                        if (sendBtn) sendBtn.addEventListener('click', sendMessage);
                        if (msgInput) msgInput.addEventListener('keydown', function (e) { if (e.key === 'Enter') sendMessage(); });
                        pollInterval = setInterval(pollMessages, 2500);
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
