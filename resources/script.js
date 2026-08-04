const cssVariables = [
    '--font-family', '--font-size-base',
    '--bg-body', '--text-main', '--text-sub', '--border-color',
    '--row-bg', '--row-border', '--row-hover',
    '--input-bg', '--input-border', '--input-text', '--input-placeholder', '--toggle-bg',
    '--header-hover', '--tab-bg', '--tab-active-bg', '--tab-text', '--tab-active-text',
    '--btn-primary', '--btn-primary-hover', '--btn-success', '--btn-success-hover',
    '--btn-secondary', '--btn-secondary-hover', '--btn-secondary-text',
    '--status-success-bg', '--status-success-text',
    '--status-error-bg', '--status-error-text',
    '--status-info-bg', '--status-info-text'
];
let themes = {};
let baseCSS = "";
let customThemes = JSON.parse(localStorage.getItem('fjl_custom_themes') || '{}');
// Ids parsed straight out of resources/style.css at load time, before
// customThemes/host-imported themes are merged in. Used to tell "a
// genuinely custom/imported theme" (removable) apart from "a built-in
// theme the user has live-edited overrides for" (not removable --
// use Factory Reset for that).
let builtInThemeIds = new Set();
let _importedThemesLoaded = false;

function parseStyleCSS(cssText) {
    const themeRegex = /(?:\/\*[\s\S]*?\*\/\s*)?(?:(:root)|\[data-theme=["']?([^"']+)["']?\])\s*\{([^}]+)\}/g;
    let match;
    let parsedThemes = {};
    while ((match = themeRegex.exec(cssText)) !== null) {
        let themeId = match[1] ? "" : match[2];
        let content = match[3];
        let vars = {};
        // Safely extract variables even if a trailing semicolon is missing
        const varRegex = /(--[\w-]+)\s*:\s*([^;]+?)(?=\s*;|\s*$)/g;
        let vMatch;
        while ((vMatch = varRegex.exec(content)) !== null) {
            vars[vMatch[1].trim()] = vMatch[2].trim();
        }
        parsedThemes[themeId] = vars;
    }
    let cleanCSS = cssText.replace(themeRegex, '').trim();
    return { themes: parsedThemes, baseCSS: cleanCSS };
}

function generateFullCSS() {
    let out = "";
    let i = 1;
    for (let id in themes) {
        let comment = id === "" ? "Default Light" : id;
        let sel = id === "" ? ":root" : `[data-theme="${id}"]`;
        out += `/* ${i}. ${comment} */\n${sel} {\n`;
        for (let v of cssVariables) {
            if (themes[id][v]) out += `    ${v}: ${themes[id][v]};\n`;
        }
        out += `}\n\n`;
        i++;
    }
    return out + baseCSS;
}

function updateThemeDropdown() {
    const select = document.getElementById('themeSelect');
    const current = select.value;
    select.innerHTML = '<option value="default">Default Light</option>';
    for (let id in themes) {
        if (id === "") continue;
        let opt = document.createElement('option');
        opt.value = id; opt.text = id;
        select.appendChild(opt);
    }
    if (current && [...select.options].some(o => o.value === current)) select.value = current;
}

function updateStyleTag() {
    let out = "";
    for (let id in customThemes) {
        let sel = id === "default" || id === "light" || id === "" ? ":root" : `[data-theme="${id}"]`;
        out += `${sel} {\n`;
        for (let v of cssVariables) {
            if (customThemes[id][v]) out += `    ${v}: ${customThemes[id][v]};\n`;
        }
        out += `}\n`;
    }
    let styleTag = document.getElementById('dynamic-theme-overrides');
    if (!styleTag) {
        styleTag = document.createElement('style');
        styleTag.id = 'dynamic-theme-overrides';
        document.head.appendChild(styleTag);
    }
    styleTag.innerHTML = out;
}

function updateActiveThemeProperty(prop, value) {
    const themeSelector = document.getElementById('themeSelect');
    const themeId = themeSelector ? themeSelector.value : 'default';

    if (!customThemes[themeId]) customThemes[themeId] = {};
    if (!themes[themeId]) themes[themeId] = {};

    customThemes[themeId][prop] = value;
    themes[themeId][prop] = value;
    localStorage.setItem('fjl_custom_themes', JSON.stringify(customThemes));
    updateStyleTag();
}

function mergeImportedThemes(hostThemes) {
    // Host-persisted (imported_themes.json) is the durable source of
    // truth; localStorage is just a fast-path cache for instant render
    // before this round-trip resolves. Runs once per palette session --
    // re-running on every load_defaults would clobber an in-progress
    // live edit.
    if (_importedThemesLoaded || !hostThemes || Object.keys(hostThemes).length === 0) return;
    _importedThemesLoaded = true;

    for (let id in hostThemes) {
        if (!themes[id]) themes[id] = {};
        Object.assign(themes[id], hostThemes[id]);
        if (!customThemes[id]) customThemes[id] = hostThemes[id];
    }
    localStorage.setItem('fjl_custom_themes', JSON.stringify(customThemes));
    updateThemeDropdown();
    updateStyleTag();
    updateRemoveButtonState();
}

function updateRemoveButtonState() {
    const btn = document.getElementById('themeRemoveBtn');
    if (!btn) return;
    const themeSelector = document.getElementById('themeSelect');
    const id = themeSelector ? themeSelector.value : 'default';
    const removable = id !== 'default' && !builtInThemeIds.has(id) && (id in customThemes);
    btn.disabled = !removable;
    btn.title = removable ? `Remove the "${id}" theme` : 'Select a custom (imported) theme to enable';
}

function removeSelectedTheme() {
    const themeSelector = document.getElementById('themeSelect');
    const id = themeSelector ? themeSelector.value : null;
    if (!id || id === 'default' || builtInThemeIds.has(id) || !(id in customThemes)) return;

    if (!confirm(`Permanently remove the "${id}" theme? Re-import its .theme.json to bring it back.`)) return;

    delete themes[id];
    delete customThemes[id];
    localStorage.setItem('fjl_custom_themes', JSON.stringify(customThemes));
    adsk.fusionSendData('notification', JSON.stringify({ action: 'remove_imported_theme', id: id }));

    updateThemeDropdown();
    updateStyleTag();
    themeSelector.value = 'default';
    changeTheme();
}

function requestImport(type) { adsk.fusionSendData('notification', JSON.stringify({ action: 'import_file', file_type: type })); }
function requestExport(type) {
    const id = document.getElementById('themeSelect').value;
    if (type === 'json' && id === 'default') return alert("Please select a specific custom theme from the dropdown to export as JSON.");
    const content = type === 'json' ? JSON.stringify({ id: id, vars: themes[id] }, null, 2) : generateFullCSS();
    const defaultName = type === 'json' ? `${id}.theme.json` : 'style.css';
    adsk.fusionSendData('notification', JSON.stringify({ action: 'export_file', file_type: type, content: content, default_name: defaultName }));
}

function applyTheme(theme) {
    if (theme === 'default' || theme === 'light') {
        document.documentElement.removeAttribute('data-theme');
    } else {
        document.documentElement.setAttribute('data-theme', theme);
    }
    // Fusion's palette host (CEF) appears to stamp an inline
    // background-color onto <body> itself (matches the Light theme's
    // --bg-body exactly, rgb(245,245,245) -- likely a flash-of-
    // unstyled-content guard). An inline style always wins over our
    // external stylesheet's `body { background-color: var(--bg-body); }`
    // rule by specificity, no matter what data-theme is set, so strip
    // it every time a theme is (re)applied and let our CSS govern.
    document.body.style.removeProperty('background-color');
}

function changeTheme() {
    const theme = document.getElementById('themeSelect').value;
    localStorage.setItem('fjl_theme', theme);
    applyTheme(theme);

    const currentVars = themes[theme] || {};
    const fontFam = document.getElementById('fontFamilySelector');
    const fontSize = document.getElementById('fontSizeSelector');
    if (fontFam && currentVars['--font-family']) {
        let fam = currentVars['--font-family'].replace(/"/g, "'");
        let match = Array.from(fontFam.options).find(o => o.value === fam);
        if (match) fontFam.value = match.value;
    }
    if (fontSize && currentVars['--font-size-base']) {
        let match = Array.from(fontSize.options).find(o => o.value === currentVars['--font-size-base']);
        if (match) fontSize.value = match.value;
    }

    adsk.fusionSendData('notification', JSON.stringify({ action: 'save_theme', theme: theme }));
    updateRemoveButtonState();
}

function resetThemeCache() {
    if(confirm("This will permanently delete all custom imported themes and font overrides. Continue?")) {
        localStorage.removeItem('fjl_custom_themes');
        localStorage.removeItem('fjl_theme');
        customThemes = {};
        _importedThemesLoaded = false;

        // Also wipe the host-side store -- otherwise the next palette
        // load would just re-import everything from imported_themes.json.
        adsk.fusionSendData('notification', JSON.stringify({ action: 'reset_imported_themes' }));

        let styleTag = document.getElementById('dynamic-theme-overrides');
        if (styleTag) styleTag.remove();

        document.getElementById('themeSelect').value = 'default';
        changeTheme();
    }
}

const savedTheme = localStorage.getItem('fjl_theme') || 'default';
document.getElementById('themeSelect').value = savedTheme;
applyTheme(savedTheme);

function switchTab(tabId, event) {
    document.querySelectorAll('.tab-content').forEach(el => el.classList.remove('active'));
    document.querySelectorAll('.tab-btn').forEach(el => el.classList.remove('active'));
    document.getElementById(tabId).classList.add('active');
    event.currentTarget.classList.add('active');
}

function showHelp() { document.getElementById('helpModal').style.display = 'flex'; }
function hideHelp(e) { if(e) e.preventDefault(); document.getElementById('helpModal').style.display = 'none'; }

function sendAction(actionName) {
    adsk.fusionSendData('notification', JSON.stringify({ action: actionName }));
}

function toggleRow(id, isVisible) {
    document.getElementById(id).style.display = isVisible ? 'flex' : 'none';
}

function updateVisibility() {
    const dynamicSizeType = document.getElementById('dynamicSizeType').value;
    const isFixedNum = document.getElementById('isNumberOfFingersFixed').checked;
    const jointType = document.getElementById('jointType').value;

    toggleRow('grp-fixedNumFingers', isFixedNum);
    toggleRow('grp-fixedNotchSize', dynamicSizeType === 'fixed notch size');
    toggleRow('grp-fixedFingerSize', dynamicSizeType === 'fixed finger size');
    toggleRow('grp-minNotchSize', !isFixedNum && dynamicSizeType === 'fixed finger size');
    toggleRow('grp-minFingerSize', !isFixedNum && dynamicSizeType !== 'fixed finger size');
    toggleRow('grp-dovetailAngle', jointType === 'through dovetail');
    toggleRow('grp-reverseTaper', jointType === 'through dovetail');
}

function toggleSection(sectionEl) {
    sectionEl.classList.toggle('collapsed');
    // Save immediately (not debounced) so the collapsed state isn't lost if the palette
    // is closed before a debounced saveSettings() timer would otherwise have fired.
    clearTimeout(saveSettingsTimeout);
    adsk.fusionSendData('notification', JSON.stringify({ action: 'save_settings', payload: getPayload() }));
}

function getPayload() {
    return {
        placementType: document.getElementById('placementType').value,
        dynamicSizeType: document.getElementById('dynamicSizeType').value,
        jointType: document.getElementById('jointType').value,
        dovetailAngle: document.getElementById('dovetailAngle').value,
        reverseTaper: document.getElementById('reverseTaper').checked,
        isNumberOfFingersFixed: document.getElementById('isNumberOfFingersFixed').checked,
        fixedNumFingers: document.getElementById('fixedNumFingers').value,
        fixedNotchSize: document.getElementById('fixedNotchSize').value,
        fixedFingerSize: document.getElementById('fixedFingerSize').value,
        minNotchSize: document.getElementById('minNotchSize').value,
        minFingerSize: document.getElementById('minFingerSize').value,
        gap: document.getElementById('gap').value,
        gapToPart: document.getElementById('gapToPart').value,
        collapsedSections: {
            buttjoint: document.getElementById('section-buttjoint').classList.contains('collapsed'),
            config: document.getElementById('section-config').classList.contains('collapsed'),
            thememanager: document.getElementById('section-thememanager').classList.contains('collapsed')
        }
    };
}

function generateJoints() {
    adsk.fusionSendData('notification', JSON.stringify({ action: 'generate', payload: getPayload() }));
}

function previewJoints() {
    adsk.fusionSendData('notification', JSON.stringify({ action: 'preview', payload: getPayload() }));
}

let saveSettingsTimeout;
function saveSettings() {
    clearTimeout(saveSettingsTimeout);
    saveSettingsTimeout = setTimeout(() => {
        adsk.fusionSendData('notification', JSON.stringify({ action: 'save_settings', payload: getPayload() }));
    }, 500);
}

let previewTimeout;
function autoPreview() {
    saveSettings();
    const hasBody0 = document.getElementById('btn-body0').classList.contains('btn-primary');
    const hasBody1 = document.getElementById('btn-body1').classList.contains('btn-primary');
    if (hasBody0 && hasBody1) {
        clearTimeout(previewTimeout);
        previewTimeout = setTimeout(() => {
            previewJoints();
        }, 500); // 500ms debounce to prevent freezing the Fusion BRep engine
    }
}

function savePreset() {
    const name = prompt("Enter a name for this preset:");
    if (name) {
        adsk.fusionSendData('notification', JSON.stringify({ action: 'save_preset', name: name, payload: getPayload() }));
    }
}

function updatePreset() {
    const name = document.getElementById('presetSelect').value;
    if (!name) {
        alert("Select a preset first.");
        return;
    }
    // save_preset overwrites in place when the name already exists - same action as
    // Save, just reusing the currently-selected name instead of prompting for a new one.
    adsk.fusionSendData('notification', JSON.stringify({ action: 'save_preset', name: name, payload: getPayload() }));
}

function loadPreset() {
    const name = document.getElementById('presetSelect').value;
    if (name) {
        adsk.fusionSendData('notification', JSON.stringify({ action: 'load_preset', name: name }));
    }
}

function deletePreset() {
    const name = document.getElementById('presetSelect').value;
    if (name && confirm(`Are you sure you want to delete the preset "${name}"?`)) {
        adsk.fusionSendData('notification', JSON.stringify({ action: 'delete_preset', name: name }));
    }
}

function showResetConfirm() { document.getElementById('resetConfirmModal').style.display = 'flex'; }
function hideResetConfirm(e) { if(e) e.preventDefault(); document.getElementById('resetConfirmModal').style.display = 'none'; }
function confirmResetDefaults() {
    hideResetConfirm();
    adsk.fusionSendData('notification', JSON.stringify({ action: 'reset_defaults' }));
}

// Handle incoming messages from Python (Updates selection counts)
function updateSelBtn(id, text, isActive) {
    const btn = document.getElementById(id);
    btn.innerText = text;
    if (isActive) {
        btn.classList.add('btn-primary');
        btn.classList.remove('btn-secondary');
    } else {
        btn.classList.add('btn-secondary');
        btn.classList.remove('btn-primary');
    }
}

window.fusionJavaScriptHandler = {
    handle: function(action, data) {
        try {
            if (action === 'selection_updated') {
                const info = JSON.parse(data);
                if (info.target === 'body0') {
                    updateSelBtn('btn-body0', `Select 1st Body/Bodies (${info.count})`, info.count > 0);
                } else if (info.target === 'body1') {
                    updateSelBtn('btn-body1', `Select 2nd Body/Bodies (${info.count})`, info.count > 0);
                } else if (info.target === 'direction') {
                    updateSelBtn('btn-dir', info.count ? 'Direction (Selected)' : 'Select Direction (Auto)', info.count > 0);
                }
                autoPreview();
            } else if (action === 'file_imported') {
                const payload = JSON.parse(data);
                if (payload.file_type === 'css') {
                    const parsed = parseStyleCSS(payload.content);
                    Object.assign(themes, parsed.themes);
                    Object.assign(customThemes, parsed.themes);
                    localStorage.setItem('fjl_custom_themes', JSON.stringify(customThemes));
                    // Persist host-side too (each theme block in the
                    // bundle, skip "" -- that's :root, not a named theme).
                    Object.entries(parsed.themes).forEach(([id, vars]) => {
                        if (id !== '') adsk.fusionSendData('notification', JSON.stringify({ action: 'save_imported_theme', id: id, vars: vars }));
                    });
                    updateThemeDropdown(); updateStyleTag(); updateRemoveButtonState();
                } else if (payload.file_type === 'json') {
                    try {
                        const themeData = JSON.parse(payload.content);
                        if (themeData.vars && themeData.id !== undefined) {
                            themes[themeData.id] = themeData.vars;
                            customThemes[themeData.id] = themeData.vars;
                            localStorage.setItem('fjl_custom_themes', JSON.stringify(customThemes));
                            adsk.fusionSendData('notification', JSON.stringify({ action: 'save_imported_theme', id: themeData.id, vars: themeData.vars }));
                            updateThemeDropdown(); updateStyleTag();
                            document.getElementById('themeSelect').value = themeData.id;
                            changeTheme();
                        }
                    } catch(e) { alert("Invalid JSON theme format."); }
                }
            } else if (action === 'load_defaults') {
                const defaults = JSON.parse(data);
                if (defaults.style_css) {
                    const parsed = parseStyleCSS(defaults.style_css);
                    themes = parsed.themes; baseCSS = parsed.baseCSS;
                    builtInThemeIds = new Set(Object.keys(parsed.themes));
                    for (let id in customThemes) {
                        if (!themes[id]) themes[id] = {};
                        Object.assign(themes[id], customThemes[id]);
                    }
                    updateThemeDropdown();
                    updateStyleTag();
                }
                if (defaults.imported_themes) mergeImportedThemes(defaults.imported_themes);
                if (defaults.addin_version) document.getElementById('versionTag').textContent = 'v' + defaults.addin_version;
                if (defaults.placementType) document.getElementById('placementType').value = defaults.placementType;
                if (defaults.dynamicSizeType) document.getElementById('dynamicSizeType').value = defaults.dynamicSizeType;
                if (defaults.jointType) document.getElementById('jointType').value = defaults.jointType;
                if (defaults.dovetailAngle) document.getElementById('dovetailAngle').value = defaults.dovetailAngle;
                if (defaults.reverseTaper !== undefined) document.getElementById('reverseTaper').checked = defaults.reverseTaper;
                if (defaults.isNumberOfFingersFixed !== undefined) document.getElementById('isNumberOfFingersFixed').checked = defaults.isNumberOfFingersFixed;
                if (defaults.fixedNumFingers) document.getElementById('fixedNumFingers').value = defaults.fixedNumFingers;
                if (defaults.fixedNotchSize) document.getElementById('fixedNotchSize').value = defaults.fixedNotchSize;
                if (defaults.fixedFingerSize) document.getElementById('fixedFingerSize').value = defaults.fixedFingerSize;
                if (defaults.minNotchSize) document.getElementById('minNotchSize').value = defaults.minNotchSize;
                if (defaults.minFingerSize) document.getElementById('minFingerSize').value = defaults.minFingerSize;
                if (defaults.gap) document.getElementById('gap').value = defaults.gap;
                if (defaults.gapToPart) document.getElementById('gapToPart').value = defaults.gapToPart;
                if (defaults.theme) {
                    document.getElementById('themeSelect').value = defaults.theme;
                    changeTheme();
                }
                if (defaults.collapsedSections) {
                    const cs = defaults.collapsedSections;
                    document.getElementById('section-buttjoint').classList.toggle('collapsed', !!cs.buttjoint);
                    document.getElementById('section-config').classList.toggle('collapsed', !!cs.config);
                    document.getElementById('section-thememanager').classList.toggle('collapsed', !!cs.thememanager);
                }

                if (defaults.presets) {
                    const select = document.getElementById('presetSelect');
                    select.innerHTML = '<option value="">-- Presets --</option>';
                    defaults.presets.forEach(p => {
                        const opt = document.createElement('option');
                        opt.value = p; opt.innerText = p;
                        select.appendChild(opt);
                    });
                    if (defaults.selectedPreset) select.value = defaults.selectedPreset;
                }
                updateVisibility();
                autoPreview();
            } else if (action === 'update_presets') {
                const dataObj = JSON.parse(data);
                const select = document.getElementById('presetSelect');
                select.innerHTML = '<option value="">-- Presets --</option>';
                dataObj.presets.forEach(p => {
                    const opt = document.createElement('option');
                    opt.value = p; opt.innerText = p;
                    select.appendChild(opt);
                });
                if (dataObj.selected) select.value = dataObj.selected;
            }
        } catch (e) { console.log(e); }
        return 'OK';
    }
};

// Initialize UI
updateVisibility();

// Wait slightly to guarantee Fusion's CEF binding is active before requesting data
window.addEventListener('load', () => {
    setTimeout(() => {
        adsk.fusionSendData('notification', JSON.stringify({ action: 'html_loaded' }));
    }, 150);
});
