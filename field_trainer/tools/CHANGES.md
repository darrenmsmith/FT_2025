
## 2026-05-17 — Dev cone fleet rollout COMPLETE
### Final boot times (after Bucket B + Plan A)
| Cone | Boot | bat0 IP | Notes |
|---|---|---|---|
| D1 | 70.0s | .101 | Original test cone, consistently slowest |
| D2 | 60.3s | .102 | |
| D3 | 59.1s | .103 | |
| D4 | 58.0s | .104 | Fastest |
| D5 | 59.0s | .105 | |

### Fleet stats
- Field deployment time bound: 70s (D1) — down from ~96–110s
- Average non-D1: ~59s
- D1 vs others: ~10s slower, same recipe — likely SD card variation

### Recipe (definitive, validated 5x)
- tools/cone_optimize.sh applies all changes idempotently
- Disables: cloud-init, ModemManager, keyboard-setup, rpi-eeprom-update, apt-daily timers
- Masks: apt-daily services, NetworkManager stack (3 units)
- Does NOT touch: wlan1-internet.service (load-bearing for unknown reasons), batman-mesh.service (architecturally correct)

### Remaining boot time on cones (mostly kernel/driver bound)
1. batman-mesh.service ~18-20s (waiting on brcmfmac driver load)
2. dev-mmcblk0p2.device ~15-18s (SD card detection)
3. systemd-rfkill.service ~10-13s (waiting on rfkill device from brcmfmac)
- Further userspace optimization unlikely to help significantly
