/**
 * Chatapp client – proxy approach. No Sendbird SDK.
 * Uses /api/chat/send and /api/chat/messages (polling).
 * Used by webapp, kiosk, mobile.
 * API_URL replaced at build (http://192.168.1.171:8000).
 */
(function () {
    'use strict';

    var _u = 'http://192.168.1.171:8000';
    var API_URL = (_u.startsWith('http') ? _u : '').replace(/\/$/, '');

    var channelUrl = null;
    var mySendbirdUserId = null;
    var seenMessageIds = {};
    var pollInterval = null;
    var currentCall = null;
    var callSdkReady = false;
    var callRecipientId = null;

    function logCallLifecycle(eventName, details) {
        var payload = {
            event: eventName,
            ts: new Date().toISOString(),
            page: window.location.pathname + window.location.search,
            visibility: document.visibilityState,
            online: !!navigator.onLine
        };
        if (details && typeof details === 'object') {
            for (var k in details) {
                if (Object.prototype.hasOwnProperty.call(details, k)) payload[k] = details[k];
            }
        }
        try {
            console.info('[MeridianCall]', JSON.stringify(payload));
        } catch (_err) {}
        try {
            if (window.webkit
                && window.webkit.messageHandlers
                && window.webkit.messageHandlers.meridianLogger
                && typeof window.webkit.messageHandlers.meridianLogger.postMessage === 'function') {
                window.webkit.messageHandlers.meridianLogger.postMessage(payload);
            }
        } catch (_err2) {}
        if (eventName === 'sendbird_websocket_connected'
            || eventName === 'sendbird_call_setup_failed'
            || eventName === 'calls_sdk_missing') {
            try {
                fetch(api('/api/calls/socket-event'), {
                    method: 'POST',
                    headers: { 'Content-Type': 'application/json' },
                    credentials: 'include',
                    body: JSON.stringify(payload)
                });
            } catch (_err3) {}
        }
    }

    function api(path) {
        return (API_URL || window.location.origin).replace(/\/$/, '') + path;
    }

    function setStatus(msg, className) {
        var el = document.getElementById('status');
        if (el) { el.textContent = msg; el.className = className || 'info'; }
    }

    function setCallStatus(msg, className) {
        var el = document.getElementById('callStatus');
        if (!el) return;
        el.style.display = 'block';
        el.textContent = msg;
        el.className = className || 'info';
    }

    function attachDirectCallHandlers(call) {
        if (!call) return;
        currentCall = call;
        call.onConnected = function () {
            logCallLifecycle('direct_call_connected', {
                call_id: (call.callId || call.id || '').toString(),
                recipient_sendbird_user_id: callRecipientId || ''
            });
            setCallStatus('Call connected.', 'success');
            var endBtn = document.getElementById('endCallBtn');
            if (endBtn) endBtn.disabled = false;
        };
        call.onEnded = function () {
            logCallLifecycle('direct_call_ended', {
                call_id: (call.callId || call.id || '').toString(),
                recipient_sendbird_user_id: callRecipientId || ''
            });
            currentCall = null;
            var endBtn = document.getElementById('endCallBtn');
            if (endBtn) endBtn.disabled = true;
            setCallStatus('Call ended.', 'info');
        };
    }

    function initCalls(tokenData, recipientData) {
        var SendBirdCall = window.SendBirdCall;
        logCallLifecycle('calls_init_start', {
            self_sendbird_user_id: tokenData && tokenData.sendbird_user_id || '',
            recipient_sendbird_user_id: recipientData && recipientData.sendbird_user_id || ''
        });
        if (!SendBirdCall) {
            logCallLifecycle('calls_sdk_missing', {
                sdk_script: 'https://cdn.jsdelivr.net/npm/sendbird-calls@1.12.2/SendBirdCall.min.js'
            });
            setCallStatus('Calls SDK not loaded.', 'error');
            return;
        }
        fetch(api('/api/chat/config'), { credentials: 'include' })
            .then(function (r) { return r.json(); })
            .then(function (cfg) {
                if (!cfg || !cfg.app_id) throw new Error('No app_id in config.');
                callRecipientId = recipientData.sendbird_user_id;

                logCallLifecycle('sendbird_call_init', {
                    app_id: cfg.app_id,
                    self_sendbird_user_id: tokenData.sendbird_user_id || '',
                    recipient_sendbird_user_id: callRecipientId || ''
                });
                SendBirdCall.init(cfg.app_id);
                return SendBirdCall.useMedia().then(function () {
                    logCallLifecycle('sendbird_call_authenticate_start', {
                        app_id: cfg.app_id,
                        self_sendbird_user_id: tokenData.sendbird_user_id || ''
                    });
                    return new Promise(function (resolve, reject) {
                        SendBirdCall.authenticate({
                            userId: tokenData.sendbird_user_id,
                            accessToken: tokenData.session_token || ''
                        }, function (result, error) {
                            if (error) {
                                logCallLifecycle('sendbird_call_authenticate_error', {
                                    app_id: cfg.app_id,
                                    self_sendbird_user_id: tokenData.sendbird_user_id || '',
                                    error: (error && error.message) || String(error)
                                });
                                reject(error);
                            } else {
                                logCallLifecycle('sendbird_call_authenticated', {
                                    app_id: cfg.app_id,
                                    self_sendbird_user_id: tokenData.sendbird_user_id || ''
                                });
                                resolve(result);
                            }
                        });
                    });
                }).then(function () {
                    logCallLifecycle('sendbird_websocket_connect_start', {
                        app_id: cfg.app_id,
                        self_sendbird_user_id: tokenData.sendbird_user_id || '',
                        transport: 'wss',
                        remote_port_hint: 443
                    });
                    return SendBirdCall.connectWebSocket();
                }).then(function () {
                    logCallLifecycle('sendbird_websocket_connected', {
                        app_id: cfg.app_id,
                        self_sendbird_user_id: tokenData.sendbird_user_id || '',
                        recipient_sendbird_user_id: callRecipientId || '',
                        transport: 'wss',
                        remote_port_hint: 443,
                        local_port_note: 'managed by SDK/OS (ephemeral)'
                    });
                    SendBirdCall.addListener('chat-client-call-listener', {
                        onRinging: function (call) {
                            logCallLifecycle('sendbird_on_ringing', {
                                call_id: (call && (call.callId || call.id) || '').toString(),
                                from_sendbird_user_id: (call && call.caller && (call.caller.userId || call.caller.user_id) || '').toString(),
                                to_sendbird_user_id: callRecipientId || ''
                            });
                            attachDirectCallHandlers(call);
                            call.accept({
                                callOption: {
                                    localMediaView: document.getElementById('localVideo'),
                                    remoteMediaView: document.getElementById('remoteVideo'),
                                    audioEnabled: true,
                                    videoEnabled: true
                                }
                            });
                            setCallStatus('Incoming call accepted.', 'info');
                        }
                    });
                    callSdkReady = true;
                    var callRow = document.getElementById('callRow');
                    var callVideos = document.getElementById('callVideos');
                    if (callRow) callRow.style.display = 'flex';
                    if (callVideos) callVideos.style.display = 'flex';
                    setCallStatus('Call ready. Tap Start video call.', 'success');
                });
            })
            .catch(function (err) {
                logCallLifecycle('sendbird_call_setup_failed', {
                    error: (err && err.message) || String(err),
                    self_sendbird_user_id: tokenData && tokenData.sendbird_user_id || '',
                    recipient_sendbird_user_id: recipientData && recipientData.sendbird_user_id || ''
                });
                setCallStatus('Call setup failed: ' + (err && err.message || err), 'error');
            });
    }

    function startVideoCall() {
        if (!callSdkReady || !callRecipientId) {
            setCallStatus('Call is not ready yet.', 'error');
            return;
        }
        if (currentCall) {
            setCallStatus('Already in a call.', 'info');
            return;
        }
        var SendBirdCall = window.SendBirdCall;
        var call = SendBirdCall.dial({
            userId: callRecipientId,
            isVideoCall: true,
            callOption: {
                localMediaView: document.getElementById('localVideo'),
                remoteMediaView: document.getElementById('remoteVideo'),
                audioEnabled: true,
                videoEnabled: true
            }
        }, function (dialedCall, error) {
            if (error) {
                setCallStatus('Dial failed: ' + (error && error.message || error), 'error');
                return;
            }
            attachDirectCallHandlers(dialedCall);
            setCallStatus('Calling…', 'info');
        });
        attachDirectCallHandlers(call);
    }

    function endCurrentCall() {
        if (!currentCall) return;
        currentCall.end();
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
        var startVideoCallBtn = document.getElementById('startVideoCallBtn');
        var endCallBtn = document.getElementById('endCallBtn');

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
                initCalls(tokenData, recipientData);
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
                        if (startVideoCallBtn) startVideoCallBtn.addEventListener('click', startVideoCall);
                        if (endCallBtn) endCallBtn.addEventListener('click', endCurrentCall);
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
