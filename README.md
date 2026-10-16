# MayaCardio assessment implementation baseline

**Important:** this is a starter implementation, not a verified passing submission. The supplied assessment has a blank `biosignal-mock` download field. Full acceptance requires that executable, `check_ground_truth`, a real ARM64 environment, a free cloud deployment, and fault-injection tests.

## Structure
- `pipeline/`: TCP mock client, CRC validation, SQLite store, offline processing, sync engine, CLI.
- `cloud/`: FastAPI ingestion, idempotent SQLite storage, export and results endpoints.
- `tests/`: focused unit tests.

## Windows development
```powershell
py -3.11 -m venv .venv
.\.venv\Scripts\Activate.ps1
python -m pip install -e ".[dev]"
pytest
```
Run mock in another terminal (once the real binary is obtained):
```powershell
biosignal-mock --mode ramp --seed 7 --duration 3600 --port 7100
```
Start cloud API:
```powershell
$env:CLOUD_DB="./data/cloud.db"
uvicorn cloud.app:app --host 127.0.0.1 --port 8000
```
Start device pipeline in another terminal:
```powershell
$env:CLOUD_URL="http://127.0.0.1:8000"
$env:PIPELINE_DB="./data/pipeline.db"
pipeline run
```
Commands: `pipeline status`, `pipeline export --session ID --from device`, `pipeline export --session ID --from cloud`, `pipeline results --session ID`.

## Linux/ARM64
```bash
sudo apt-get update && sudo apt-get install -y python3 python3-venv python3-pip
python3 -m venv .venv && . .venv/bin/activate
python -m pip install -e ".[dev]"
pytest
```
Run the mock on the same board. Configure `MOCK_HOST=127.0.0.1`, `MOCK_PORT=7100`, `PIPELINE_DB=/var/lib/mayacardio/pipeline.db`, and `CLOUD_URL=https://YOUR-CLOUD-HOST`.

## Cloud deployment
Deploy `cloud.app:app` to a free Python hosting tier, start with:
`uvicorn cloud.app:app --host 0.0.0.0 --port ${PORT:-8000}`
Use a persistent writable database path. An ephemeral filesystem does not satisfy long-lived cloud-copy requirements. Confirm current free-tier limits before choosing a provider.

## Required validation before submission
1. `pytest` and save output.
2. Run `--mode ramp` and compare device export to `check_ground_truth`.
3. Inject duplicate replies, bad CRC, sensor stalls, mock restart, network loss/return, process kill, reboot/power cut, disk-full, and system-clock change.
4. Demonstrate mode switch in 10s, online result latency <=5s, cloud catch-up <=15 min after a 2-hour outage.
5. Measure CPU average, peak memory, disk bytes written, network bytes over one hour on ARM64.
6. Record a <=5-minute demo showing network cut, process kill, and power cut.

## Known limitations that must be addressed
This baseline has not been integration-tested against the actual mock. In particular, simultaneous sensor polling is sequential, so verify it stays within the mock's 10-second buffer. Session restart loss accounting is conservative but needs validation against ground truth. The status mode currently reports configured cloud presence rather than the last observed live connectivity. Cloud processing now stores results after ingestion when both sensors have completed a window, but the <=5-second target still needs measurement on the deployed setup. Heart-rate peak detection and all edge cases must be compared with the provided reference implementation. Abrupt power-cut loss bound and resource figures must be measured, never guessed. Do not claim the assessment passes until these are fixed and tested.
