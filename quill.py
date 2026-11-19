"""Clipper: the code behind the buttons.

The editor itself is Cloudmorrow's timeline kit, declared in quill.toml:
projects, the pieces on their tracks and the blurs on the pieces, with the
kit's own field names. This is the rest, run in the sandbox as whoever
presses it: starting a project from a video or a sound (a button on its
sheet, in Media or Files), and asking for a save or an export. The video
itself is never touched here: services/render.py, a program beside the
server, draws the frames, fills in lengths and sizes, and renders the saves
and the exports.
"""

from cloudmorrow.quill import action, error, go, redraw, toast

PROJECT, PIECE, MEDIA, FILE = "clipper.project", "clipper.piece", "clipper.media", "file"
EXPORTS = "Clipper Exports"
TRACKS = [
    {"id": "V2", "kind": "video", "name": "Video 2"},
    {"id": "V1", "kind": "video", "name": "Video 1"},
    {"id": "A1", "kind": "audio", "name": "Audio 1"},
    {"id": "A2", "kind": "audio", "name": "Audio 2"},
]
VIDEO_SUFFIXES = (".mp4", ".mov", ".m4v", ".mkv", ".webm", ".avi", ".mts", ".m2ts", ".3gp", ".mpg", ".mpeg", ".ogv")
AUDIO_SUFFIXES = (".mp3", ".m4a", ".aac", ".wav", ".flac", ".ogg", ".oga", ".opus", ".wma", ".aif", ".aiff")
IMAGE_SUFFIXES = (".jpg", ".jpeg", ".png", ".gif", ".webp", ".bmp", ".tif", ".tiff", ".heic", ".heif", ".avif")
# How long a photo stays on the timeline when it is added, in seconds (the kit's).
IMAGE_LENGTH = 5.0
FORMATS = {"mp4": "MP4", "webm": "WebM", "mov": "MOV", "gif": "GIF", "m4a": "M4A"}
# What a save can be written as, by the name's suffix; anything else is written as an MP4 beside the video.
SAVE_SUFFIXES = {".mp4": "mp4", ".m4v": "mp4", ".mov": "mov", ".webm": "webm", ".gif": "gif", ".m4a": "m4a"}


# -- numbers and words ---------------------------------------------------------------------
def number(value, fallback=0.0):
    """A decimal field, which the store keeps as text, as a float."""
    try:
        return float(value)
    except (TypeError, ValueError):
        return fallback


def kind_of(record):
    """'video', 'audio', 'image', or None for a file that is none of them."""
    name = str(record.get("name") or "").lower()
    mime = str(record.get("mime") or "")
    if mime.startswith("video/") or name.endswith(VIDEO_SUFFIXES):
        return "video"
    if mime.startswith("audio/") or name.endswith(AUDIO_SUFFIXES):
        return "audio"
    if mime.startswith("image/") or name.endswith(IMAGE_SUFFIXES):
        return "image"
    return None


def known_lengths(ctx):
    """How long each file is, as the renderer read it; a file changed since is not known."""
    return {
        m["source"]: (number(m["duration"]), str(m.get("modified") or ""))
        for m in ctx.records.list(MEDIA)
        if number(m.get("duration")) > 0
    }


def length_of(lengths, file):
    length, modified = lengths.get(file.id, (0.0, ""))
    return length if length and modified == str(file.get("modified") or "") else None


# -- buttons --------------------------------------------------------------------------------
@action("edit_video")
def edit_video(ctx, video):
    kind = kind_of(video) if video.get("kind") == "file" else None
    if kind is None:
        return error(f"{video['name']} is neither a video, a photo nor a sound")
    title = str(video["name"]).rsplit(".", 1)[0]
    project = ctx.records.create(PROJECT, name=title, tracks=TRACKS, status="editing", source=video.id)
    length = IMAGE_LENGTH if kind == "image" else length_of(known_lengths(ctx), video)
    piece = {
        "project": project.id,
        "track": "A1" if kind == "audio" else "V1",
        "source": video.id,
        "name": video["name"],
        "start": 0,
        "offset": 0,
        "volume": 1,
        "muted": False,
    }
    if length:
        piece["length"] = round(length, 3)
    ctx.records.create(PIECE, piece)
    return [toast(f"Editing {title}"), go("editor", project=project.id)]


@action("export")
def export(ctx, project, format="mp4", size="project", name=""):
    if project.get("status") in ("queued", "rendering"):
        return error("It is being rendered already; wait for it to finish")
    pieces = ctx.records.list(PIECE, project=project.id)
    if not pieces:
        return error("Put something on the tracks first: there is nothing to export")
    if format == "m4a" and all(p.get("muted") for p in pieces):
        return error("Every piece is muted: a sound-only export would be silent")
    if format not in FORMATS:
        return error(f"No such format: {format}")
    ctx.records.patch(
        PROJECT,
        project.id,
        {
            "status": "queued",
            "message": f"Waiting to be exported as {FORMATS[format]}",
            "format": format,
            "size": size or "project",
            "export_name": (name or "").strip() or project["name"],
            "overwrite": False,
            "save_name": "",
        },
    )
    return toast(f"Queued: the export lands in My Files › {EXPORTS}")


@action("save")
def save(ctx, project, overwrite=False, name=""):
    """Over the video the project came from, or as a new file beside it. The
    kind is the name's suffix; one the renderer cannot write (MKV, AVI…) is
    saved as an MP4 beside the video instead, and never over it."""
    if project.get("status") in ("queued", "rendering"):
        return error("It is being rendered already; wait for it to finish")
    if not project.get("source"):
        return error("This project was not started from a video: there is nothing to write over. Export it instead")
    if not ctx.records.list(PIECE, project=project.id):
        return error("Put something on the tracks first: there is nothing to save")
    name = (name or "").strip()
    if not overwrite and not name:
        return error("Give the new file a name")
    if "/" in name:
        return error("A name has no slashes: the file goes beside the video")
    ctx.records.patch(
        PROJECT,
        project.id,
        {
            "status": "queued",
            "message": "Waiting to be written over the video" if overwrite else f"Waiting to be saved as {name}",
            "size": "project",
            "overwrite": bool(overwrite),
            "save_name": name,
        },
    )
    if overwrite:
        return toast("Saving over the video; the one before goes to the Trash")
    return toast(f"Saving as {name}, beside the video")


@action("refresh")
def refresh(ctx):
    return redraw()
