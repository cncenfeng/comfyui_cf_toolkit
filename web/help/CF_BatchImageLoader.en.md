Loads images from the input subdirectory and outputs a unified tensor batch.

- subdirectory: folder under ComfyUI/input/ where images are stored
- width/height: resize output images. 0 means no resize, keep original size
- exclude_files: hidden parameter managed by the frontend (eye button to show/hide files)

Use the upload button to add images, drag to reorder, click thumbnail to preview, and the eye button to exclude specific files from the batch.