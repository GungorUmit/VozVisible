def test_transcribe_bytes_callable():
    import importlib.util, sys, pathlib
    mod_path = pathlib.Path(__file__).parent.parent / 'spoken_to_signed' / 'audio_to_text' / 'infer.py'
    spec = importlib.util.spec_from_file_location('sv_infer', str(mod_path))
    mod = importlib.util.module_from_spec(spec)
    sys.modules['sv_infer'] = mod
    spec.loader.exec_module(mod)
    assert hasattr(mod, 'transcribe_bytes') and callable(mod.transcribe_bytes)
