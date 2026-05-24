Manages videos in the output subdirectory and optionally concatenates all into one file.

- subdirectory: folder under ComfyUI/output/
- concatenate: ON = merge all videos in the directory into a single mp4 (uses ffmpeg, requires ffmpeg in PATH)
- overwrite: ON = replace existing concatenated output; OFF = keep previous

Outputs the path to the concatenated video and the total count.