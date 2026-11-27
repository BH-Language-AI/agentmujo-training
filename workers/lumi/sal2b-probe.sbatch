#!/bin/bash
#SBATCH --job-name=sal2b-probe
#SBATCH --account=project_465003647
#SBATCH --partition=dev-g
#SBATCH --nodes=1
#SBATCH --ntasks=1
#SBATCH --cpus-per-task=7
#SBATCH --gpus-per-task=1
#SBATCH --time=00:30:00
#SBATCH --output=amj-sal2b-probe-%j.out
# SAL2B proba generisanja: base Salamandra-2B + LoRA adapter, 10 promptova.
# Upotreba: sbatch sal2b-probe.sbatch <adapter-dir> <out.json>
set -euo pipefail
ADAPTER="${1:?upotreba: sbatch sal2b-probe.sbatch <adapter-dir> <out.json>}"
OUT="${2:?upotreba: sbatch sal2b-probe.sbatch <adapter-dir> <out.json>}"
module purge
module load Local-LAIF lumi-aif-singularity-bindings
export SIF=/appl/local/laifs/containers/lumi-multitorch-latest.sif
export PYLIBS=/scratch/project_465003647/agentmujo/pylibs
export SINGULARITYENV_HF_HUB_CACHE=/scratch/project_465003647/agentmujo/hfcache
export SINGULARITYENV_PYTHONPATH="$PYLIBS:/repo/src"
REPO=/scratch/project_465003647/agentmujo/repo
cd "$REPO" && git pull -q 2>/dev/null || echo "WARN: git pull nije uspio"
srun --unbuffered singularity exec -B "$REPO:/repo" -B /scratch:/scratch "$SIF" \
  python -u /repo/workers/lumi/probe_sal2b.py "$ADAPTER" "$OUT"
echo PROBE_DONE
