"""
Capture the compute environment used for the SQE paper package.

The output is descriptive metadata only. It does not estimate runtimes or
resource usage that were not logged during the original experiment runs.
"""

import argparse
import json
import subprocess
from datetime import datetime, timezone
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]


def run(command):
    completed = subprocess.run(
        command,
        check=False,
        text=True,
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
    )
    return {
        "command": command,
        "returncode": completed.returncode,
        "stdout": completed.stdout.strip(),
        "stderr": completed.stderr.strip(),
    }


def parse_lscpu(output):
    values = {}
    for line in output.splitlines():
        if ":" not in line:
            continue
        key, value = line.split(":", 1)
        values[key.strip()] = value.strip()
    return {
        "architecture": values.get("Architecture"),
        "cpu_model": values.get("Model name"),
        "cpu_threads": int(values["CPU(s)"]) if values.get("CPU(s)", "").isdigit() else None,
        "threads_per_core": values.get("Thread(s) per core"),
        "cores_per_socket": values.get("Core(s) per socket"),
        "sockets": values.get("Socket(s)"),
        "numa_nodes": values.get("NUMA node(s)"),
    }


def parse_free(output):
    for line in output.splitlines():
        fields = line.split()
        if fields and fields[0] == "Mem:":
            return {
                "total": fields[1],
                "used": fields[2],
                "free": fields[3],
                "available": fields[-1],
            }
    return {}


def parse_gpus(output):
    gpus = []
    for line in output.splitlines():
        parts = [part.strip() for part in line.split(",")]
        if len(parts) == 3:
            gpus.append(
                {
                    "name": parts[0],
                    "memory_total": parts[1],
                    "driver_version": parts[2],
                }
            )
    return gpus


def main(args):
    root = Path(args.root).resolve()
    output = root / args.output

    lscpu_result = run(["lscpu"])
    free_result = run(["free", "-h"])
    gpu_result = run(
        [
            "nvidia-smi",
            "--query-gpu=name,memory.total,driver_version",
            "--format=csv,noheader",
        ]
    )
    uname_result = run(["uname", "-a"])
    python_result = run(["python3", "--version"])

    report = {
        "artifact_type": "compute_environment_metadata",
        "checked_at_utc": datetime.now(timezone.utc).isoformat(timespec="seconds"),
        "is_experiment_metric": False,
        "runtime_measurements_available": False,
        "runtime_note": (
            "The original retrieval runs did not record wall-clock runtime per "
            "method. This file reports observed hardware and software metadata only."
        ),
        "os": uname_result["stdout"],
        "python3": python_result["stdout"] or python_result["stderr"],
        "cpu": parse_lscpu(lscpu_result["stdout"]) if lscpu_result["returncode"] == 0 else {},
        "memory": parse_free(free_result["stdout"]) if free_result["returncode"] == 0 else {},
        "gpus": parse_gpus(gpu_result["stdout"]) if gpu_result["returncode"] == 0 else [],
        "raw_commands": {
            "lscpu": lscpu_result,
            "free": free_result,
            "nvidia_smi": gpu_result,
            "uname": uname_result,
            "python3": python_result,
        },
    }
    output.write_text(json.dumps(report, indent=2) + "\n")
    print(json.dumps(report, indent=2))
    return 0


if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("--root", default=str(ROOT))
    parser.add_argument("--output", default="COMPUTE_ENVIRONMENT.json")
    raise SystemExit(main(parser.parse_args()))
