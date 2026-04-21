/**
 * Webapp Events tab: list today’s calendar events, add/edit/delete modal + credentialed API calls. MeridianEvents.init(...) from app.js.
 * Scope: #pageEvents only. Not: kiosk schedule screen, medications merge, or shared calendar month view.
 */
(function () {
    'use strict';

    var _familyCircleId = null;
    var _showStatus = function () {};
    var _initialized = false;

    function localDateISO(d) {
        d = d || new Date();
        var y = d.getFullYear();
        var m = String(d.getMonth() + 1);
        if (m.length === 1) m = '0' + m;
        var day = String(d.getDate());
        if (day.length === 1) day = '0' + day;
        return y + '-' + m + '-' + day;
    }

    function addDaysISO(iso, days) {
        var p = iso.split('-');
        var dt = new Date(parseInt(p[0], 10), parseInt(p[1], 10) - 1, parseInt(p[2], 10));
        dt.setDate(dt.getDate() + days);
        return localDateISO(dt);
    }

    function eventDayLabel(startTime) {
        if (!startTime || startTime.length < 10) return '';
        var day = startTime.slice(0, 10);
        var today = localDateISO();
        if (day === today) {
            return 'Today';
        }
        var parts = day.split('-');
        var dt = new Date(parseInt(parts[0], 10), parseInt(parts[1], 10) - 1, parseInt(parts[2], 10));
        return dt.toLocaleDateString(undefined, { weekday: 'short', month: 'short', day: 'numeric' });
    }

    function loadEvents() {
        var list = document.getElementById('eventsList');
        if (!list || !_familyCircleId) return;
        var today = new Date().toISOString().slice(0, 10);
        list.innerHTML = 'Loading…';
        meridianApiClient.listEventsForDate(_familyCircleId, today)
            .then(function (response) {
                var data = response && response.body;
                if (!list || !data) return;
                if (!data.data || !Array.isArray(data.data) || data.data.length === 0) {
                    list.innerHTML = '<p class="muted">No events in the next 30 days. Use <strong>Add event</strong> to create one.</p>';
                    return;
                }
                var items = data.data.map(function (e) {
                    var id = (e.id || '').replace(/"/g, '&quot;');
                    var title = meridianEscapeHtml(e.display || e.title || '');
                    var startTime = e.start_time || '';
                    var dayLabel = eventDayLabel(startTime);
                    var timePart = (startTime && startTime.length >= 16) ? startTime.slice(11, 16) : '';
                    var metaText = dayLabel ? dayLabel + (timePart ? ' · ' + timePart : '') : (timePart || '');
                    var meta = metaText ? '<p class="event-card__meta">' + meridianEscapeHtml(metaText) + '</p>' : '';
                    return '<li data-event-id="' + id + '" data-event=\'' + JSON.stringify(e).replace(/'/g, '&#39;') + '">' +
                        '<article class="event-card">' +
                        meta +
                        '<p class="event-card__title">' + title + '</p>' +
                        '<div class="event-card__actions">' +
                        '<button type="button" class="event-edit-btn btn-inline btn-edit">Edit</button>' +
                        '<button type="button" class="event-delete-btn btn-inline btn-delete">Delete</button>' +
                        '</div></article></li>';
                });
                list.innerHTML = '<ul class="list-panel">' + items.join('') + '</ul>';
            })
            .catch(function () { if (list) list.innerHTML = '<p class="muted">Could not load events</p>'; });
    }

    function initEvents() {
        var container = document.getElementById('pageEvents');
        if (!container) return;
        if (_initialized) {
            loadEvents();
            return;
        }
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
            if (titleEl) titleEl.textContent = 'Add event';
            var today = localDateISO();
            document.getElementById('eventTitle').value = '';
            document.getElementById('eventDate').value = today;
            document.getElementById('eventStartTime').value = '09:00';
            document.getElementById('eventEndTime').value = '';
            document.getElementById('eventLocation').value = '';
            document.getElementById('eventDescription').value = '';
            if (modal) modal.classList.add('visible');
        }

        function openForEdit(eventData) {
            editingEventId = eventData.id;
            var titleEl = document.getElementById('eventFormTitle');
            if (titleEl) titleEl.textContent = 'Edit event';
            var st = eventData.start_time || '';
            var et = eventData.end_time || '';
            var date = st ? st.slice(0, 10) : localDateISO();
            var startTime = st && st.length >= 16 ? st.slice(11, 16) : '09:00';
            var endTime = et && et.length >= 16 ? et.slice(11, 16) : '';
            document.getElementById('eventTitle').value = eventData.title || '';
            document.getElementById('eventDate').value = date;
            document.getElementById('eventStartTime').value = startTime;
            document.getElementById('eventEndTime').value = endTime;
            document.getElementById('eventLocation').value = eventData.location || '';
            document.getElementById('eventDescription').value = eventData.description || '';
            if (modal) modal.classList.add('visible');
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
                    meridianApiClient.deleteEvent(_familyCircleId, eventId)
                        .then(function () {
                            _showStatus('\u2713 Event deleted', 'success');
                            loadEvents();
                        })
                        .catch(function (err) { _showStatus('\u2717 ' + err.message, 'error'); });
                }
            });
        }

        if (cancelBtn) cancelBtn.addEventListener('click', function () { if (modal) modal.classList.remove('visible'); });
        if (modal) modal.addEventListener('click', function (e) { if (e.target === modal) modal.classList.remove('visible'); });

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

                var request = editingEventId
                    ? meridianApiClient.updateEvent(_familyCircleId, editingEventId, payload)
                    : meridianApiClient.createEvent(_familyCircleId, payload);
                request
                    .then(function () {
                            if (modal) modal.classList.remove('visible');
                            var wasEdit = !!editingEventId;
                            editingEventId = null;
                            _showStatus(wasEdit ? '\u2713 Event updated' : '\u2713 Event added', 'success');
                            loadEvents();
                    })
                    .catch(function (err) {
                        _showStatus('\u2717 ' + err.message, 'error');
                    });
            });
        }

        loadEvents();
    }

    window.MeridianEvents = {
        init: function (familyCircleId, showStatus) {
            _familyCircleId = familyCircleId;
            _showStatus = showStatus || function () {};
            initEvents();
        }
    };
})();
