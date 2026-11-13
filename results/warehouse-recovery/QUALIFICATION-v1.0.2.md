# Warehouse cart recovery v1.0.2

The [v1.0.1 practice missions](../../tasks/warehouse-recovery-v1.0.1/environment/workspace/practice.py)
used the same type of aisle obstruction and nearly the same grip-change
coordinates as the scored scenes. A controller could recalibrate at a
chosen location without checking where the motion actually changed.

The [v1.0.2 practice missions](../../tasks/warehouse-recovery-v1.0.2/environment/workspace/practice.py)
separate nominal driving, obstruction handling, and changed grip at a
different dock. Scored scenes now vary both obstruction locations and
the extent of grip changes, with four scenes on uniform flooring. The
issue, sensor API, and docking tolerances are unchanged. The reward
remains the fraction of 16 scenes docked safely and settled.

| Local control | Reward | Docks | Collisions |
| --- | ---: | ---: | ---: |
| Reference using live observations on final approach | 1.0000 | 16/16 | 0 |
| Unchanged v1.0.1 reference with one fixed recalibration window | 0.7500 | 12/16 | 0 |
| Reroute with original drive estimate | 0.4375 | 7/16 | 1 |
| Fixed east route with recalibration | 0.2500 | 4/16 | 0 |
| No-op | 0 | 0/16 | 0 |

The unchanged reference failed on at least one scene in each of the three
grip-change locations. Its misses were recorded as incorrect final state
after a valid route. The updated reference uses repeated marker readings
and gyro feedback instead of picking a grip-change point. It also passed
all three practice missions. See the
[per-scene diagnostics](local-v1.0.2).

The [Harbor controls](harbor-controls-v1.0.2/warehouse-recovery-v1.0.2-oracle-nop/result.json)
returned oracle 1.0 and no-op 0.0 on the same task checksum in 58
seconds, with no exceptions. The [freeze manifest](frozen-v1.0.2.json)
records the agent-visible files separately from the verifier and oracle.
The v1.0.1 files still match their original manifest. Neither version has
had a fresh model trial.
