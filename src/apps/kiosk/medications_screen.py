"""Medications editor screen: mount for webapp inline editor (kiosk_medications_embed.js)."""

from . import html_primitives as hp


def build_medications_html(services, api_url: str) -> str:
    inner = (
        hp.kiosk_header("Medications")
        + hp.kiosk_caption("Same editor as the web dashboard. Add rows, edit, then Save.")
        + hp.spacer(12)
        + '<div id="kioskMedsEditorRoot"></div>'
        + hp.spacer(16)
        + '<div class="home-action-row">'
        + '<button type="button" class="add-event-btn btn-large" data-screen="settings">Back to Settings</button>'
        + "</div>"
    )
    return hp.panel(inner, class_name="settings-panel")
