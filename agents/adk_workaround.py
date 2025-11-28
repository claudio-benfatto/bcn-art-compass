"""
ADK workaround for event.actions.compaction dict bug.

Usage: import and call patch_event_compaction(event) before accessing compaction attributes.
"""
from google.adk.events.event_actions import EventCompaction

def patch_event_compaction(event):
    """
    If event.actions.compaction is a dict, reconstruct as EventCompaction.
    Returns patched compaction object (model or None).
    """
    compaction = getattr(getattr(event, "actions", None), "compaction", None)
    if compaction is None:
        return None
    if isinstance(compaction, dict):
        try:
            compaction = EventCompaction.model_validate(compaction)
        except Exception:
            return None
    return compaction
