/**
 * Webapp Health/Settings meds UI: today’s list + mark-taken; Settings inline editor wiring. MeridianMedications.init(...). Inline editor module is bundled below in this same file.
 * Scope: DOM for #healthMedsTakeHost / #healthMedsEditorHost and credentialed fetches. Not: kiosk embed (kiosk_medications_embed.js), FDA search, or server routes.
 */
(function () {
    'use strict';

    var _familyCircleId = null;
    var _showStatus = function () {};
    var _takeMounted = false;
    var _editorMounted = false;
    var _takeClickBound = false;
    var _inlineSnapshot = [];
    var _healthMedAutosave = null;
    var _latestTakeRows = { timedRows: [], prnRows: [] };
    var _markAllBusy = false;

    var SAVE_MEDS_DISK_SVG =
        '<svg xmlns="http://www.w3.org/2000/svg" width="18" height="18" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round" aria-hidden="true" focusable="false">' +
        '<path d="M19 21H5a2 2 0 0 1-2-2V5a2 2 0 0 1 2-2h11l5 5v11a2 2 0 0 1-2 2z"/><polyline points="17 21 17 13 7 13 7 21"/><line x1="7" y1="3" x2="17" y2="3"/></svg>';

    function buildTakeListHTML() {
        return (
            '<div id="healthMedsStatusBar" class="health-meds-status" hidden></div>' +
            '<div class="health-meds-actions-row">' +
            '<button id="healthMedsMarkAllBtn" type="button" class="btn-health-secondary" disabled>Mark all non-PRN (not as-needed) as taken</button>' +
            '</div>' +
            '<div id="healthMedsList" class="health-meds-list-host">' +
            '<div class="health-meds-skeleton" aria-hidden="true">' +
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
                '<span class="health-meds-chip health-meds-chip--stat">' +
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
            '<div class="health-meds-chips">' + chips.join('') + '</div>';
    }

    function updateMarkAllButton() {
        var btn = document.getElementById('healthMedsMarkAllBtn');
        if (!btn) return;
        var dueCount = (_latestTakeRows.timedRows || []).filter(function (m) {
            return m && m.status !== 'done' && (m.time || '').toLowerCase() !== 'prn';
        }).length;
        btn.disabled = _markAllBusy || dueCount < 1;
        btn.textContent = _markAllBusy
            ? 'Marking non-as-needed doses...'
            : 'Mark all non-PRN (not as-needed) as taken';
    }

    function updateMarkAllButton() {
        var btn = document.getElementById('healthMedsMarkAllBtn');
        if (!btn) return;
        var dueCount = (_latestTakeRows.timedRows || []).filter(function (m) {
            return m && m.status !== 'done' && (m.time || '').toLowerCase() !== 'prn';
        }).length;
        btn.disabled = _markAllBusy || dueCount < 1;
        btn.textContent = _markAllBusy
            ? 'Marking non-as-needed doses...'
            : 'Mark all non-PRN (not as-needed) as taken';
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
                '<p class="med-card__prn-limit-note">' +
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
        var timedItems = rows.timedRows.map(itemHtmlTimedMain);
        var prnItems = rows.prnRows.map(itemHtmlPrnMain);
        var corrParts = [];
        rows.timedRows.forEach(function (m) {
            if (m.status === 'done') corrParts.push(itemHtmlTimedCorrection(m));
        });
        rows.prnRows.forEach(function (m) {
            var row = itemHtmlPrnCorrection(m);
            if (row) corrParts.push(row);
        });
        paintCaregiverStatus(rows);
        _latestTakeRows = rows;
        updateMarkAllButton();
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
                timedItems.length === 0 && prnItems.length === 0
                    ? emptyMsg
                    : (
                        '<div class="health-meds-timed-scroll">' +
                        '<ul class="list-panel list-panel--meds">' + timedItems.join('') + '</ul>' +
                        '</div>' +
                        (
                            prnItems.length
                                ? '<section class="health-meds-prn-sticky" aria-label="As needed medications">' +
                                  '<h4 class="health-meds-prn-sticky__title">As needed</h4>' +
                                  '<ul class="list-panel list-panel--meds list-panel--prn-sticky">' +
                                  prnItems.join('') +
                                  '</ul></section>'
                                : ''
                        )
                    );
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
        meridianApiClient.getMedications(_familyCircleId)
            .then(function (response) {
                var data = response && response.body;
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
        meridianApiClient.getEmergencyProfile(_familyCircleId)
            .then(function (response) {
                var body = response && response.body;
                var data = body && body.data;
                var meds = (data && data.medical && data.medical.medications) || [];
                _inlineSnapshot = MeridianMedicationsInline.cloneSnapshot(meds);
                MeridianMedicationsInline.renderRows(listEl, meds);
            })
            .catch(function () {
                _showStatus('Could not load medication list for editing', 'error');
            });
    }

    function postMarkTaken(medId, timeSlot, wantTaken) {
        return meridianApiClient.markMedicationTaken(
            _familyCircleId,
            medId,
            timeSlot,
            wantTaken
        );
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
        postMarkTaken(medId, timeSlot, wantTaken)
            .then(function (r) {
                loadMeds();
            })
            .catch(function (err) { _showStatus('\u2717 ' + err.message, 'error'); })
            .then(function () { setBusy(false); });
    }

    function markAllScheduledTaken() {
        if (_markAllBusy || !_familyCircleId) return;
        var dueRows = (_latestTakeRows.timedRows || []).filter(function (m) {
            return m && m.status !== 'done' && (m.time || '').toLowerCase() !== 'prn';
        });
        if (!dueRows.length) return;
        _markAllBusy = true;
        updateMarkAllButton();
        var chain = Promise.resolve();
        dueRows.forEach(function (m) {
            chain = chain.then(function () {
                var medId = parseInt(m.id, 10);
                var slot = m.time || '';
                if (!medId || !slot) return null;
                return postMarkTaken(medId, slot, true);
            });
        });
        chain
            .then(function () {
                _showStatus('\u2713 Marked all non-as-needed doses as taken', 'success');
                loadMeds();
            })
            .catch(function (err) {
                _showStatus('\u2717 ' + (err.message || 'Could not mark all doses'), 'error');
            })
            .then(function () {
                _markAllBusy = false;
                updateMarkAllButton();
            });
    }

    function onTakeListClick(e) {
        var markAllBtn = e.target.closest('#healthMedsMarkAllBtn');
        if (markAllBtn) {
            markAllScheduledTaken();
            return;
        }
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
                var rows = MeridianMedicationsInline.collectRows(inlineList);
                return MeridianMedicationsInline.saveDiff(_familyCircleId, _inlineSnapshot, rows)
                    .then(function () {
                        if (!silent) _showStatus('\u2713 Medications saved', 'success');
                        loadMeds();
                        return meridianApiClient.getEmergencyProfile(_familyCircleId);
                    })
                    .then(function (response) {
                        var body = response && response.body;
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
        init: function (familyCircleId, showStatus) {
            _familyCircleId = familyCircleId;
            _showStatus = showStatus || function () {};
            initMedications();
        }
    };
})();
/**
 * Shared medication row editor: HTML for rows, collect from DOM, sequential diff save/delete vs /medications (api base from caller).
 * Scope: MeridianMedicationsInline + reusable by webapp Settings, ICE editor, kiosk embed. Not: page layout, ICE non-med fields, or Python.
 */
(function (global) {
    'use strict';

    var TIME_NAMES = ['Morning', 'Noon', 'Evening', 'prn'];

    function htmlToEl(html) {
        var d = document.createElement('div');
        d.innerHTML = html.trim();
        return d.firstChild;
    }

    var TRASH_SVG =
        '<svg xmlns="http://www.w3.org/2000/svg" width="20" height="20" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round" aria-hidden="true" focusable="false">' +
        '<path d="M3 6h18"/><path d="M19 6v14a2 2 0 0 1-2 2H7a2 2 0 0 1-2-2V6"/>' +
        '<path d="M8 6V4a2 2 0 0 1 2-2h4a2 2 0 0 1 2 2v2"/><line x1="10" y1="11" x2="10" y2="17"/><line x1="14" y1="11" x2="14" y2="17"/></svg>';

    function medRowHtml(m) {
        m = m || {};
        var idAttr = m.id != null && m.id !== '' ? String(m.id) : '';
        var name = global.meridianEscapeAttr(m.name || '');
        var dosage = global.meridianEscapeAttr(m.dosage || '');
        var frequency = global.meridianEscapeAttr(m.frequency || '');
        var rxcui = global.meridianEscapeAttr((m.fda_rxcui != null && m.fda_rxcui !== '') ? String(m.fda_rxcui) : '');
        var times = m.medication_times || [];
        var timeChecks = TIME_NAMES.map(function (t) {
            var lbl = t === 'prn' ? 'As needed' : t;
            var chk = times.indexOf(t) >= 0 ? ' checked' : '';
            return '<label class="ice-med-time-opt"><input type="checkbox" class="ice-med-time" value="' +
                global.meridianEscapeAttr(t) + '"' + chk + '> ' + lbl + '</label>';
        }).join('');
        return '<div class="ice-med-row" data-med-id="' + global.meridianEscapeAttr(idAttr) + '">' +
            '<div class="ice-med-fields">' +
            '<input type="text" class="event-input ice-med-name" placeholder="Name" value="' + name + '">' +
            '<input type="text" class="event-input ice-med-dosage" placeholder="Dosage" value="' + dosage + '">' +
            '<input type="text" class="event-input ice-med-frequency" placeholder="Frequency" value="' + frequency + '">' +
            '<input type="text" class="event-input ice-med-rxcui" placeholder="RxCUI (optional)" value="' + rxcui + '">' +
            '</div>' +
            '<div class="ice-med-actions-row">' +
            '<div class="ice-med-times-row">' + timeChecks + '</div>' +
            '<div class="ice-med-delete-cell">' +
            '<label class="ice-med-select-label">' +
            '<input type="checkbox" class="ice-med-select">' +
            '<span class="ice-med-select__trash" aria-hidden="true">' + TRASH_SVG + '</span>' +
            '</label></div></div></div>';
    }

    function renderRows(containerEl, meds) {
        if (!containerEl) return;
        containerEl.innerHTML = '';
        meds = meds || [];
        if (meds.length === 0) {
            containerEl.appendChild(htmlToEl(medRowHtml({})));
        } else {
            meds.forEach(function (m) {
                containerEl.appendChild(htmlToEl(medRowHtml(m)));
            });
        }
        containerEl.dispatchEvent(new CustomEvent('meridianMedRowsRendered', { bubbles: false }));
    }

    function validateUniqueMedicationNames(rows) {
        var seen = {};
        for (var i = 0; i < rows.length; i++) {
            var n = (rows[i].name || '').trim();
            if (!n) continue;
            var k = n.toLowerCase();
            if (seen[k]) return 'Each medication name must be unique.';
            seen[k] = true;
        }
        return null;
    }

    function collectRows(listEl) {
        var out = [];
        if (!listEl) return out;
        listEl.querySelectorAll('.ice-med-row').forEach(function (row) {
            var idRaw = row.getAttribute('data-med-id');
            var id = idRaw ? parseInt(idRaw, 10) : null;
            if (idRaw && (isNaN(id) || id < 1)) id = null;
            var nameEl = row.querySelector('.ice-med-name');
            var dosageEl = row.querySelector('.ice-med-dosage');
            var frequencyEl = row.querySelector('.ice-med-frequency');
            var rxcuiEl = row.querySelector('.ice-med-rxcui');
            var times = [];
            row.querySelectorAll('.ice-med-time:checked').forEach(function (c) {
                times.push(c.value);
            });
            out.push({
                id: id,
                name: (nameEl && nameEl.value) ? nameEl.value.trim() : '',
                dosage: (dosageEl && dosageEl.value) ? dosageEl.value.trim() : '',
                frequency: (frequencyEl && frequencyEl.value) ? frequencyEl.value.trim() : '',
                fda_rxcui: (rxcuiEl && rxcuiEl.value) ? rxcuiEl.value.trim() : '',
                medication_times: times
            });
        });
        return out;
    }

    /** True if row is not a blank placeholder (saved med, typed fields, times, or RxCUI). */
    function rowIsSubstantiveForDelete(row) {
        if (!row) return false;
        var idRaw = row.getAttribute('data-med-id');
        var id = idRaw ? parseInt(idRaw, 10) : null;
        if (idRaw && !isNaN(id) && id >= 1) return true;
        var nameEl = row.querySelector('.ice-med-name');
        var name = (nameEl && nameEl.value) ? nameEl.value.trim() : '';
        if (name) return true;
        var dosageEl = row.querySelector('.ice-med-dosage');
        var frequencyEl = row.querySelector('.ice-med-frequency');
        var rxcuiEl = row.querySelector('.ice-med-rxcui');
        if (dosageEl && dosageEl.value.trim()) return true;
        if (frequencyEl && frequencyEl.value.trim()) return true;
        if (rxcuiEl && rxcuiEl.value.trim()) return true;
        return !!row.querySelector('.ice-med-time:checked');
    }

    function wireList(listEl, addBtn, deleteSelectedBtn, selectAllBtn, hooks) {
        hooks = hooks || {};
        var onListMutate = hooks.onListMutate;
        function notifyMutate() {
            if (typeof onListMutate === 'function') onListMutate();
        }
        function syncDeleteToolbar() {
            if (!deleteSelectedBtn || !listEl) return;
            deleteSelectedBtn.disabled = !listEl.querySelector('.ice-med-select:checked');
        }
        if (!listEl) return;
        listEl.addEventListener('meridianMedRowsRendered', syncDeleteToolbar);
        listEl.addEventListener('change', function (ev) {
            if (ev.target && ev.target.classList && ev.target.classList.contains('ice-med-select')) {
                syncDeleteToolbar();
            }
        });
        if (addBtn) {
            addBtn.addEventListener('click', function () {
                listEl.appendChild(htmlToEl(medRowHtml({})));
                notifyMutate();
                syncDeleteToolbar();
            });
        }
        if (selectAllBtn) {
            selectAllBtn.addEventListener('click', function () {
                var boxes = listEl.querySelectorAll('.ice-med-select');
                if (!boxes.length) return;
                var allChecked = Array.prototype.every.call(boxes, function (cb) {
                    return cb.checked;
                });
                var next = !allChecked;
                boxes.forEach(function (cb) {
                    cb.checked = next;
                });
                syncDeleteToolbar();
            });
        }
        if (deleteSelectedBtn) {
            deleteSelectedBtn.addEventListener('click', function () {
                var cbs = listEl.querySelectorAll('.ice-med-select:checked');
                if (!cbs.length) return;
                var substantive = [];
                cbs.forEach(function (cb) {
                    var row = cb.closest('.ice-med-row');
                    if (row && rowIsSubstantiveForDelete(row)) substantive.push(cb);
                });
                if (substantive.length === 0) {
                    cbs.forEach(function (cb) {
                        var row = cb.closest('.ice-med-row');
                        if (row) row.remove();
                    });
                    if (!listEl.querySelector('.ice-med-row')) {
                        listEl.appendChild(htmlToEl(medRowHtml({})));
                    }
                    notifyMutate();
                    syncDeleteToolbar();
                    return;
                }
                if (!confirm('Remove ' + substantive.length + ' medication row(s) from this list?')) return;
                cbs.forEach(function (cb) {
                    var row = cb.closest('.ice-med-row');
                    if (row) row.remove();
                });
                if (!listEl.querySelector('.ice-med-row')) {
                    listEl.appendChild(htmlToEl(medRowHtml({})));
                }
                notifyMutate();
                syncDeleteToolbar();
                if (typeof hooks.onRowsDeleted === 'function') hooks.onRowsDeleted();
            });
        }
        syncDeleteToolbar();
    }

    function wireAutoSave(listEl, options) {
        options = options || {};
        var debounceMs = options.debounceMs != null ? options.debounceMs : 1000;
        var isEnabled = options.isEnabled;
        var save = options.save;
        if (!listEl || typeof isEnabled !== 'function' || typeof save !== 'function') {
            return { schedule: function () {}, cancel: function () {} };
        }
        var timer = null;
        var running = false;
        function cancel() {
            if (timer) clearTimeout(timer);
            timer = null;
        }
        function schedule() {
            cancel();
            timer = setTimeout(function () {
                timer = null;
                if (!isEnabled() || running) return;
                running = true;
                var p = save();
                function done() {
                    running = false;
                }
                if (p && typeof p.then === 'function') {
                    p.then(done).catch(done);
                } else {
                    done();
                }
            }, debounceMs);
        }
        listEl.addEventListener('input', schedule);
        listEl.addEventListener('change', schedule);
        return { schedule: schedule, cancel: cancel };
    }

    function cloneSnapshot(meds) {
        return JSON.parse(JSON.stringify(meds || []));
    }

    function saveDiff(familyCircleId, initial, rows) {
        var dupErr = validateUniqueMedicationNames(rows);
        if (dupErr) return Promise.reject(new Error(dupErr));
        var chain = Promise.resolve();
        var currentById = {};
        rows.forEach(function (m) {
            if (m.id != null) currentById[m.id] = m;
        });
        initial.forEach(function (m) {
            if (m.id == null) return;
            if (!currentById[m.id]) {
                var delId = m.id;
                chain = chain.then(function () {
                    return meridianApiClient.deleteMedication(familyCircleId, delId);
                });
            }
        });
        rows.forEach(function (m) {
            var name = (m.name || '').trim();
            if (!name) {
                if (m.id != null) {
                    var rmId = m.id;
                    chain = chain.then(function () {
                        return meridianApiClient.deleteMedication(familyCircleId, rmId);
                    });
                }
                return;
            }
            var times = m.medication_times && m.medication_times.length ? m.medication_times : ['Morning'];
            var body = {
                name: name,
                medication_times: times,
                fda_rxcui: (m.fda_rxcui || '').trim() || null
            };
            if (m.dosage) body.dosage = m.dosage;
            if (m.frequency) body.frequency = m.frequency;
            if (m.id != null) {
                var putId = m.id;
                var putBody = body;
                chain = chain.then(function () {
                    return meridianApiClient.updateMedication(familyCircleId, putId, putBody);
                });
            } else {
                var postBody = body;
                chain = chain.then(function () {
                    return meridianApiClient.addMedication(familyCircleId, postBody);
                });
            }
        });
        return chain;
    }

    global.MeridianMedicationsInline = {
        TIME_NAMES: TIME_NAMES,
        TRASH_SVG: TRASH_SVG,
        medRowHtml: medRowHtml,
        htmlToEl: htmlToEl,
        renderRows: renderRows,
        collectRows: collectRows,
        validateUniqueMedicationNames: validateUniqueMedicationNames,
        wireList: wireList,
        wireAutoSave: wireAutoSave,
        cloneSnapshot: cloneSnapshot,
        saveDiff: saveDiff
    };
})(typeof window !== 'undefined' ? window : this);
