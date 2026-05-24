import os
from .cf_batch_media import CF_BatchImageLoader, CF_BatchImageManager
from .cf_batch_video import CF_BatchVideoLoader, CF_BatchVideoManager
from .simple_audio_cutter import CF_SimpleAudioCutter
from .qwen_image_edit import CF_QwenImageEditEnhanced
from .cf_universal_calculator import CF_UniversalCalculator

NODE_CLASS_MAPPINGS = {
    "CF_BatchImageLoader": CF_BatchImageLoader,
    "CF_BatchImageManager": CF_BatchImageManager,
    "CF_BatchVideoLoader": CF_BatchVideoLoader,
    "CF_BatchVideoManager": CF_BatchVideoManager,
    "CF_SimpleAudioCutter": CF_SimpleAudioCutter,
    "CF_QwenImageEditEnhanced": CF_QwenImageEditEnhanced,
    "CF_UniversalCalculator": CF_UniversalCalculator,
}

NODE_DISPLAY_NAME_MAPPINGS = {
    "CF_BatchImageLoader": "CF 批量图像加载器",
    "CF_BatchImageManager": "CF 批量图像管理器",
    "CF_BatchVideoLoader": "CF 批量视频加载器",
    "CF_BatchVideoManager": "CF 批量视频管理器",
    "CF_SimpleAudioCutter": "CF 简易音频切片器",
    "CF_QwenImageEditEnhanced": "CF Qwen Image Edit (Batch Image)",
    "CF_UniversalCalculator": "CF 通用运算器",
}

WEB_DIRECTORY = "web"

__all__ = ['NODE_CLASS_MAPPINGS', 'NODE_DISPLAY_NAME_MAPPINGS', 'WEB_DIRECTORY']