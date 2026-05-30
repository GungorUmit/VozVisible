# Lightweight runtime transcription helper for VozVisible
# Uses HuggingFace Whisper model for on-the-fly transcription.
from typing import Optional

_model = None
_processor = None

def _load_model(model_name: str = "openai/whisper-small"):
    global _model, _processor
    if _model is None:
        from transformers import WhisperProcessor, WhisperForConditionalGeneration
        _processor = WhisperProcessor.from_pretrained(model_name)
        _model = WhisperForConditionalGeneration.from_pretrained(model_name)
        # Prefer Spanish transcription by default
        try:
            forced_decoder_ids = _processor.get_decoder_prompt_ids(language="spanish", task="transcribe")
            _model.config.forced_decoder_ids = forced_decoder_ids
            _model.config.suppress_tokens = []
        except Exception:
            pass
        # Keep model on CPU by default; container can move to GPU by setting device later.
        try:
            import torch
            _model.to("cpu")
        except Exception:
            pass
    return _model, _processor


def transcribe_bytes(audio_bytes: bytes, sampling_rate: int = 16000, model_name: str = "openai/whisper-small") -> str:
    """Transcribe raw audio bytes and return recognized text.

    This function attempts to read audio from bytes using soundfile, with a librosa
    fallback for resampling when necessary.
    """
    model, processor = _load_model(model_name)

    # import lazily to avoid heavy deps at module import time
    try:
        import soundfile as sf
        import io as _io
        data, sr = sf.read(_io.BytesIO(audio_bytes), dtype="float32")
    except Exception:
        # Fallback: write to temp file and use librosa
        try:
            import tempfile
            import librosa
            import io as _io
            with tempfile.NamedTemporaryFile(suffix='.wav', delete=True) as tmp:
                tmp.write(audio_bytes)
                tmp.flush()
                data, sr = librosa.load(tmp.name, sr=None)
        except Exception as e:
            raise RuntimeError(f"Unable to read uploaded audio: {e}")

    # Resample if needed
    if sr != sampling_rate:
        try:
            import librosa
            data = librosa.resample(data, orig_sr=sr, target_sr=sampling_rate)
            sr = sampling_rate
        except Exception:
            pass

    inputs = processor(data, sampling_rate=sampling_rate, return_tensors="pt")

    # Generate transcription (use .generate on the model)
    try:
        generated_ids = model.generate(inputs.input_features)
        transcription = processor.batch_decode(generated_ids, skip_special_tokens=True)[0]
        return transcription
    except Exception as e:
        raise RuntimeError(f"Transcription failed: {e}")
