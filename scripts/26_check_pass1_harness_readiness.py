"""
Preflight-check the local EvoAgentBench SWE-bench Pass@1 runner.

This script does not run agents, start containers, or create Pass@1 evidence.
It reports whether the local environment is ready to execute real downstream
SWE-bench task-success runs using the prepared SQE retrieval-context packets.
"""

import argparse
import datetime as dt
import importlib.util
import json
import os
import shutil
import socket
import subprocess
import sys
from pathlib import Path
import grp
import pwd


DEFAULT_EVO_ROOT = Path("/home/nlp-07/evermemos/EverOS/benchmarks/EvoAgentBench")
DEFAULT_SQE_ROOT = Path("/home/nlp-07/sqe_experiment")


def check_python_imports(python_path, modules):
    code = (
        "import importlib.util, json\n"
        f"mods={modules!r}\n"
        "print(json.dumps({m: importlib.util.find_spec(m) is not None for m in mods}))\n"
    )
    try:
        proc = subprocess.run(
            [str(python_path), "-c", code],
            text=True,
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            timeout=30,
            check=False,
        )
    except Exception as exc:
        return {
            "python": str(python_path),
            "ok": False,
            "error": f"{type(exc).__name__}: {exc}",
            "modules": {},
        }
    modules_found = {}
    if proc.stdout.strip():
        try:
            modules_found = json.loads(proc.stdout)
        except json.JSONDecodeError:
            pass
    missing = sorted([name for name, found in modules_found.items() if not found])
    return {
        "python": str(python_path),
        "ok": proc.returncode == 0 and not missing,
        "returncode": proc.returncode,
        "modules": modules_found,
        "missing": missing,
        "stderr": proc.stderr.strip()[:1000],
    }


def check_docker_access():
    docker = shutil.which("docker")
    sock = Path("/var/run/docker.sock")
    result = {
        "docker_cli": docker,
        "socket": str(sock),
        "socket_exists": sock.exists(),
        "can_run_docker_ps": False,
    }
    if sock.exists():
        stat = sock.stat()
        result["socket_uid"] = stat.st_uid
        result["socket_gid"] = stat.st_gid
        try:
            socket_group = grp.getgrgid(stat.st_gid)
            result["socket_group_name"] = socket_group.gr_name
            result["socket_group_members"] = sorted(socket_group.gr_mem)
        except KeyError:
            result["socket_group_name"] = None
            result["socket_group_members"] = []
        result["user_uid"] = os.getuid()
        result["user_groups"] = os.getgroups()
        try:
            user = pwd.getpwuid(os.getuid()).pw_name
        except KeyError:
            user = None
        result["user_name"] = user
        result["user_group_names"] = []
        for gid in os.getgroups():
            try:
                result["user_group_names"].append(grp.getgrgid(gid).gr_name)
            except KeyError:
                result["user_group_names"].append(str(gid))
        result["user_in_socket_group"] = stat.st_gid in os.getgroups()
        result["user_listed_in_socket_group"] = (
            bool(user) and user in result["socket_group_members"]
        )
    if not docker:
        result["error"] = "docker CLI not found"
        return result
    try:
        proc = subprocess.run(
            [docker, "ps"],
            text=True,
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            timeout=20,
            check=False,
        )
    except Exception as exc:
        result["error"] = f"{type(exc).__name__}: {exc}"
        return result
    result["returncode"] = proc.returncode
    result["can_run_docker_ps"] = proc.returncode == 0
    result["stdout"] = proc.stdout.strip()[:1000]
    result["stderr"] = proc.stderr.strip()[:1000]
    return result


def check_alternate_container_runtimes():
    """Record non-Docker runtimes for diagnosis; SWE-bench still needs Docker."""
    runtimes = {}
    for name in ["nerdctl", "podman", "apptainer", "singularity"]:
        binary = shutil.which(name)
        entry = {
            "binary": binary,
            "present": binary is not None,
            "can_list_containers": False,
            "is_drop_in_for_evoagentbench_swebench": False,
        }
        if binary and name in {"nerdctl", "podman"}:
            try:
                proc = subprocess.run(
                    [binary, "ps"],
                    text=True,
                    stdout=subprocess.PIPE,
                    stderr=subprocess.PIPE,
                    timeout=20,
                    check=False,
                )
                entry["returncode"] = proc.returncode
                entry["can_list_containers"] = proc.returncode == 0
                entry["stdout"] = proc.stdout.strip()[:1000]
                entry["stderr"] = proc.stderr.strip()[:1000]
            except Exception as exc:
                entry["error"] = f"{type(exc).__name__}: {exc}"
        runtimes[name] = entry
    return {
        "note": (
            "Diagnostic only. EvoAgentBench SWE-bench uses Docker SDK and "
            "Docker socket APIs, so alternate runtimes are not Pass@1 readiness "
            "unless the harness is ported and verified."
        ),
        "runtimes": runtimes,
    }


def check_evoagentbench_data(evo_root):
    swe_dir = evo_root / "data" / "swebench"
    parquet = swe_dir / "test-00000-of-00001.parquet"
    split = swe_dir / "task_split.json"
    images = swe_dir / "images"
    tar_files = sorted(images.glob("*.tar")) if images.exists() else []
    manifest = swe_dir / "sqe_prepared_manifest.json"
    return {
        "swebench_data_dir": str(swe_dir),
        "parquet": str(parquet),
        "parquet_exists": parquet.exists(),
        "split_file": str(split),
        "split_file_exists": split.exists(),
        "prepared_manifest": str(manifest),
        "prepared_manifest_exists": manifest.exists(),
        "images_dir": str(images),
        "images_dir_exists": images.exists(),
        "n_local_tar_images": len(tar_files),
    }


def check_context_packets(sqe_root):
    context_dir = sqe_root / "pass1_contexts"
    verifier = sqe_root / "scripts" / "25_verify_pass1_contexts.py"
    result = {
        "context_dir": str(context_dir),
        "context_dir_exists": context_dir.exists(),
        "verifier": str(verifier),
        "verifier_exists": verifier.exists(),
        "valid": False,
    }
    if not verifier.exists():
        result["problems"] = ["context verifier missing"]
        return result
    spec = importlib.util.spec_from_file_location("pass1_context_verifier", verifier)
    if spec is None or spec.loader is None:
        result["problems"] = ["cannot load context verifier"]
        return result
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    expected_methods = getattr(module, "DEFAULT_EXPECTED_METHODS", [])
    report = module.verify_contexts(context_dir, expected_methods=expected_methods)
    result["report"] = report
    result["valid"] = not report.get("failures")
    result["expected_methods"] = expected_methods
    result["methods"] = [
        {"method": row.get("method"), "n_rows": row.get("n_rows")}
        for row in report.get("reports", [])
    ]
    result["problems"] = report.get("failures", [])
    return result


def check_run_configs(sqe_root, evo_root):
    config_dir = sqe_root / "pass1_evoagentbench_configs"
    paths = {
        "codex_agent": config_dir / "codex_agent.yaml",
        "dense_config": config_dir / "config_dense_codex.yaml",
        "selective_config": config_dir / "config_selective_codex.yaml",
        "always_expand_config": config_dir / "config_always_expand_codex.yaml",
        "random_gated_config": config_dir / "config_random_gated_codex.yaml",
        "dense_domain": config_dir / "software_engineering_dense.yaml",
        "selective_domain": config_dir / "software_engineering_selective.yaml",
        "always_expand_domain": config_dir / "software_engineering_always_expand.yaml",
        "random_gated_domain": config_dir / "software_engineering_random_gated.yaml",
        "runbook": config_dir / "RUNBOOK.md",
        "codex_adapter": evo_root / "src" / "agents" / "codex" / "codex.py",
        "codex_adapter_init": evo_root / "src" / "agents" / "codex" / "__init__.py",
        "codex_adapter_example": evo_root / "src" / "agents" / "codex" / "codex.yaml.example",
    }
    command = shutil.which("codex")
    missing = [name for name, path in paths.items() if not path.exists()]
    if command is None:
        missing.append("codex_cli")
    return {
        "config_dir": str(config_dir),
        "files": {name: str(path) for name, path in paths.items()},
        "missing": missing,
        "codex_cli": command,
        "valid": not missing,
    }


def main(args):
    evo_root = Path(args.evo_root).resolve()
    sqe_root = Path(args.sqe_root).resolve()
    python_path = Path(args.python).expanduser()

    py = check_python_imports(
        python_path,
        ["docker", "swebench", "yaml", "pandas"],
    )
    docker = check_docker_access()
    alternate_runtimes = check_alternate_container_runtimes()
    data = check_evoagentbench_data(evo_root)
    contexts = check_context_packets(sqe_root)
    run_configs = check_run_configs(sqe_root, evo_root)

    blockers = []
    if not py["ok"]:
        blockers.append(f"missing Python modules: {py.get('missing', [])}")
    if not docker["can_run_docker_ps"]:
        blockers.append("current user cannot access Docker daemon")
    if not data["parquet_exists"]:
        blockers.append("missing EvoAgentBench SWE-bench parquet file")
    if not data["split_file_exists"]:
        blockers.append("missing EvoAgentBench SWE-bench split file")
    if not contexts["valid"]:
        blockers.append("retrieval context packets are missing or invalid")
    if not run_configs["valid"]:
        blockers.append(f"missing run config or Codex adapter files: {run_configs['missing']}")

    report = {
        "artifact_type": "pass1_harness_preflight",
        "is_pass1_result": False,
        "checked_at_utc": dt.datetime.now(dt.timezone.utc)
        .replace(microsecond=0)
        .isoformat(),
        "host": socket.gethostname(),
        "evo_root": str(evo_root),
        "sqe_root": str(sqe_root),
        "python_imports": py,
        "docker": docker,
        "alternate_container_runtimes": alternate_runtimes,
        "evoagentbench_data": data,
        "context_packets": contexts,
        "run_configs": run_configs,
        "ready_to_run_pass1": not blockers,
        "blockers": blockers,
        "note": (
            "Preflight only. A pass here does not create task-success evidence; "
            "it only indicates that real EvoAgentBench runs can be attempted."
        ),
    }

    text = json.dumps(report, indent=2, sort_keys=True) + "\n"
    if args.output:
        output = Path(args.output)
        output.parent.mkdir(parents=True, exist_ok=True)
        output.write_text(text)
    print(text, end="")
    return 0


if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("--sqe_root", default=str(DEFAULT_SQE_ROOT))
    parser.add_argument("--evo_root", default=str(DEFAULT_EVO_ROOT))
    parser.add_argument(
        "--python",
        default="/home/nlp-07/evermemos/EverOS/methods/evermemos/.venv/bin/python",
    )
    parser.add_argument("--output", default="")
    raise SystemExit(main(parser.parse_args()))
