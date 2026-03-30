/**
 * Kiosk Medications screen: same inline editor as the webapp (meridian_medications_inline.js).
 * Runs after each showScreen via window.onKioskScreenShown (scripts in injected HTML do not run).
 */
(function () {
    'use strict';

    var _inlineSnapshot = [];
    var _kioskMedAutosave = null;

    var SAVE_MEDS_DISK_SVG =
        '<svg xmlns="http://www.w3.org/2000/svg" width="18" height="18" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round">' +
        '<path d="M19 21H5a2 2 0 0 1-2-2V5a2 2 0 0 1 2-2h11l5 5v11a2 2 0 0 1-2 2z"/><polyline points="17 21 17 13 7 13 7 21"/><line x1="7" y1="3" x2="17" y2="3"/></svg>';

    function apiBase() {
        return '';
    }

    function statusMsg(msg) {
        if (typeof showToast === 'function') {
            showToast(msg);
        } else {
            alert(msg);
        }
    }

    function loadInlineMedsFromProfile(fcId, inlineList) {
        if (_kioskMedAutosave) _kioskMedAutosave.cancel();
        fetch(
            apiBase() + '/api/family_circles/' + encodeURIComponent(fcId) + '/emergency-profile',
            { credentials: 'include' }
        )
            .then(function (r) { return r.ok ? r.json() : null; })
            .then(function (body) {
                var data = body && body.data;
                var meds = (data && data.medical && data.medical.medications) || [];
                _inlineSnapshot = MeridianMedicationsInline.cloneSnapshot(meds);
                MeridianMedicationsInline.renderRows(inlineList, meds);
            })
            .catch(function () {
                statusMsg('Could not load medications for editing');
            });
    }

    function mountMedicationsEditor() {
        var root = document.getElementById('kioskMedsEditorRoot');
        if (!root) return;
        if (typeof MeridianMedicationsInline === 'undefined') {
            root.innerHTML = '<p class="kiosk-caption">Editor failed to load. Reload or use the web dashboard.</p>';
            return;
        }
        var trash = MeridianMedicationsInline.TRASH_SVG;
        root.innerHTML =
            '<div class="ice-med-toolbar-top">' +
            '<button type="button" id="kioskMedsSelectAllBtn" class="btn-inline ice-med-select-all-btn">Select all</button>' +
            '<label class="ice-med-autosave-label">' +
            '<input type="checkbox" id="kioskMedsAutoSave" class="ice-med-autosave-cb">' +
            'Save as you go</label>' +
            '</div>' +
            '<div class="ice-medications-editor" id="kioskMedsInlineList"></div>' +
            '<div class="ice-med-editor-actions kiosk-meds-actions">' +
            '<button type="button" id="kioskMedsAddBtn" class="btn-add">Add medication</button>' +
            '<button type="button" id="kioskMedsDeleteSelectedBtn" class="btn-inline btn-delete ice-med-delete-selected-btn">' +
            '<span class="ice-med-delete-selected-btn__icon" aria-hidden="true">' + trash + '</span>' +
            '<span>Delete selected</span></button>' +
            '<button type="button" id="kioskMedsSaveBtn" class="ice-med-save-btn">' +
            '<span class="ice-med-save-btn__icon" aria-hidden="true">' + SAVE_MEDS_DISK_SVG + '</span>' +
            'Save medications</button>' +
            '</div>';

        var inlineList = document.getElementById('kioskMedsInlineList');
        var addBtn = document.getElementById('kioskMedsAddBtn');
        var selAllBtn = document.getElementById('kioskMedsSelectAllBtn');
        var delBtn = document.getElementById('kioskMedsDeleteSelectedBtn');
        var saveBtn = document.getElementById('kioskMedsSaveBtn');

        function persistMedications(silent) {
            return fetch(apiBase() + '/api/session', { credentials: 'include' })
                .then(function (r) { return r.ok ? r.json() : null; })
                .then(function (session) {
                    var fcId = session && session.family_circle_id;
                    if (!fcId) {
                        if (!silent) statusMsg('Not signed in');
                        return null;
                    }
                    var rows = MeridianMedicationsInline.collectRows(inlineList);
                    return MeridianMedicationsInline.saveDiff(apiBase(), fcId, _inlineSnapshot, rows).then(function () {
                        return fcId;
                    });
                })
                .then(function (fcId) {
                    if (!fcId) return;
                    if (!silent) statusMsg('Medications saved');
                    return fetch(
                        apiBase() + '/api/family_circles/' + encodeURIComponent(fcId) + '/emergency-profile',
                        { credentials: 'include' }
                    );
                })
                .then(function (r) { return r && r.ok ? r.json() : null; })
                .then(function (body) {
                    if (!body || !body.data) return;
                    var meds = (body.data.medical && body.data.medical.medications) || [];
                    _inlineSnapshot = MeridianMedicationsInline.cloneSnapshot(meds);
                    if (_kioskMedAutosave) _kioskMedAutosave.cancel();
                    MeridianMedicationsInline.renderRows(inlineList, meds);
                })
                .catch(function (err) {
                    statusMsg((err && err.message) ? err.message : 'Save failed');
                });
        }

        _kioskMedAutosave = MeridianMedicationsInline.wireAutoSave(inlineList, {
            isEnabled: function () {
                var c = document.getElementById('kioskMedsAutoSave');
                return !!(c && c.checked);
            },
            debounceMs: 1000,
            save: function () {
                return persistMedications(true);
            }
        });

        MeridianMedicationsInline.wireList(inlineList, addBtn, delBtn, selAllBtn, {
            onListMutate: function () {
                if (_kioskMedAutosave) _kioskMedAutosave.schedule();
            }
        });

        var kioskAuto = document.getElementById('kioskMedsAutoSave');
        if (kioskAuto) {
            kioskAuto.addEventListener('change', function () {
                if (this.checked && _kioskMedAutosave) _kioskMedAutosave.schedule();
            });
        }

        if (saveBtn) {
            saveBtn.addEventListener('click', function () {
                persistMedications(false);
            });
        }

        fetch(apiBase() + '/api/session', { credentials: 'include' })
            .then(function (r) { return r.ok ? r.json() : null; })
            .then(function (session) {
                var fcId = session && session.family_circle_id;
                if (!fcId) {
                    var host = root.querySelector('.ice-medications-editor');
                    if (host) {
                        host.innerHTML = '<p class="kiosk-caption">Sign in required.</p>';
                    }
                    return;
                }
                loadInlineMedsFromProfile(fcId, inlineList);
            })
            .catch(function () {
                statusMsg('Could not verify session');
            });
    }

    window.onKioskScreenShown = function (name) {
        if (name === 'medications') {
            mountMedicationsEditor();
        }
    };
})();
