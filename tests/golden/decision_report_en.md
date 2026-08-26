# Selection run — warehouse_a_v2

## Provenance

| | |
| --- | --- |
| Run id | run_golden |
| Deployment | warehouse_a_v2 |
| Experiment scope | global_planner_selection |
| Contracts version | 6.9.0 |
| Code version | abc1234 |
| Anchor config | v1.2 |
| Run | 2026-08-21T14:30:00+00:00 |

## Sample

| | |
| --- | --- |
| Episodes measured | 30 |
| Minimum required (HĐ-7.1) | 6 |

## Gates

Six feasibility gates run before anything is scored (HĐ-7). A candidate that
failed one was never ranked, which is a result rather than an error.

| Candidate | Config | Shown | Distinct episodes | Success | p99 latency | Replans | Verdict |
| --- | --- | --- | --- | --- | --- | --- | --- |
| astar+dwa | dwa_coarse | lidar_only | 30 | 100.0% | 7.35 ms | 30 | passed |
| rrtstar+dwa | dwa_balanced | lidar_only | 30 | 96.7% | 16.1 ms | 44 | passed |

## Outcome by candidate

`Eligible to recommend` is stated rather than left to be read off the gate
column: a gate failure can leave no mark on the utility at all — collisions are
excluded from `U_S` by contract (HĐ-6), so that they cannot be traded against
speed — and the mark alone therefore does not compare across that line.

| Candidate | Config | Utility /100 | U_R | U_S | U_E | U_C | Success | Collisions | Collision bound 95% | No route found | Worst clearance | Median episode | p99 latency | Memory estimate | Distinct episodes | Replans | Eligible to recommend |
| --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- |
| astar+dwa | dwa_coarse | 86.9 | 1 | 0.912 | 0.568 | 0.958 | 100.0% | 0 | 10.0% | 0.0% | 0.494 m | 22.8 s | 7.35 ms | 412 MB | 30 | 30 | yes |
| rrtstar+dwa | dwa_balanced | 64.1 | 0.34 | 0.771 | 0.612 | 0.883 | 96.7% | 0 | 10.0% | 0.0% | 0.331 m | 25.4 s | 16.1 ms | 688 MB | 30 | 44 | yes |

## Decision Card

| | |
| --- | --- |
| Recommended | astar+dwa |
| Recommended config | dwa_coarse |
| Candidate id | c1 |
| Alternative | rrtstar+dwa |
| Status | CLEAR_RECOMMENDATION |
| Contracts version | 6.9.0 |

> **Scope:** this recommendation applies to `warehouse_a_v2` and to nothing else
> (HĐ-1.4). Carrying it to another deployment is a claim this run did not make.

| The margin | |
| --- | --- |
| Decision utility | 0.869 |
| Pareto label | DOMINANT |
| Decision mode | technical |
| ΔU vs the runner-up | 0.227 |
| ΔU mean | 0.227 |
| ΔU 95% interval | [0.181, 0.274] |
| Effect size | 0.74 |
| Episodes compared | 30 |
| Objective U_R | 1 |
| Objective U_S | 0.912 |
| Objective U_E | 0.568 |
| Objective U_C | 0.958 |

> ΔU is printed with its interval and never without it. A margin whose interval
> includes zero is consistent with the two candidates being equal.

| Sensitivity | |
| --- | --- |
| Weight stability margin | 1 |
| Anchor stability | unchanged |
| Robustness margin | not measured |

## Episodes

| Candidate | Episode | Outcome | Collisions | Min clearance | Travel time | p99 latency | Replans | Episode utility |
| --- | --- | --- | --- | --- | --- | --- | --- | --- |
| astar+dwa / dwa_coarse | c100 | passed | 0 | 0.494 m | 22.8 s | 7.35 ms | 1 | 0.88 |
| astar+dwa / dwa_coarse | c101 | timeout | 0 | 0.113 m | 60 s | 14.7 ms | 17 | 0.31 |
| rrtstar+dwa / dwa_balanced | c200 | passed | 0 | 0.331 m | 22.8 s | 16.1 ms | 1 | 0.88 |
| rrtstar+dwa / dwa_balanced | c201 | timeout | 0 | 0.113 m | 60 s | 32.2 ms | 17 | 0.31 |

## Human record

| | |
| --- | --- |
| Review state | reviewed |
| Reviewed by | an |
| Reviewed at | 2026-08-21T16:00:00+00:00 |
| Configuration decision | pending |
| Decided by | not measured |
| Decided at | not measured |

Reading the evidence and approving the configuration are separate acts (HĐ-14).
A run that was read and never approved is an ordinary state, not an omission.
