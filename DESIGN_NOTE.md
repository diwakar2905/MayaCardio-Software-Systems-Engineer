# MayaCardio design note — Never Lose a Heartbeat
**Status:** implementation baseline; all performance and power-cut claims require target measurements.

## Architecture
The device collector reads newline-delimited JSON from the supplied mock, validates the CRC-32 against the exact bytes of the `data` array, and stores accepted samples in SQLite. The local database uses WAL mode, `synchronous=FULL`, and a composite primary key `(session_id, sensor, index)` to make repeat delivery idempotent. Explicit loss ranges are stored rather than filled with invented values. A FastAPI cloud service stores samples and losses using the same identity key. The device marks rows synced only after a successful cloud response; retries are safe because cloud inserts are idempotent. Processing logic is shared between device and cloud.

## Intended guarantees
- Duplicate sample keys are not inserted twice.
- CRC-invalid data is rejected.
- Mock-reported loss ranges and detected index gaps are recorded.
- Samples are persisted locally before cloud upload.
- Cloud upload can be retried after a lost acknowledgement.
- No interpolation is performed.

## Not yet proven
The provided mock download field is blank in the supplied assessment, so the integration tests and ground-truth comparison cannot yet be performed. Zero loss across arbitrary power cuts cannot be asserted without testing the storage hardware and OS. Buffer safety, mode switching, cloud latency, 2-hour catch-up, disk-full handling, and result parity must be measured on ARM64.

## Required measured values
ARM64 environment: **fill after test**  
Average CPU over one hour: **fill after test**  
Peak memory: **fill after test**  
Disk bytes written: **fill after test**  
Network bytes sent: **fill after test**  
Maximum observed power-cut loss: **fill after test**  
Declared power-cut loss bound: **fill only after measurement**
