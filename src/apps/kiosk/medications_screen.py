"""
Kiosk Medications screen: shell HTML and root node for the shared inline medication editor (kiosk_medications_embed.js + meridian_medications_inline.js).

Scope: panel + placeholder div only.
Not here: row editor, save/delete API calls, or webapp Settings editor (different host element).
"""

from . import html_primitives as hp


def build_medications_html(services, api_url: str) -> str:
    inner = (
        hp.kiosk_header("Medications")
        + hp.spacer(12)
        + '<div class="kiosk-settings">'
        + '<section class="kiosk-settings-card">'
        + '<div class="kiosk-settings-card__body">'
        + hp.kiosk_caption(
            "Same editor as the web dashboard. Confirmed removals save right away. "
            "For other edits, tap Save medications or turn on Save as you go."
        )
        + hp.spacer(10)
        + '<div id="kioskMedsEditorRoot"></div>'
        + hp.spacer(14)
        + '<button type="button" class="add-event-btn btn-large kiosk-settings-back-btn kiosk-meds-panel-back" data-screen="settings">Back to Settings</button>'
        + "</div></section></div>"
    )
    return hp.panel(inner, class_name="settings-panel kiosk-meds-panel")
