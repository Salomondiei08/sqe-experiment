PY ?= python3
VERIFY_REPORT ?= /tmp/sqe_verify_make_verify.json

.PHONY: help paper verify readiness release manifest arxiv external-evidence-resume

help:
	@printf '%s\n' \
		'Targets:' \
		'  make paper                    Rebuild and verify the current paper package from existing evidence.' \
		'  make verify                   Run the final seed-42 package verifier.' \
		'  make readiness                Refresh docs/audits/SUBMISSION_READINESS.json and missing-evidence blockers.' \
		'  make release                  Refresh local Hugging Face and GitHub release directories.' \
		'  make manifest                 Refresh docs/manifests/ARTIFACT_MANIFEST.json.' \
		'  make arxiv                    Build a minimal, compile-checked arXiv source archive.' \
		'  make external-evidence-resume Run guarded resume after real Pass@1 rows and human labels exist.'

paper:
	bash scripts/run_paper_pipeline.sh

verify:
	$(PY) scripts/07_verify_experiment.py \
		--data_dir data_500_memory_seed42 \
		--index_dir index_500_seed42 \
		--results_dir results/seed42 \
		--paper_dir paper \
		--report_path $(VERIFY_REPORT)

readiness:
	$(PY) scripts/14_submission_readiness_check.py \
		--root . \
		--output docs/audits/SUBMISSION_READINESS.json
	$(PY) scripts/35_write_missing_evidence_blockers.py \
		--root . \
		--output MISSING_EVIDENCE_BLOCKERS.json

release:
	$(PY) scripts/33_prepare_hf_dataset_release.py \
		--root . \
		--output_dir /tmp/sqe_hf_dataset_release \
		--include_detailed_results
	$(PY) scripts/34_prepare_github_code_release.py \
		--root . \
		--output_dir /tmp/sqe_github_code_release \
		--include_result_summaries

manifest:
	$(PY) scripts/13_make_artifact_manifest.py \
		--root . \
		--output docs/manifests/ARTIFACT_MANIFEST.json

arxiv:
	$(PY) scripts/46_prepare_arxiv_submission.py

external-evidence-resume:
	scripts/44_resume_after_external_evidence.sh verify-only
