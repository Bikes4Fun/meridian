/**
 * ICE / emergency profile editor (webapp). API_URL from build (__API_URL__).
 */
(function () {
    'use strict';

    var _u = '__API_URL__';
    var API_URL = (_u.startsWith('http') ? _u : '');
    var _familyCircleId = null;
    var _loadedPaths = { photo_path: null, dnr_document_path: null };

    function showIceStatus(message, type) {
        var container = document.getElementById('iceStatus');
        if (!container) return;
        var box = document.createElement('div');
        box.className = type;
        box.textContent = message;
        container.appendChild(box);
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

    function fillReadonlyMedical(medical) {
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

        var medEl = document.getElementById('iceMedications');
        if (medEl) {
            medEl.innerHTML = '';
            var meds = medical.medications || [];
            if (meds.length === 0) {
                medEl.innerHTML = '<li class="muted">None listed</li>';
            } else {
                meds.forEach(function (m) {
                    var li = document.createElement('li');
                    var parts = [m.name || '', m.dosage || '', m.frequency || ''].filter(Boolean);
                    li.textContent = parts.join(' · ');
                    medEl.appendChild(li);
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
            fillReadonlyMedical({});
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

        var prev = document.getElementById('icePhotoPreview');
        if (prev && crId) {
            prev.hidden = false;
            prev.src = (API_URL || '').replace(/\/$/, '') + '/api/users/' + encodeURIComponent(crId) + '/photo';
            prev.onerror = function () { prev.hidden = true; };
        }

        fillReadonlyMedical(medical);
    }

    function wireUploadPreviews() {
        var photoInput = document.getElementById('icePhoto');
        var prev = document.getElementById('icePhotoPreview');
        if (photoInput && prev) {
            photoInput.addEventListener('change', function () {
                var f = photoInput.files && photoInput.files[0];
                if (!f) return;
                var r = new FileReader();
                r.onload = function () {
                    prev.hidden = false;
                    prev.src = r.result;
                };
                r.readAsDataURL(f);
            });
        }
        var dnrInput = document.getElementById('iceDnrDoc');
        var dnrName = document.getElementById('iceDnrDocName');
        if (dnrInput && dnrName) {
            dnrInput.addEventListener('change', function () {
                var f = dnrInput.files && dnrInput.files[0];
                dnrName.textContent = f ? f.name : '';
            });
        }
    }

    function init() {
        var apiBase = (API_URL || '').replace(/\/$/, '');
        var pdfLink = document.getElementById('icePdfLink');
        wireUploadPreviews();

        fetch(apiBase + '/api/session', { credentials: 'include' })
            .then(function (r) {
                if (r.status === 401) {
                    window.location.href = '/login.html';
                    return null;
                }
                return r.ok ? r.json() : null;
            })
            .then(function (session) {
                if (!session || !session.family_circle_id) {
                    window.location.href = '/login.html';
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
                fetch(
                    apiBase + '/api/family_circles/' + encodeURIComponent(_familyCircleId) + '/emergency-profile',
                    {
                        method: 'PUT',
                        credentials: 'include',
                        headers: { 'Content-Type': 'application/json' },
                        body: JSON.stringify(payload)
                    }
                )
                    .then(function (r) {
                        return r.json().then(function (d) {
                            if (!r.ok) throw new Error(d.error || 'Save failed');
                            return d;
                        });
                    })
                    .then(function () {
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
