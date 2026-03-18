/**
 * Events page – populate pageEvents when navigated to.
 * Exposes MeridianEvents.init(apiUrl, familyCircleId, showStatus) for app.js to call.
 */
(function () {
    'use strict';

    var _apiUrl = '';
    var _familyCircleId = null;
    var _showStatus = function () {};
    var _initialized = false;

    function buildEventsHTML() {
        return '<h2>Events</h2>' +
            '<p style="font-size: 14px; color: #666;">Today\'s schedule</p>' +
            '<div id="eventsList">Loading…</div>' +
            '<button id="addEventBtn" type="button">Add Event</button>' +
            '<div id="eventFormModal">' +
            '<div class="modal-inner">' +
            '<h3 id="eventFormTitle">Add Event</h3>' +
            '<form id="eventForm">' +
            '<input type="text" id="eventTitle" placeholder="Title" required class="event-input">' +
            '<input type="date" id="eventDate" required class="event-input">' +
            '<input type="time" id="eventStartTime" required class="event-input">' +
            '<input type="time" id="eventEndTime" placeholder="End time (optional)" class="event-input">' +
            '<input type="text" id="eventLocation" placeholder="Location (optional)" class="event-input">' +
            '<textarea id="eventDescription" placeholder="Description (optional)" rows="3" class="event-input"></textarea>' +
            '<div class="event-form-actions">' +
            '<button type="submit" class="event-btn-primary">Save</button>' +
            '<button type="button" id="eventFormCancel" class="event-btn-secondary">Cancel</button>' +
            '</div></form></div></div>';
    }

    function loadEvents() {
        var list = document.getElementById('eventsList');
        if (!list || !_familyCircleId) return;
        var today = new Date().toISOString().slice(0, 10);
        var apiBase = (_apiUrl || '').replace(/\/$/, '');
        fetch(apiBase + '/api/family_circles/' + _familyCircleId + '/calendar/events?date=' + today, { credentials: 'include' })
            .then(function (r) { return r.ok ? r.json() : null; })
            .then(function (data) {
                if (!list) return;
                if (!data || !data.data || data.data.length === 0) {
                    list.innerHTML = '<p style="color: #666; margin: 0;">No events today</p>';
                    return;
                }
                var items = data.data.map(function (e) {
                    var id = (e.id || '').replace(/"/g, '&quot;');
                    var title = (e.display || e.title || '').replace(/</g, '&lt;').replace(/>/g, '&gt;');
                    return '<li data-event-id="' + id + '" data-event=\'' + JSON.stringify(e).replace(/'/g, '&#39;') + '\'>' +
                        '<span>' + title + '</span> ' +
                        '<button type="button" class="event-edit-btn" style="font-size:12px;padding:2px 8px;margin-left:4px;">Edit</button> ' +
                        '<button type="button" class="event-delete-btn" style="font-size:12px;padding:2px 8px;">Delete</button></li>';
                });
                list.innerHTML = '<ul style="margin: 0; padding-left: 20px; list-style: none;">' + items.join('') + '</ul>';
            })
            .catch(function () { if (list) list.innerHTML = '<p style="color: #999;">Could not load events</p>'; });
    }

    function initEvents() {
        var container = document.getElementById('pageEvents');
        if (!container) return;
        if (_initialized) {
            loadEvents();
            return;
        }
        container.innerHTML = buildEventsHTML();
        _initialized = true;

        var addBtn = document.getElementById('addEventBtn');
        var modal = document.getElementById('eventFormModal');
        var form = document.getElementById('eventForm');
        var cancelBtn = document.getElementById('eventFormCancel');
        var eventsList = document.getElementById('eventsList');

        var editingEventId = null;

        function openForAdd() {
            editingEventId = null;
            var titleEl = document.getElementById('eventFormTitle');
            if (titleEl) titleEl.textContent = 'Add Event';
            var today = new Date().toISOString().slice(0, 10);
            document.getElementById('eventTitle').value = '';
            document.getElementById('eventDate').value = today;
            document.getElementById('eventStartTime').value = '09:00';
            document.getElementById('eventEndTime').value = '';
            document.getElementById('eventLocation').value = '';
            document.getElementById('eventDescription').value = '';
            if (modal) modal.style.display = 'flex';
        }

        function openForEdit(eventData) {
            editingEventId = eventData.id;
            var titleEl = document.getElementById('eventFormTitle');
            if (titleEl) titleEl.textContent = 'Edit Event';
            var st = eventData.start_time || '';
            var et = eventData.end_time || '';
            var date = st ? st.slice(0, 10) : new Date().toISOString().slice(0, 10);
            var startTime = st && st.length >= 16 ? st.slice(11, 16) : '09:00';
            var endTime = et && et.length >= 16 ? et.slice(11, 16) : '';
            document.getElementById('eventTitle').value = eventData.title || '';
            document.getElementById('eventDate').value = date;
            document.getElementById('eventStartTime').value = startTime;
            document.getElementById('eventEndTime').value = endTime;
            document.getElementById('eventLocation').value = eventData.location || '';
            document.getElementById('eventDescription').value = eventData.description || '';
            if (modal) modal.style.display = 'flex';
        }

        if (addBtn) addBtn.addEventListener('click', openForAdd);

        if (eventsList) {
            container.addEventListener('click', function (e) {
                var li = e.target.closest('li[data-event-id]');
                if (!li) return;
                if (e.target.classList.contains('event-edit-btn')) {
                    try {
                        var data = JSON.parse(li.getAttribute('data-event') || '{}');
                        openForEdit(data);
                    } catch (err) { _showStatus('Could not load event', 'error'); }
                } else if (e.target.classList.contains('event-delete-btn')) {
                    var eventId = li.getAttribute('data-event-id');
                    if (!eventId) return;
                    if (!confirm('Delete this event?')) return;
                    var apiBase = (_apiUrl || '').replace(/\/$/, '');
                    fetch(apiBase + '/api/family_circles/' + _familyCircleId + '/calendar/events/' + encodeURIComponent(eventId), {
                        method: 'DELETE',
                        credentials: 'include'
                    })
                        .then(function (r) {
                            if (r.ok) {
                                _showStatus('\u2713 Event deleted', 'success');
                                loadEvents();
                            } else return r.json().then(function (d) { throw new Error(d.error || 'Failed to delete'); });
                        })
                        .catch(function (err) { _showStatus('\u2717 ' + err.message, 'error'); });
                }
            });
        }

        if (cancelBtn) cancelBtn.addEventListener('click', function () { if (modal) modal.style.display = 'none'; });
        if (modal) modal.addEventListener('click', function (e) { if (e.target === modal) modal.style.display = 'none'; });

        if (form) {
            form.addEventListener('submit', function (e) {
                e.preventDefault();
                var title = document.getElementById('eventTitle').value.trim();
                var date = document.getElementById('eventDate').value;
                var startTime = document.getElementById('eventStartTime').value;
                var endTime = document.getElementById('eventEndTime').value;
                var location = document.getElementById('eventLocation').value.trim();
                var description = document.getElementById('eventDescription').value.trim();
                if (!title || !date || !startTime) {
                    _showStatus('Title, date, and start time required', 'error');
                    return;
                }
                var startDateTime = date + 'T' + startTime + ':00';
                var payload = { title: title, start_time: startDateTime, location: location || undefined, description: description || undefined };
                if (endTime) payload.end_time = date + 'T' + endTime + ':00';

                var apiBase = (_apiUrl || '').replace(/\/$/, '');
                var url = apiBase + '/api/family_circles/' + _familyCircleId + '/calendar/events';
                var method = 'POST';
                if (editingEventId) {
                    url += '/' + encodeURIComponent(editingEventId);
                    method = 'PUT';
                }
                fetch(url, {
                    method: method,
                    headers: { 'Content-Type': 'application/json' },
                    credentials: 'include',
                    body: JSON.stringify(payload)
                })
                    .then(function (r) {
                        if (r.ok) {
                            if (modal) modal.style.display = 'none';
                            var wasEdit = !!editingEventId;
                            editingEventId = null;
                            _showStatus(wasEdit ? '\u2713 Event updated' : '\u2713 Event added', 'success');
                            loadEvents();
                        } else return r.json().then(function (d) { throw new Error(d.error || (editingEventId ? 'Failed to update event' : 'Failed to add event')); });
                    })
                    .catch(function (err) {
                        _showStatus('\u2717 ' + err.message, 'error');
                    });
            });
        }

        loadEvents();
    }

    window.MeridianEvents = {
        init: function (apiUrl, familyCircleId, showStatus) {
            _apiUrl = apiUrl || '';
            _familyCircleId = familyCircleId;
            _showStatus = showStatus || function () {};
            initEvents();
        }
    };
})();
