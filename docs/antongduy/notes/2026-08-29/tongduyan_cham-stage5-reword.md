# Cham tay, mu arm - gom theo episode (rubric r0.1.0)

43 muc | 17 episode | nguon: `stage5-reword`

Moi episode: doc khoi **PACKET** mot lan, roi cham moi muc duoi no.

- **R1** hypothesis dung vung truoc packet khong - `holds` / `plausible_other` / `wrong`
- **R2** `subject` co dung thanh phan cau noi toi khong - `yes` / `no`
- **R3** moi ref mo duoc trong packet **va** noi ve dung mechanism - `all` / `some` / `none`
- **R5** cho khong de xuat gi: im lang co dung cho khong - `correct` / `should_have`

Khong muc nao noi arm nao viet no, cung khong noi no thuoc luot chay nao.
Dung doan.

---

# Episode `1d18a81ba501`

*cluster: doorway_v1_full_stack_selection_c23dddbd | vai: cardless*

<details open><summary><b>PACKET</b></summary>

**Phan quyet**: outcome_only | thang: `C1` | thua: `C5`

**Khac biet giua hai ben**

| ref | strength | noi gi | so kem theo |
|---|---|---|---|
| `contrast:component_differs:3` | **context** | the two stacks differ in local_controller, local_controller_config; a mechanism that explains the difference has to live in one of those | - |
| `contrast:detection_only_on_loser:1` | **support** | replan_storm fired on C5 and not on C1 | replans = 3 |
| `contrast:detection_only_on_loser:2` | **support** | stuck_cluster fired on C5 and not on C1 | stopped seconds = 51.55; stops = 6 |
| `contrast:divergence_precedes_outcome:4` | **context** | the two runs parted at 2.3 m along the route | - |
| `contrast:outcome_differs:5` | **context** | C1 ended this episode ahead of C5 on reached the goal, worst clearance, travel time | min clearance loser = 0.279438; min clearance winner = 0.396683; success loser = 0; success winner = 1; travel time s loser = 60; travel time s winner = 17.65 |

**Detector da ban**

| ref | tren ai | so kem theo |
|---|---|---|
| `obs:replan_storm:C5@1d18a81ba501` | `C5` | replans = 3; window.end_m = 3.09832; window.end_s = 46.85; window.start_m = 3.08195; window.start_s = 36.85 |
| `obs:stuck_cluster:C5@1d18a81ba501` | `C5` | stopped_seconds = 51.55; stops = 6; window.end_m = 3.09832; window.end_s = 60; window.start_m = 2.47992; window.start_s = 4.9 |

**So do duoc cua tung ben**

- `C1`: collision_count = 0 | min_clearance = 0.396683 | p99_latency_ms = 0 | replan_count = 0 | success = 1 | travel_time_s = 17.65
- `C5`: collision_count = 0 | min_clearance = 0.279438 | p99_latency_ms = 12.6268 | replan_count = 9 | success = 0 | travel_time_s = 60

**Khong biet duoc tu episode nay**

- no planning-input sidecar was recorded for this episode
- this episode records no measured passage width or no inflated footprint, so no passage can be compared against one

**Thanh phan moi ben**

- `C1`: global planner = `C2` | local controller = `C3` | local controller config = `C4`
- `C5`: global planner = `C2` | local controller = `C6` | local controller config = `C7`

> One episode. There is no confidence interval on a single sample, and this is not the run's verdict: the decision card ranks candidates over every episode that was run.

</details>

### 001

> local_controller experienced local minimum entrapment on C5, which did not occur on C1

- register: `diagnosis` | subject: `local_controller` | type: `local_minimum_entrapment`
- refs: `contrast:detection_only_on_loser:2`
- contract: `contrast_support`, `subject_match`, `polarity_match`

| R1 | R2 | R3 | R5 |
|---|---|---|---|
|  |  |  | n/a |

### 002

> the local_controller encountered a local minimum, as indicated by the stuck_cluster detector firing only on C5 in this episode, causing the losing run to stop moving

- register: `diagnosis` | subject: `local_controller` | type: `local_minimum_entrapment`
- refs: `contrast:detection_only_on_loser:2`
- contract: `contrast_support`, `subject_match`, `polarity_match`

| R1 | R2 | R3 | R5 |
|---|---|---|---|
|  |  |  | n/a |

---

# Episode `31a398df5569`

*cluster: sudden_stop_v6_full_stack_selection_06f40334 | vai: safety_critical*

<details open><summary><b>PACKET</b></summary>

**Phan quyet**: episode_decision_utility | thang: `C1` | thua: `C5`

**Khac biet giua hai ben**

| ref | strength | noi gi | so kem theo |
|---|---|---|---|
| `contrast:component_differs:1` | **context** | the two stacks differ in global_planner, local_controller, local_controller_config; a mechanism that explains the difference has to live in one of those | - |
| `contrast:divergence_precedes_outcome:2` | **context** | the two runs parted at 3.6 m along the route | - |

**Detector da ban**

| ref | tren ai | so kem theo |
|---|---|---|
| `obs:stuck_cluster:C1@31a398df5569` | `C1` | stopped_seconds = 5.75; stops = 1; window.end_m = 4.18302; window.end_s = 12.65; window.start_m = 4.17366; window.start_s = 6.9 |

**So do duoc cua tung ben**

- `C1`: collision_count = 0 | min_clearance = 0.475725 | p99_latency_ms = 7.33982 | replan_count = 1 | success = 1 | travel_time_s = 24.15
- `C5`: collision_count = 0 | min_clearance = 0.734835 | p99_latency_ms = 0 | replan_count = 0 | success = 1 | travel_time_s = 22.9

**Khong biet duoc tu episode nay**

- no planning-input sidecar was recorded for this episode
- this episode records no measured passage width or no inflated footprint, so no passage can be compared against one

**Thanh phan moi ben**

- `C1`: global planner = `C2` | local controller = `C3` | local controller config = `C4`
- `C5`: global planner = `C6` | local controller = `C7` | local controller config = `C8`

> One episode. There is no confidence interval on a single sample, and this is not the run's verdict: the decision card ranks candidates over every episode that was run.

</details>

### 003 - **khong de xuat gi**

> every proposal was refused before submission (quantity_in_statement); an abstention with a reason beats a claim the platform would refuse

| R1 | R2 | R3 | R5 |
|---|---|---|---|
| n/a | n/a | n/a |  |

### 004

> local_controller on C1 triggered a stuck_cluster detector in this episode

- register: `diagnosis` | subject: `local_controller` | type: `local_minimum_entrapment`
- refs: `obs:stuck_cluster:C1@31a398df5569`

| R1 | R2 | R3 | R5 |
|---|---|---|---|
|  |  |  | n/a |

---

# Episode `3e3973656a9d`

*cluster: doorway_v1_full_stack_selection_c23dddbd | vai: cardless*

<details open><summary><b>PACKET</b></summary>

**Phan quyet**: outcome_margin | thang: `C1` | thua: `C5`

**Khac biet giua hai ben**

| ref | strength | noi gi | so kem theo |
|---|---|---|---|
| `contrast:component_differs:2` | **context** | the two stacks differ in local_controller, local_controller_config; a mechanism that explains the difference has to live in one of those | - |
| `contrast:detection_only_on_loser:1` | **support** | stuck_cluster fired on C5 and not on C1 | stopped seconds = 4.8; stops = 1 |
| `contrast:divergence_precedes_outcome:3` | **context** | the two runs parted at 3.0 m along the route, where replan fired on one side | - |
| `contrast:outcome_differs:4` | **context** | C1 ended this episode ahead of C5 on worst clearance, travel time | min clearance loser = 0.296756; min clearance winner = 0.406214; travel time s loser = 24.7; travel time s winner = 17.05 |

**Detector da ban**

| ref | tren ai | so kem theo |
|---|---|---|
| `obs:stuck_cluster:C5@3e3973656a9d` | `C5` | stopped_seconds = 4.8; stops = 1; window.end_m = 2.63605; window.end_s = 9.85; window.start_m = 2.6125; window.start_s = 5.05 |

**So do duoc cua tung ben**

- `C1`: collision_count = 0 | min_clearance = 0.406214 | p99_latency_ms = 0 | replan_count = 0 | success = 1 | travel_time_s = 17.05
- `C5`: collision_count = 0 | min_clearance = 0.296756 | p99_latency_ms = 12.8349 | replan_count = 1 | success = 1 | travel_time_s = 24.7

**Khong biet duoc tu episode nay**

- no planning-input sidecar was recorded for this episode
- this episode records no measured passage width or no inflated footprint, so no passage can be compared against one

**Thanh phan moi ben**

- `C1`: global planner = `C2` | local controller = `C3` | local controller config = `C4`
- `C5`: global planner = `C2` | local controller = `C6` | local controller config = `C7`

> One episode. There is no confidence interval on a single sample, and this is not the run's verdict: the decision card ranks candidates over every episode that was run.

</details>

### 005

> The local_controller on C5 became stuck in a cluster requiring a stop and replan, as detected by the stuck_cluster detector

- register: `diagnosis` | subject: `local_controller` | type: `local_minimum_entrapment`
- refs: `obs:stuck_cluster:C5@3e3973656a9d`

| R1 | R2 | R3 | R5 |
|---|---|---|---|
|  |  |  | n/a |

### 006

> The local_controller of C5 triggered a replan during navigation, contributing to its longer travel time

- register: `diagnosis` | subject: `local_controller` | type: `replan_instability`
- refs: `diag:C5.replan_count`, `diag:C5.travel_time_s`

| R1 | R2 | R3 | R5 |
|---|---|---|---|
|  |  |  | n/a |

### 007

> The local_controller on C5 underwent a local minimum entrapment, causing a stop and replan that increased travel time relative to C1

- register: `diagnosis` | subject: `local_controller` | type: `local_minimum_entrapment`
- refs: `contrast:detection_only_on_loser:1`
- contract: `contrast_support`, `subject_match`, `polarity_match`

| R1 | R2 | R3 | R5 |
|---|---|---|---|
|  |  |  | n/a |

---

# Episode `3f3271808c9d`

*cluster: doorway_v1_full_stack_selection_c23dddbd | vai: cardless*

<details open><summary><b>PACKET</b></summary>

**Phan quyet**: outcome_margin | thang: `C1` | thua: `C5`

**Khac biet giua hai ben**

| ref | strength | noi gi | so kem theo |
|---|---|---|---|
| `contrast:component_differs:2` | **context** | the two stacks differ in local_controller, local_controller_config; a mechanism that explains the difference has to live in one of those | - |
| `contrast:detection_only_on_loser:1` | **support** | stuck_cluster fired on C5 and not on C1 | stopped seconds = 4.9; stops = 1 |
| `contrast:divergence_precedes_outcome:3` | **context** | the two runs parted at 2.3 m along the route, where replan fired on one side | - |
| `contrast:outcome_differs:4` | **context** | C1 ended this episode ahead of C5 on worst clearance, travel time | min clearance loser = 0.368427; min clearance winner = 0.402013; travel time s loser = 21.6; travel time s winner = 16.2 |

**Detector da ban**

| ref | tren ai | so kem theo |
|---|---|---|
| `obs:stuck_cluster:C5@3f3271808c9d` | `C5` | stopped_seconds = 4.9; stops = 1; window.end_m = 2.42893; window.end_s = 9.5; window.start_m = 2.39811; window.start_s = 4.6 |

**So do duoc cua tung ben**

- `C1`: collision_count = 0 | min_clearance = 0.402013 | p99_latency_ms = 0 | replan_count = 0 | success = 1 | travel_time_s = 16.2
- `C5`: collision_count = 0 | min_clearance = 0.368427 | p99_latency_ms = 13.7426 | replan_count = 1 | success = 1 | travel_time_s = 21.6

**Khong biet duoc tu episode nay**

- no planning-input sidecar was recorded for this episode
- this episode records no measured passage width or no inflated footprint, so no passage can be compared against one

**Thanh phan moi ben**

- `C1`: global planner = `C2` | local controller = `C3` | local controller config = `C4`
- `C5`: global planner = `C2` | local controller = `C6` | local controller config = `C7`

> One episode. There is no confidence interval on a single sample, and this is not the run's verdict: the decision card ranks candidates over every episode that was run.

</details>

### 008

> local_controller experienced local minimum entrapment on C5, as indicated by stuck_cluster detection, causing C5 to stop and lose time compared to C1

- register: `contrast` | subject: `local_controller` | type: `local_minimum_entrapment`
- refs: `contrast:detection_only_on_loser:1`, `obs:stuck_cluster:C5@3f3271808c9d`, `contrast:outcome_differs:4/travel_time_s_loser`
- contract: `contrast_support`, `occurrence_evidence`, `subject_match`, `polarity_match`

| R1 | R2 | R3 | R5 |
|---|---|---|---|
|  |  |  | n/a |

### 009

> A local minimum entrapment occurred in local_controller on C5, as indicated by the stuck_cluster detector firing once

- register: `diagnosis` | subject: `local_controller` | type: `local_minimum_entrapment`
- refs: `contrast:detection_only_on_loser:1`
- contract: `contrast_support`, `subject_match`, `polarity_match`

| R1 | R2 | R3 | R5 |
|---|---|---|---|
|  |  |  | n/a |

---

# Episode `4ec011c9a0c3`

*cluster: doorway_v1_full_stack_selection_c23dddbd | vai: cardless*

<details open><summary><b>PACKET</b></summary>

**Phan quyet**: outcome_only | thang: `C1` | thua: `C5`

**Khac biet giua hai ben**

| ref | strength | noi gi | so kem theo |
|---|---|---|---|
| `contrast:component_differs:3` | **context** | the two stacks differ in local_controller, local_controller_config; a mechanism that explains the difference has to live in one of those | - |
| `contrast:detection_only_on_loser:1` | **support** | replan_storm fired on C5 and not on C1 | replans = 3 |
| `contrast:detection_only_on_loser:2` | **support** | stuck_cluster fired on C5 and not on C1 | stopped seconds = 53.2; stops = 3 |
| `contrast:divergence_precedes_outcome:4` | **context** | the two runs parted at 2.9 m along the route, where replan fired on one side | - |
| `contrast:outcome_differs:5` | **context** | C1 ended this episode ahead of C5 on reached the goal, travel time | success loser = 0; success winner = 1; travel time s loser = 60; travel time s winner = 16.3 |

**Detector da ban**

| ref | tren ai | so kem theo |
|---|---|---|
| `obs:replan_storm:C5@4ec011c9a0c3#1` | `C5` | replans = 3; window.end_m = 2.85251; window.end_s = 41.9; window.start_m = 2.85251; window.start_s = 31.9 |
| `obs:replan_storm:C5@4ec011c9a0c3#2` | `C5` | replans = 3; window.end_m = 2.85251; window.end_s = 56.9; window.start_m = 2.85251; window.start_s = 46.9 |
| `obs:stuck_cluster:C5@4ec011c9a0c3` | `C5` | stopped_seconds = 53.2; stops = 3; window.end_m = 2.86647; window.end_s = 60; window.start_m = 2.58354; window.start_s = 4.95 |

**So do duoc cua tung ben**

- `C1`: collision_count = 0 | min_clearance = 0.387222 | p99_latency_ms = 0 | replan_count = 0 | success = 1 | travel_time_s = 16.3
- `C5`: collision_count = 0 | min_clearance = 0.418809 | p99_latency_ms = 13.0767 | replan_count = 9 | success = 0 | travel_time_s = 60

**Khong biet duoc tu episode nay**

- no planning-input sidecar was recorded for this episode
- this episode records no measured passage width or no inflated footprint, so no passage can be compared against one

**Thanh phan moi ben**

- `C1`: global planner = `C2` | local controller = `C3` | local controller config = `C4`
- `C5`: global planner = `C2` | local controller = `C6` | local controller config = `C7`

> One episode. There is no confidence interval on a single sample, and this is not the run's verdict: the decision card ranks candidates over every episode that was run.

</details>

### 010 - **khong de xuat gi**

> every proposal was refused before submission (wording_above_associated); an abstention with a reason beats a claim the platform would refuse

| R1 | R2 | R3 | R5 |
|---|---|---|---|
| n/a | n/a | n/a |  |

### 011

> local_controller on C5 experienced local_minimum_entrapment while local_controller on C1 did not

- register: `diagnosis` | subject: `local_controller` | type: `local_minimum_entrapment`
- refs: `contrast:detection_only_on_loser:2`
- contract: `contrast_support`, `subject_match`, `polarity_match`

| R1 | R2 | R3 | R5 |
|---|---|---|---|
|  |  |  | n/a |

### 012

> global_planner on C5 experienced replan_instability while global_planner on C1 did not

- register: `diagnosis` | subject: `global_planner` | type: `replan_instability`
- refs: `contrast:detection_only_on_loser:1`
- contract: `contrast_support`, `subject_match`, `polarity_match`

| R1 | R2 | R3 | R5 |
|---|---|---|---|
|  |  |  | n/a |

---

# Episode `501a98d1fd9a`

*cluster: sudden_stop_custom_v2_full_stack_selection_c23dddbd | vai: strongest_for_runnerup*

<details open><summary><b>PACKET</b></summary>

**Phan quyet**: episode_decision_utility | thang: `C5` | thua: `C1`

**Khac biet giua hai ben**

| ref | strength | noi gi | so kem theo |
|---|---|---|---|
| `contrast:component_differs:1` | **context** | the two stacks differ in local_controller, local_controller_config; a mechanism that explains the difference has to live in one of those | - |
| `contrast:divergence_precedes_outcome:2` | **context** | the two runs parted at 3.0 m along the route | - |
| `contrast:outcome_differs:3` | **context** | C5 ended this episode ahead of C1 on worst clearance | min clearance loser = 0.172218; min clearance winner = 0.250112 |

**Detector da ban**

| ref | tren ai | so kem theo |
|---|---|---|
| `obs:stuck_cluster:C5@501a98d1fd9a` | `C5` | stopped_seconds = 5.9; stops = 1; window.end_m = 3.63672; window.end_s = 12.1; window.start_m = 3.59883; window.start_s = 6.2 |

**So do duoc cua tung ben**

- `C1`: collision_count = 0 | min_clearance = 0.172218 | p99_latency_ms = 0 | replan_count = 0 | success = 1 | travel_time_s = 24.95
- `C5`: collision_count = 0 | min_clearance = 0.250112 | p99_latency_ms = 7.37313 | replan_count = 1 | success = 1 | travel_time_s = 26.15

**Khong biet duoc tu episode nay**

- no planning-input sidecar was recorded for this episode
- this episode records no measured passage width or no inflated footprint, so no passage can be compared against one

**Thanh phan moi ben**

- `C1`: global planner = `C2` | local controller = `C3` | local controller config = `C4`
- `C5`: global planner = `C2` | local controller = `C6` | local controller config = `C7`

> One episode. There is no confidence interval on a single sample, and this is not the run's verdict: the decision card ranks candidates over every episode that was run.

</details>

### 013

> The local_controller_config difference explains why C5 maintained higher min clearance than C1 in this episode

- register: `diagnosis` | subject: `local_controller` | type: `component_specific_attribution`
- refs: `contrast:component_differs:1`, `contrast:outcome_differs:3/min_clearance_loser`, `contrast:outcome_differs:3/min_clearance_winner`
- contract: `subject_match`

| R1 | R2 | R3 | R5 |
|---|---|---|---|
|  |  |  | n/a |

### 014 - **khong de xuat gi**

> every proposal was refused before submission (quantity_in_statement); an abstention with a reason beats a claim the platform would refuse

| R1 | R2 | R3 | R5 |
|---|---|---|---|
| n/a | n/a | n/a |  |

---

# Episode `50f9cae5941c`

*cluster: sudden_stop_custom_v2_full_stack_selection_c23dddbd | vai: safety_critical*

<details open><summary><b>PACKET</b></summary>

**Phan quyet**: episode_decision_utility | thang: `C1` | thua: `C5`

**Khac biet giua hai ben**

| ref | strength | noi gi | so kem theo |
|---|---|---|---|
| `contrast:component_differs:3` | **context** | the two stacks differ in local_controller, local_controller_config; a mechanism that explains the difference has to live in one of those | - |
| `contrast:detection_only_on_loser:1` | **support** | near_miss_cluster fired on C5 and not on C1 | min clearance m = 0.129033; samples = 18 |
| `contrast:detection_only_on_loser:2` | **support** | stuck_cluster fired on C5 and not on C1 | stopped seconds = 5.9; stops = 1 |
| `contrast:divergence_precedes_outcome:4` | **context** | the two runs parted at 3.0 m along the route | - |
| `contrast:outcome_differs:5` | **context** | C1 ended this episode ahead of C5 on worst clearance, travel time | min clearance loser = 0.129033; min clearance winner = 0.184095; travel time s loser = 27.65; travel time s winner = 24.75 |

**Detector da ban**

| ref | tren ai | so kem theo |
|---|---|---|
| `obs:near_miss_cluster:C5@50f9cae5941c` | `C5` | min_clearance_m = 0.129033; samples = 18; window.end_m = 7.46516; window.end_s = 20.7; window.start_m = 7.17333; window.start_s = 19.85 |
| `obs:stuck_cluster:C5@50f9cae5941c` | `C5` | stopped_seconds = 5.9; stops = 1; window.end_m = 3.63704; window.end_s = 12.05; window.start_m = 3.58702; window.start_s = 6.15 |

**So do duoc cua tung ben**

- `C1`: collision_count = 0 | min_clearance = 0.184095 | p99_latency_ms = 0 | replan_count = 0 | success = 1 | travel_time_s = 24.75
- `C5`: collision_count = 0 | min_clearance = 0.129033 | p99_latency_ms = 7.34177 | replan_count = 1 | success = 1 | travel_time_s = 27.65

**Khong biet duoc tu episode nay**

- no planning-input sidecar was recorded for this episode
- this episode records no measured passage width or no inflated footprint, so no passage can be compared against one

**Thanh phan moi ben**

- `C1`: global planner = `C2` | local controller = `C3` | local controller config = `C4`
- `C5`: global planner = `C2` | local controller = `C6` | local controller config = `C7`

> One episode. There is no confidence interval on a single sample, and this is not the run's verdict: the decision card ranks candidates over every episode that was run.

</details>

### 015

> Local_controller on C5 exhibited replan instability in this episode, as indicated by the stuck_cluster detector firing on C5, which contributed to increased travel time.

- register: `diagnosis` | subject: `local_controller` | type: `replan_instability`
- refs: `contrast:detection_only_on_loser:2`, `contrast:outcome_differs:5/travel_time_s_loser`
- contract: `contrast_support`, `subject_match`, `polarity_match`

| R1 | R2 | R3 | R5 |
|---|---|---|---|
|  |  |  | n/a |

### 016

> The local_controller on C5 triggered a clearance refusal event, indicated by a near_miss_cluster, leading to a lower minimum clearance than C1.

- register: `diagnosis` | subject: `local_controller` | type: `clearance_refusal`
- refs: `contrast:detection_only_on_loser:1`
- contract: `contrast_support`, `subject_match`, `polarity_match`

| R1 | R2 | R3 | R5 |
|---|---|---|---|
|  |  |  | n/a |

### 017

> The local_controller on C5 experienced local minimum entrapment, as evidenced by a stuck_cluster, resulting in a delay that increased its travel time relative to C1.

- register: `diagnosis` | subject: `local_controller` | type: `local_minimum_entrapment`
- refs: `contrast:detection_only_on_loser:2`
- contract: `contrast_support`, `subject_match`, `polarity_match`

| R1 | R2 | R3 | R5 |
|---|---|---|---|
|  |  |  | n/a |

---

# Episode `6637b6e1f8e1`

*cluster: doorway_v1_full_stack_selection_c23dddbd | vai: cardless*

<details open><summary><b>PACKET</b></summary>

**Phan quyet**: outcome_only | thang: `C1` | thua: `C5`

**Khac biet giua hai ben**

| ref | strength | noi gi | so kem theo |
|---|---|---|---|
| `contrast:component_differs:3` | **context** | the two stacks differ in local_controller, local_controller_config; a mechanism that explains the difference has to live in one of those | - |
| `contrast:detection_only_on_loser:1` | **support** | replan_storm fired on C5 and not on C1 | replans = 3 |
| `contrast:detection_only_on_loser:2` | **support** | stuck_cluster fired on C5 and not on C1 | stopped seconds = 42.1; stops = 5 |
| `contrast:divergence_precedes_outcome:4` | **context** | the two runs parted at 2.2 m along the route, where replan fired on one side | - |
| `contrast:outcome_differs:5` | **context** | C1 ended this episode ahead of C5 on reached the goal, worst clearance, travel time | min clearance loser = 0.186099; min clearance winner = 0.412451; success loser = 0; success winner = 1; travel time s loser = 60; travel time s winner = 17.6 |

**Detector da ban**

| ref | tren ai | so kem theo |
|---|---|---|
| `obs:replan_storm:C5@6637b6e1f8e1` | `C5` | replans = 3; window.end_m = 2.884; window.end_s = 43.3; window.start_m = 2.83208; window.start_s = 33.3 |
| `obs:stuck_cluster:C5@6637b6e1f8e1` | `C5` | stopped_seconds = 42.1; stops = 5; window.end_m = 2.91367; window.end_s = 48.8; window.start_m = 2.3775; window.start_s = 4.7 |

**So do duoc cua tung ben**

- `C1`: collision_count = 0 | min_clearance = 0.412451 | p99_latency_ms = 0 | replan_count = 0 | success = 1 | travel_time_s = 17.6
- `C5`: collision_count = 0 | min_clearance = 0.186099 | p99_latency_ms = 17.2811 | replan_count = 7 | success = 0 | travel_time_s = 60

**Khong biet duoc tu episode nay**

- no planning-input sidecar was recorded for this episode
- this episode records no measured passage width or no inflated footprint, so no passage can be compared against one

**Thanh phan moi ben**

- `C1`: global planner = `C2` | local controller = `C3` | local controller config = `C4`
- `C5`: global planner = `C2` | local controller = `C6` | local controller config = `C7`

> One episode. There is no confidence interval on a single sample, and this is not the run's verdict: the decision card ranks candidates over every episode that was run.

</details>

### 018

> local_controller experienced local minimum entrapment in this episode on C5, as stuck_cluster fired on C5 and not on C1

- register: `diagnosis` | subject: `local_controller` | type: `local_minimum_entrapment`
- refs: `contrast:detection_only_on_loser:2`
- contract: `contrast_support`, `subject_match`, `polarity_match`

| R1 | R2 | R3 | R5 |
|---|---|---|---|
|  |  |  | n/a |

### 019

> global_planner exhibited replan instability in this episode on C5, as replan_storm fired on C5 and not on C1

- register: `diagnosis` | subject: `global_planner` | type: `replan_instability`
- refs: `contrast:detection_only_on_loser:1`
- contract: `contrast_support`, `subject_match`, `polarity_match`

| R1 | R2 | R3 | R5 |
|---|---|---|---|
|  |  |  | n/a |

### 020

> local_controller encountered a local minimum entrapment on C5 as indicated by stuck_cluster firing only on the loser, causing repeated stops and delay

- register: `diagnosis` | subject: `local_controller` | type: `local_minimum_entrapment`
- refs: `contrast:detection_only_on_loser:2`
- contract: `contrast_support`, `subject_match`, `polarity_match`

| R1 | R2 | R3 | R5 |
|---|---|---|---|
|  |  |  | n/a |

### 021

> global_planner on C5 exhibited replan instability by firing a replan_storm only on the loser and executing multiple replans

- register: `diagnosis` | subject: `global_planner` | type: `replan_instability`
- refs: `contrast:detection_only_on_loser:1`

| R1 | R2 | R3 | R5 |
|---|---|---|---|
|  |  |  | n/a |

### 022

> local_controller exhibited high expansion latency in this episode on C5

- register: `diagnosis` | subject: `local_controller` | type: `expansion_latency_association`
- refs: `diag:C5.p99_latency_ms`

| R1 | R2 | R3 | R5 |
|---|---|---|---|
|  |  |  | n/a |

---

# Episode `685501eb617d`

*cluster: doorway_v1_full_stack_selection_c23dddbd | vai: cardless*

<details open><summary><b>PACKET</b></summary>

**Phan quyet**: outcome_margin | thang: `C1` | thua: `C5`

**Khac biet giua hai ben**

| ref | strength | noi gi | so kem theo |
|---|---|---|---|
| `contrast:component_differs:2` | **context** | the two stacks differ in local_controller, local_controller_config; a mechanism that explains the difference has to live in one of those | - |
| `contrast:detection_only_on_loser:1` | **support** | stuck_cluster fired on C5 and not on C1 | stopped seconds = 5.1; stops = 1 |
| `contrast:divergence_precedes_outcome:3` | **context** | the two runs parted at 2.2 m along the route, where replan fired on one side | - |
| `contrast:outcome_differs:4` | **context** | C1 ended this episode ahead of C5 on travel time | travel time s loser = 20.2; travel time s winner = 16.1 |

**Detector da ban**

| ref | tren ai | so kem theo |
|---|---|---|
| `obs:stuck_cluster:C5@685501eb617d` | `C5` | stopped_seconds = 5.1; stops = 1; window.end_m = 2.36658; window.end_s = 9.65; window.start_m = 2.34127; window.start_s = 4.55 |

**So do duoc cua tung ben**

- `C1`: collision_count = 0 | min_clearance = 0.402939 | p99_latency_ms = 0 | replan_count = 0 | success = 1 | travel_time_s = 16.1
- `C5`: collision_count = 0 | min_clearance = 0.430209 | p99_latency_ms = 14.1645 | replan_count = 1 | success = 1 | travel_time_s = 20.2

**Khong biet duoc tu episode nay**

- no planning-input sidecar was recorded for this episode
- this episode records no measured passage width or no inflated footprint, so no passage can be compared against one

**Thanh phan moi ben**

- `C1`: global planner = `C2` | local controller = `C3` | local controller config = `C4`
- `C5`: global planner = `C2` | local controller = `C6` | local controller config = `C7`

> One episode. There is no confidence interval on a single sample, and this is not the run's verdict: the decision card ranks candidates over every episode that was run.

</details>

### 023

> The local_controller of C5 experienced local minimum entrapment during this episode, as indicated by the stuck_cluster detector firing on C5 but not on C1

- register: `diagnosis` | subject: `local_controller` | type: `local_minimum_entrapment`
- refs: `contrast:detection_only_on_loser:1`
- contract: `contrast_support`, `subject_match`, `polarity_match`

| R1 | R2 | R3 | R5 |
|---|---|---|---|
|  |  |  | n/a |

### 024

> The local_controller of C5 triggered a replan at the divergence point, indicating replan instability slowed C5 compared to C1, which had no replans

- register: `diagnosis` | subject: `local_controller` | type: `replan_instability`
- refs: `contrast:divergence_precedes_outcome:3`, `diag:C5.replan_count`, `diag:C1.replan_count`
- contract: `occurrence_evidence`, `subject_match`, `polarity_match`

| R1 | R2 | R3 | R5 |
|---|---|---|---|
|  |  |  | n/a |

### 025 - **khong de xuat gi**

> every proposal was refused before submission (quantity_in_statement); an abstention with a reason beats a claim the platform would refuse

| R1 | R2 | R3 | R5 |
|---|---|---|---|
| n/a | n/a | n/a |  |

---

# Episode `76db6b6c6ca1`

*cluster: sudden_stop_v6_full_stack_selection_06f40334 | vai: typical*

<details open><summary><b>PACKET</b></summary>

**Phan quyet**: episode_decision_utility | thang: `-` | thua: `-`

**Detector da ban**

| ref | tren ai | so kem theo |
|---|---|---|
| `obs:latency_spike:C1@76db6b6c6ca1` | `C1` | peak_latency_ms = 113.861; ticks = 1; window.end_m = 2.48764; window.end_s = 4; window.start_m = 2.48764; window.start_s = 4 |
| `obs:stuck_cluster:C1@76db6b6c6ca1` | `C1` | stopped_seconds = 5.8; stops = 1; window.end_m = 4.184; window.end_s = 12.7; window.start_m = 4.1716; window.start_s = 6.9 |

**So do duoc cua tung ben**

- `C1`: collision_count = 0 | min_clearance = 0.523931 | p99_latency_ms = 18.3783 | replan_count = 1 | success = 1 | travel_time_s = 24.35
- `C5`: collision_count = 0 | min_clearance = 0.641517 | p99_latency_ms = 0 | replan_count = 0 | success = 1 | travel_time_s = 23

**Khong biet duoc tu episode nay**

- no planning-input sidecar was recorded for this episode
- this episode records no measured passage width or no inflated footprint, so no passage can be compared against one

**Thanh phan moi ben**

- `C1`: global planner = `C2` | local controller = `C3` | local controller config = `C4`
- `C5`: global planner = `C6` | local controller = `C7` | local controller config = `C8`

> One episode. There is no confidence interval on a single sample, and this is not the run's verdict: the decision card ranks candidates over every episode that was run.

</details>

### 026

> The local_controller exhibited a stuck cluster, stopping the robot for several seconds during this episode

- register: `diagnosis` | subject: `local_controller` | type: `local_minimum_entrapment`
- refs: `obs:stuck_cluster:C1@76db6b6c6ca1`

| R1 | R2 | R3 | R5 |
|---|---|---|---|
|  |  |  | n/a |

### 027

> The global_planner performed a replan during this episode

- register: `diagnosis` | subject: `global_planner` | type: `replan_instability`
- refs: `diag:C1.replan_count`

| R1 | R2 | R3 | R5 |
|---|---|---|---|
|  |  |  | n/a |

### 028

> The runtime_transport experienced a latency spike with a high peak latency during this episode

- register: `diagnosis` | subject: `runtime_transport` | type: `candidate_latency_attribution`
- refs: `obs:latency_spike:C1@76db6b6c6ca1`, `obs:latency_spike:C1@76db6b6c6ca1/peak_latency_ms`

| R1 | R2 | R3 | R5 |
|---|---|---|---|
|  |  |  | n/a |

### 029

> The local_controller on C1 experienced local minimum entrapment (stuck_cluster) in this episode

- register: `diagnosis` | subject: `local_controller` | type: `local_minimum_entrapment`
- refs: `obs:stuck_cluster:C1@76db6b6c6ca1`

| R1 | R2 | R3 | R5 |
|---|---|---|---|
|  |  |  | n/a |

---

# Episode `7c2cc3d5019f`

*cluster: doorway_v1_full_stack_selection_c23dddbd | vai: cardless*

<details open><summary><b>PACKET</b></summary>

**Phan quyet**: outcome_only | thang: `C1` | thua: `C5`

**Khac biet giua hai ben**

| ref | strength | noi gi | so kem theo |
|---|---|---|---|
| `contrast:component_differs:3` | **context** | the two stacks differ in local_controller, local_controller_config; a mechanism that explains the difference has to live in one of those | - |
| `contrast:detection_only_on_loser:1` | **support** | replan_storm fired on C5 and not on C1 | replans = 3 |
| `contrast:detection_only_on_loser:2` | **support** | stuck_cluster fired on C5 and not on C1 | stopped seconds = 51.5; stops = 3 |
| `contrast:divergence_precedes_outcome:4` | **context** | the two runs parted at 3.0 m along the route, where replan fired on one side | - |
| `contrast:outcome_differs:5` | **context** | C1 ended this episode ahead of C5 on reached the goal, worst clearance, travel time | min clearance loser = 0.277429; min clearance winner = 0.397158; success loser = 0; success winner = 1; travel time s loser = 60; travel time s winner = 18.05 |

**Detector da ban**

| ref | tren ai | so kem theo |
|---|---|---|
| `obs:replan_storm:C5@7c2cc3d5019f` | `C5` | replans = 3; window.end_m = 3.08392; window.end_s = 48.25; window.start_m = 3.05351; window.start_s = 38.25 |
| `obs:stuck_cluster:C5@7c2cc3d5019f` | `C5` | stopped_seconds = 51.5; stops = 3; window.end_m = 3.10071; window.end_s = 60; window.start_m = 2.58563; window.start_s = 5 |

**So do duoc cua tung ben**

- `C1`: collision_count = 0 | min_clearance = 0.397158 | p99_latency_ms = 0 | replan_count = 0 | success = 1 | travel_time_s = 18.05
- `C5`: collision_count = 0 | min_clearance = 0.277429 | p99_latency_ms = 13.7915 | replan_count = 9 | success = 0 | travel_time_s = 60

**Khong biet duoc tu episode nay**

- no planning-input sidecar was recorded for this episode
- this episode records no measured passage width or no inflated footprint, so no passage can be compared against one

**Thanh phan moi ben**

- `C1`: global planner = `C2` | local controller = `C3` | local controller config = `C4`
- `C5`: global planner = `C2` | local controller = `C6` | local controller config = `C7`

> One episode. There is no confidence interval on a single sample, and this is not the run's verdict: the decision card ranks candidates over every episode that was run.

</details>

### 030

> local_controller suffered a local minimum entrapment on the losing side that the winning side did not

- register: `diagnosis` | subject: `local_controller` | type: `local_minimum_entrapment`
- refs: `contrast:detection_only_on_loser:2`
- contract: `contrast_support`, `subject_match`, `polarity_match`

| R1 | R2 | R3 | R5 |
|---|---|---|---|
|  |  |  | n/a |

### 031

> The local_controller on C5 experienced a local minimum entrapment, as evidenced by the stuck_cluster detector, causing multiple stops and delaying progress

- register: `diagnosis` | subject: `local_controller` | type: `local_minimum_entrapment`
- refs: `contrast:detection_only_on_loser:2`
- contract: `contrast_support`, `subject_match`, `polarity_match`

| R1 | R2 | R3 | R5 |
|---|---|---|---|
|  |  |  | n/a |

---

# Episode `a646b0f7b414`

*cluster: doorway_v1_full_stack_selection_c23dddbd | vai: cardless*

<details open><summary><b>PACKET</b></summary>

**Phan quyet**: outcome_margin | thang: `C1` | thua: `C5`

**Khac biet giua hai ben**

| ref | strength | noi gi | so kem theo |
|---|---|---|---|
| `contrast:component_differs:2` | **context** | the two stacks differ in local_controller, local_controller_config; a mechanism that explains the difference has to live in one of those | - |
| `contrast:detection_only_on_loser:1` | **support** | stuck_cluster fired on C5 and not on C1 | stopped seconds = 13.15; stops = 1 |
| `contrast:divergence_precedes_outcome:3` | **context** | the two runs parted at 2.3 m along the route, where replan fired on one side | - |
| `contrast:outcome_differs:4` | **context** | C1 ended this episode ahead of C5 on worst clearance, travel time | min clearance loser = 0.320665; min clearance winner = 0.38505; travel time s loser = 32.35; travel time s winner = 17.55 |

**Detector da ban**

| ref | tren ai | so kem theo |
|---|---|---|
| `obs:stuck_cluster:C5@a646b0f7b414` | `C5` | stopped_seconds = 13.15; stops = 1; window.end_m = 2.43275; window.end_s = 17.75; window.start_m = 2.37291; window.start_s = 4.6 |

**So do duoc cua tung ben**

- `C1`: collision_count = 0 | min_clearance = 0.38505 | p99_latency_ms = 0 | replan_count = 0 | success = 1 | travel_time_s = 17.55
- `C5`: collision_count = 0 | min_clearance = 0.320665 | p99_latency_ms = 16.1724 | replan_count = 2 | success = 1 | travel_time_s = 32.35

**Khong biet duoc tu episode nay**

- no planning-input sidecar was recorded for this episode
- this episode records no measured passage width or no inflated footprint, so no passage can be compared against one

**Thanh phan moi ben**

- `C1`: global planner = `C2` | local controller = `C3` | local controller config = `C4`
- `C5`: global planner = `C2` | local controller = `C6` | local controller config = `C7`

> One episode. There is no confidence interval on a single sample, and this is not the run's verdict: the decision card ranks candidates over every episode that was run.

</details>

### 032 - **khong de xuat gi**

> every proposal was refused before submission (quantity_in_statement); an abstention with a reason beats a claim the platform would refuse

| R1 | R2 | R3 | R5 |
|---|---|---|---|
| n/a | n/a | n/a |  |

### 033

> local_controller on C5 experienced a local minimum entrapment

- register: `diagnosis` | subject: `local_controller` | type: `local_minimum_entrapment`
- refs: `obs:stuck_cluster:C5@a646b0f7b414`

| R1 | R2 | R3 | R5 |
|---|---|---|---|
|  |  |  | n/a |

---

# Episode `d0a5c200c750`

*cluster: sudden_stop_custom_v2_full_stack_selection_c23dddbd | vai: typical*

<details open><summary><b>PACKET</b></summary>

**Phan quyet**: episode_decision_utility | thang: `-` | thua: `-`

**Detector da ban**

| ref | tren ai | so kem theo |
|---|---|---|
| `obs:stuck_cluster:C1@d0a5c200c750` | `C1` | stopped_seconds = 1.7; stops = 1; window.end_m = 6.99934; window.end_s = 19.1; window.start_m = 6.99493; window.start_s = 17.4 |
| `obs:stuck_cluster:C5@d0a5c200c750` | `C5` | stopped_seconds = 5.7; stops = 1; window.end_m = 3.68339; window.end_s = 12.05; window.start_m = 3.67444; window.start_s = 6.35 |

**So do duoc cua tung ben**

- `C1`: collision_count = 0 | min_clearance = 0.255411 | p99_latency_ms = 0 | replan_count = 0 | success = 1 | travel_time_s = 26.7
- `C5`: collision_count = 0 | min_clearance = 0.2376 | p99_latency_ms = 6.61034 | replan_count = 1 | success = 1 | travel_time_s = 26.15

**Khong biet duoc tu episode nay**

- no planning-input sidecar was recorded for this episode
- this episode records no measured passage width or no inflated footprint, so no passage can be compared against one

**Thanh phan moi ben**

- `C1`: global planner = `C2` | local controller = `C3` | local controller config = `C4`
- `C5`: global planner = `C2` | local controller = `C6` | local controller config = `C7`

> One episode. There is no confidence interval on a single sample, and this is not the run's verdict: the decision card ranks candidates over every episode that was run.

</details>

### 034 - **khong de xuat gi**

> every proposal was refused before submission (quantity_in_statement); an abstention with a reason beats a claim the platform would refuse

| R1 | R2 | R3 | R5 |
|---|---|---|---|
| n/a | n/a | n/a |  |

### 035 - **khong de xuat gi**

> every proposal was refused before submission (quantity_in_statement); an abstention with a reason beats a claim the platform would refuse

| R1 | R2 | R3 | R5 |
|---|---|---|---|
| n/a | n/a | n/a |  |

---

# Episode `d3265359df38`

*cluster: doorway_v1_full_stack_selection_c23dddbd | vai: cardless*

<details open><summary><b>PACKET</b></summary>

**Phan quyet**: outcome_only | thang: `C1` | thua: `C5`

**Khac biet giua hai ben**

| ref | strength | noi gi | so kem theo |
|---|---|---|---|
| `contrast:component_differs:3` | **context** | the two stacks differ in local_controller, local_controller_config; a mechanism that explains the difference has to live in one of those | - |
| `contrast:detection_only_on_loser:1` | **support** | replan_storm fired on C5 and not on C1 | replans = 3 |
| `contrast:detection_only_on_loser:2` | **support** | stuck_cluster fired on C5 and not on C1 | stopped seconds = 52.3; stops = 3 |
| `contrast:divergence_precedes_outcome:4` | **context** | the two runs parted at 2.9 m along the route, where replan fired on one side | - |
| `contrast:outcome_differs:5` | **context** | C1 ended this episode ahead of C5 on reached the goal, travel time | success loser = 0; success winner = 1; travel time s loser = 60; travel time s winner = 16.05 |

**Detector da ban**

| ref | tren ai | so kem theo |
|---|---|---|
| `obs:replan_storm:C5@d3265359df38#1` | `C5` | replans = 3; window.end_m = 2.85727; window.end_s = 40.25; window.start_m = 2.85727; window.start_s = 30.25 |
| `obs:replan_storm:C5@d3265359df38#2` | `C5` | replans = 3; window.end_m = 2.85727; window.end_s = 55.25; window.start_m = 2.85727; window.start_s = 45.25 |
| `obs:stuck_cluster:C5@d3265359df38` | `C5` | stopped_seconds = 52.3; stops = 3; window.end_m = 2.85727; window.end_s = 60; window.start_m = 2.54942; window.start_s = 4.95 |

**So do duoc cua tung ben**

- `C1`: collision_count = 0 | min_clearance = 0.397373 | p99_latency_ms = 0 | replan_count = 0 | success = 1 | travel_time_s = 16.05
- `C5`: collision_count = 0 | min_clearance = 0.418008 | p99_latency_ms = 14.8766 | replan_count = 9 | success = 0 | travel_time_s = 60

**Khong biet duoc tu episode nay**

- no planning-input sidecar was recorded for this episode
- this episode records no measured passage width or no inflated footprint, so no passage can be compared against one

**Thanh phan moi ben**

- `C1`: global planner = `C2` | local controller = `C3` | local controller config = `C4`
- `C5`: global planner = `C2` | local controller = `C6` | local controller config = `C7`

> One episode. There is no confidence interval on a single sample, and this is not the run's verdict: the decision card ranks candidates over every episode that was run.

</details>

### 036 - **khong de xuat gi**

> every proposal was refused before submission (quantity_in_statement); an abstention with a reason beats a claim the platform would refuse

| R1 | R2 | R3 | R5 |
|---|---|---|---|
| n/a | n/a | n/a |  |

### 037

> The local_controller of the losing candidate (C5) experienced local minimum entrapment in this episode, as indicated by the stuck_cluster detection, causing multiple stops that delayed its progress.

- register: `diagnosis` | subject: `local_controller` | type: `local_minimum_entrapment`
- refs: `contrast:component_differs:3`, `contrast:detection_only_on_loser:2`
- contract: `contrast_support`, `subject_match`, `polarity_match`

| R1 | R2 | R3 | R5 |
|---|---|---|---|
|  |  |  | n/a |

---

# Episode `d4de2e64507f`

*cluster: sudden_stop_v6_full_stack_selection_06f40334 | vai: strongest_for_runnerup*

<details open><summary><b>PACKET</b></summary>

**Phan quyet**: episode_decision_utility | thang: `C5` | thua: `C1`

**Khac biet giua hai ben**

| ref | strength | noi gi | so kem theo |
|---|---|---|---|
| `contrast:component_differs:2` | **context** | the two stacks differ in global_planner, local_controller, local_controller_config; a mechanism that explains the difference has to live in one of those | - |
| `contrast:detection_only_on_loser:1` | **support** | stuck_cluster fired on C1 and not on C5 | stopped seconds = 5.8; stops = 1 |
| `contrast:divergence_precedes_outcome:3` | **context** | the two runs parted at 3.6 m along the route | - |
| `contrast:outcome_differs:4` | **context** | C5 ended this episode ahead of C1 on worst clearance, travel time | min clearance loser = 0.552471; min clearance winner = 0.78283; travel time s loser = 24.3; travel time s winner = 22 |

**Detector da ban**

| ref | tren ai | so kem theo |
|---|---|---|
| `obs:stuck_cluster:C1@d4de2e64507f` | `C1` | stopped_seconds = 5.8; stops = 1; window.end_m = 4.14438; window.end_s = 12.55; window.start_m = 4.13052; window.start_s = 6.75 |

**So do duoc cua tung ben**

- `C1`: collision_count = 0 | min_clearance = 0.552471 | p99_latency_ms = 13.13 | replan_count = 1 | success = 1 | travel_time_s = 24.3
- `C5`: collision_count = 0 | min_clearance = 0.78283 | p99_latency_ms = 0 | replan_count = 0 | success = 1 | travel_time_s = 22

**Khong biet duoc tu episode nay**

- no planning-input sidecar was recorded for this episode
- this episode records no measured passage width or no inflated footprint, so no passage can be compared against one

**Thanh phan moi ben**

- `C1`: global planner = `C2` | local controller = `C3` | local controller config = `C4`
- `C5`: global planner = `C6` | local controller = `C7` | local controller config = `C8`

> One episode. There is no confidence interval on a single sample, and this is not the run's verdict: the decision card ranks candidates over every episode that was run.

</details>

### 038

> The local_controller experienced local minimum entrapment on C1, delaying it behind C5

- register: `diagnosis` | subject: `local_controller` | type: `local_minimum_entrapment`
- refs: `contrast:detection_only_on_loser:1`
- contract: `contrast_support`, `subject_match`, `polarity_match`

| R1 | R2 | R3 | R5 |
|---|---|---|---|
|  |  |  | n/a |

### 039

> local_controller of C1 experienced a local minimum entrapment in this episode

- register: `diagnosis` | subject: `local_controller` | type: `local_minimum_entrapment`
- refs: `contrast:component_differs:2`, `obs:stuck_cluster:C1@d4de2e64507f`
- contract: `occurrence_evidence`, `subject_match`, `polarity_match`

| R1 | R2 | R3 | R5 |
|---|---|---|---|
|  |  |  | n/a |

---

# Episode `e87fc5b937ab`

*cluster: sudden_stop_custom_v2_full_stack_selection_c23dddbd | vai: strongest_for_winner*

<details open><summary><b>PACKET</b></summary>

**Phan quyet**: episode_decision_utility | thang: `C1` | thua: `C5`

**Khac biet giua hai ben**

| ref | strength | noi gi | so kem theo |
|---|---|---|---|
| `contrast:component_differs:3` | **context** | the two stacks differ in local_controller, local_controller_config; a mechanism that explains the difference has to live in one of those | - |
| `contrast:detection_only_on_loser:1` | **support** | near_miss_cluster fired on C5 and not on C1 | min clearance m = 0.145266; samples = 8 |
| `contrast:detection_worse_on_loser:2` | **support** | stuck_cluster fired on both, and materially worse on C5 | severity ratio = 4.10714; stopped seconds = 5.75; stops = 1 |
| `contrast:divergence_precedes_outcome:4` | **context** | the two runs parted at 3.1 m along the route | - |
| `contrast:outcome_differs:5` | **context** | C1 ended this episode ahead of C5 on worst clearance, travel time | min clearance loser = 0.145266; min clearance winner = 0.24697; travel time s loser = 27.4; travel time s winner = 25.9 |

**Detector da ban**

| ref | tren ai | so kem theo |
|---|---|---|
| `obs:near_miss_cluster:C5@e87fc5b937ab` | `C5` | min_clearance_m = 0.145266; samples = 8; window.end_m = 7.46425; window.end_s = 20.35; window.start_m = 7.33514; window.start_s = 20 |
| `obs:stuck_cluster:C1@e87fc5b937ab` | `C1` | stopped_seconds = 1.4; stops = 1; window.end_m = 7.01237; window.end_s = 18.4; window.start_m = 7.00877; window.start_s = 17 |
| `obs:stuck_cluster:C5@e87fc5b937ab` | `C5` | stopped_seconds = 5.75; stops = 1; window.end_m = 3.7532; window.end_s = 12.1; window.start_m = 3.7433; window.start_s = 6.35 |

**So do duoc cua tung ben**

- `C1`: collision_count = 0 | min_clearance = 0.24697 | p99_latency_ms = 0 | replan_count = 0 | success = 1 | travel_time_s = 25.9
- `C5`: collision_count = 0 | min_clearance = 0.145266 | p99_latency_ms = 12.847 | replan_count = 1 | success = 1 | travel_time_s = 27.4

**Khong biet duoc tu episode nay**

- no planning-input sidecar was recorded for this episode
- this episode records no measured passage width or no inflated footprint, so no passage can be compared against one

**Thanh phan moi ben**

- `C1`: global planner = `C2` | local controller = `C3` | local controller config = `C4`
- `C5`: global planner = `C2` | local controller = `C6` | local controller config = `C7`

> One episode. There is no confidence interval on a single sample, and this is not the run's verdict: the decision card ranks candidates over every episode that was run.

</details>

### 040

> The local_controller on C5 experienced a local minimum entrapment (stuck cluster) that was more severe than on C1

- register: `diagnosis` | subject: `local_controller` | type: `local_minimum_entrapment`
- refs: `contrast:detection_worse_on_loser:2`, `contrast:component_differs:3`
- contract: `contrast_support`, `subject_match`, `polarity_match`

| R1 | R2 | R3 | R5 |
|---|---|---|---|
|  |  |  | n/a |

### 041 - **khong de xuat gi**

> every proposal was refused before submission (quantity_in_statement); an abstention with a reason beats a claim the platform would refuse

| R1 | R2 | R3 | R5 |
|---|---|---|---|
| n/a | n/a | n/a |  |

---

# Episode `fff606f44b13`

*cluster: sudden_stop_v6_full_stack_selection_06f40334 | vai: strongest_for_winner*

<details open><summary><b>PACKET</b></summary>

**Phan quyet**: episode_decision_utility | thang: `C1` | thua: `C5`

**Khac biet giua hai ben**

| ref | strength | noi gi | so kem theo |
|---|---|---|---|
| `contrast:component_differs:1` | **context** | the two stacks differ in global_planner, local_controller, local_controller_config; a mechanism that explains the difference has to live in one of those | - |
| `contrast:divergence_precedes_outcome:2` | **context** | the two runs parted at 3.5 m along the route | - |

**Detector da ban**

| ref | tren ai | so kem theo |
|---|---|---|
| `obs:stuck_cluster:C1@fff606f44b13` | `C1` | stopped_seconds = 5.85; stops = 1; window.end_m = 4.13926; window.end_s = 12.65; window.start_m = 4.11857; window.start_s = 6.8 |

**So do duoc cua tung ben**

- `C1`: collision_count = 0 | min_clearance = 0.557092 | p99_latency_ms = 11.7444 | replan_count = 1 | success = 1 | travel_time_s = 24.45
- `C5`: collision_count = 0 | min_clearance = 0.915188 | p99_latency_ms = 0 | replan_count = 0 | success = 1 | travel_time_s = 24.15

**Khong biet duoc tu episode nay**

- no planning-input sidecar was recorded for this episode
- this episode records no measured passage width or no inflated footprint, so no passage can be compared against one

**Thanh phan moi ben**

- `C1`: global planner = `C2` | local controller = `C3` | local controller config = `C4`
- `C5`: global planner = `C6` | local controller = `C7` | local controller config = `C8`

> One episode. There is no confidence interval on a single sample, and this is not the run's verdict: the decision card ranks candidates over every episode that was run.

</details>

### 042

> local_controller encountered a stuck cluster on C1 in this episode

- register: `diagnosis` | subject: `local_controller` | type: `local_minimum_entrapment`
- refs: `obs:stuck_cluster:C1@fff606f44b13`

| R1 | R2 | R3 | R5 |
|---|---|---|---|
|  |  |  | n/a |

### 043 - **khong de xuat gi**

> No mechanism evidence: no geometry for clearance checks, no planning inputs for planner replay, no expansion or sampling data; the observed differences (latency, replans, clearance) do not map to a catalog mechanism.

| R1 | R2 | R3 | R5 |
|---|---|---|---|
| n/a | n/a | n/a |  |
