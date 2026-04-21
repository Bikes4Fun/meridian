/**
 * Webapp client – single JS file. Handles login, check-in, and chat.
 * __API_URL__ replaced at build. The first IIFE defines shared meridian* helpers (login redirect, API base, escaping) for this file, events.js, medications.js, ice_editor.js (no separate meridian_api_base.js).
 */
(function (global) {
    'use strict';
    global.meridianLoginPageWithReturn = function () {
        return '/login.html?next=' + encodeURIComponent(global.location.pathname + global.location.search);
    };
    global.meridianPostLoginRedirectTarget = function () {
        var next = new URLSearchParams(global.location.search).get('next');
        if (!next || typeof next !== 'string') return '/';
        next = next.trim();
        if (!next || next.indexOf('//') === 0 || next.charAt(0) !== '/' || next.indexOf('://') >= 0) {
            return '/';
        }
        return next;
    };
    global.meridianEscapeHtml = function (s) {
        return String(s || '').replace(/</g, '&lt;').replace(/>/g, '&gt;');
    };
    global.meridianEscapeAttr = function (s) {
        return String(s || '').replace(/&/g, '&amp;').replace(/"/g, '&quot;');
    };
})(typeof window !== 'undefined' ? window : this);

(function () {
    'use strict';

    var _familyCircleId = null;
    var _userId = null;
    var _mobileChatLoaded = false;

    function init() {
        if (document.getElementById('loginForm')) {
            initLogin();
            return;
        }
        if (document.getElementById('appNav')) {
            function finishDashboardInit() {
                document.body.classList.remove('pending');
                var topLogin = document.querySelector('.app-topbar-login');
                if (topLogin) topLogin.style.display = 'none';
                if (document.getElementById('logoutLink')) document.getElementById('logoutLink').style.display = 'inline';
                initNav();
                initKioskAlertShortcut();
                initHealthShortcuts();
                initHealthFoldFromHash();
                initCheckin();
                initLogoutLink();
                initIdleLogout();
                initSettingsAdmin();
                if (window.MeridianMedications) {
                    MeridianMedications.init(_familyCircleId, showStatus);
                }
            }
            function applySessionPayload(session) {
                if (!session || !session.family_circle_id || !session.user_id) {
                    return false;
                }
                _familyCircleId = session.family_circle_id;
                _userId = session.user_id;
                return true;
            }
            var boot = typeof window.__MERIDIAN_SESSION__ !== 'undefined' ? window.__MERIDIAN_SESSION__ : null;
            if (boot && boot.user_id && boot.family_circle_id) {
                if (applySessionPayload(boot)) {
                    finishDashboardInit();
                } else {
                    window.location.href = meridianLoginPageWithReturn();
                }
                return;
            }
            meridianApiClient.getSession()
                .then(function (response) {
                    var session = response && response.body;
                    if (!applySessionPayload(session)) {
                        window.location.href = meridianLoginPageWithReturn();
                        return;
                    }
                    finishDashboardInit();
                })
                .catch(function () { window.location.href = meridianLoginPageWithReturn(); });
            return;
        }
        initLogoutLink();
    }

    function initLogin() {
        document.getElementById('loginForm').addEventListener('submit', function (e) {
            e.preventDefault();
            var familyCircleId = document.getElementById('familyCircleId').value.trim();
            var userId = document.getElementById('userId').value.trim();
            if (!familyCircleId || !userId) return;
            meridianApiClient.login(userId, familyCircleId)
            .then(function () {
                window.location.href = meridianPostLoginRedirectTarget();
            })
            .catch(function (err) {
                alert(err.message || 'Login failed');
            });
        });
    }

    function showStatus(message, type) {
        var container = document.getElementById('status');
        if (!container) return;
        if (type === 'success') {
            var olds = container.querySelectorAll('div.success');
            for (var i = 0; i < olds.length; i++) olds[i].remove();
        }
        var box = document.createElement('div');
        box.className = type;
        box.textContent = message;
        container.appendChild(box);
        while (container.children.length > 5) {
            container.removeChild(container.firstChild);
        }
    }

    function checkIn() {
        var userId = _userId;
        var notes = document.getElementById('notes').value;
        var btn = document.getElementById('checkinBtn');

        if (!userId) {
            showStatus('Session expired. Please log in again.', 'error');
            return;
        }

        btn.disabled = true;
        showStatus('Getting your location...', 'info');

        if (!navigator.geolocation) {
            showStatus('GPS not supported on this device!', 'error');
            btn.disabled = false;
            return;
        }

        navigator.geolocation.getCurrentPosition(
            function (position) {
                var latitude = position.coords.latitude;
                var longitude = position.coords.longitude;

                showStatus('Found location: ' + latitude.toFixed(4) + ', ' + longitude.toFixed(4) + '. Sending...', 'info');

                var fcId = _familyCircleId;
                if (!fcId) {
                    showStatus('Session expired. Please log in again.', 'error');
                    btn.disabled = false;
                    return;
                }
                meridianApiClient.createCheckin(fcId, {
                    user_id: userId,
                    latitude: latitude,
                    longitude: longitude,
                    notes: notes || null
                })
                    .then(function () {
                            showStatus('\u2713 Check-in successful!', 'success');
                            document.getElementById('notes').value = '';
                    })
                    .catch(function (err) {
                        showStatus('\u2717 Error: ' + (err.message || 'Check-in failed'), 'error');
                    })
                    .then(function () {
                        btn.disabled = false;
                    });
            },
            function (error) {
                var msg = 'Could not get location. ';
                if (error.code === 1) msg += 'Permission denied.';
                else if (error.code === 2) msg += 'Position unavailable.';
                else if (error.code === 3) msg += 'Timeout.';
                showStatus(msg, 'error');
                btn.disabled = false;
            },
            { enableHighAccuracy: true, timeout: 10000, maximumAge: 0 }
        );
    }

    function markAllMobileNonPrnTaken() {
        var btn = document.getElementById('mobileMarkAllMedsBtn');
        if (!btn) return;
        if (!_familyCircleId) {
            showStatus('Session expired. Please log in again.', 'error');
            return;
        }
        var originalLabel = btn.textContent;
        btn.disabled = true;
        btn.textContent = 'Marking non-as-needed doses...';
        meridianApiClient.getMedications(_familyCircleId)
            .then(function (response) {
                var body = response && response.body;
                var meds = (body && body.data && body.data.timed_medications) || [];
                var due = meds.filter(function (m) {
                    return (
                        m &&
                        m.status !== 'done' &&
                        (String(m.time || '').trim().toLowerCase() !== 'prn')
                    );
                });
                if (!due.length) {
                    showStatus('No non-as-needed doses pending for today.', 'success');
                    return null;
                }
                var chain = Promise.resolve();
                due.forEach(function (m) {
                    var medId = parseInt(m.id, 10);
                    var slot = String(m.time || '').trim();
                    if (!medId || !slot) return;
                    chain = chain.then(function () {
                        return meridianApiClient.markMedicationTaken(
                            _familyCircleId,
                            medId,
                            slot,
                            true
                        );
                    });
                });
                return chain.then(function () {
                    if (due.length === 1) {
                        showStatus('Marked 1 non-as-needed dose as taken.', 'success');
                    } else {
                        showStatus('Marked ' + due.length + ' non-as-needed doses as taken.', 'success');
                    }
                });
            })
            .catch(function (err) {
                showStatus('Mark all failed: ' + (err.message || String(err)), 'error');
            })
            .then(function () {
                btn.disabled = false;
                btn.textContent = originalLabel;
            });
    }

    function activateAlert() {
        meridianApiClient.getEmergencyAlertStatus()
            .then(function () {
                return meridianApiClient.setEmergencyAlert(true);
            })
            .then(function () {
                showStatus('Alert mode activated. The kiosk should show the emergency screen.', 'success');
            })
            .catch(function (err) {
                showStatus('Alert failed: ' + (err.message || String(err)), 'error');
            });
    }

    function cancelAlert() {
        meridianApiClient.setEmergencyAlert(false)
            .then(function () {
                showStatus('Alert cancelled.', 'success');
            })
            .catch(function (err) {
                showStatus('Cancel failed: ' + (err.message || String(err)), 'error');
            });
    }

    function initNav() {
        var nav = document.getElementById('appNav');
        if (!nav) return;
        nav.addEventListener('click', function (e) {
            var raw = e.target;
            var el = raw.nodeType === 1 ? raw : raw.parentElement;
            if (!el || !el.closest) return;
            var btn = el.closest('.nav-btn');
            if (!btn) return;
            var pageId = btn.getAttribute('data-page') || '';
            var targetId = btn.getAttribute('data-target-id');
            if (!targetId) return;
            [].forEach.call(nav.querySelectorAll('.nav-btn'), function (b) { b.classList.remove('active'); });
            [].forEach.call(document.querySelectorAll('.page'), function (p) { p.classList.remove('active'); });
            btn.classList.add('active');
            var target = document.getElementById(targetId);
            if (target) target.classList.add('active');
            if (pageId === 'events' && window.MeridianEvents) {
                MeridianEvents.init(_familyCircleId, showStatus);
            }
            if (
                (pageId === 'health' || pageId === 'settings') &&
                window.MeridianMedications
            ) {
                MeridianMedications.init(_familyCircleId, showStatus);
            }
            if (pageId === 'settings') {
                loadAdminPermissions();
            }
            if (pageId === 'mobile' && !_mobileChatLoaded) {
                _mobileChatLoaded = true;
                initChatContacts();
            }
            if (pageId === 'health' || pageId === 'settings') {
                setTimeout(syncFoldDetailsFromHash, 0);
            }
        });
    }

    function initKioskAlertShortcut() {
        var shortcut = document.getElementById('kioskAlertShortcutBtn');
        if (!shortcut) return;
        shortcut.addEventListener('click', function () {
            meridianApiClient.getEmergencyAlertStatus()
                .then(function (resp) {
                    var isActive = !!(resp && resp.data && resp.data.activated);
                    if (isActive) {
                        return meridianApiClient.setEmergencyAlert(false).then(function () {
                            showStatus('Alert cancelled.', 'success');
                        });
                    }
                    var proceed = window.confirm(
                        'This will switch the kiosk to emergency mode. Activate alert now?'
                    );
                    if (!proceed) return null;
                    return meridianApiClient.setEmergencyAlert(true).then(function () {
                        showStatus('Alert mode activated. The kiosk should show the emergency screen.', 'success');
                        var nav = document.getElementById('appNav');
                        var settingsBtn = nav && nav.querySelector('.nav-btn[data-page="settings"]');
                        if (settingsBtn) settingsBtn.click();
                        setTimeout(function () {
                            var el = document.getElementById('settingsKioskAlert');
                            if (el) el.scrollIntoView({ behavior: 'smooth', block: 'nearest' });
                            var cancelBtn = document.getElementById('cancelAlertBtn');
                            if (cancelBtn) cancelBtn.focus();
                        }, 50);
                    });
                })
                .catch(function (err) {
                    showStatus('Alert failed: ' + (err.message || String(err)), 'error');
                });
        });
    }

    function syncFoldDetailsFromHash() {
        var id = (location.hash || '').replace(/^#/, '');
        if (!id) return;
        var el = document.getElementById(id);
        if (el && el.tagName === 'DETAILS') el.open = true;
    }

    function initHealthFoldFromHash() {
        window.addEventListener('hashchange', syncFoldDetailsFromHash);
        syncFoldDetailsFromHash();
    }

    function openHealthMedicationList() {
        var nav = document.getElementById('appNav');
        var healthBtn = nav && nav.querySelector('.nav-btn[data-page="health"]');
        if (healthBtn) healthBtn.click();
        setTimeout(function () {
            var el = document.getElementById('health-section-medications');
            if (el && el.tagName === 'DETAILS') el.open = true;
            if (el) el.scrollIntoView({ behavior: 'smooth', block: 'nearest' });
        }, 50);
    }

    function openSettingsKioskControls() {
        var nav = document.getElementById('appNav');
        var settingsBtn = nav && nav.querySelector('.nav-btn[data-page="settings"]');
        if (settingsBtn) settingsBtn.click();
        setTimeout(function () {
            var el = document.getElementById('settingsKioskAlert');
            if (el) el.scrollIntoView({ behavior: 'smooth', block: 'nearest' });
        }, 50);
    }

    function initHealthShortcuts() {
        var nav = document.getElementById('appNav');
        if (!nav) return;
        var takeHost = document.getElementById('healthMedsTakeHost');
        if (takeHost) {
            takeHost.addEventListener('click', function (e) {
                if (e.target.closest('.health-meds-empty__cta')) {
                    e.preventDefault();
                    openHealthMedicationList();
                }
            });
        }
        var settingsMedsShortcut = document.getElementById('settingsMedicationListBtn');
        if (settingsMedsShortcut) {
            settingsMedsShortcut.addEventListener('click', function () {
                openHealthMedicationList();
            });
        }
        var settingsKioskBtn = document.getElementById('settingsKioskControlsBtn');
        if (settingsKioskBtn) {
            settingsKioskBtn.addEventListener('click', function () {
                openSettingsKioskControls();
            });
        }
    }

    function adminApiFetchGrantRevoke(familyCircleId, userId, permission, granted) {
        return meridianApiClient
            .setPermission(familyCircleId, {
                user_id: userId,
                permission: permission,
                granted: granted
            })
            .then(function (response) {
                return (response && response.body) || {};
            });
    }

    var ADMIN_PERMISSION_LABELS = {
        'family_members.invite': 'Invite family members',
        'family_members.remove': 'Remove family members',
        'family_permissions.manage': 'Change member permissions',
        'medications.write': 'Change medications',
        'emergency_alert.manage': 'Trigger emergency alert',
        'emergency_call.911': 'Call 911 (planned)',
        'care_recipient.write': 'Update care recipient profile',
        'emergency_contacts.write': 'Update emergency contacts',
        'calendar.write': 'Edit calendar'
    };
    var ADMIN_PERMISSION_DEFAULT_ORDER = [
        'family_members.invite',
        'family_members.remove',
        'family_permissions.manage',
        'medications.write',
        'emergency_alert.manage',
        'emergency_call.911',
        'care_recipient.write',
        'emergency_contacts.write',
        'calendar.write'
    ];
    var ADMIN_ACCESS_PRESETS = {
        other: [],
        family: ['emergency_alert.manage', 'emergency_call.911'],
        admin: [
            'family_members.invite',
            'family_members.remove',
            'family_permissions.manage',
            'medications.write',
            'emergency_alert.manage',
            'emergency_call.911',
            'care_recipient.write',
            'emergency_contacts.write',
            'calendar.write'
        ]
    };
    var _adminPermissionCatalog = [];
    var _adminPermissionsState = {};

    function setAdminPermissionsStatus(message, type) {
        var el = document.getElementById('adminPermissionsStatus');
        if (!el) return;
        el.textContent = message || '';
        el.className = type === 'error'
            ? 'admin-subsection__lead error'
            : type === 'success'
                ? 'admin-subsection__lead success'
                : 'muted admin-subsection__lead';
    }

    function permissionLabel(permission) {
        return ADMIN_PERMISSION_LABELS[permission] || permission;
    }

    function permissionSummary(permissions) {
        var labels = (permissions || []).map(function (permission) {
            return permissionLabel(permission);
        });
        if (!labels.length) return 'No explicit permissions';
        if (labels.length <= 3) return labels.join(', ');
        return labels.slice(0, 3).join(', ') + ' +' + (labels.length - 3) + ' more';
    }

    function roleFromPermissions(permissions) {
        var sorted = (permissions || []).slice().sort().join('|');
        if (sorted === ADMIN_ACCESS_PRESETS.admin.slice().sort().join('|')) return 'admin';
        if (sorted === ADMIN_ACCESS_PRESETS.family.slice().sort().join('|')) return 'family';
        return 'other';
    }

    function collectRowPermissions(row) {
        var checks = row.querySelectorAll('.admin-perm-checkbox');
        var out = [];
        checks.forEach(function (cb) {
            if (cb.checked) out.push(cb.getAttribute('data-permission'));
        });
        return out.sort();
    }

    function setRowDirtyState(row, uid) {
        var saveBtn = row.querySelector('.admin-perm-save');
        if (!saveBtn) return;
        var current = collectRowPermissions(row);
        var initial = (_adminPermissionsState[uid] && _adminPermissionsState[uid].initial) || [];
        var dirty = current.join('|') !== initial.join('|');
        saveBtn.disabled = !dirty || uid === _userId;
    }

    function renderAdminPermissionsRows(members) {
        var tbody = document.getElementById('adminPermissionsTableBody');
        if (!tbody) return;
        if (!members || members.length === 0) {
            tbody.innerHTML = '<tr><td colspan="5" class="muted">No family members found.</td></tr>';
            return;
        }
        var catalogSet = {};
        ADMIN_PERMISSION_DEFAULT_ORDER.forEach(function (p) { catalogSet[p] = true; });
        members.forEach(function (m) {
            (Array.isArray(m.permissions) ? m.permissions : []).forEach(function (p) {
                if (p) catalogSet[p] = true;
            });
        });
        _adminPermissionCatalog = ADMIN_PERMISSION_DEFAULT_ORDER.filter(function (p) {
            return !!catalogSet[p];
        });
        Object.keys(catalogSet)
            .sort()
            .forEach(function (p) {
                if (_adminPermissionCatalog.indexOf(p) < 0) _adminPermissionCatalog.push(p);
            });
        _adminPermissionsState = {};
        var html = members.map(function (m) {
            var uid = (m.id || '').trim();
            var name = (m.display_name || uid || 'Unknown').trim();
            var permissions = (Array.isArray(m.permissions) ? m.permissions.slice() : []).sort();
            _adminPermissionsState[uid] = { initial: permissions.slice() };
            var accessType = roleFromPermissions(permissions);
            var summaryText = permissionSummary(permissions);
            var disabled = uid === _userId ? ' disabled title="Cannot change your own access here"' : '';
            var permissionControls = _adminPermissionCatalog.map(function (permission) {
                var checked = permissions.indexOf(permission) >= 0 ? ' checked' : '';
                return (
                    '<label class="admin-checkbox-label admin-checkbox-label--table">' +
                    '<input type="checkbox" class="admin-perm-checkbox" data-permission="' + meridianEscapeAttr(permission) + '"' + checked + disabled + '> ' +
                    meridianEscapeHtml(permissionLabel(permission)) +
                    '</label>'
                );
            }).join(' ');
            return (
                '<tr data-user-id="' + meridianEscapeAttr(uid) + '">' +
                '<td>' + meridianEscapeHtml(name) + '</td>' +
                '<td><code class="admin-code">' + meridianEscapeHtml(uid) + '</code></td>' +
                '<td>' +
                '<select class="admin-table-select admin-access-select"' + disabled + '>' +
                '<option value="admin"' + (accessType === 'admin' ? ' selected' : '') + '>Admin</option>' +
                '<option value="family"' + (accessType === 'family' ? ' selected' : '') + '>Family</option>' +
                '<option value="other"' + (accessType === 'other' ? ' selected' : '') + '>Other</option>' +
                '</select>' +
                '</td>' +
                '<td>' +
                '<div class="muted admin-perm-summary">' + meridianEscapeHtml(summaryText) + '</div>' +
                '<div class="admin-perm-editor" style="display:none;">' +
                permissionControls +
                '</div>' +
                '</td>' +
                '<td>' +
                '<div class="admin-perm-actions">' +
                '<button type="button" class="btn-health-secondary admin-perm-customize"' + disabled + '>Customize</button>' +
                '<button type="button" class="btn-health-secondary admin-perm-save" disabled' + disabled + '>Save</button>' +
                '</div>' +
                '</td>' +
                '</tr>'
            );
        }).join('');
        tbody.innerHTML = html;
    }

    function loadAdminPermissions() {
        if (!_familyCircleId) return;
        var tbody = document.getElementById('adminPermissionsTableBody');
        if (!tbody) return;
        tbody.innerHTML = '<tr><td colspan="5" class="muted">Loading...</td></tr>';
        setAdminPermissionsStatus('Loading members and permissions...');
        Promise.all([
            meridianApiClient.getFamilyMembers(_familyCircleId).then(function (r) {
                return (r && r.body) || {};
            }),
            meridianApiClient.getPermissions(_familyCircleId).then(function (r) {
                return (r && r.body) || {};
            })
        ])
            .then(function (results) {
                var membersData = (results[0] && results[0].data) || [];
                var permsByUser = (results[1] && results[1].data) || {};
                var members = (membersData || []).map(function (m) {
                    var copy = Object.assign({}, m);
                    var uid = (copy.id || '').trim();
                    copy.permissions = Array.isArray(permsByUser[uid]) ? permsByUser[uid] : [];
                    return copy;
                });
                renderAdminPermissionsRows(members);
                setAdminPermissionsStatus('Loaded.');
            })
            .catch(function (err) {
                tbody.innerHTML = '<tr><td colspan="5" class="muted">Failed to load members: ' + meridianEscapeHtml(err.message || String(err)) + '</td></tr>';
                setAdminPermissionsStatus('Failed to load permissions.', 'error');
            });
    }

    function initSettingsAdmin() {
        var refreshBtn = document.getElementById('adminPermissionsRefreshBtn');
        var tbody = document.getElementById('adminPermissionsTableBody');
        if (!refreshBtn || !tbody) return;
        refreshBtn.addEventListener('click', function () {
            loadAdminPermissions();
        });
        tbody.addEventListener('change', function (e) {
            var raw = e.target;
            var row = raw && raw.closest ? raw.closest('tr') : null;
            if (!row) return;
            var uid = (row.getAttribute('data-user-id') || '').trim();
            if (!uid || !_familyCircleId) return;
            if (raw.classList && raw.classList.contains('admin-access-select')) {
                var preset = raw.value;
                if (ADMIN_ACCESS_PRESETS[preset]) {
                    var target = ADMIN_ACCESS_PRESETS[preset];
                    row.querySelectorAll('.admin-perm-checkbox').forEach(function (cb) {
                        cb.checked = target.indexOf(cb.getAttribute('data-permission')) >= 0;
                    });
                }
            }
            if (
                (raw.classList && raw.classList.contains('admin-access-select')) ||
                (raw.classList && raw.classList.contains('admin-perm-checkbox'))
            ) {
                setRowDirtyState(row, uid);
            }
        });
        tbody.addEventListener('click', function (e) {
            var raw = e.target;
            var customizeBtn = raw && raw.closest ? raw.closest('.admin-perm-customize') : null;
            if (customizeBtn && !customizeBtn.disabled) {
                var customizeRow = customizeBtn.closest('tr');
                if (!customizeRow) return;
                var editor = customizeRow.querySelector('.admin-perm-editor');
                if (!editor) return;
                var isOpen = editor.style.display !== 'none';
                editor.style.display = isOpen ? 'none' : 'block';
                customizeBtn.textContent = isOpen ? 'Customize' : 'Close';
                return;
            }
            var btn = raw && raw.closest ? raw.closest('.admin-perm-save') : null;
            if (!btn || btn.disabled) return;
            var row = btn.closest('tr');
            if (!row) return;
            var uid = (row.getAttribute('data-user-id') || '').trim();
            if (!uid || !_familyCircleId) return;
            var current = collectRowPermissions(row);
            var initial = (_adminPermissionsState[uid] && _adminPermissionsState[uid].initial) || [];
            var toGrant = current.filter(function (p) { return initial.indexOf(p) < 0; });
            var toRevoke = initial.filter(function (p) { return current.indexOf(p) < 0; });
            if (toGrant.length === 0 && toRevoke.length === 0) {
                setAdminPermissionsStatus('No permission changes to save.');
                return;
            }
            btn.disabled = true;
            var requests = [];
            toGrant.forEach(function (permission) {
                requests.push(
                    adminApiFetchGrantRevoke(_familyCircleId, uid, permission, true)
                );
            });
            toRevoke.forEach(function (permission) {
                requests.push(
                    adminApiFetchGrantRevoke(_familyCircleId, uid, permission, false)
                );
            });
            Promise.all(requests)
                .then(function () {
                    _adminPermissionsState[uid].initial = current.slice().sort();
                    var summaryEl = row.querySelector('.admin-perm-summary');
                    if (summaryEl) summaryEl.textContent = permissionSummary(current);
                    var editorEl = row.querySelector('.admin-perm-editor');
                    if (editorEl) editorEl.style.display = 'none';
                    var customizeEl = row.querySelector('.admin-perm-customize');
                    if (customizeEl) customizeEl.textContent = 'Customize';
                    setAdminPermissionsStatus('Permissions updated.', 'success');
                    setRowDirtyState(row, uid);
                })
                .catch(function (err) {
                    setAdminPermissionsStatus('Permission update failed: ' + (err.message || String(err)), 'error');
                    btn.disabled = false;
                });
        });
        loadAdminPermissions();
    }

    function initCheckin() {
        var btn = document.getElementById('checkinBtn');
        if (btn) btn.addEventListener('click', checkIn);
        var markAllBtn = document.getElementById('mobileMarkAllMedsBtn');
        if (markAllBtn) markAllBtn.addEventListener('click', markAllMobileNonPrnTaken);
        var alertBtn = document.getElementById('alertBtn');
        if (alertBtn) alertBtn.addEventListener('click', activateAlert);
        var cancelBtn = document.getElementById('cancelAlertBtn');
        if (cancelBtn) cancelBtn.addEventListener('click', cancelAlert);
    }

    function initChatContacts() {
        var grid = document.getElementById('contactsGrid');
        if (!grid || !_familyCircleId) return;
        meridianApiClient.getContacts(_familyCircleId)
            .then(function (response) {
                var data = response && response.body;
                if (!data || !data.data) return;
                var chatContacts = data.data.filter(function (c) {
                    var relationship = (c.relationship || '').toLowerCase();
                    return relationship !== 'care recipient' && relationship !== 'care_recipient' && relationship !== 'patient';
                });
                if (chatContacts.length === 0) {
                    grid.innerHTML = '<p class="muted">No family contacts to show.</p>';
                    return;
                }
                grid.innerHTML = '';
                chatContacts.forEach(function (c) {
                    var name = c.display_name || c.id || 'Contact';
                    var tile = document.createElement('div');
                    tile.className = 'contact-tile';
                    var inner = document.createElement('div');
                    inner.className = 'contact-tile-inner';
                    var avatar = document.createElement('div');
                    avatar.className = 'contact-avatar';
                    avatar.textContent = (name || '?').charAt(0).toUpperCase();
                    if (c.user_id) {
                        var img = document.createElement('img');
                        img.src = meridianApiClient.getUserPhotoUrl(c.user_id);
                        img.alt = name;
                        img.onerror = function () { img.style.display = 'none'; };
                        avatar.appendChild(img);
                    }
                    inner.appendChild(avatar);
                    var label = document.createElement('span');
                    label.className = 'contact-name';
                    label.textContent = name;
                    inner.appendChild(label);
                    tile.appendChild(inner);
                    grid.appendChild(tile);
                });
            })
            .catch(function () {});
    }

    function initLogoutLink() {
        var link = document.getElementById('logoutLink');
        if (!link) return;
        link.addEventListener('click', function (e) {
            e.preventDefault();
            meridianApiClient.logout()
                .then(function () { window.location.href = '/login.html'; })
                .catch(function () { window.location.href = '/login.html'; });
        });
    }

    function initIdleLogout() {
        var sec = typeof window.__MERIDIAN_IDLE_LOGOUT_SEC__ === 'number' ? window.__MERIDIAN_IDLE_LOGOUT_SEC__ : 1800;
        var idleMs = sec * 1000;
        if (idleMs <= 0) return;
        var timer = null;
        function doLogout() {
            meridianApiClient.logout()
                .then(function () { window.location.href = '/login.html'; })
                .catch(function () { window.location.href = '/login.html'; });
        }
        function reset() {
            if (timer) clearTimeout(timer);
            timer = setTimeout(doLogout, idleMs);
        }
        ['mousedown', 'keydown', 'touchstart', 'scroll'].forEach(function (ev) {
            document.addEventListener(ev, reset, { passive: true });
        });
        reset();
    }

    if (document.readyState === 'loading') {
        document.addEventListener('DOMContentLoaded', init);
    } else {
        init();
    }
})();
