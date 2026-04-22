#!/bin/sh
# SMART health + five key attributes per block device. One line per
# device, constant schema:
#     smart sda: HEALTH=PASSED TEMP=34 REALLOC=0 PENDING=0 OFFLINE_UNC=0
# Grep for HEALTH!=PASSED, PENDING>0, REALLOC>0 to catch dying drives
# before MinIO's 30s-stall self-quarantine kicks in.
exec timeout -s KILL 120s /bin/sh -c '
for dev in /dev/sd? /dev/nvme?n?; do
    [ -b "$dev" ] || continue
    name=$(basename "$dev")
    smartctl -H -A "$dev" 2>&1 | awk -v d="$name" "
        /SMART overall-health/ { health=\$NF }
        /Temperature_Celsius/  { temp=\$10 }
        /Composite Temperature/ { temp=\$3 }
        /Reallocated_Sector_Ct/ { realloc=\$10 }
        /Current_Pending_Sector/ { pending=\$10 }
        /Offline_Uncorrectable/ { offline=\$10 }
        END {
            printf \"%s: HEALTH=%s TEMP=%s REALLOC=%s PENDING=%s OFFLINE_UNC=%s\n\",
                d,
                (health ? health : \"?\"),
                (temp ? temp : \"?\"),
                (realloc ? realloc : \"?\"),
                (pending ? pending : \"?\"),
                (offline ? offline : \"?\")
        }
    "
done
' | add_prefix 'smart '
