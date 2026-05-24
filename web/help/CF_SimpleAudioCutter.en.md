Audio slicer and AI analyzer based on Qwen2-Audio-7B.

- audio_file: select from pre-uploaded audio files
- keyframe_json: JSON array of timestamps in seconds, managed visually by the waveform editor
- skip_initial_segment: ON = first marker is the start point only (skip segment before it)
- include_tail_segment: ON = include segment from last marker to the end
- analysis_prompt: natural language instruction for the AI to analyze the audio (e.g. lyrics, emotion, instruments)
- segment_index: which single segment to output as 'current segment'
- other params: control LLM generation behavior (temperature, top_p, seed, etc.)

Outputs:
- merged audio: all selected segments combined
- segment durations: duration of each segment in integer seconds
- analysis text: AI-generated analysis result
- audio duration: total length in seconds
- current segment audio: the single selected segment
- total segments: number of segments