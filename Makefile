.PHONY: eval test test-intent test-voice test-modalities

eval:
	python scripts/run_eval.py

test: eval

test-intent:
	python scripts/test_scam_intent.py

test-voice:
	python scripts/evaluate_voice_diversity.py

test-modalities:
	python tests/deep_check_all_modalities.py
