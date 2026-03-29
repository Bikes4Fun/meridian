/**
 * Patient health data — medications list, mark taken, add/edit/delete via one modal.
 * Mounts in #healthMedsEditor. Exposes MeridianMedications.init(apiUrl, familyCircleId, showStatus).
 */
(function () {
    'use strict';

    var _apiUrl = '';
    var _familyCircleId = null;
    var _showStatus = function () {};
    var _structureInitialized = false;
    var _timeNames = ['Morning', 'Noon', 'Evening', 'prn'];

    function timeCheckboxesHtml(nameAttr, checkedSet) {
        checkedSet = checkedSet || {};
        return _timeNames.map(function (t) {
            var lbl = t === 'prn' ? 'As needed' : t;
            var chk = checkedSet[t] ? ' checked' : '';
            return '<label class="check-row"><input type="checkbox" name="' + nameAttr + '" value="' + t + '"' + chk + '><span>' + lbl + '</span></label>';
        }).join('');
    }

    function buildHealthMedsHTML() {
        var timeChecks = timeCheckboxesHtml('med_time', {});
        return '<div id="healthMedsList">Loading…</div>' +
            '<button id="addMedBtn" type="button" class="btn-add">Add medication</button>' +
            '<div id="medFormModal">' +
            '<div class="modal-inner">' +
            '<h3 id="medFormTitle">Add medication</h3>' +
            '<form id="medForm">' +
            '<input type="hidden" id="medId" value="">' +
            '<input type="text" id="medName" placeholder="Name" required class="event-input">' +
            '<input type="text" id="medDosage" placeholder="Dosage" class="event-input">' +
            '<fieldset class="med-time-fieldset"><legend class="med-time-legend">Times</legend><div class="med-time-grid">' +
            timeChecks +
            '</div></fieldset>' +
            '<div class="event-form-actions">' +
            '<button type="submit" class="event-btn-primary">Save</button>' +
            '<button type="button" id="medFormCancel" class="event-btn-secondary">Cancel</button>' +
            '</div></form></div></div>';
    }

    function escapeHtml(s) {
        return String(s || '').replace(/</g, '&lt;').replace(/>/g, '&gt;');
    }

    function escapeAttr(s) {
        return String(s || '').replace(/&/g, '&amp;').replace(/"/g, '&quot;');
    }

    function itemHtmlTimed(m) {
        var name = escapeHtml(m.name);
        var done = m.status === 'done';
        var slot = m.time || '';
        var meta = escapeHtml(slot) + (done ? ' · Taken \u2713' : ' · Not taken');
        var takeLbl = done ? 'Uncheck' : 'Take';
        return '<li data-med-id="' + m.id + '" data-med-time="' + escapeAttr(slot) + '" data-med-prn="0" data-med-done="' + (done ? '1' : '0') + '">' +
            '<article class="med-card">' +
            '<p class="med-card__title">' + name + '</p>' +
            '<p class="med-card__meta">' + meta + '</p>' +
            '<div class="med-card__actions">' +
            '<button type="button" class="med-mark-taken-btn btn-inline btn-take">' + takeLbl + '</button>' +
            '<button type="button" class="med-edit-btn btn-inline btn-edit">Edit</button>' +
            '<button type="button" class="med-delete-btn btn-inline btn-delete">Delete</button>' +
            '</div></article></li>';
    }

    function itemHtmlPrn(m) {
        var name = escapeHtml(m.name);
        var taken = m.status === 'taken';
        var status = m.last_taken ? 'Last: ' + escapeHtml(m.last_taken) : (taken ? 'Taken \u2713' : 'Not taken today');
        var takeLbl = taken ? 'Uncheck' : 'Take';
        return '<li data-med-id="' + m.id + '" data-med-time="prn" data-med-prn="1" data-med-done="' + (taken ? '1' : '0') + '">' +
            '<article class="med-card">' +
            '<p class="med-card__title">' + name + ' (PRN)</p>' +
            '<p class="med-card__meta">' + status + '</p>' +
            '<div class="med-card__actions">' +
            '<button type="button" class="med-mark-taken-btn btn-inline btn-take">' + takeLbl + '</button>' +
            '<button type="button" class="med-edit-btn btn-inline btn-edit">Edit</button>' +
            '<button type="button" class="med-delete-btn btn-inline btn-delete">Delete</button>' +
            '</div></article></li>';
    }

    function paintListFromData(data) {
        var timed = (data && data.timed_medications) || [];
        var prn = (data && data.prn_medications) || [];
        var seen = {};
        var items = [];
        timed.forEach(function (m) {
            if (seen[m.id]) return;
            seen[m.id] = true;
            items.push(itemHtmlTimed(m));
        });
        prn.forEach(function (m) {
            if (seen[m.id]) return;
            seen[m.id] = true;
            items.push(itemHtmlPrn(m));
        });
        var listEl = document.getElementById('healthMedsList');
        var emptyMsg = '<p class="muted">No medications</p>';
        if (listEl) {
            listEl.innerHTML = items.length === 0 ? emptyMsg : '<ul class="list-panel">' + items.join('') + '</ul>';
        }
    }

    function loadMeds() {
        var listEl = document.getElementById('healthMedsList');
        if (!listEl || !_familyCircleId) return;
        var apiBase = (_apiUrl || '').replace(/\/$/, '');
        fetch(apiBase + '/api/family_circles/' + _familyCircleId + '/medications', { credentials: 'include' })
            .then(function (r) { return r.ok ? r.json() : null; })
            .then(function (data) {
                if (!data || !data.data) {
                    listEl.innerHTML = '<p class="muted">Could not load medications</p>';
                    return;
                }
                paintListFromData(data.data);
            })
            .catch(function () { listEl.innerHTML = '<p class="muted">Could not load medications</p>'; });
    }

    function markMedTaken(li, wantTaken) {
        var medId = parseInt(li.getAttribute('data-med-id'), 10);
        var timeSlot = li.getAttribute('data-med-time') || '';
        if (!timeSlot) return;
        var apiBase = (_apiUrl || '').replace(/\/$/, '');
        fetch(apiBase + '/api/family_circles/' + _familyCircleId + '/medications/' + medId + '/mark-taken', {
            method: 'POST',
            headers: { 'Content-Type': 'application/json' },
            credentials: 'include',
            body: JSON.stringify({ time: timeSlot, taken: wantTaken })
        })
            .then(function (r) {
                if (r.ok) {
                    _showStatus(wantTaken ? '\u2713 Marked taken' : 'Unchecked', 'success');
                    loadMeds();
                } else return r.json().then(function (d) { throw new Error(d.error || 'Failed'); });
            })
            .catch(function (err) { _showStatus('\u2717 ' + err.message, 'error'); });
    }

    function initMedications() {
        var editorRoot = document.getElementById('healthMedsEditor');
        var pageHealth = document.getElementById('pageHealth');
        if (!_structureInitialized && editorRoot) {
            editorRoot.innerHTML = buildHealthMedsHTML();
            _structureInitialized = true;

            var modal = document.getElementById('medFormModal');
            var form = document.getElementById('medForm');
            var cancelBtn = document.getElementById('medFormCancel');

            function openForAdd() {
                document.getElementById('medFormTitle').textContent = 'Add medication';
                document.getElementById('medId').value = '';
                document.getElementById('medName').value = '';
                document.getElementById('medDosage').value = '';
                document.querySelectorAll('#medForm input[name=med_time]').forEach(function (c) { c.checked = false; });
                if (modal) modal.classList.add('visible');
            }

            function openForEdit(medId) {
                var apiBase = (_apiUrl || '').replace(/\/$/, '');
                fetch(apiBase + '/api/family_circles/' + _familyCircleId + '/medications/' + medId, { credentials: 'include' })
                    .then(function (r) { return r.ok ? r.json() : null; })
                    .then(function (data) {
                        if (!data || !data.data) {
                            _showStatus('Could not load medication', 'error');
                            return;
                        }
                        var d = data.data;
                        document.getElementById('medFormTitle').textContent = 'Edit medication';
                        document.getElementById('medId').value = d.id;
                        document.getElementById('medName').value = d.name || '';
                        document.getElementById('medDosage').value = d.dosage || '';
                        document.querySelectorAll('#medForm input[name=med_time]').forEach(function (c) {
                            c.checked = (d.medication_times || []).indexOf(c.value) >= 0;
                        });
                        if (modal) modal.classList.add('visible');
                    })
                    .catch(function () { _showStatus('Could not load medication', 'error'); });
            }

            var host = pageHealth || editorRoot;
            host.addEventListener('click', function (e) {
                if (e.target.id === 'addMedBtn') {
                    openForAdd();
                    return;
                }
                var li = e.target.closest('li[data-med-id]');
                if (!li) return;
                var medId = parseInt(li.getAttribute('data-med-id'), 10);
                if (e.target.classList.contains('med-mark-taken-btn')) {
                    var done = li.getAttribute('data-med-done') === '1';
                    markMedTaken(li, !done);
                    return;
                }
                if (e.target.classList.contains('med-edit-btn')) {
                    openForEdit(medId);
                } else if (e.target.classList.contains('med-delete-btn')) {
                    if (!confirm('Delete this medication?')) return;
                    var apiBase = (_apiUrl || '').replace(/\/$/, '');
                    fetch(apiBase + '/api/family_circles/' + _familyCircleId + '/medications/' + medId, {
                        method: 'DELETE',
                        credentials: 'include'
                    })
                        .then(function (r) {
                            if (r.ok) {
                                _showStatus('\u2713 Medication deleted', 'success');
                                loadMeds();
                            } else return r.json().then(function (d) { throw new Error(d.error || 'Failed to delete'); });
                        })
                        .catch(function (err) { _showStatus('\u2717 ' + err.message, 'error'); });
                }
            });

            if (cancelBtn) cancelBtn.addEventListener('click', function () { if (modal) modal.classList.remove('visible'); });
            if (modal) modal.addEventListener('click', function (e) { if (e.target === modal) modal.classList.remove('visible'); });

            if (form) {
                form.addEventListener('submit', function (e) {
                    e.preventDefault();
                    var name = document.getElementById('medName').value.trim();
                    var dosage = document.getElementById('medDosage').value.trim();
                    var medId = document.getElementById('medId').value;
                    var times = [];
                    document.querySelectorAll('#medForm input[name=med_time]:checked').forEach(function (c) { times.push(c.value); });
                    if (!name || times.length === 0) {
                        _showStatus('Name and at least one time required', 'error');
                        return;
                    }
                    var payload = { name: name, medication_times: times };
                    if (dosage) payload.dosage = dosage;

                    var apiBase = (_apiUrl || '').replace(/\/$/, '');
                    var url = apiBase + '/api/family_circles/' + _familyCircleId + '/medications';
                    var method = 'POST';
                    if (medId) {
                        url += '/' + medId;
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
                                if (modal) modal.classList.remove('visible');
                                _showStatus(medId ? '\u2713 Medication updated' : '\u2713 Medication added', 'success');
                                loadMeds();
                            } else return r.json().then(function (d) { throw new Error(d.error || 'Failed'); });
                        })
                        .catch(function (err) { _showStatus('\u2717 ' + err.message, 'error'); });
                });
            }
        }

        loadMeds();
    }

    window.MeridianMedications = {
        init: function (apiUrl, familyCircleId, showStatus) {
            _apiUrl = apiUrl || '';
            _familyCircleId = familyCircleId;
            _showStatus = showStatus || function () {};
            initMedications();
        }
    };
})();
