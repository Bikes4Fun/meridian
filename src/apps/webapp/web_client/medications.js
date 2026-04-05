/**
 * Webapp Health/Settings meds UI: today’s list + mark-taken; Settings inline editor wiring. MeridianMedications.init(...). Requires meridian_medications_inline.js.
 * Scope: DOM for #healthMedsTakeHost / #healthMedsEditorHost and credentialed fetches. Not: kiosk embed (kiosk_medications_embed.js), FDA search, or server routes.
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

    function buildTakeListHTML() {
        return (
            '<div id="healthMedsStatusBar" class="health-meds-status" hidden></div>' +
            '<div id="healthMedsList" class="health-meds-list-host">' +
            '<div class="health-meds-skeleton" aria-busy="true" aria-label="Loading medications">' +
            '<div class="health-meds-skeleton__card"></div>' +
            '<div class="health-meds-skeleton__card"></div>' +
            '<div class="health-meds-skeleton__card"></div>' +
            '</div></div>' +
            '<section id="healthMedsCorrectionsWrap" class="med-corrections" aria-labelledby="healthMedsCorrectionsTitle">' +
            '<h3 class="med-corrections__title" id="healthMedsCorrectionsTitle">Adjust today\u2019s logs</h3>' +
            '<p class="muted med-corrections__hint">Undo a scheduled dose or remove the last as-needed dose if something was marked by mistake.</p>' +
            '<div id="healthMedsCorrectionsList" class="med-corrections__list"></div>' +
            '</section>'
        );
    }

    function collectDisplayedMedRows(data) {
        var timed = (data && data.timed_medications) || [];
        var prn = (data && data.prn_medications) || [];
        var seen = {};
        var timedRows = [];
        timed.forEach(function (m) {
            var rowKey = String(m.id) + '|' + String(m.time || '');
            if (seen[rowKey]) return;
            seen[rowKey] = true;
            timedRows.push(m);
        });
        var prnRows = [];
        prn.forEach(function (m) {
            if (seen[m.id]) return;
            seen[m.id] = true;
            prnRows.push(m);
        });
        return { timedRows: timedRows, prnRows: prnRows };
    }

    function paintCaregiverStatus(rows) {
        var bar = document.getElementById('healthMedsStatusBar');
        if (!bar) return;
        var tr = rows.timedRows;
        var pr = rows.prnRows;
        var tTotal = tr.length;
        var tDone = tr.filter(function (m) { return m.status === 'done'; }).length;
        var tDue = tTotal - tDone;
        var pTotal = pr.length;
        if (tTotal === 0 && pTotal === 0) {
            bar.innerHTML = '';
            bar.setAttribute('hidden', '');
            return;
        }
        bar.removeAttribute('hidden');
        var chips = [];
        if (tTotal > 0) {
            chips.push(
                '<span class="health-meds-chip health-meds-chip--stat" role="status">' +
                    tDone +
                    ' / ' +
                    tTotal +
                    ' scheduled taken</span>'
            );
            if (tDue > 0) {
                chips.push(
                    '<span class="health-meds-chip health-meds-chip--due">' +
                        tDue +
                        ' still due</span>'
                );
            }
        }
        if (pTotal > 0) {
            var pDoses = pr.reduce(function (a, m) {
                return a + (parseInt(m.doses_today, 10) || 0);
            }, 0);
            chips.push(
                '<span class="health-meds-chip health-meds-chip--prn">PRN ' +
                    pDoses +
                    ' dose' +
                    (pDoses === 1 ? '' : 's') +
                    ' today</span>'
            );
        }
        bar.innerHTML =
            '<div class="health-meds-chips" role="status">' + chips.join('') + '</div>';
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

    function itemHtmlTimedMain(m) {
        var name = meridianEscapeHtml(m.name);
        var done = m.status === 'done';
        var slot = m.time || '';
        var inlineMeta = ' · ' + meridianEscapeHtml(slot);
        if (m.frequency && String(m.frequency).trim()) {
            inlineMeta = inlineMeta + ' · ' + meridianEscapeHtml(String(m.frequency).trim());
        }
        var rxcui = (m.fda_rxcui && String(m.fda_rxcui).trim())
            ? '<p class="med-card__rxcui">RxCUI ' + meridianEscapeHtml(String(m.fda_rxcui).trim()) + '</p>'
            : '';
        var cardState =
            (done ? 'med-card med-card--done' : 'med-card med-card--pending') + ' med-card--web';
        if (done) {
            return (
                '<li data-med-id="' +
                m.id +
                '" data-med-time="' +
                meridianEscapeAttr(slot) +
                '" data-med-prn="0" data-med-done="1">' +
                '<article class="' +
                cardState +
                '">' +
                '<div class="med-card__web-row">' +
                '<div class="med-card__web-main">' +
                '<p class="med-card__title">' +
                name +
                '<span class="med-card__title-inline">' +
                inlineMeta +
                '</span></p>' +
                rxcui +
                '</div></div></article></li>'
            );
        }
        var badgeHtml =
            '<span class="med-card__badge med-card__badge--due">Not done</span>';
        return (
            '<li data-med-id="' +
            m.id +
            '" data-med-time="' +
            meridianEscapeAttr(slot) +
            '" data-med-prn="0" data-med-done="0">' +
            '<article class="' +
            cardState +
            '">' +
            '<div class="med-card__web-row">' +
            '<div class="med-card__web-main">' +
            '<p class="med-card__title">' +
            name +
            '<span class="med-card__title-inline">' +
            inlineMeta +
            '</span></p>' +
            rxcui +
            '</div>' +
            badgeHtml +
            '<div class="med-card__actions">' +
            '<button type="button" class="med-mark-taken-btn btn-med-action btn-med-action--take">Take</button></div>' +
            '</div></article></li>'
        );
    }

    function itemHtmlTimedCorrection(m) {
        var name = meridianEscapeHtml(m.name);
        var slot = m.time || '';
        var inlineMeta = ' · ' + meridianEscapeHtml(slot);
        if (m.frequency && String(m.frequency).trim()) {
            inlineMeta = inlineMeta + ' · ' + meridianEscapeHtml(String(m.frequency).trim());
        }
        return (
            '<li data-med-id="' +
            m.id +
            '" data-med-time="' +
            meridianEscapeAttr(slot) +
            '" data-med-prn="0" data-med-done="1">' +
            '<article class="med-card med-card--done med-card--web med-card--correction">' +
            '<div class="med-card__web-row">' +
            '<div class="med-card__web-main">' +
            '<p class="med-card__title">' +
            name +
            '<span class="med-card__title-inline">' +
            inlineMeta +
            '</span></p>' +
            '</div>' +
            '<div class="med-card__actions">' +
            '<button type="button" class="med-mark-taken-btn btn-med-action btn-med-action--undo">Undo</button></div>' +
            '</div></article></li>'
        );
    }

    function itemHtmlPrnMain(m) {
        var name = meridianEscapeHtml(m.name);
        var doses = parseInt(m.doses_today, 10) || 0;
        var maxRaw = m.max_daily;
        var maxNum = maxRaw != null && String(maxRaw).trim() !== '' ? parseInt(maxRaw, 10) : NaN;
        var hasMax = !isNaN(maxNum) && maxNum > 0;
        var canTake = !hasMax || doses < maxNum;
        var freqPart = (m.frequency && String(m.frequency).trim())
            ? '<span class="med-card__title-inline"> · ' + meridianEscapeHtml(String(m.frequency).trim()) + '</span>'
            : '';
        var lastLine = '';
        if (doses > 0) {
            var lastParts = [];
            if (m.last_taken) {
                lastParts.push('Last: ' + meridianEscapeHtml(String(m.last_taken)));
            }
            if (doses > 1) {
                lastParts.push(String(doses) + ' today');
            }
            if (lastParts.length) {
                lastLine = '<p class="med-card__meta">' + lastParts.join(' · ') + '</p>';
            }
        }
        var limitNote = '';
        if (hasMax && !canTake) {
            limitNote =
                '<p class="med-card__prn-limit-note" role="status">' +
                'Daily limit reached for today (' +
                doses +
                ' of ' +
                maxNum +
                '). Open <strong>Adjust today\u2019s logs</strong> below if you need to remove a dose.' +
                '</p>';
        }
        var rxcui = (m.fda_rxcui && String(m.fda_rxcui).trim())
            ? '<p class="med-card__rxcui">RxCUI ' + meridianEscapeHtml(String(m.fda_rxcui).trim()) + '</p>'
            : '';
        var cardState =
            'med-card med-card--prn' +
            (doses > 0 ? ' med-card--done' : ' med-card--pending') +
            ' med-card--web';
        var badgeHtml =
            doses === 0
                ? '<span class="med-card__badge med-card__badge--prn">Not taken today</span>'
                : '';
        var actions = '';
        if (canTake) {
            actions =
                '<div class="med-card__actions">' +
                '<button type="button" class="med-mark-taken-btn btn-med-action btn-med-action--take" data-prn-action="take">Take</button></div>';
        }
        return (
            '<li data-med-id="' +
            m.id +
            '" data-med-time="prn" data-med-prn="1" data-prn-doses="' +
            doses +
            '">' +
            '<article class="' +
            cardState +
            '">' +
            '<div class="med-card__web-row">' +
            '<div class="med-card__web-main">' +
            '<p class="med-card__title">' +
            name +
            ' <span class="med-card__prn-label">(as needed)</span>' +
            freqPart +
            '</p>' +
            lastLine +
            limitNote +
            rxcui +
            '</div>' +
            badgeHtml +
            actions +
            '</div></article></li>'
        );
    }

    function itemHtmlPrnCorrection(m) {
        var name = meridianEscapeHtml(m.name);
        var doses = parseInt(m.doses_today, 10) || 0;
        if (doses < 1) return '';
        var sub =
            doses === 1 ? '1 dose logged today' : String(doses) + ' doses logged today';
        return (
            '<li data-med-id="' +
            m.id +
            '" data-med-time="prn" data-med-prn="1" data-prn-doses="' +
            doses +
            '">' +
            '<article class="med-card med-card--prn med-card--done med-card--web med-card--correction">' +
            '<div class="med-card__web-row">' +
            '<div class="med-card__web-main">' +
            '<p class="med-card__title">' +
            name +
            ' <span class="med-card__prn-label">(as needed)</span></p>' +
            '<p class="med-card__meta">' +
            meridianEscapeHtml(sub) +
            '</p></div>' +
            '<div class="med-card__actions">' +
            '<button type="button" class="med-mark-taken-btn btn-med-action btn-med-action--undo" data-prn-action="undo">Undo</button></div>' +
            '</div></article></li>'
        );
    }

    function paintListFromData(data) {
        var rows = collectDisplayedMedRows(data);
        var mainItems = rows.timedRows
            .map(itemHtmlTimedMain)
            .concat(rows.prnRows.map(itemHtmlPrnMain));
        var corrParts = [];
        rows.timedRows.forEach(function (m) {
            if (m.status === 'done') corrParts.push(itemHtmlTimedCorrection(m));
        });
        rows.prnRows.forEach(function (m) {
            var row = itemHtmlPrnCorrection(m);
            if (row) corrParts.push(row);
        });
        paintCaregiverStatus(rows);
        var listEl = document.getElementById('healthMedsList');
        var corrEl = document.getElementById('healthMedsCorrectionsList');
        var emptyMsg =
            '<div class="health-meds-empty">' +
            '<p class="health-meds-empty__title">No medications yet</p>' +
            '<button type="button" class="btn-health-secondary health-meds-empty__cta">Open medication list</button>' +
            '<p class="health-meds-empty__hint muted">Expand <strong>Medications</strong> in the left menu, or use <strong>Settings</strong> &rarr; Open medication list. <strong>Info</strong> tab for the guide.</p>' +
            '</div>';
        if (listEl) {
            listEl.innerHTML =
                mainItems.length === 0
                    ? emptyMsg
                    : '<ul class="list-panel list-panel--meds">' + mainItems.join('') + '</ul>';
        }
        if (corrEl) {
            corrEl.innerHTML =
                corrParts.length === 0
                    ? '<p class="muted med-corrections__empty">Nothing to adjust right now.</p>'
                    : '<ul class="list-panel list-panel--meds list-panel--corrections">' +
                      corrParts.join('') +
                      '</ul>';
        }
    }

    function loadMeds() {
        var listEl = document.getElementById('healthMedsList');
        if (!listEl || !_familyCircleId) return;
        var apiBase = meridianApiBaseNormalize(_apiUrl);
        fetch(apiBase + '/api/family_circles/' + encodeURIComponent(_familyCircleId) + '/medications', { credentials: 'include' })
            .then(function (r) { return r.ok ? r.json() : null; })
            .then(function (data) {
                var bar = document.getElementById('healthMedsStatusBar');
                if (!data || !data.data) {
                    listEl.innerHTML =
                        '<div class="health-meds-empty">' +
                        '<p class="health-meds-empty__title">Could not load medications</p>' +
                        '<p class="health-meds-empty__hint muted">Check your connection and refresh the page.</p>' +
                        '</div>';
                    if (bar) {
                        bar.innerHTML =
                            '<div class="health-meds-chips" role="alert">' +
                            '<span class="health-meds-chip health-meds-chip--error">Snapshot unavailable</span>' +
                            '</div>';
                        bar.removeAttribute('hidden');
                    }
                    return;
                }
                paintListFromData(data.data);
            })
            .catch(function () {
                listEl.innerHTML =
                    '<div class="health-meds-empty">' +
                    '<p class="health-meds-empty__title">Could not load medications</p>' +
                    '<p class="health-meds-empty__hint muted">Check your connection and refresh the page.</p>' +
                    '</div>';
                var bar = document.getElementById('healthMedsStatusBar');
                if (bar) {
                    bar.innerHTML =
                        '<div class="health-meds-chips" role="alert">' +
                        '<span class="health-meds-chip health-meds-chip--error">Snapshot unavailable</span>' +
                        '</div>';
                    bar.removeAttribute('hidden');
                }
            });
    }

    function loadInlineMedsFromProfile() {
        var listEl = document.getElementById('healthMedsInlineList');
        if (!listEl || !_familyCircleId) return;
        if (_healthMedAutosave) _healthMedAutosave.cancel();
        var apiBase = meridianApiBaseNormalize(_apiUrl);
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
        var article = li.querySelector('article.med-card');
        var btns = li.querySelectorAll('button.med-mark-taken-btn');
        function setBusy(busy) {
            if (article) {
                if (busy) article.setAttribute('aria-busy', 'true');
                else article.removeAttribute('aria-busy');
            }
            btns.forEach(function (b) {
                b.disabled = !!busy;
            });
        }
        setBusy(true);
        var apiBase = meridianApiBaseNormalize(_apiUrl);
        fetch(apiBase + '/api/family_circles/' + encodeURIComponent(_familyCircleId) + '/medications/' + medId + '/mark-taken', {
            method: 'POST',
            headers: { 'Content-Type': 'application/json' },
            credentials: 'include',
            body: JSON.stringify({ time: timeSlot, taken: wantTaken })
        })
            .then(function (r) {
                if (r.ok) {
                    loadMeds();
                } else return r.json().then(function (d) { throw new Error(d.error || 'Failed'); });
            })
            .catch(function (err) { _showStatus('\u2717 ' + err.message, 'error'); })
            .then(function () { setBusy(false); });
            .catch(function (err) { _showStatus('\u2717 ' + err.message, 'error'); })
            .then(function () { setBusy(false); });
    }

    function onTakeListClick(e) {
        var btn = e.target.closest('.med-mark-taken-btn');
        if (!btn) return;
        var li = e.target.closest('li[data-med-id]');
        if (!li) return;
        if (li.getAttribute('data-med-prn') === '1') {
            var pact = btn.getAttribute('data-prn-action') || '';
            if (pact === 'undo') {
                markMedTaken(li, false);
            } else if (pact === 'take') {
                markMedTaken(li, true);
            }
            return;
        }
        var done = li.getAttribute('data-med-done') === '1';
        markMedTaken(li, !done);
    }

    function initMedications() {
        var takeHost = document.getElementById('healthMedsTakeHost');
        var editorRoot = document.getElementById('healthMedsEditorHost');
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
                var apiBase = meridianApiBaseNormalize(_apiUrl);
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
                },
                onRowsDeleted: function () {
                    if (_healthMedAutosave) _healthMedAutosave.cancel();
                    runMedsSave(false);
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
