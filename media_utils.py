"""
Shared media utilities — directory management, file listing, ordering, HTTP routes.
Used by cf_batch_media.py (image) and cf_batch_video.py (video).
"""
import os
import re
import mimetypes
import folder_paths
import server
from aiohttp import web


def get_input_dir(subdir=""):
    base = folder_paths.get_input_directory()
    target = os.path.join(base, subdir)
    os.makedirs(target, exist_ok=True)
    return target


def get_output_dir(subdir=""):
    base = folder_paths.get_output_directory()
    target = os.path.normpath(os.path.join(base, subdir))
    if not target.startswith(os.path.normpath(base)):
        raise ValueError(f"Invalid subdir: {subdir}")
    os.makedirs(target, exist_ok=True)
    return target


def list_media_files(target_dir, extensions):
    """List files matching '{number}.{ext}' pattern, sorted by number prefix."""
    ext_pattern = "|".join(re.escape(e.lstrip(".")) for e in extensions)
    pattern = re.compile(rf"^(\d+)\.({ext_pattern})$", re.IGNORECASE)
    files = []
    for f in os.listdir(target_dir):
        m = pattern.match(f)
        if m:
            files.append((int(m.group(1)), f))
    files.sort(key=lambda x: x[0])
    return [f for _, f in files]


def get_next_number(target_dir):
    """Find the smallest unused number prefix in the directory."""
    used = set()
    for f in os.listdir(target_dir):
        m = re.match(r"^(\d+)", f)
        if m:
            used.add(int(m.group(1)))
    n = 0
    while n in used:
        n += 1
    return n


def clear_directory(target_dir):
    """Remove all files in the directory."""
    for f in os.listdir(target_dir):
        fp = os.path.join(target_dir, f)
        if os.path.isfile(fp):
            os.remove(fp)


def apply_ordering(target_dir, ordered_filenames):
    """Reorder files: delete unlisted, rename remaining to {000.ext} seq."""
    existing = set(os.listdir(target_dir))
    to_delete = existing - set(ordered_filenames)
    for f in to_delete:
        fp = os.path.join(target_dir, f)
        if os.path.isfile(fp):
            os.remove(fp)
    temp_map = []
    for i, old_name in enumerate(ordered_filenames):
        ext = old_name.rsplit(".", 1)[-1]
        new_name = f"{i:03d}.{ext}"
        old_path = os.path.join(target_dir, old_name)
        temp_path = os.path.join(target_dir, f"_temp_{i}_{old_name}")
        if os.path.exists(old_path):
            os.rename(old_path, temp_path)
            temp_map.append((temp_path, new_name))
    for temp_path, new_name in temp_map:
        os.rename(temp_path, os.path.join(target_dir, new_name))


def register_media_routes(prefix, dir_func):
    """
    Register 4 HTTP routes:
      GET  /{prefix}/list?subdir=...       → {files: [...]}
      GET  /{prefix}/next_number?subdir=... → {next_num: int}
      GET  /{prefix}/preview?subdir=...&filename=... → file response
      POST /{prefix}/apply                → {files: [...]}
    dir_func(subdir) must return the target directory path.
    """

    async def _list(request):
        subdir = request.query.get("subdir", "")
        target = dir_func(subdir)
        files = list_media_files(target, [".png", ".jpg", ".jpeg", ".mp4", ".avi", ".mov", ".webm"])
        return web.json_response({"files": files, "dir": target})

    async def _next_number(request):
        subdir = request.query.get("subdir", "")
        target = dir_func(subdir)
        n = get_next_number(target)
        return web.json_response({"next_num": n})

    async def _preview(request):
        subdir = request.query.get("subdir", "")
        filename = request.query.get("filename", "")
        if not filename:
            return web.json_response({"error": "no filename"}, status=400)
        target = dir_func(subdir)
        safe_path = os.path.join(target, os.path.basename(filename))
        if not os.path.exists(safe_path):
            return web.json_response({"error": "file not found"}, status=404)
        return web.FileResponse(safe_path, headers={
            "Content-Type": mimetypes.guess_type(safe_path)[0] or "application/octet-stream",
            "Cache-Control": "no-store, no-cache, must-revalidate",
        })

    async def _apply(request):
        data = await request.json()
        subdir = data.get("subdir", "")
        ordered = data.get("ordered_filenames", [])
        target = dir_func(subdir)
        apply_ordering(target, ordered)
        files = list_media_files(target, [".png", ".jpg", ".jpeg", ".mp4", ".avi", ".mov", ".webm"])
        return web.json_response({"files": files, "dir": target})

    try:
        server.PromptServer.instance.routes.get(f"/cf_media/{prefix}/list")(_list)
        server.PromptServer.instance.routes.get(f"/cf_media/{prefix}/next_number")(_next_number)
        server.PromptServer.instance.routes.get(f"/cf_media/{prefix}/preview")(_preview)
        server.PromptServer.instance.routes.post(f"/cf_media/{prefix}/apply")(_apply)
    except Exception as e:
        print(f"[CF_Media] Route registration failed for /cf_media/{prefix}: {e}")
