/**
 * Medications: today's doses on #healthMedsTakeHost; inline editing only on #settingsMedsEditor (kiosk parity).
 * Exposes MeridianMedications.init(apiUrl, familyCircleId, showStatus). Requires meridian_medications_inline.js.
 */
(function () {
    'use strict';

    var _apiUrl = '';
    var _familyCircleId = null;
    var _showStatus = function () {};
    var _takeMounted = false;
    var _editorMounted = false;
    var _takeClickBound = false;
    var _inlineSnapshot = [];
    var _healthMedAutosave = null;

    var SAVE_MEDS_DISK_SVG =
        '<svg xmlns="http://www.w3.org/2000/svg" width="18" height="18" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round">' +
        '<path d="M19 21H5a2 2 0 0 1-2-2V5a2 2 0 0 1 2-2h11l5 5v11a2 2 0 0 1-2 2z"/><polyline points="17 21 17 13 7 13 7 21"/><line x1="7" y1="3" x2="17" y2="3"/></svg>';

    function escapeHtml(s) {
        return String(s || '').replace(/</g, '&lt;').replace(/>/g, '&gt;');
    }

    function escapeAttr(s) {
        return String(s || '').replace(/&/g, '&amp;').replace(/"/g, '&quot;');
    }

    function buildTakeListHTML() {
        return '<div id="healthMedsList">Loading…</div>';
    }

    function buildSettingsEditorHTML() {
        var trash = MeridianMedicationsInline.TRASH_SVG;
        return '<div class="ice-med-toolbar-top">' +
            '<button id="healthMedsSelectAllBtn" type="button" class="btn-inline ice-med-select-all-btn">Select all</button>' +
            '<label class="ice-med-autosave-label">' +
            '<input type="checkbox" id="healthMedsAutoSave" class="ice-med-autosave-cb">' +
            'Save as you go</label>' +
            '</div>' +
            '<div class="ice-medications-editor" id="healthMedsInlineList"></div>' +
            '<div class="ice-med-editor-actions">' +
            '<button id="healthMedsAddBtn" type="button" class="btn-add">Add medication</button>' +
            '<button id="healthMedsDeleteSelectedBtn" type="button" class="btn-inline btn-delete ice-med-delete-selected-btn">' +
            '<span class="ice-med-delete-selected-btn__icon" aria-hidden="true">' + trash + '</span>' +
            '<span>Delete selected</span></button>' +
            '<button id="healthMedsSaveBtn" type="button" class="ice-med-save-btn">' +
            '<span class="ice-med-save-btn__icon" aria-hidden="true">' + SAVE_MEDS_DISK_SVG + '</span>' +
            'Save medications</button>' +
            '</div>';
    }

    function itemHtmlTimed(m) {
        var name = escapeHtml(m.name);
        var done = m.status === 'done';
        var slot = m.time || '';
        var meta = escapeHtml(slot) + (done ? ' · Taken \u2713' : ' · Not taken');
        var takeLbl = done ? 'Uncheck' : 'Take';
        var rxcui = (m.fda_rxcui && String(m.fda_rxcui).trim()) ? '<p class="med-card__meta med-card__rxcui">RxCUI ' + escapeHtml(String(m.fda_rxcui).trim()) + '</p>' : '';
        return '<li data-med-id="' + m.id + '" data-med-time="' + escapeAttr(slot) + '" data-med-prn="0" data-med-done="' + (done ? '1' : '0') + '">' +
            '<article class="med-card">' +
            '<p class="med-card__title">' + name + '</p>' +
            '<p class="med-card__meta">' + meta + '</p>' +
            rxcui +
            '<div class="med-card__actions">' +
            '<button type="button" class="med-mark-taken-btn btn-inline btn-take">' + takeLbl + '</button>' +
            '</div></article></li>';
    }

    function itemHtmlPrn(m) {
        var name = escapeHtml(m.name);
        var taken = m.status === 'taken';
        var status = m.last_taken ? 'Last: ' + escapeHtml(m.last_taken) : (taken ? 'Taken \u2713' : 'Not taken today');
        var takeLbl = taken ? 'Uncheck' : 'Take';
        var rxcui = (m.fda_rxcui && String(m.fda_rxcui).trim()) ? '<p class="med-card__meta med-card__rxcui">RxCUI ' + escapeHtml(String(m.fda_rxcui).trim()) + '</p>' : '';
        return '<li data-med-id="' + m.id + '" data-med-time="prn" data-med-prn="1" data-med-done="' + (taken ? '1' : '0') + '">' +
            '<article class="med-card">' +
            '<p class="med-card__title">' + name + ' (PRN)</p>' +
            '<p class="med-card__meta">' + status + '</p>' +
            rxcui +
            '<div class="med-card__actions">' +
            '<button type="button" class="med-mark-taken-btn btn-inline btn-take">' + takeLbl + '</button>' +
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
        fetch(apiBase + '/api/family_circles/' + encodeURIComponent(_familyCircleId) + '/medications', { credentials: 'include' })
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

    function loadInlineMedsFromProfile() {
        var listEl = document.getElementById('healthMedsInlineList');
        if (!listEl || !_familyCircleId) return;
        if (_healthMedAutosave) _healthMedAutosave.cancel();
        var apiBase = (_apiUrl || '').replace(/\/$/, '');
        fetch(
            apiBase + '/api/family_circles/' + encodeURIComponent(_familyCircleId) + '/emergency-profile',
            { credentials: 'include' }
        )
            .then(function (r) { return r.ok ? r.json() : null; })
            .then(function (body) {
                var data = body && body.data;
                var meds = (data && data.medical && data.medical.medications) || [];
                _inlineSnapshot = MeridianMedicationsInline.cloneSnapshot(meds);
                MeridianMedicationsInline.renderRows(listEl, meds);
            })
            .catch(function () {
                _showStatus('Could not load medication list for editing', 'error');
            });
    }

    function markMedTaken(li, wantTaken) {
        var medId = parseInt(li.getAttribute('data-med-id'), 10);
        var timeSlot = li.getAttribute('data-med-time') || '';
        if (!timeSlot) return;
        var apiBase = (_apiUrl || '').replace(/\/$/, '');
        fetch(apiBase + '/api/family_circles/' + encodeURIComponent(_familyCircleId) + '/medications/' + medId + '/mark-taken', {
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

    function onTakeListClick(e) {
        var li = e.target.closest('li[data-med-id]');
        if (!li || !e.target.classList.contains('med-mark-taken-btn')) return;
        var done = li.getAttribute('data-med-done') === '1';
        markMedTaken(li, !done);
    }

    function initMedications() {
        var takeHost = document.getElementById('healthMedsTakeHost');
        var editorRoot = document.getElementById('settingsMedsEditor');
        var pageHealth = document.getElementById('pageHealth');

        if (typeof MeridianMedicationsInline === 'undefined') {
            if (editorRoot) {
                editorRoot.innerHTML = '<p class="muted">Medication editor could not load. Refresh the page.</p>';
            }
        }

        if (!_takeMounted && takeHost) {
            takeHost.innerHTML = buildTakeListHTML();
            _takeMounted = true;
        }
        if (!_takeClickBound && pageHealth) {
            pageHealth.addEventListener('click', onTakeListClick);
            _takeClickBound = true;
        }

        if (!_editorMounted && editorRoot && typeof MeridianMedicationsInline !== 'undefined') {
            editorRoot.innerHTML = buildSettingsEditorHTML();
            _editorMounted = true;

            var inlineList = document.getElementById('healthMedsInlineList');
            var addBtn = document.getElementById('healthMedsAddBtn');
            var selAllBtn = document.getElementById('healthMedsSelectAllBtn');
            var delBtn = document.getElementById('healthMedsDeleteSelectedBtn');
            var saveBtn = document.getElementById('healthMedsSaveBtn');
            function runMedsSave(silent) {
                if (!_familyCircleId) return Promise.resolve();
                var apiBase = (_apiUrl || '').replace(/\/$/, '');
                var rows = MeridianMedicationsInline.collectRows(inlineList);
                return MeridianMedicationsInline.saveDiff(apiBase, _familyCircleId, _inlineSnapshot, rows)
                    .then(function () {
                        if (!silent) _showStatus('\u2713 Medications saved', 'success');
                        loadMeds();
                        return fetch(
                            apiBase + '/api/family_circles/' + encodeURIComponent(_familyCircleId) + '/emergency-profile',
                            { credentials: 'include' }
                        );
                    })
                    .then(function (r) { return r && r.ok ? r.json() : null; })
                    .then(function (body) {
                        if (!body || !body.data) return;
                        var meds = (body.data.medical && body.data.medical.medications) || [];
                        _inlineSnapshot = MeridianMedicationsInline.cloneSnapshot(meds);
                        if (_healthMedAutosave) _healthMedAutosave.cancel();
                        MeridianMedicationsInline.renderRows(inlineList, meds);
                    })
                    .catch(function (err) {
                        _showStatus('\u2717 ' + (err.message || 'Save failed'), 'error');
                    });
            }

            _healthMedAutosave = MeridianMedicationsInline.wireAutoSave(inlineList, {
                isEnabled: function () {
                    var c = document.getElementById('healthMedsAutoSave');
                    return !!(c && c.checked);
                },
                debounceMs: 1000,
                save: function () {
                    return runMedsSave(true);
                }
            });

            MeridianMedicationsInline.wireList(inlineList, addBtn, delBtn, selAllBtn, {
                onListMutate: function () {
                    if (_healthMedAutosave) _healthMedAutosave.schedule();
                }
            });

            var autoChk = document.getElementById('healthMedsAutoSave');
            if (autoChk) {
                autoChk.addEventListener('change', function () {
                    if (this.checked && _healthMedAutosave) _healthMedAutosave.schedule();
                });
            }

            if (saveBtn) {
                saveBtn.addEventListener('click', function () {
                    runMedsSave(false);
                });
            }
        }

        loadMeds();
        if (typeof MeridianMedicationsInline !== 'undefined') {
            loadInlineMedsFromProfile();
        }
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
