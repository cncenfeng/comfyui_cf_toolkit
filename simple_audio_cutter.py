import json
import logging
import math
import mimetypes
import os
import wave
import torch
import folder_paths
import numpy as np
import server
from aiohttp import web

MAX_MARKERS = 64


def _strip_path(path):
    path = (path or "").strip()
    if path.startswith('"'):
        path = path[1:]
    if path.endswith('"'):
        path = path[:-1]
    return path


def _list_input_audio_files():
    input_dir = folder_paths.get_input_directory()
    if not input_dir or not os.path.isdir(input_dir):
        return []
    audio_extensions = {".wav", ".mp3", ".flac", ".ogg", ".m4a", ".aac"}
    discovered = []
    for root, _dirs, files in os.walk(input_dir):
        for filename in files:
            ext = os.path.splitext(filename)[1].lower()
            if ext not in audio_extensions:
                continue
            full_path = os.path.join(root, filename)
            rel_path = os.path.relpath(full_path, input_dir).replace("\\", "/")
            discovered.append(rel_path)
    return sorted(discovered)


def _resolve_audio_path(audio_file):
    audio_file = _strip_path(audio_file)
    if not audio_file:
        raise ValueError("audio_file is empty")
    if os.path.isabs(audio_file) and os.path.isfile(audio_file):
        return audio_file
    try:
        annotated = folder_paths.get_annotated_filepath(audio_file)
        if annotated and os.path.isfile(annotated):
            return annotated
    except Exception:
        pass
    input_candidate = os.path.join(folder_paths.get_input_directory(), audio_file)
    if os.path.isfile(input_candidate):
        return input_candidate
    raise ValueError(f"Audio file not found: {audio_file}")


def _load_audio_tensor_from_file(audio_file):
    audio_path = _resolve_audio_path(audio_file)
    ext = os.path.splitext(audio_path)[1].lower()

    if ext != ".wav":
        try:
            from pydub import AudioSegment
            seg = AudioSegment.from_file(audio_path)
            sr = seg.frame_rate
            if seg.channels > 1:
                seg = seg.set_channels(1)
            raw = np.array(seg.get_array_of_samples(), dtype=np.float32)
            max_val = 1 << (8 * seg.sample_width - 1)
            if max_val > 0:
                raw /= max_val
            waveform = torch.from_numpy(raw).unsqueeze(0).float()
            return {"waveform": waveform, "sample_rate": sr}
        except ImportError:
            raise ValueError("pydub not installed. Please install: pip install pydub")
        except Exception as e:
            raise ValueError(f"pydub failed: {e}\nPlease ensure ffmpeg is in PATH")

    import wave
    with wave.open(audio_path, "rb") as wav_file:
        channels = wav_file.getnchannels()
        sampwidth = wav_file.getsampwidth()
        sr = wav_file.getframerate()
        frames = wav_file.getnframes()
        data = wav_file.readframes(frames)

    if frames <= 0 or sr <= 0:
        raise ValueError("Invalid WAV file")

    if sampwidth == 1:
        arr = np.frombuffer(data, dtype=np.uint8).astype(np.float32)
        arr = (arr - 128.0) / 128.0
    elif sampwidth == 2:
        arr = np.frombuffer(data, dtype=np.int16).astype(np.float32)
        arr = arr / 32768.0
    elif sampwidth == 3:
        raw = np.frombuffer(data, dtype=np.uint8).reshape(-1, 3)
        signed = (raw[:, 0].astype(np.int32) |
                  (raw[:, 1].astype(np.int32) << 8) |
                  (raw[:, 2].astype(np.int32) << 16))
        sign_mask = 1 << 23
        signed = (signed ^ sign_mask) - sign_mask
        arr = signed.astype(np.float32) / float(1 << 23)
    elif sampwidth == 4:
        arr = np.frombuffer(data, dtype=np.int32).astype(np.float32)
        arr = arr / float(1 << 31)
    else:
        raise ValueError(f"Unsupported sample width: {sampwidth}")

    if channels > 1:
        arr = arr.reshape(-1, channels)
        arr = np.mean(arr, axis=1)
    else:
        arr = arr.ravel()

    waveform = torch.from_numpy(arr).unsqueeze(0).float()
    return {"waveform": waveform, "sample_rate": sr}


def _read_waveform_peaks(audio_file, bins=1400):
    audio = _load_audio_tensor_from_file(audio_file)
    waveform = audio["waveform"]
    sample_rate = audio["sample_rate"]
    if waveform.ndim == 2:
        waveform = waveform.unsqueeze(0)
    waveform_np = waveform.numpy()
    if waveform_np.shape[1] > 1:
        samples = np.mean(np.abs(waveform_np), axis=1)[0]
    else:
        samples = np.abs(waveform_np[0, 0])
    frame_count = len(samples)
    bins = max(64, min(int(bins), 4096))
    if samples.size == 0:
        peaks = []
    else:
        edges = np.linspace(0, samples.size, num=bins + 1, dtype=np.int64)
        peaks = []
        for idx in range(bins):
            start = edges[idx]
            end = edges[idx + 1]
            if end <= start:
                peaks.append(0.0)
                continue
            peaks.append(float(np.max(samples[start:end])))
    duration = float(frame_count) / float(sample_rate) if sample_rate > 0 else 0.0
    return {
        "duration": duration,
        "sample_rate": sample_rate,
        "peaks": peaks,
        "audio_path": _resolve_audio_path(audio_file),
    }


def _parse_keyframe_list(value):
    if value is None:
        return []
    if isinstance(value, (list, tuple)):
        raw = value
    else:
        text = str(value).strip()
        if not text:
            return []
        parsed = json.loads(text)
        raw = parsed.get("keyframes", []) if isinstance(parsed, dict) else parsed
    return [max(0.0, float(x)) for x in raw]


def _normalize_keyframe_list(keyframes, total_duration=None):
    seen = set()
    norm = []
    for sec in keyframes or []:
        sec = max(0.0, float(sec))
        if total_duration is not None and total_duration > 0:
            sec = min(sec, total_duration - 0.001)
        bucket = int(round(sec * 1000))
        if bucket not in seen:
            seen.add(bucket)
            norm.append(sec)
    norm.sort()
    return norm[:MAX_MARKERS]


def _normalize_audio_tensor(audio):
    waveform = audio["waveform"]
    sample_rate = audio["sample_rate"]
    if waveform.ndim == 2:
        waveform = waveform.unsqueeze(0)
    return waveform, sample_rate


def _slice_audio(audio, start_frame, end_frame):
    waveform, sample_rate = _normalize_audio_tensor(audio)
    start_frame = max(0, int(start_frame))
    end_frame = max(start_frame + 1, int(end_frame))
    return {
        "waveform": waveform[..., start_frame:end_frame],
        "sample_rate": sample_rate,
    }


def _build_segments(total_duration, keyframes, skip_initial_segment, include_tail_segment):
    total_duration = max(0.0, total_duration)
    markers = _normalize_keyframe_list(keyframes, total_duration)

    if not markers:
        return [(0.0, total_duration)], total_duration

    segments = []
    if skip_initial_segment:
        starts = markers[:-1]
        ends = markers[1:]
        if include_tail_segment and markers:
            starts.append(markers[-1])
            ends.append(total_duration)
    else:
        starts = [0.0] + markers[:-1]
        ends = markers[:]
        if include_tail_segment and markers:
            starts.append(markers[-1])
            ends.append(total_duration)

    for s, e in zip(starts, ends):
        if e > s:
            segments.append((float(s), float(e)))

    if not segments:
        segments = [(0.0, total_duration)]

    total_selected = sum(e - s for s, e in segments)
    return segments, total_selected


def _safe_int(value, default=0):
    try:
        if value is None:
            return default
        if isinstance(value, str):
            value = value.strip()
            if value == "":
                return default
        return int(value)
    except Exception:
        return default


class CF_SimpleAudioCutter:
    @classmethod
    def INPUT_TYPES(cls):
        files = _list_input_audio_files() or [""]
        return {
            "required": {
                "音频文件": (files, {"default": files[0]}),
                "关键帧JSON": ("STRING", {"default": "[]", "multiline": False}),
                "跳过初始段": ("BOOLEAN", {"default": True}),
                "包含尾部段": ("BOOLEAN", {"default": False}),
            },
            "optional": {
                "分段索引": ("INT", {"default": 0, "min": 0, "max": 1000000, "step": 1, "hidden": True}),
                "渲染ID": ("STRING", {"default": "", "hidden": True})
            },
        }

    RETURN_TYPES = ("AUDIO", "STRING")
    RETURN_NAMES = ("音频", "分段整数秒列表")
    FUNCTION = "select_segment"
    CATEGORY = "CF工具包"

    @classmethod
    def VALIDATE_INPUTS(cls, 音频文件="", 关键帧JSON="[]", **_kwargs):
        try:
            if 音频文件:
                _resolve_audio_path(音频文件)
            _parse_keyframe_list(关键帧JSON)
            return True
        except Exception as e:
            return str(e)

    def select_segment(
        self,
        音频文件="",
        关键帧JSON="[]",
        跳过初始段=True,
        包含尾部段=False,
        分段索引=0,
        渲染ID="",
    ):
        audio = _load_audio_tensor_from_file(音频文件)
        waveform, sample_rate = _normalize_audio_tensor(audio)
        total_duration = waveform.shape[-1] / sample_rate if sample_rate else 0.0

        keyframes = _parse_keyframe_list(关键帧JSON)
        segments, _ = _build_segments(total_duration, keyframes, 跳过初始段, 包含尾部段)

        start_seconds = segments[0][0]
        end_seconds = segments[-1][1]

        start_frame = int(math.floor(start_seconds * sample_rate))
        end_frame = int(math.ceil(end_seconds * sample_rate))
        selected_audio = _slice_audio(audio, start_frame, end_frame)

        int_lines = [str(int(round(e - s))) for s, e in segments]
        segment_ints_str = "\n".join(int_lines)

        return (selected_audio, segment_ints_str)


# ---------- HTTP 路由（统一使用 /simpleaudio 前缀） ----------
async def simple_audio_file(request):
    audio_file = request.query.get("audio_file", "")
    try:
        path = _resolve_audio_path(audio_file)
        return web.FileResponse(path, headers={"Content-Type": mimetypes.guess_type(path)[0] or "application/octet-stream"})
    except Exception as e:
        return web.json_response({"error": str(e)}, status=400)


async def simple_audio_waveform(request):
    audio_file = request.query.get("audio_file", "")
    bins = request.query.get("bins", "1400")
    try:
        data = _read_waveform_peaks(audio_file, bins=int(bins))
        data["audio_url"] = f"/simpleaudio/audio-file?audio_file={audio_file}"
        return web.json_response(data)
    except Exception as e:
        return web.json_response({"error": str(e)}, status=400)


_prompt_server_instance = getattr(server.PromptServer, "instance", None)
if _prompt_server_instance is not None:
    _prompt_server_instance.routes.get("/simpleaudio/audio-file")(simple_audio_file)
    _prompt_server_instance.routes.get("/simpleaudio/audio-waveform")(simple_audio_waveform)


NODE_CLASS_MAPPINGS = {"CF_SimpleAudioCutter": CF_SimpleAudioCutter}
NODE_DISPLAY_NAME_MAPPINGS = {"CF_SimpleAudioCutter": "CF 简易音频切片器"}