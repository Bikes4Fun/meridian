/**
 * ICE / emergency profile editor (webapp). __API_URL__ at build; load meridian_api_base.js and meridian_medications_inline.js first.
 * Medications: inline rows; all saved with Save profile. Emergency contacts: POST /contacts per row.
 */
(function () {
    'use strict';

    var _u = '__API_URL__';
    var API_BASE = meridianApiBaseForFetch(_u.startsWith('http') ? _u : '');
    var _familyCircleId = null;
    var _loadedPaths = { photo_path: null, dnr_document_path: null };
    var _pendingPhotoFile = null;
    var _pendingDnrFile = null;
    var _iceMedsInitial = [];
    var _iceEcInitial = [];
    var _iceMedAutosave = null;

    function escapeAttr(s) {
        return String(s || '').replace(/&/g, '&amp;').replace(/"/g, '&quot;');
    }

    function cloneEcSnapshot(rows) {
        return JSON.parse(JSON.stringify(rows || []));
    }

    function htmlToEl(html) {
        var d = document.createElement('div');
        d.innerHTML = html.trim();
        return d.firstChild;
    }

    function renderIceMedications(medical) {
        if (_iceMedAutosave) _iceMedAutosave.cancel();
        medical = medical || {};
        var container = document.getElementById('iceMedications');
        MeridianMedicationsInline.renderRows(container, medical.medications || []);
    }

    function saveIceMedicationsSilent() {
        var medContainer = document.getElementById('iceMedications');
        if (!medContainer || !_familyCircleId) return Promise.resolve();
        var apiBase = API_BASE || '';
        var medRows = MeridianMedicationsInline.collectRows(medContainer);
        return MeridianMedicationsInline.saveDiff(apiBase, _familyCircleId, _iceMedsInitial, medRows)
            .then(function () {
                return fetch(
                    apiBase + '/api/family_circles/' + encodeURIComponent(_familyCircleId) + '/emergency-profile',
                    { credentials: 'include' }
                );
            })
            .then(function (r) { return r && r.ok ? r.json() : null; })
            .then(function (body) {
                if (!body || !body.data) return;
                var medical = body.data.medical || {};
                _iceMedsInitial = MeridianMedicationsInline.cloneSnapshot(medical.medications || []);
                renderIceMedications(medical);
            })
            .catch(function (err) {
                showIceStatus(err.message || 'Medications save failed', 'error');
            });
    }

    function ecRowHtml(c) {
        c = c || {};
        var id = escapeAttr(c.id || '');
        var name = escapeAttr(c.display_name || '');
        var phone = escapeAttr(c.phone || '');
        var rel = escapeAttr(c.relationship || '');
        var pr = c.emergency_priority || '';
        var selPri = pr === 'secondary_emergency' ? 'secondary_emergency' : (pr === 'primary_emergency' ? 'primary_emergency' : '');
        var optPri = selPri === 'primary_emergency' ? ' selected' : '';
        var optSec = selPri === 'secondary_emergency' ? ' selected' : '';
        var optNone = !selPri ? ' selected' : '';
        return '<div class="ice-ec-row" data-contact-id="' + id + '">' +
            '<input type="text" class="event-input ice-ec-name" placeholder="Name" value="' + name + '">' +
            '<input type="text" class="event-input ice-ec-phone" placeholder="Phone" value="' + phone + '">' +
            '<input type="text" class="event-input ice-ec-rel" placeholder="Relationship" value="' + rel + '">' +
            '<select class="event-input ice-ec-priority" aria-label="ICE priority">' +
            '<option value="primary_emergency"' + optPri + '>Primary emergency</option>' +
            '<option value="secondary_emergency"' + optSec + '>Secondary emergency</option>' +
            '<option value=""' + optNone + '>Not on ICE list</option>' +
            '</select>' +
            '<button type="button" class="btn-inline btn-delete ice-ec-remove">Remove</button>' +
            '</div>';
    }

    function renderEmergencyContacts(contacts) {
        var container = document.getElementById('iceEmergencyContacts');
        if (!container) return;
        container.innerHTML = '';
        var list = contacts || [];
        if (list.length === 0) {
            container.appendChild(htmlToEl(ecRowHtml({ id: 'ec_ice_' + Date.now() })));
        } else {
            list.forEach(function (c) {
                container.appendChild(htmlToEl(ecRowHtml(c)));
            });
        }
    }

    function collectEmergencyContactsFromDom() {
        var out = [];
        document.querySelectorAll('#iceEmergencyContacts .ice-ec-row').forEach(function (row) {
            var id = (row.getAttribute('data-contact-id') || '').trim();
            if (!id) {
                id = 'ec_ice_' + Date.now() + '_' + Math.random().toString(36).slice(2, 9);
                row.setAttribute('data-contact-id', id);
            }
            var nameEl = row.querySelector('.ice-ec-name');
            var phoneEl = row.querySelector('.ice-ec-phone');
            var relEl = row.querySelector('.ice-ec-rel');
            var priEl = row.querySelector('.ice-ec-priority');
            out.push({
                id: id,
                display_name: (nameEl && nameEl.value) ? nameEl.value.trim() : '',
                phone: (phoneEl && phoneEl.value) ? phoneEl.value.trim() : '',
                relationship: (relEl && relEl.value) ? relEl.value.trim() : '',
                emergency_priority: (priEl && priEl.value) ? priEl.value.trim() : ''
            });
        });
        return out;
    }

    function postContact(apiBase, familyCircleId, body) {
        return fetch(
            apiBase + '/api/family_circles/' + encodeURIComponent(familyCircleId) + '/contacts',
            {
                method: 'POST',
                credentials: 'include',
                headers: { 'Content-Type': 'application/json' },
                body: JSON.stringify(body)
            }
        ).then(function (r) {
            if (!r.ok) {
                return r.json().then(function (d) {
                    throw new Error(d.error || 'Contact save failed');
                });
            }
        });
    }

    function saveEmergencyContacts(apiBase, familyCircleId, initialList, rows) {
        var chain = Promise.resolve();
        var initialById = {};
        initialList.forEach(function (c) {
            if (c.id) initialById[c.id] = c;
        });
        var currentById = {};
        rows.forEach(function (c) {
            if (c.id) currentById[c.id] = c;
        });
        Object.keys(initialById).forEach(function (kid) {
            if (!currentById[kid]) {
                var prev = initialById[kid];
                chain = chain.then(function () {
                    return postContact(apiBase, familyCircleId, {
                        id: prev.id,
                        display_name: prev.display_name || '',
                        phone: prev.phone || null,
                        relationship: prev.relationship || null,
                        emergency_priority: null
                    });
                });
            }
        });
        rows.forEach(function (c) {
            var name = (c.display_name || '').trim();
            if (!name) return;
            var payload = {
                id: c.id,
                display_name: name,
                phone: c.phone || null,
                relationship: c.relationship || null,
                emergency_priority: c.emergency_priority || null
            };
            chain = chain.then(function () {
                return postContact(apiBase, familyCircleId, payload);
            });
        });
        return chain;
    }

    function showIceStatus(message, type) {
        var container = document.getElementById('iceStatus');
        if (!container) return;
        var box = document.createElement('div');
        box.className = type;
        box.textContent = message;
        container.appendChild(box);
    }

    function setUploadButtonState(buttonId, enabled) {
        var btn = document.getElementById(buttonId);
        if (!btn) return;
        btn.disabled = !enabled;
    }

    function setBanner(text, isError) {
        var el = document.getElementById('iceBanner');
        if (!el) return;
        if (!text) {
            el.hidden = true;
            el.textContent = '';
            el.classList.remove('ice-banner--error');
            return;
        }
        el.hidden = false;
        el.textContent = text;
        el.classList.toggle('ice-banner--error', !!isError);
    }

    // TODO: When conditions/allergies become editable on this page, add inputs and merge into save payload;
    // today this only updates display from emergency profile GET.
    function syncConditionsAllergiesFromMedical(medical) {
        medical = medical || {};
        var condEl = document.getElementById('iceConditions');
        if (condEl) condEl.textContent = medical.conditions || '—';

        var algEl = document.getElementById('iceAllergies');
        if (algEl) {
            algEl.innerHTML = '';
            var allergies = medical.allergies || [];
            if (allergies.length === 0) {
                algEl.innerHTML = '<li class="muted">None listed</li>';
            } else {
                allergies.forEach(function (a) {
                    var li = document.createElement('li');
                    li.textContent = a;
                    algEl.appendChild(li);
                });
            }
        }
    }

    function applyProfile(data) {
        var idInput = document.getElementById('iceCareRecipientId');
        var saveBtn = document.getElementById('iceSaveBtn');
        if (!data) {
            if (idInput) idInput.value = '';
            if (saveBtn) {
                saveBtn.disabled = true;
                saveBtn.title = 'No care recipient on file yet for this family circle.';
            }
            setBanner(
                'No emergency profile data yet for this family. Demo seed includes a care recipient (e.g. fm_care_001); until then, fields are disabled for save.',
                true
            );
            syncConditionsAllergiesFromMedical({});
            _iceMedsInitial = [];
            renderIceMedications({ medications: [] });
            _iceEcInitial = [];
            renderEmergencyContacts([]);
            return;
        }

        setBanner('', false);
        if (saveBtn) {
            saveBtn.disabled = false;
            saveBtn.title = '';
        }

        var crId = data.care_recipient_user_id || '';
        if (idInput) idInput.value = crId;

        var profile = data.profile || {};
        var nameEl = document.getElementById('iceName');
        var dobEl = document.getElementById('iceDob');
        if (nameEl) nameEl.value = profile.name || '';
        if (dobEl) dobEl.value = (profile.dob || '').slice(0, 10);

        var medical = data.medical || {};
        var dnrEl = document.getElementById('iceDnr');
        if (dnrEl) dnrEl.checked = !!medical.dnr;

        var emergency = data.emergency || {};
        var proxy = emergency.proxy || {};
        var proxyNameEl = document.getElementById('iceProxyName');
        var proxyPhoneEl = document.getElementById('iceProxyPhone');
        if (proxyNameEl) proxyNameEl.value = proxy.name || '';
        if (proxyPhoneEl) proxyPhoneEl.value = data.medical_proxy_phone || '';

        var poaNameEl = document.getElementById('icePoaName');
        var poaPhoneEl = document.getElementById('icePoaPhone');
        if (poaNameEl) poaNameEl.value = data.poa_name || '';
        if (poaPhoneEl) poaPhoneEl.value = data.poa_phone || '';

        var notesEl = document.getElementById('iceNotes');
        if (notesEl) notesEl.value = data.notes || '';

        _loadedPaths.photo_path = data.photo_path || null;
        _loadedPaths.dnr_document_path = data.dnr_document_path || null;
        updateDnrDocLink(crId);

        var prev = document.getElementById('icePhotoPreview');
        if (prev && crId) {
            prev.hidden = false;
            prev.src = (API_BASE || '') + '/api/users/' + encodeURIComponent(crId) + '/photo?v=' + Date.now();
            prev.onerror = function () { prev.hidden = true; };
        }

        syncConditionsAllergiesFromMedical(medical);
        _iceMedsInitial = MeridianMedicationsInline.cloneSnapshot(medical.medications);
        renderIceMedications(medical);
        var ecs = data.emergency_contacts || [];
        _iceEcInitial = cloneEcSnapshot(ecs);
        renderEmergencyContacts(ecs);
    }

    function updateDnrDocLink(crId) {
        var link = document.getElementById('iceDnrDocLink');
        if (!link) return;
        if (crId && _loadedPaths.dnr_document_path && _familyCircleId) {
            link.hidden = false;
            link.href = (API_BASE || '') + '/api/family_circles/' + encodeURIComponent(_familyCircleId) +
                '/care-recipients/' + encodeURIComponent(crId) + '/dnr-document';
        } else {
            link.hidden = true;
            link.href = '#';
        }
    }

    function uploadCareRecipientDnrDocument(file) {
        var apiBase = API_BASE || '';
        var crId = (document.getElementById('iceCareRecipientId') || {}).value;
        if (!file || !crId) return Promise.resolve(false);
        if (!_familyCircleId) {
            showIceStatus('Still loading; wait a moment and choose the file again.', 'error');
            return Promise.resolve(false);
        }
        var fd = new FormData();
        fd.append('document', file);
        fd.append('care_recipient_user_id', crId);
        return fetch(
            apiBase + '/api/family_circles/' + encodeURIComponent(_familyCircleId) + '/care-recipient-dnr-document',
            { method: 'POST', credentials: 'include', body: fd }
        )
            .then(function (r) {
                return r.json().then(function (j) {
                    if (!r.ok) throw new Error((j && j.error) ? j.error : 'Upload failed');
                    return j;
                });
            })
            .then(function (body) {
                var d = body && body.data;
                if (d && d.dnr_document_path) _loadedPaths.dnr_document_path = d.dnr_document_path;
                updateDnrDocLink(crId);
                showIceStatus('Document uploaded.', 'success');
                return true;
            })
            .catch(function (err) {
                showIceStatus(err.message || 'Document upload failed', 'error');
                return false;
            });
    }

    function uploadCareRecipientPhoto(file) {
        var apiBase = API_BASE || '';
        var crId = (document.getElementById('iceCareRecipientId') || {}).value;
        if (!file || !crId) return Promise.resolve(false);
        if (!_familyCircleId) {
            showIceStatus('Still loading; wait a moment and choose the photo again.', 'error');
            return Promise.resolve(false);
        }
        var fd = new FormData();
        fd.append('photo', file);
        fd.append('care_recipient_user_id', crId);
        return fetch(
            apiBase + '/api/family_circles/' + encodeURIComponent(_familyCircleId) + '/care-recipient-photo',
            { method: 'POST', credentials: 'include', body: fd }
        )
            .then(function (r) {
                return r.json().then(function (j) {
                    if (!r.ok) throw new Error((j && j.error) ? j.error : 'Upload failed');
                    return j;
                });
            })
            .then(function (body) {
                var d = body && body.data;
                if (d && d.photo_path) _loadedPaths.photo_path = d.photo_path;
                var prev = document.getElementById('icePhotoPreview');
                if (prev) {
                    prev.hidden = false;
                    prev.src = apiBase + '/api/users/' + encodeURIComponent(crId) + '/photo?v=' + Date.now();
                    prev.onerror = function () {
                        showIceStatus('Photo saved but preview could not load.', 'error');
                    };
                }
                showIceStatus('Photo uploaded.', 'success');
                return true;
            })
            .catch(function (err) {
                showIceStatus(err.message || 'Photo upload failed', 'error');
                return false;
            });
    }

    function wireUploadPreviews() {
        var photoInput = document.getElementById('icePhoto');
        var prev = document.getElementById('icePhotoPreview');
        var photoName = document.getElementById('icePhotoName');
        var photoUploadBtn = document.getElementById('icePhotoUploadBtn');
        if (photoInput && prev) {
            photoInput.addEventListener('change', function () {
                var f = photoInput.files && photoInput.files[0];
                _pendingPhotoFile = f || null;
                setUploadButtonState('icePhotoUploadBtn', !!_pendingPhotoFile);
                if (photoName) photoName.textContent = f ? f.name : '';
                if (!f) return;
                var r = new FileReader();
                r.onload = function () {
                    prev.hidden = false;
                    prev.src = r.result;
                };
                r.readAsDataURL(f);
            });
        }
        if (photoUploadBtn) {
            photoUploadBtn.addEventListener('click', function () {
                if (!_pendingPhotoFile) return;
                setUploadButtonState('icePhotoUploadBtn', false);
                uploadCareRecipientPhoto(_pendingPhotoFile).then(function (ok) {
                    if (ok) {
                        _pendingPhotoFile = null;
                        if (photoInput) photoInput.value = '';
                        if (photoName) photoName.textContent = '';
                    }
                    setUploadButtonState('icePhotoUploadBtn', !!_pendingPhotoFile);
                });
            });
        }
        var dnrInput = document.getElementById('iceDnrDoc');
        var dnrName = document.getElementById('iceDnrDocName');
        var dnrUploadBtn = document.getElementById('iceDnrUploadBtn');
        if (dnrInput && dnrName) {
            dnrInput.addEventListener('change', function () {
                var f = dnrInput.files && dnrInput.files[0];
                _pendingDnrFile = f || null;
                setUploadButtonState('iceDnrUploadBtn', !!_pendingDnrFile);
                dnrName.textContent = f ? f.name : '';
            });
        }
        if (dnrUploadBtn) {
            dnrUploadBtn.addEventListener('click', function () {
                if (!_pendingDnrFile) return;
                setUploadButtonState('iceDnrUploadBtn', false);
                uploadCareRecipientDnrDocument(_pendingDnrFile).then(function (ok) {
                    if (ok) {
                        _pendingDnrFile = null;
                        if (dnrInput) dnrInput.value = '';
                        if (dnrName) dnrName.textContent = '';
                    }
                    setUploadButtonState('iceDnrUploadBtn', !!_pendingDnrFile);
                });
            });
        }
    }

    function init() {
        var apiBase = API_BASE || '';
        var pdfLink = document.getElementById('icePdfLink');
        wireUploadPreviews();

        var medContainer = document.getElementById('iceMedications');
        var addMedBtn = document.getElementById('iceAddMedBtn');
        var selAllMedBtn = document.getElementById('iceMedsSelectAllBtn');
        var delMedBtn = document.getElementById('iceMedsDeleteSelectedBtn');

        _iceMedAutosave = MeridianMedicationsInline.wireAutoSave(medContainer, {
            isEnabled: function () {
                var c = document.getElementById('iceMedsAutoSave');
                return !!(c && c.checked);
            },
            debounceMs: 1000,
            save: function () {
                return saveIceMedicationsSilent();
            }
        });

        MeridianMedicationsInline.wireList(medContainer, addMedBtn, delMedBtn, selAllMedBtn, {
            onListMutate: function () {
                if (_iceMedAutosave) _iceMedAutosave.schedule();
            }
        });

        var iceMedsAuto = document.getElementById('iceMedsAutoSave');
        if (iceMedsAuto) {
            iceMedsAuto.addEventListener('change', function () {
                if (this.checked && _iceMedAutosave) _iceMedAutosave.schedule();
            });
        }

        var ecContainer = document.getElementById('iceEmergencyContacts');
        var addEcBtn = document.getElementById('iceAddEmergencyContactBtn');
        if (addEcBtn && ecContainer) {
            addEcBtn.addEventListener('click', function () {
                ecContainer.appendChild(htmlToEl(ecRowHtml({ id: 'ec_ice_' + Date.now() })));
            });
            ecContainer.addEventListener('click', function (e) {
                if (!e.target.classList.contains('ice-ec-remove')) return;
                var row = e.target.closest('.ice-ec-row');
                if (row) row.remove();
                if (!ecContainer.querySelector('.ice-ec-row')) {
                    ecContainer.appendChild(htmlToEl(ecRowHtml({ id: 'ec_ice_' + Date.now() })));
                }
            });
        }

        fetch(apiBase + '/api/session', { credentials: 'include' })
            .then(function (r) {
                if (r.status === 401) {
                    window.location.href = meridianLoginPageWithReturn();
                    return null;
                }
                return r.ok ? r.json() : null;
            })
            .then(function (session) {
                if (!session || !session.family_circle_id) {
                    window.location.href = meridianLoginPageWithReturn();
                    return;
                }
                _familyCircleId = session.family_circle_id;
                if (pdfLink) {
                    pdfLink.href = apiBase + '/api/family_circles/' + encodeURIComponent(_familyCircleId) + '/emergency-profile/pdf';
                }
                return fetch(
                    apiBase + '/api/family_circles/' + encodeURIComponent(_familyCircleId) + '/emergency-profile',
                    { credentials: 'include' }
                );
            })
            .then(function (r) {
                if (!r) return null;
                return r.ok ? r.json() : null;
            })
            .then(function (body) {
                var pending = document.getElementById('icePending');
                var app = document.getElementById('iceApp');
                if (pending) pending.hidden = true;
                if (app) app.hidden = false;
                var data = body && body.data ? body.data : null;
                applyProfile(data);
            })
            .catch(function () {
                var pending = document.getElementById('icePending');
                if (pending) pending.textContent = 'Could not load.';
            });

        var form = document.getElementById('iceForm');
        if (form) {
            form.addEventListener('submit', function (e) {
                e.preventDefault();
                var crId = (document.getElementById('iceCareRecipientId') || {}).value;
                if (!crId) {
                    showIceStatus('Cannot save without a care recipient id on file.', 'error');
                    return;
                }
                var payload = {
                    care_recipient_user_id: crId,
                    profile: {
                        name: (document.getElementById('iceName') || {}).value.trim(),
                        dob: (document.getElementById('iceDob') || {}).value || null
                    },
                    medical: {
                        dnr: !!(document.getElementById('iceDnr') || {}).checked
                    },
                    emergency: {
                        proxy: {
                            name: (document.getElementById('iceProxyName') || {}).value.trim()
                        }
                    },
                    medical_proxy_phone: (document.getElementById('iceProxyPhone') || {}).value.trim() || null,
                    poa_name: (document.getElementById('icePoaName') || {}).value.trim() || null,
                    poa_phone: (document.getElementById('icePoaPhone') || {}).value.trim() || null,
                    notes: (document.getElementById('iceNotes') || {}).value.trim() || null,
                    photo_path: _loadedPaths.photo_path,
                    dnr_document_path: _loadedPaths.dnr_document_path
                };
                var medContainer = document.getElementById('iceMedications');
                var medRows = MeridianMedicationsInline.collectRows(medContainer);
                var ecRows = collectEmergencyContactsFromDom();
                MeridianMedicationsInline.saveDiff(apiBase, _familyCircleId, _iceMedsInitial, medRows)
                    .then(function () {
                        return saveEmergencyContacts(apiBase, _familyCircleId, _iceEcInitial, ecRows);
                    })
                    .then(function () {
                        return fetch(
                            apiBase + '/api/family_circles/' + encodeURIComponent(_familyCircleId) + '/emergency-profile',
                            {
                                method: 'PUT',
                                credentials: 'include',
                                headers: { 'Content-Type': 'application/json' },
                                body: JSON.stringify(payload)
                            }
                        );
                    })
                    .then(function (r) {
                        return r.json().then(function (d) {
                            if (!r.ok) throw new Error(d.error || 'Save failed');
                            return d;
                        });
                    })
                    .then(function () {
                        return fetch(
                            apiBase + '/api/family_circles/' + encodeURIComponent(_familyCircleId) + '/emergency-profile',
                            { credentials: 'include' }
                        );
                    })
                    .then(function (r) {
                        return r.ok ? r.json() : null;
                    })
                    .then(function (body) {
                        var data = body && body.data ? body.data : null;
                        if (data) applyProfile(data);
                        showIceStatus('Profile saved.', 'success');
                    })
                    .catch(function (err) {
                        showIceStatus(err.message || 'Save failed', 'error');
                    });
            });
        }
    }

    if (document.readyState === 'loading') {
        document.addEventListener('DOMContentLoaded', init);
    } else {
        init();
    }
})();
