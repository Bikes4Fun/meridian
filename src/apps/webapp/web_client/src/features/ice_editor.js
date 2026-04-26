/**
 * Webapp ICE (emergency profile) editor: medical block uses MeridianMedicationsInline; contacts/photos/DNR via emergency-profile + contacts APIs. __API_URL__ injected at build.
 * Scope: ice_editor page behavior. Not: kiosk emergency screen, PDF print flow, or kiosk-only bridge APIs.
 */
(function () {
    'use strict';

    var _familyCircleId = null;
    var _loadedPaths = { photo_path: null, dnr_document_path: null };
    var _pendingDnrFile = null;
    var _iceMedsInitial = [];
    var _iceEcInitial = [];
    var _iceMedAutosave = null;
    var _documents = [];

    function cloneEcSnapshot(rows) {
        return JSON.parse(JSON.stringify(rows || []));
    }

    function htmlToEl(html) {
        var d = document.createElement('div');
        d.innerHTML = html.trim();
        return d.firstChild;
    }

    function escapeHtml(s) {
        return String(s || '').replace(/</g, '&lt;').replace(/>/g, '&gt;');
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
        var medRows = MeridianMedicationsInline.collectRows(medContainer);
        return MeridianMedicationsInline.saveDiff(_familyCircleId, _iceMedsInitial, medRows)
            .then(function () {
                return meridianApiClient.getEmergencyProfile(_familyCircleId);
            })
            .then(function (response) {
                var body = response && response.body;
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
        var id = meridianEscapeAttr(c.id || '');
        var name = meridianEscapeAttr(c.display_name || '');
        var phone = meridianEscapeAttr(c.phone || '');
        var rel = meridianEscapeAttr(c.relationship || '');
        var pr = c.emergency_priority || '';
        var selPri = pr === 'secondary_emergency' ? 'secondary_emergency' : (pr === 'primary_emergency' ? 'primary_emergency' : '');
        var optPri = selPri === 'primary_emergency' ? ' selected' : '';
        var optSec = selPri === 'secondary_emergency' ? ' selected' : '';
        var optNone = !selPri ? ' selected' : '';
        return '<div class="ice-ec-row ec-line" data-contact-id="' + id + '">' +
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

    function postContact(familyCircleId, body) {
        return meridianApiClient.postContact(familyCircleId, body);
    }

    function saveEmergencyContacts(familyCircleId, initialList, rows) {
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
                    return postContact(familyCircleId, {
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
                return postContact(familyCircleId, payload);
            });
        });
        return chain;
    }

    function showIceStatus(message, type) {
        var container = document.getElementById('iceStatus');
        if (!container) return;
        container.innerHTML = '';
        var box = document.createElement('div');
        box.className = type;
        box.textContent = message;
        container.appendChild(box);
        setTimeout(function () { if (box.parentNode) box.parentNode.removeChild(box); }, 3000);
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

    function iceCompletenessModel(data) {
        var d = data || {};
        var profile = d.profile || {};
        var medical = d.medical || {};
        var contacts = d.emergency_contacts || [];
        var hasName = !!String(profile.name || '').trim();
        var hasDob = !!String(profile.dob || '').trim();
        var hasDnr = Object.prototype.hasOwnProperty.call(medical, 'dnr');
        var hasEmergencyContact = contacts.some(function (c) {
            return !!String((c && c.display_name) || '').trim();
        });
        var hasProxyName = !!String((d.emergency && d.emergency.proxy && d.emergency.proxy.name) || '').trim();
        var hasProxyPhone = !!String(d.medical_proxy_phone || '').trim();
        var hasProxy = hasProxyName && hasProxyPhone;
        var hasPhoto = !!String(d.photo_path || '').trim();
        var hasDnrDoc = !!String(d.dnr_document_path || '').trim();
        var done = [hasName, hasDob, hasDnr, hasEmergencyContact, hasProxy, hasPhoto, hasDnrDoc]
            .filter(Boolean).length;
        var primaryExists = contacts.some(function (c) {
            return (c && c.emergency_priority) === 'primary_emergency';
        });
        var warnings = [];
        if (!hasDnrDoc) warnings.push('Missing DNR/POLST document');
        if (!primaryExists) warnings.push('No primary emergency contact');
        if (!hasProxyPhone) warnings.push('Missing proxy phone number');
        return { done: done, warnings: warnings };
    }

    function renderIceCompleteness(data) {
        var host = document.getElementById('healthIceCompleteness') || document.getElementById('iceCompleteness');
        if (!host) return;
        var model = iceCompletenessModel(data);
        var done = model.done || 0;
        var sm = document.getElementById('iceCompletionSummaryMain');
        if (sm) sm.textContent = done + ' of 7 fields complete';
        var pct = Math.max(0, Math.min(100, Math.round((done / 7) * 100)));
        var completeHints = [];
        if (done >= 1) completeHints.push('Identity started');
        if (done >= 3) completeHints.push('Core code-status fields saved');
        if (done >= 5) completeHints.push('At least one contact and proxy info present');
        if (done >= 7) completeHints.push('Critical fields complete');
        if (!completeHints.length) completeHints.push('No core fields complete yet');
        var completeHtml = '<ul class="list-tight">' + completeHints.map(function (w) {
            return '<li>' + escapeHtml(w) + '</li>';
        }).join('') + '</ul>';
        var missingHtml = model.warnings.length
            ? '<ul class="list-tight list-tight--miss">' + model.warnings.map(function (w) {
                return '<li>' + escapeHtml(w) + '</li>';
            }).join('') + '</ul>'
            : '<ul class="list-tight list-tight--miss"><li>No urgent missing items.</li></ul>';
        host.innerHTML =
            '<div class="bar bar--slim"><div style="height:100%;width:' + pct + '%;background:#c4a574"></div></div>' +
            '<div class="completion-sec">' +
            '<p class="completion-sec-h">In place</p>' +
            completeHtml +
            '</div>' +
            '<div class="completion-sec">' +
            '<p class="completion-sec-h">Still to do</p>' +
            missingHtml +
            '</div>';
    }

    function allergyRowHtml(allergy) {
        var allergen = typeof allergy === 'string' ? allergy : (allergy && allergy.allergen) || '';
        var reaction = typeof allergy === 'string' ? '' : (allergy && allergy.reaction) || '';
        return '<div class="allergy-line">' +
            '<input class="input-tight ice-allergy-value" type="text" value="' + escapeHtml(allergen) + '" placeholder="Substance / drug">' +
            '<input class="input-tight ice-allergy-reaction" type="text" value="' + escapeHtml(reaction) + '" placeholder="Reaction (optional)">' +
            '<button type="button" class="btn-inline btn-delete ice-allergy-remove">✕</button>' +
            '</div>';
    }

    function syncConditionsAllergiesFromMedical(medical) {
        medical = medical || {};
        var condEl = document.getElementById('iceConditions');
        if (condEl) {
            var ct = medical.conditions || '';
            condEl.value = ct;
        }

        renderAllergyRows(medical.allergies || []);
    }

    function renderAllergyRows(allergens) {
        var algEl = document.getElementById('iceAllergies');
        if (!algEl) return;
        if (!allergens.length) {
            algEl.innerHTML = '<p class="tiny muted" id="iceAllergiesEmpty">None listed — use + Allergy to add</p>';
        } else {
            algEl.innerHTML = allergens.map(allergyRowHtml).join('');
        }
    }

    function collectAllergyRows() {
        var out = [];
        document.querySelectorAll('#iceAllergies .allergy-line').forEach(function (row) {
            var allergenInp = row.querySelector('.ice-allergy-value');
            var reactionInp = row.querySelector('.ice-allergy-reaction');
            var allergen = allergenInp ? (allergenInp.value || '').trim() : '';
            if (!allergen) return;
            out.push({ allergen: allergen, reaction: reactionInp ? (reactionInp.value || '').trim() : '' });
        });
        return out;
    }

    function dnrValueFromForm() {
        var dnrEl = document.getElementById('iceDnr');
        if (!dnrEl) return 0;
        if (dnrEl.tagName === 'SELECT') {
            return parseInt(dnrEl.value, 10) || 0;
        }
        return dnrEl.checked ? 1 : 0;
    }

    function getFullName() {
        var first = (document.getElementById('iceFirstName') || {}).value || '';
        var last = (document.getElementById('iceLastName') || {}).value || '';
        return [first.trim(), last.trim()].filter(Boolean).join(' ');
    }

    function updateIceIdentityStrip() {
        var name = getFullName();
        var av = document.getElementById('iceIdentityAvatar');
        if (av) {
            var t = (name || '').trim();
            if (!t) {
                av.textContent = '—';
            } else {
                var parts = t.split(/\s+/);
                var a = (parts[0].charAt(0) || '').toUpperCase();
                var b = (parts.length > 1 ? parts[parts.length - 1].charAt(0) : a).toUpperCase();
                av.textContent = (a + b).slice(0, 2);
            }
        }
        var dnrEl = document.getElementById('iceDnr');
        var dniSel = document.getElementById('iceDniStatus');
        var nutSel = document.getElementById('iceNutritionStatus');
        var dniT = dniSel && dniSel.options[dniSel.selectedIndex] ? dniSel.options[dniSel.selectedIndex].text : '—';
        var nutT = nutSel && nutSel.options[nutSel.selectedIndex] ? nutSel.options[nutSel.selectedIndex].text : '—';
        var dnrShort = 'not set';
        if (dnrEl) {
            if (dnrEl.tagName === 'SELECT' && dnrEl.options[dnrEl.selectedIndex]) {
                dnrShort = dnrEl.options[dnrEl.selectedIndex].text;
            } else {
                dnrShort = dnrEl.checked ? 'no CPR' : 'not DNR (see form)';
            }
        }
        var cr = document.getElementById('iceCodeReadout');
        if (cr) {
            cr.textContent = 'DNR: ' + dnrShort + ' · DNI: ' + dniT + ' · Nutrition: ' + nutT;
        }
        var dnc = document.getElementById('iceDnrCurrent');
        if (dnc && dnrEl && dnrEl.tagName === 'SELECT' && dnrEl.options[dnrEl.selectedIndex]) {
            dnc.textContent = dnrEl.options[dnrEl.selectedIndex].text;
        } else if (dnc) {
            dnc.textContent = dnrEl && dnrEl.checked ? 'DNR / no CPR' : 'Not DNR (see checkbox)';
        }
        var dniLine = document.getElementById('iceDniCurrentLine');
        if (dniLine && dniSel && dniSel.options[dniSel.selectedIndex]) {
            dniLine.textContent = dniSel.options[dniSel.selectedIndex].text;
        }
        var nutLine = document.getElementById('iceNutritionCurrentLine');
        if (nutLine && nutSel && nutSel.options[nutSel.selectedIndex]) {
            nutLine.textContent = nutSel.options[nutSel.selectedIndex].text;
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
            var av0 = document.getElementById('iceIdentityAvatar');
            if (av0) av0.textContent = '—';
            var prev0 = document.getElementById('icePhotoPreview');
            if (prev0) {
                prev0.hidden = true;
                prev0.removeAttribute('src');
            }
            var cr0 = document.getElementById('iceCodeReadout');
            if (cr0) cr0.textContent = '—';
            var dnc0 = document.getElementById('iceDnrCurrent');
            if (dnc0) dnc0.textContent = '—';
            syncConditionsAllergiesFromMedical({});
            _iceMedsInitial = [];
            renderIceMedications({ medications: [] });
            _iceEcInitial = [];
            renderEmergencyContacts([]);
            renderIceCompleteness({});
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
        var nameParts = (profile.name || '').trim().split(/\s+/);
        var firstEl = document.getElementById('iceFirstName');
        var lastEl = document.getElementById('iceLastName');
        var dobEl = document.getElementById('iceDob');
        if (firstEl) firstEl.value = nameParts[0] || '';
        if (lastEl) lastEl.value = nameParts.length > 1 ? nameParts.slice(1).join(' ') : '';
        if (dobEl) dobEl.value = (profile.dob || '').slice(0, 10);

        var medical = data.medical || {};
        var dnrEl = document.getElementById('iceDnr');
        if (dnrEl) {
            if (dnrEl.tagName === 'SELECT') {
                dnrEl.value = String(medical.dnr !== undefined && medical.dnr !== null ? medical.dnr : 0);
            } else {
                dnrEl.checked = !!medical.dnr;
            }
        }
        var dniEl = document.getElementById('iceDniStatus');
        if (dniEl && medical.dni_status) dniEl.value = medical.dni_status;
        var nutEl = document.getElementById('iceNutritionStatus');
        if (nutEl && medical.nutrition_status) nutEl.value = medical.nutrition_status;

        var devEl = document.getElementById('iceDevicesNotes');
        if (devEl) devEl.value = data.devices_notes || '';
        var histEl = document.getElementById('iceBriefHistory');
        if (histEl) histEl.value = data.brief_history || '';
        var otherEl = document.getElementById('iceOtherNotes');
        if (otherEl) otherEl.value = data.other_notes || '';

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
        if (prev) {
            if (crId && _loadedPaths.photo_path) {
                prev.hidden = false;
                prev.src = meridianApiClient.getUserPhotoUrl(crId);
                prev.onerror = function () {
                    prev.hidden = true;
                    prev.removeAttribute('src');
                };
            } else {
                prev.hidden = true;
                prev.removeAttribute('src');
            }
        }

        syncConditionsAllergiesFromMedical(medical);
        _iceMedsInitial = MeridianMedicationsInline.cloneSnapshot(medical.medications);
        renderIceMedications(medical);
        var ecs = data.emergency_contacts || [];
        _iceEcInitial = cloneEcSnapshot(ecs);
        renderEmergencyContacts(ecs);
        renderIceCompleteness(data);
        updateIceIdentityStrip();
    }

    var _DOC_TYPE_OPTIONS = [
        'Physician orders / signed POLST',
        'Health care POA',
        'Advanced directive',
        'ID or insurance (copy)',
        'Other…'
    ];

    function docTypeSelectHtml(selected) {
        return '<select class="input-tight ice-doc-type" aria-label="Document type">' +
            _DOC_TYPE_OPTIONS.map(function (t) {
                return '<option' + (t === selected ? ' selected' : '') + '>' + escapeHtml(t) + '</option>';
            }).join('') +
            '</select>';
    }

    function docRowHtml(doc) {
        var id = doc.id || '';
        var docType = doc.doc_type || _DOC_TYPE_OPTIONS[0];
        var docLabel = doc.doc_label || '';
        var docDate = doc.doc_date || '';
        var filePath = doc.file_path || '';
        return '<div class="doc-row-1l" data-doc-id="' + escapeHtml(String(id)) + '">' +
            docTypeSelectHtml(docType) +
            '<input class="input-tight ice-doc-label" type="text" value="' + escapeHtml(docLabel) + '" placeholder="Label (optional)" aria-label="Document label">' +
            '<input class="input-tight ice-doc-date" type="date" value="' + escapeHtml(docDate) + '" aria-label="Last updated">' +
            '<input type="text" class="input-tight ice-doc-filename" value="' + escapeHtml(filePath ? filePath.replace(/^[0-9a-f]{32}/, '').replace(/^\./, '') || filePath : 'No file') + '" readonly aria-label="File name">' +
            '<div class="ice-mock-doc-cta">' +
            '<input type="file" class="ice-mock-file ice-doc-file-input" style="display:none" accept=".pdf,.png,.jpg,.jpeg,.gif,.webp,.doc,.docx,application/pdf,image/*">' +
            '<button type="button" class="btn btn-sm ice-doc-upload-btn">' + (filePath ? 'Replace' : 'Upload') + '</button>' +
            '<button type="button" class="btn btn-sm btn-outline ice-doc-delete-btn">Remove</button>' +
            '</div>' +
            '</div>';
    }

    function renderDocuments(docs) {
        _documents = docs || [];
        var container = document.getElementById('iceDocsContainer');
        if (!container) return;
        container.innerHTML = _documents.map(docRowHtml).join('');
        var addBtn = document.getElementById('iceDocsAddBtn');
        if (addBtn) addBtn.disabled = false;
    }

    function loadDocumentsPromise() {
        if (!_familyCircleId) return Promise.resolve();
        return meridianApiClient.getDocuments(_familyCircleId)
            .then(function (response) {
                var body = response && response.body;
                renderDocuments((body && body.data) || []);
                var container = document.getElementById('iceDocsContainer');
                if (container) {
                    container.querySelectorAll('[data-doc-id]').forEach(function (row) {
                        wireDocumentRow(row);
                    });
                }
            })
            .catch(function () {
                renderDocuments([]);
            });
    }

    function loadDocuments() {
        loadDocumentsPromise();
    }

    function wireDocumentRow(rowEl) {
        var docId = parseInt(rowEl.getAttribute('data-doc-id'), 10);
        var typeSel = rowEl.querySelector('.ice-doc-type');
        var labelInp = rowEl.querySelector('.ice-doc-label');
        var dateInp = rowEl.querySelector('.ice-doc-date');
        var fileInp = rowEl.querySelector('.ice-doc-file-input');
        var uploadBtn = rowEl.querySelector('.ice-doc-upload-btn');
        var deleteBtn = rowEl.querySelector('.ice-doc-delete-btn');
        var filenameInp = rowEl.querySelector('.ice-doc-filename');

        function saveMetadata() {
            if (!docId || !_familyCircleId) return Promise.resolve();
            return meridianApiClient.updateDocument(_familyCircleId, docId, {
                doc_type: typeSel ? typeSel.value : '',
                doc_label: labelInp ? labelInp.value.trim() : '',
                doc_date: dateInp ? dateInp.value : ''
            });
        }

        if (typeSel) {
            typeSel.addEventListener('change', saveMetadata);
        }
        if (dateInp) dateInp.addEventListener('change', saveMetadata);
        if (labelInp) labelInp.addEventListener('change', saveMetadata);

        if (fileInp && uploadBtn) {
            uploadBtn.addEventListener('click', function () {
                fileInp.click();
            });
            fileInp.addEventListener('change', function () {
                var f = fileInp.files && fileInp.files[0];
                if (!f || !_familyCircleId) return;
                uploadBtn.disabled = true;
                uploadBtn.textContent = 'Uploading…';
                saveMetadata()
                    .then(function () {
                        return meridianApiClient.uploadDocumentFile(_familyCircleId, docId, f);
                    })
                    .then(function (response) {
                        var body = response && response.body;
                        var fp = (body && body.data && body.data.file_path) || '';
                        if (filenameInp) filenameInp.value = fp ? fp.replace(/^[0-9a-f]{32}/, '').replace(/^\./, '') || fp : '';
                        uploadBtn.disabled = false;
                        uploadBtn.textContent = 'Replace';
                        fileInp.value = '';
                        showIceStatus('Saved ✓', 'success');
                        loadDocuments();
                    })
                    .catch(function (err) {
                        showIceStatus(err.message || 'Upload failed', 'error');
                        uploadBtn.disabled = false;
                        uploadBtn.textContent = 'Upload';
                    });
            });
        }

        if (deleteBtn) {
            deleteBtn.addEventListener('click', function () {
                if (!_familyCircleId) return;
                meridianApiClient.deleteDocument(_familyCircleId, docId)
                    .then(function () {
                        rowEl.remove();
                        showIceStatus('Saved ✓', 'success');
                    })
                    .catch(function (err) {
                        showIceStatus(err.message || 'Delete failed', 'error');
                    });
            });
        }
    }

    function updateDnrDocLink(crId) {
        var link = document.getElementById('iceDnrDocLink');
        if (!link) return;
        if (crId && _loadedPaths.dnr_document_path && _familyCircleId) {
            link.hidden = false;
            link.href = meridianApiClient.getCareRecipientDnrDocumentUrl(_familyCircleId, crId);
        } else {
            link.hidden = true;
            link.href = '#';
        }
    }

    function uploadCareRecipientDnrDocument(file) {
        var crId = (document.getElementById('iceCareRecipientId') || {}).value;
        if (!file || !crId) return Promise.resolve(false);
        if (!_familyCircleId) {
            showIceStatus('Still loading; wait a moment and choose the file again.', 'error');
            return Promise.resolve(false);
        }
        return meridianApiClient
            .uploadCareRecipientDnrDocument(_familyCircleId, crId, file)
            .then(function (response) {
                var body = response && response.body;
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
        var crId = (document.getElementById('iceCareRecipientId') || {}).value;
        if (!file || !crId) return Promise.resolve(false);
        if (!_familyCircleId) {
            showIceStatus('Still loading; wait a moment and choose the photo again.', 'error');
            return Promise.resolve(false);
        }
        return meridianApiClient
            .uploadCareRecipientPhoto(_familyCircleId, crId, file)
            .then(function (response) {
                var body = response && response.body;
                var d = body && body.data;
                if (d && d.photo_path) _loadedPaths.photo_path = d.photo_path;
                var prev = document.getElementById('icePhotoPreview');
                if (prev) {
                    prev.hidden = false;
                    prev.src = meridianApiClient.getUserPhotoUrl(crId);
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
        var dnrInput = document.getElementById('iceDnrDoc');
        var dnrName = document.getElementById('iceDnrDocName');
        var dnrUploadBtn = document.getElementById('iceDnrUploadBtn');
        if (dnrInput && dnrName) {
            dnrInput.addEventListener('change', function () {
                var f = dnrInput.files && dnrInput.files[0];
                _pendingDnrFile = f || null;
                setUploadButtonState('iceDnrUploadBtn', !!_pendingDnrFile);
                if (dnrName.tagName === 'INPUT') {
                    dnrName.value = f ? f.name : 'No file';
                } else {
                    dnrName.textContent = f ? f.name : 'No file selected';
                }
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
                        if (dnrName) {
                            if (dnrName.tagName === 'INPUT') dnrName.value = 'No file';
                            else dnrName.textContent = 'No file selected';
                        }
                    }
                    setUploadButtonState('iceDnrUploadBtn', !!_pendingDnrFile);
                });
            });
        }
    }

    function wirePhotoUpload() {
        var photoInput = document.getElementById('icePhotoInput');
        var photoBtn = document.getElementById('icePhotoUploadBtn');
        if (!photoInput || !photoBtn) return;
        photoBtn.addEventListener('click', function () { photoInput.click(); });
        photoInput.addEventListener('change', function () {
            var f = photoInput.files && photoInput.files[0];
            if (!f) return;
            photoBtn.disabled = true;
            photoBtn.textContent = 'Uploading…';
            uploadCareRecipientPhoto(f).then(function () {
                photoBtn.disabled = false;
                photoBtn.textContent = 'Change photo';
                photoInput.value = '';
                showIceStatus('Saved ✓', 'success');
            });
        });
    }

    function init() {
        var pdfLink = document.getElementById('icePdfLink');
        wireUploadPreviews();
        wirePhotoUpload();

        var openDocs = document.getElementById('iceOpenDocsBtn');
        if (openDocs) {
            openDocs.addEventListener('click', function () {
                var d = document.getElementById('ice-mock-section-docs');
                if (d) {
                    d.open = true;
                    d.scrollIntoView({ behavior: 'smooth', block: 'nearest' });
                }
            });
        }
        var firstForAvatar = document.getElementById('iceFirstName');
        var lastForAvatar = document.getElementById('iceLastName');
        if (firstForAvatar) firstForAvatar.addEventListener('input', updateIceIdentityStrip);
        if (lastForAvatar) lastForAvatar.addEventListener('input', updateIceIdentityStrip);
        var dnrU = document.getElementById('iceDnr');
        if (dnrU) dnrU.addEventListener('change', updateIceIdentityStrip);
        var dniU = document.getElementById('iceDniStatus');
        if (dniU) dniU.addEventListener('change', updateIceIdentityStrip);
        var nutU = document.getElementById('iceNutritionStatus');
        if (nutU) nutU.addEventListener('change', updateIceIdentityStrip);
        var idEd = document.getElementById('iceIdentityEditBtn');
        if (idEd) {
            idEd.addEventListener('click', function () {
                var n = document.getElementById('iceFirstName');
                if (n) { n.focus(); n.select(); }
            });
        }
        var medEdit = document.getElementById('iceMedsEditAllBtn');
        if (medEdit) {
            medEdit.addEventListener('click', function () {
                var b = document.getElementById('iceMedications');
                if (b) b.scrollIntoView({ behavior: 'smooth', block: 'nearest' });
            });
        }
        var medAddF = document.getElementById('iceMedsAddFocusBtn');
        var addMedB = document.getElementById('iceAddMedBtn');
        if (medAddF && addMedB) {
            medAddF.addEventListener('click', function () { addMedB.click(); });
        }
        var ecEd = document.getElementById('iceEcEditAllBtn');
        if (ecEd) {
            ecEd.addEventListener('click', function () {
                var p = document.getElementById('iceProxyName');
                if (p) p.scrollIntoView({ behavior: 'smooth', block: 'nearest' });
            });
        }
        var ecAdd = document.getElementById('iceEcAddCompactBtn');
        var ecAddMain = document.getElementById('iceAddEmergencyContactBtn');
        if (ecAdd && ecAddMain) {
            ecAdd.addEventListener('click', function () { ecAddMain.click(); });
        }

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

        var algContainer = document.getElementById('iceAllergies');
        if (algContainer) {
            algContainer.addEventListener('click', function (e) {
                if (!e.target.classList.contains('ice-allergy-remove')) return;
                var row = e.target.closest('.allergy-line');
                if (row) {
                    row.remove();
                    if (!algContainer.querySelector('.ice-allergy-value')) {
                        algContainer.innerHTML = '<p class="tiny muted" id="iceAllergiesEmpty">None listed — use + Allergy to add</p>';
                    }
                }
            });
        }
        var addAllergyBtn = document.getElementById('iceAddAllergyBtn');
        if (addAllergyBtn) {
            addAllergyBtn.addEventListener('click', function () {
                var emptyP = document.getElementById('iceAllergiesEmpty');
                if (emptyP) emptyP.remove();
                if (!algContainer) return;
                var d = document.createElement('div');
                d.innerHTML = allergyRowHtml('');
                algContainer.appendChild(d.firstChild);
            });
        }

        var docsContainer = document.getElementById('iceDocsContainer');
        if (docsContainer) {
            docsContainer.addEventListener('click', function (e) {
                var row = e.target.closest('[data-doc-id]');
                if (row) wireDocumentRow(row);
            });
        }
        var docsAddBtn = document.getElementById('iceDocsAddBtn');
        if (docsAddBtn) {
            docsAddBtn.addEventListener('click', function () {
                if (!_familyCircleId) return;
                docsAddBtn.disabled = true;
                meridianApiClient.addDocument(_familyCircleId, {
                    doc_type: _DOC_TYPE_OPTIONS[0],
                    doc_label: '',
                    doc_date: '',
                    sort_order: _documents.length
                })
                    .then(function () {
                        return loadDocumentsPromise();
                    })
                    .then(function () {
                        docsAddBtn.disabled = false;
                        showIceStatus('Saved ✓', 'success');
                    })
                    .catch(function (err) {
                        showIceStatus(err.message || 'Could not add row', 'error');
                        docsAddBtn.disabled = false;
                    });
            });
        }

        meridianApiClient.getSession()
            .then(function (response) {
                var session = response && response.body;
                if (!session || !session.family_circle_id) {
                    window.location.href = meridianLoginPageWithReturn();
                    return;
                }
                _familyCircleId = session.family_circle_id;
                if (pdfLink) {
                    pdfLink.href = meridianApiClient.getEmergencyProfilePdfUrl(_familyCircleId);
                }
                return meridianApiClient.getEmergencyProfile(_familyCircleId);
            })
            .then(function (response) {
                var body = response && response.body;
                var pending = document.getElementById('icePending');
                var app = document.getElementById('iceApp');
                if (pending) pending.hidden = true;
                if (app) app.hidden = false;
                var data = body && body.data ? body.data : null;
                applyProfile(data);
                loadDocuments();
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
                var dniSel = document.getElementById('iceDniStatus');
                var nutSel = document.getElementById('iceNutritionStatus');
                var payload = {
                    care_recipient_user_id: crId,
                    profile: {
                        name: getFullName(),
                        dob: (document.getElementById('iceDob') || {}).value || null
                    },
                    medical: {
                        dnr: dnrValueFromForm(),
                        dni_status: dniSel ? dniSel.value : null,
                        nutrition_status: nutSel ? nutSel.value : null
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
                    devices_notes: null,
                    brief_history: (document.getElementById('iceBriefHistory') || {}).value.trim() || null,
                    other_notes: null,
                    photo_path: _loadedPaths.photo_path,
                    dnr_document_path: _loadedPaths.dnr_document_path
                };
                var condEl = document.getElementById('iceConditions');
                var condText = condEl ? condEl.value : '';
                var conditions = condText.split(/[,\n]+/).map(function (s) { return s.trim(); }).filter(Boolean);
                var allergens = collectAllergyRows();
                var medContainer = document.getElementById('iceMedications');
                var medRows = MeridianMedicationsInline.collectRows(medContainer);
                var ecRows = collectEmergencyContactsFromDom();
                MeridianMedicationsInline.saveDiff(_familyCircleId, _iceMedsInitial, medRows)
                    .then(function () {
                        return saveEmergencyContacts(_familyCircleId, _iceEcInitial, ecRows);
                    })
                    .then(function () {
                        return meridianApiClient.updateEmergencyProfile(_familyCircleId, payload);
                    })
                    .then(function () {
                        return meridianApiClient.replaceAllConditions(_familyCircleId, conditions);
                    })
                    .then(function () {
                        return meridianApiClient.replaceAllAllergies(_familyCircleId, allergens);
                    })
                    .then(function () {
                        return meridianApiClient.getEmergencyProfile(_familyCircleId);
                    })
                    .then(function (response) {
                        var body = response && response.body;
                        var data = body && body.data ? body.data : null;
                        if (data) applyProfile(data);
                        showIceStatus('Saved ✓', 'success');
                        if (typeof window.meridianRefreshHealthIceCompleteness === 'function') {
                            window.meridianRefreshHealthIceCompleteness();
                        }
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
