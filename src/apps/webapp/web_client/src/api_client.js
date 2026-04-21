/**
 * Centralized webapp API client.
 * Features should only call these methods (no direct fetch).
 */
(function (global) {
    'use strict';

    var _u = '__API_URL__';
    var _base = normalizeApiBase(_u);
    var CLIENT_HEADER_NAME = 'X-Meridian-Client';
    var CLIENT_HEADER_VALUE = 'webapp-api-client';

    function normalizeApiBase(url) {
        var trimmed = String(url || '').trim();
        if (!trimmed || !trimmed.startsWith('http')) return '';
        try {
            var api = new URL(trimmed);
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
            return trimmed.replace(/\/$/, '');
        } catch (_err) {
            return '';
        }
    }

    function setBase(url) {
        _base = normalizeApiBase(url);
        return _base;
    }

    function base() {
        return _base || '';
    }

    function build(path) {
        var p = String(path || '');
        if (!p.startsWith('/')) p = '/' + p;
        return base() + p;
    }

    function buildUserPhotoUrl(userId) {
        return build('/api/users/' + encodeURIComponent(userId) + '/photo') + '?v=' + Date.now();
    }

    function buildEmergencyProfilePdfUrl(familyCircleId) {
        return build(
            '/api/family_circles/' +
                encodeURIComponent(familyCircleId) +
                '/emergency-profile/pdf'
        );
    }

    function buildCareRecipientDnrDocumentUrl(familyCircleId, careRecipientUserId) {
        return build(
            '/api/family_circles/' +
                encodeURIComponent(familyCircleId) +
                '/care-recipients/' +
                encodeURIComponent(careRecipientUserId) +
                '/dnr-document'
        );
    }

    function request(path, options) {
        var opts = options || {};
        var headers = Object.assign({}, opts.headers || {});
        headers[CLIENT_HEADER_NAME] = CLIENT_HEADER_VALUE;
        var finalOptions = {
            method: opts.method || 'GET',
            credentials: 'include',
            headers: headers
        };
        if (opts.body !== undefined) finalOptions.body = opts.body;
        return fetch(build(path), finalOptions).then(function (response) {
            return response.text().then(function (text) {
                var parsed = null;
                if (text) {
                    try {
                        parsed = JSON.parse(text);
                    } catch (_e) {
                        parsed = null;
                    }
                }
                if (!response.ok) {
                    var message =
                        (parsed && parsed.error) ||
                        ('Request failed (' + response.status + ')');
                    var error = new Error(message);
                    error.status = response.status;
                    error.body = parsed;
                    throw error;
                }
                return { status: response.status, body: parsed };
            });
        });
    }

    function get(path) {
        return request(path, { method: 'GET' });
    }

    function del(path) {
        return request(path, { method: 'DELETE' });
    }

    function postJson(path, payload) {
        return request(path, {
            method: 'POST',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify(payload || {})
        });
    }

    function putJson(path, payload) {
        return request(path, {
            method: 'PUT',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify(payload || {})
        });
    }

    function postForm(path, formData) {
        return request(path, { method: 'POST', body: formData });
    }

    var api = {
        configure: setBase,
        getBase: base,
        // Session/Auth
        getSession: function () { return get('/api/session'); },
        login: function (userId, familyCircleId) {
            return postJson('/api/login', {
                user_id: userId,
                family_circle_id: familyCircleId
            });
        },
        logout: function () { return postJson('/api/logout', {}); },
        // Check-ins
        createCheckin: function (familyCircleId, payload) {
            return postJson(
                '/api/family_circles/' + encodeURIComponent(familyCircleId) + '/create_checkin',
                payload
            );
        },
        // Emergency alert
        setEmergencyAlert: function (activated) {
            return postJson('/api/emergency/alert', { activated: !!activated });
        },
        // Contacts
        getContacts: function (familyCircleId) {
            return get('/api/family_circles/' + encodeURIComponent(familyCircleId) + '/contacts');
        },
        postContact: function (familyCircleId, payload) {
            return postJson(
                '/api/family_circles/' + encodeURIComponent(familyCircleId) + '/contacts',
                payload
            );
        },
        // Family permissions
        getFamilyMembers: function (familyCircleId) {
            return get('/api/family_circles/' + encodeURIComponent(familyCircleId) + '/family-members');
        },
        getPermissions: function (familyCircleId) {
            return get('/api/family_circles/' + encodeURIComponent(familyCircleId) + '/permissions');
        },
        setPermission: function (familyCircleId, payload) {
            return postJson(
                '/api/family_circles/' + encodeURIComponent(familyCircleId) + '/permissions',
                payload
            );
        },
        // Calendar
        listEventsForDate: function (familyCircleId, dateIso) {
            return get(
                '/api/family_circles/' +
                    encodeURIComponent(familyCircleId) +
                    '/calendar/events?date=' +
                    encodeURIComponent(dateIso)
            );
        },
        createEvent: function (familyCircleId, payload) {
            return postJson(
                '/api/family_circles/' + encodeURIComponent(familyCircleId) + '/calendar/events',
                payload
            );
        },
        updateEvent: function (familyCircleId, eventId, payload) {
            return putJson(
                '/api/family_circles/' +
                    encodeURIComponent(familyCircleId) +
                    '/calendar/events/' +
                    encodeURIComponent(eventId),
                payload
            );
        },
        deleteEvent: function (familyCircleId, eventId) {
            return del(
                '/api/family_circles/' +
                    encodeURIComponent(familyCircleId) +
                    '/calendar/events/' +
                    encodeURIComponent(eventId)
            );
        },
        // Medications
        getMedications: function (familyCircleId) {
            return get('/api/family_circles/' + encodeURIComponent(familyCircleId) + '/medications');
        },
        addMedication: function (familyCircleId, payload) {
            return postJson(
                '/api/family_circles/' + encodeURIComponent(familyCircleId) + '/medications',
                payload
            );
        },
        updateMedication: function (familyCircleId, medicationId, payload) {
            return putJson(
                '/api/family_circles/' +
                    encodeURIComponent(familyCircleId) +
                    '/medications/' +
                    encodeURIComponent(medicationId),
                payload
            );
        },
        deleteMedication: function (familyCircleId, medicationId) {
            return del(
                '/api/family_circles/' +
                    encodeURIComponent(familyCircleId) +
                    '/medications/' +
                    encodeURIComponent(medicationId)
            );
        },
        markMedicationTaken: function (familyCircleId, medicationId, timeSlot, taken) {
            return postJson(
                '/api/family_circles/' +
                    encodeURIComponent(familyCircleId) +
                    '/medications/' +
                    encodeURIComponent(medicationId) +
                    '/mark-taken',
                { time: timeSlot, taken: !!taken }
            );
        },
        // Emergency profile
        getEmergencyProfile: function (familyCircleId) {
            return get(
                '/api/family_circles/' + encodeURIComponent(familyCircleId) + '/emergency-profile'
            );
        },
        updateEmergencyProfile: function (familyCircleId, payload) {
            return putJson(
                '/api/family_circles/' + encodeURIComponent(familyCircleId) + '/emergency-profile',
                payload
            );
        },
        uploadCareRecipientPhoto: function (familyCircleId, careRecipientUserId, file) {
            var formData = new FormData();
            formData.append('photo', file);
            formData.append('care_recipient_user_id', careRecipientUserId);
            return postForm(
                '/api/family_circles/' +
                    encodeURIComponent(familyCircleId) +
                    '/care-recipient-photo',
                formData
            );
        },
        uploadCareRecipientDnrDocument: function (familyCircleId, careRecipientUserId, file) {
            var formData = new FormData();
            formData.append('document', file);
            formData.append('care_recipient_user_id', careRecipientUserId);
            return postForm(
                '/api/family_circles/' +
                    encodeURIComponent(familyCircleId) +
                    '/care-recipient-dnr-document',
                formData
            );
        },
        getUserPhotoUrl: function (userId) {
            return buildUserPhotoUrl(userId);
        },
        getEmergencyProfilePdfUrl: function (familyCircleId) {
            return buildEmergencyProfilePdfUrl(familyCircleId);
        },
        getCareRecipientDnrDocumentUrl: function (familyCircleId, careRecipientUserId) {
            return buildCareRecipientDnrDocumentUrl(familyCircleId, careRecipientUserId);
        }
    };

    global.meridianApiClient = api;
})(typeof window !== 'undefined' ? window : this);
