/**
 * Shared inline medication editor: row markup, DOM collect, and diff save vs /medications API.
 * Load before ice_editor.js and medications.js (no __API_URL__; callers pass api base).
 */
(function (global) {
    'use strict';

    var TIME_NAMES = ['Morning', 'Noon', 'Evening', 'prn'];

    function escapeAttr(s) {
        return String(s || '').replace(/&/g, '&amp;').replace(/"/g, '&quot;');
    }

    function htmlToEl(html) {
        var d = document.createElement('div');
        d.innerHTML = html.trim();
        return d.firstChild;
    }

    var TRASH_SVG =
        '<svg xmlns="http://www.w3.org/2000/svg" width="20" height="20" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round">' +
        '<path d="M3 6h18"/><path d="M19 6v14a2 2 0 0 1-2 2H7a2 2 0 0 1-2-2V6"/>' +
        '<path d="M8 6V4a2 2 0 0 1 2-2h4a2 2 0 0 1 2 2v2"/><line x1="10" y1="11" x2="10" y2="17"/><line x1="14" y1="11" x2="14" y2="17"/></svg>';

    function medRowHtml(m) {
        m = m || {};
        var idAttr = m.id != null && m.id !== '' ? String(m.id) : '';
        var name = escapeAttr(m.name || '');
        var dosage = escapeAttr(m.dosage || '');
        var frequency = escapeAttr(m.frequency || '');
        var rxcui = escapeAttr((m.fda_rxcui != null && m.fda_rxcui !== '') ? String(m.fda_rxcui) : '');
        var times = m.medication_times || [];
        var timeChecks = TIME_NAMES.map(function (t) {
            var lbl = t === 'prn' ? 'As needed' : t;
            var chk = times.indexOf(t) >= 0 ? ' checked' : '';
            return '<label class="ice-med-time-opt"><input type="checkbox" class="ice-med-time" value="' +
                escapeAttr(t) + '"' + chk + '> ' + lbl + '</label>';
        }).join('');
        return '<div class="ice-med-row" data-med-id="' + escapeAttr(idAttr) + '">' +
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
            '<input type="checkbox" class="ice-med-select" aria-label="Select to remove this row">' +
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

    function wireList(listEl, addBtn, deleteSelectedBtn, selectAllBtn, hooks) {
        hooks = hooks || {};
        var onListMutate = hooks.onListMutate;
        function notifyMutate() {
            if (typeof onListMutate === 'function') onListMutate();
        }
        if (!listEl) return;
        if (addBtn) {
            addBtn.addEventListener('click', function () {
                listEl.appendChild(htmlToEl(medRowHtml({})));
                notifyMutate();
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
            });
        }
        if (deleteSelectedBtn) {
            deleteSelectedBtn.addEventListener('click', function () {
                var cbs = listEl.querySelectorAll('.ice-med-select:checked');
                if (!cbs.length) return;
                if (!confirm('Remove ' + cbs.length + ' medication row(s) from this list?')) return;
                cbs.forEach(function (cb) {
                    var row = cb.closest('.ice-med-row');
                    if (row) row.remove();
                });
                if (!listEl.querySelector('.ice-med-row')) {
                    listEl.appendChild(htmlToEl(medRowHtml({})));
                }
                notifyMutate();
            });
        }
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

    function saveDiff(apiBase, familyCircleId, initial, rows) {
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
                    return fetch(
                        apiBase + '/api/family_circles/' + encodeURIComponent(familyCircleId) + '/medications/' + delId,
                        { method: 'DELETE', credentials: 'include' }
                    ).then(function (r) {
                        if (!r.ok) {
                            return r.json().then(function (d) {
                                throw new Error(d.error || 'Delete medication failed');
                            });
                        }
                    });
                });
            }
        });
        rows.forEach(function (m) {
            var name = (m.name || '').trim();
            if (!name) {
                if (m.id != null) {
                    var rmId = m.id;
                    chain = chain.then(function () {
                        return fetch(
                            apiBase + '/api/family_circles/' + encodeURIComponent(familyCircleId) + '/medications/' + rmId,
                            { method: 'DELETE', credentials: 'include' }
                        ).then(function (r) {
                            if (!r.ok) {
                                return r.json().then(function (d) {
                                    throw new Error(d.error || 'Delete medication failed');
                                });
                            }
                        });
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
                    return fetch(
                        apiBase + '/api/family_circles/' + encodeURIComponent(familyCircleId) + '/medications/' + putId,
                        {
                            method: 'PUT',
                            credentials: 'include',
                            headers: { 'Content-Type': 'application/json' },
                            body: JSON.stringify(putBody)
                        }
                    ).then(function (r) {
                        if (!r.ok) {
                            return r.json().then(function (d) {
                                throw new Error(d.error || 'Update medication failed');
                            });
                        }
                    });
                });
            } else {
                var postBody = body;
                chain = chain.then(function () {
                    return fetch(
                        apiBase + '/api/family_circles/' + encodeURIComponent(familyCircleId) + '/medications',
                        {
                            method: 'POST',
                            credentials: 'include',
                            headers: { 'Content-Type': 'application/json' },
                            body: JSON.stringify(postBody)
                        }
                    ).then(function (r) {
                        if (!r.ok) {
                            return r.json().then(function (d) {
                                throw new Error(d.error || 'Add medication failed');
                            });
                        }
                    });
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
        wireList: wireList,
        wireAutoSave: wireAutoSave,
        cloneSnapshot: cloneSnapshot,
        saveDiff: saveDiff
    };
})(typeof window !== 'undefined' ? window : this);
