/**
 * Medications page – list, add, edit, delete.
 * Exposes MeridianMedications.init(apiUrl, familyCircleId, showStatus).
 */
(function () {
    'use strict';

    var _apiUrl = '';
    var _familyCircleId = null;
    var _showStatus = function () {};
    var _initialized = false;
    var _timeNames = ['Morning', 'Noon', 'Evening', 'prn'];

    function buildMedicationsHTML() {
        var timeChecks = _timeNames.map(function (t) {
            var lbl = t === 'prn' ? 'As Needed' : t;
            return '<label><input type="checkbox" name="med_time" value="' + t + '"> ' + lbl + '</label>';
        }).join(' ');
        return '<h2>Medications</h2>' +
            '<div id="medsList">Loading…</div>' +
            '<button id="addMedBtn" type="button">Add Medication</button>' +
            '<div id="medFormModal">' +
            '<div class="modal-inner">' +
            '<h3 id="medFormTitle">Add Medication</h3>' +
            '<form id="medForm">' +
            '<input type="hidden" id="medId" value="">' +
            '<input type="text" id="medName" placeholder="Name" required class="event-input">' +
            '<input type="text" id="medDosage" placeholder="Dosage" class="event-input">' +
            '<div style="margin:8px 0;">Times: ' + timeChecks + '</div>' +
            '<div class="event-form-actions">' +
            '<button type="submit" class="event-btn-primary">Save</button>' +
            '<button type="button" id="medFormCancel" class="event-btn-secondary">Cancel</button>' +
            '</div></form></div></div>';
    }

    function loadMeds() {
        var list = document.getElementById('medsList');
        if (!list || !_familyCircleId) return;
        var apiBase = (_apiUrl || '').replace(/\/$/, '');
        fetch(apiBase + '/api/family_circles/' + _familyCircleId + '/medications', { credentials: 'include' })
            .then(function (r) { return r.ok ? r.json() : null; })
            .then(function (data) {
                if (!list) return;
                if (!data || !data.data) {
                    list.innerHTML = '<p style="color: #666;">Could not load medications</p>';
                    return;
                }
                var d = data.data;
                var timed = d.timed_medications || [];
                var prn = d.prn_medications || [];
                var seen = {};
                var items = [];
                timed.forEach(function (m) {
                    if (seen[m.id]) return;
                    seen[m.id] = true;
                    var name = (m.name || '').replace(/</g, '&lt;').replace(/>/g, '&gt;');
                    items.push('<li data-med-id="' + m.id + '" data-med=\'' + JSON.stringify(m).replace(/'/g, '&#39;') + '\'><span>' + name + '</span> ' +
                        '<button type="button" class="med-edit-btn" style="font-size:12px;padding:2px 8px;">Edit</button> ' +
                        '<button type="button" class="med-delete-btn" style="font-size:12px;padding:2px 8px;">Delete</button></li>');
                });
                prn.forEach(function (m) {
                    if (seen[m.id]) return;
                    seen[m.id] = true;
                    var name = (m.name || '').replace(/</g, '&lt;').replace(/>/g, '&gt;');
                    var taken = m.status === 'taken';
                    var status = m.last_taken ? 'Last: ' + m.last_taken : (taken ? 'Taken \u2713' : 'Not taken today');
                    var takeLbl = taken ? 'Uncheck' : 'Take';
                    items.push('<li data-med-id="' + m.id + '" data-med-prn="1" data-med-taken="' + (taken ? '1' : '0') + '" data-med=\'' + JSON.stringify(m).replace(/'/g, '&#39;') + '\'><span>' + name + ' (PRN) \u2022 ' + status + '</span> ' +
                        '<button type="button" class="med-take-prn-btn" style="font-size:12px;padding:2px 8px;">' + takeLbl + '</button> ' +
                        '<button type="button" class="med-edit-btn" style="font-size:12px;padding:2px 8px;">Edit</button> ' +
                        '<button type="button" class="med-delete-btn" style="font-size:12px;padding:2px 8px;">Delete</button></li>');
                });
                if (items.length === 0) {
                    list.innerHTML = '<p style="color: #666;">No medications</p>';
                } else {
                    list.innerHTML = '<ul style="margin:0;padding-left:20px;list-style:none;">' + items.join('') + '</ul>';
                }
            })
            .catch(function () { if (list) list.innerHTML = '<p style="color:#999;">Could not load medications</p>'; });
    }

    function initMedications() {
        var container = document.getElementById('pageMedications');
        if (!container) return;
        if (_initialized) {
            loadMeds();
            return;
        }
        container.innerHTML = buildMedicationsHTML();
        _initialized = true;

        var addBtn = document.getElementById('addMedBtn');
        var modal = document.getElementById('medFormModal');
        var form = document.getElementById('medForm');
        var cancelBtn = document.getElementById('medFormCancel');
        var medsList = document.getElementById('medsList');

        function openForAdd() {
            document.getElementById('medFormTitle').textContent = 'Add Medication';
            document.getElementById('medId').value = '';
            document.getElementById('medName').value = '';
            document.getElementById('medDosage').value = '';
            document.querySelectorAll('#medForm input[name=med_time]').forEach(function (c) { c.checked = false; });
            if (modal) modal.style.display = 'flex';
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
                    document.getElementById('medFormTitle').textContent = 'Edit Medication';
                    document.getElementById('medId').value = d.id;
                    document.getElementById('medName').value = d.name || '';
                    document.getElementById('medDosage').value = d.dosage || '';
                    document.querySelectorAll('#medForm input[name=med_time]').forEach(function (c) {
                        c.checked = (d.medication_times || []).indexOf(c.value) >= 0;
                    });
                    if (modal) modal.style.display = 'flex';
                })
                .catch(function () { _showStatus('Could not load medication', 'error'); });
        }

        if (addBtn) addBtn.addEventListener('click', openForAdd);

        if (medsList) {
            container.addEventListener('click', function (e) {
                var li = e.target.closest('li[data-med-id]');
                if (!li) return;
                var medId = parseInt(li.getAttribute('data-med-id'), 10);
                if (e.target.classList.contains('med-edit-btn')) {
                    openForEdit(medId);
                } else if (e.target.classList.contains('med-take-prn-btn')) {
                    var taken = li.getAttribute('data-med-taken') === '1';
                    var apiBase = (_apiUrl || '').replace(/\/$/, '');
                    fetch(apiBase + '/api/family_circles/' + _familyCircleId + '/medications/' + medId + '/mark-taken', {
                        method: 'POST',
                        headers: { 'Content-Type': 'application/json' },
                        credentials: 'include',
                        body: JSON.stringify({ time: 'prn', taken: !taken })
                    })
                        .then(function (r) {
                            if (r.ok) {
                                _showStatus(!taken ? '\u2713 Taken' : 'Unchecked', 'success');
                                loadMeds();
                            } else return r.json().then(function (d) { throw new Error(d.error || 'Failed'); });
                        })
                        .catch(function (err) { _showStatus('\u2717 ' + err.message, 'error'); });
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
        }

        if (cancelBtn) cancelBtn.addEventListener('click', function () { if (modal) modal.style.display = 'none'; });
        if (modal) modal.addEventListener('click', function (e) { if (e.target === modal) modal.style.display = 'none'; });

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
                            if (modal) modal.style.display = 'none';
                            _showStatus(medId ? '\u2713 Medication updated' : '\u2713 Medication added', 'success');
                            loadMeds();
                        } else return r.json().then(function (d) { throw new Error(d.error || 'Failed'); });
                    })
                    .catch(function (err) { _showStatus('\u2717 ' + err.message, 'error'); });
            });
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
