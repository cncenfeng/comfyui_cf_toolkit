"""
CF_BatchVideoLoader + CF_BatchVideoManager — two nodes, shared logic.
Uses media_utils.py for directory management, file listing, and HTTP routes.
"""
import os
import subprocess

from .cf_help_loader import get_help_en
from .media_utils import (
    get_input_dir, get_output_dir,
    list_media_files, clear_directory,
    register_media_routes,
)

VIDEO_EXTENSIONS = [".mp4", ".avi", ".mov", ".webm", ".mkv"]

register_media_routes("video_input",  lambda s: get_input_dir(s or "batch_uploads"))
register_media_routes("video_output", lambda s: get_output_dir(s or "batch_outputs"))


def _concat_videos(target_dir, files):
    list_path = os.path.join(target_dir, "_concat_list.txt")
    output_path = os.path.join(target_dir, "concatenated.mp4")
    if os.path.exists(output_path):
        os.remove(output_path)
    with open(list_path, "w", encoding="utf-8") as f:
        for name in files:
            abs_path = os.path.join(target_dir, name).replace("\\", "/")
            f.write(f"file '{abs_path}'\n")
    try:
        subprocess.run([
            "ffmpeg", "-y", "-f", "concat", "-safe", "0",
            "-i", list_path, "-c", "copy", output_path,
        ], check=True, capture_output=True)
    except subprocess.CalledProcessError as e:
        print(f"[CF_BatchVideo] ffmpeg failed: {e.stderr.decode()}")
        output_path = ""
    except FileNotFoundError:
        print("[CF_BatchVideo] ffmpeg not found in PATH")
        output_path = ""
    finally:
        if os.path.exists(list_path):
            os.remove(list_path)
    return output_path


class CF_BatchVideoLoader:
    DESCRIPTION = get_help_en("CF_BatchVideoLoader")

    @classmethod
    def INPUT_TYPES(cls):
        return {
            "required": {
                "subdirectory": ("STRING", {"default": "batch_uploads", "label": "子目录"}),
            }
        }

    RETURN_TYPES = ("INT",)
    RETURN_NAMES = ("video_count",)
    FUNCTION = "run"
    CATEGORY = "CF工具包"

    def run(self, subdirectory="batch_uploads"):
        target_dir = get_input_dir(subdirectory)
        files = list_media_files(target_dir, VIDEO_EXTENSIONS)
        return (len(files),)


class CF_BatchVideoManager:
    OUTPUT_NODE = True
    DESCRIPTION = get_help_en("CF_BatchVideoManager")

    @classmethod
    def INPUT_TYPES(cls):
        return {
            "required": {
                "subdirectory": ("STRING",  {"default": "batch_outputs", "label": "子目录"}),
                "concatenate":  ("BOOLEAN", {"default": False, "label": "拼接为单个视频"}),
                "overwrite":    ("BOOLEAN", {"default": True, "label": "覆盖模式 (关闭=追加)"}),
            }
        }

    RETURN_TYPES = ("STRING", "INT")
    RETURN_NAMES = ("output_video", "video_count")
    FUNCTION = "manage"
    CATEGORY = "CF工具包"

    def manage(self, subdirectory="batch_outputs", concatenate=False, overwrite=True):
        target_dir = get_output_dir(subdirectory)
        files = list_media_files(target_dir, VIDEO_EXTENSIONS)
        if not files:
            return "", 0
        output_path = _concat_videos(target_dir, files) if concatenate else ""
        return output_path.replace("\\", "/") if output_path else "", len(files)


NODE_CLASS_MAPPINGS = {
    "CF_BatchVideoLoader":  CF_BatchVideoLoader,
    "CF_BatchVideoManager": CF_BatchVideoManager,
}
NODE_DISPLAY_NAME_MAPPINGS = {
    "CF_BatchVideoLoader":  "CF 批量视频加载器",
    "CF_BatchVideoManager": "CF 批量视频管理器",
}
