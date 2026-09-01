# Cham tay, mu arm - gom theo episode (rubric r0.1.0)

38 muc | 30 episode | nguon: `holdout-magnitudes`

Moi episode: doc khoi **PACKET** mot lan, roi cham moi muc duoi no.

- **R1** hypothesis dung vung truoc packet khong - `holds` / `plausible_other` / `wrong`
- **R2** `subject` co dung thanh phan cau noi toi khong - `yes` / `no`
- **R3** moi ref mo duoc trong packet **va** noi ve dung mechanism - `all` / `some` / `none`
- **R5** cho khong de xuat gi: im lang co dung cho khong - `correct` / `should_have`

Khong muc nao noi arm nao viet no, cung khong noi no thuoc luot chay nao.
Dung doan.

---

# Episode `307c6a94d0f0`

> **Khong dung lai duoc packet cho episode nay.**

### 001

> The local_controller on C5 entered a local minimum entrapment (stuck_cluster) lasting {contrast:detection_worse_on_loser:1/stopped_seconds} seconds, more severe than in C1, which delayed its progress relative to C1.

- register: `diagnosis` | subject: `local_controller` | type: `local_minimum_entrapment`
- refs: `contrast:component_differs:2`, `contrast:detection_worse_on_loser:1`
- contract: `contrast_support`, `subject_match`, `polarity_match`

| R1 | R2 | R3 | R5 |
|---|---|---|---|
|  |  |  | n/a |

---

# Episode `40b620398486`

> **Khong dung lai duoc packet cho episode nay.**

### 002 - **khong de xuat gi**

> every proposal was refused before submission (quantity_in_statement); an abstention with a reason beats a claim the platform would refuse

| R1 | R2 | R3 | R5 |
|---|---|---|---|
| n/a | n/a | n/a |  |

---

# Episode `4874a8da74e7`

> **Khong dung lai duoc packet cho episode nay.**

### 003 - **khong de xuat gi**

> every proposal was refused before submission (quantity_in_statement); an abstention with a reason beats a claim the platform would refuse

| R1 | R2 | R3 | R5 |
|---|---|---|---|
| n/a | n/a | n/a |  |

---

# Episode `501a98d1fd9a`

> **Khong dung lai duoc packet cho episode nay.**

### 004 - **khong de xuat gi**

> every proposal was refused before submission (quantity_in_statement); an abstention with a reason beats a claim the platform would refuse

| R1 | R2 | R3 | R5 |
|---|---|---|---|
| n/a | n/a | n/a |  |

---

# Episode `50f9cae5941c`

*cluster: sudden_stop_custom_v2_full_stack_selection_06f40334 | vai: safety_critical*

<details open><summary><b>PACKET</b></summary>

**Phan quyet**: episode_decision_utility | thang: `C5` | thua: `C1`

**Khac biet giua hai ben**

| ref | strength | noi gi | so kem theo |
|---|---|---|---|
| `contrast:component_differs:4` | **context** | the two stacks differ in global_planner, local_controller, local_controller_config; a mechanism that explains the difference has to live in one of those | - |
| `contrast:detection_only_on_loser:1` | **support** | latency_spike fired on C1 and not on C5 | peak latency ms = 3008.12; ticks = 1 |
| `contrast:detection_only_on_loser:2` | **support** | replan_storm fired on C1 and not on C5 | replans = 3 |
| `contrast:detection_worse_on_loser:3` | **support** | stuck_cluster fired on both, and materially worse on C1 | severity ratio = 3.67797; stopped seconds = 21.7; stops = 2 |
| `contrast:divergence_precedes_outcome:5` | **context** | the two runs parted at 3.0 m along the route | - |
| `contrast:outcome_differs:6` | **context** | C5 ended this episode ahead of C1 on travel time | travel time s loser = 49.5; travel time s winner = 27.65 |

**Detector da ban**

| ref | tren ai | so kem theo |
|---|---|---|
| `obs:latency_spike:C1@50f9cae5941c` | `C1` | peak_latency_ms = 3008.12; ticks = 1; window.end_m = 7.58821; window.end_s = 36.8; window.start_m = 7.58821; window.start_s = 36.8 |
| `obs:near_miss_cluster:C5@50f9cae5941c` | `C5` | min_clearance_m = 0.129033; samples = 18; window.end_m = 7.46516; window.end_s = 20.7; window.start_m = 7.17333; window.start_s = 19.85 |
| `obs:replan_storm:C1@50f9cae5941c` | `C1` | replans = 3; window.end_m = 7.58821; window.end_s = 36.8; window.start_m = 7.58821; window.start_s = 26.8 |
| `obs:stuck_cluster:C1@50f9cae5941c` | `C1` | stopped_seconds = 21.7; stops = 2; window.end_m = 7.59196; window.end_s = 40.25; window.start_m = 7.52774; window.start_s = 18 |
| `obs:stuck_cluster:C5@50f9cae5941c` | `C5` | stopped_seconds = 5.9; stops = 1; window.end_m = 3.63704; window.end_s = 12.05; window.start_m = 3.58702; window.start_s = 6.15 |

**So do duoc cua tung ben**

- `C1`: collision_count = 0 | min_clearance = 0.150279 | p99_latency_ms = 0 | replan_count = 3 | success = 1 | travel_time_s = 49.5
- `C5`: collision_count = 0 | min_clearance = 0.129033 | p99_latency_ms = 19.6501 | replan_count = 1 | success = 1 | travel_time_s = 27.65

**Khong biet duoc tu episode nay**

- no planning-input sidecar was recorded for this episode
- this episode records no measured passage width or no inflated footprint, so no passage can be compared against one
- h4_not_complete
- h0_debt

**Thanh phan moi ben**

- `C1`: global planner = `C2` | local controller = `C3` | local controller config = `C4`
- `C5`: global planner = `C6` | local controller = `C7` | local controller config = `C8`

> One episode. There is no confidence interval on a single sample, and this is not the run's verdict: the decision card ranks candidates over every episode that was run.

</details>

### 005

> local_controller experienced a more severe stuck_cluster on C1 than on C5, causing C1 to be stopped for 21.7 s

- register: `diagnosis` | subject: `local_controller` | type: `local_minimum_entrapment`
- refs: `contrast:detection_worse_on_loser:3`
- contract: `contrast_support`, `subject_match`, `polarity_match`

| R1 | R2 | R3 | R5 |
|---|---|---|---|
|  |  |  | n/a |

### 006

> global_planner triggered a replan_storm on C1 but not on C5, causing additional replanning of 3 replans

- register: `diagnosis` | subject: `global_planner` | type: `replan_instability`
- refs: `contrast:detection_only_on_loser:2`
- contract: `contrast_support`, `subject_match`, `polarity_match`

| R1 | R2 | R3 | R5 |
|---|---|---|---|
|  |  |  | n/a |

---

# Episode `56f2bbdf0e74`

> **Khong dung lai duoc packet cho episode nay.**

### 007 - **khong de xuat gi**

> every proposal was refused before submission (quantity_in_statement); an abstention with a reason beats a claim the platform would refuse

| R1 | R2 | R3 | R5 |
|---|---|---|---|
| n/a | n/a | n/a |  |

---

# Episode `6a4888cdcf9e`

> **Khong dung lai duoc packet cho episode nay.**

### 008 - **khong de xuat gi**

> every proposal was refused before submission (quantity_in_statement); an abstention with a reason beats a claim the platform would refuse

| R1 | R2 | R3 | R5 |
|---|---|---|---|
| n/a | n/a | n/a |  |

---

# Episode `7323e60af732`

> **Khong dung lai duoc packet cho episode nay.**

### 009 - **khong de xuat gi**

> every proposal was refused before submission (magnitude_not_in_packet, quantity_in_statement); an abstention with a reason beats a claim the platform would refuse

| R1 | R2 | R3 | R5 |
|---|---|---|---|
| n/a | n/a | n/a |  |

---

# Episode `75974f6bd2c9`

*cluster: sudden_stop_custom_v2_full_stack_selection_06f40334 | vai: strongest_for_winner*

<details open><summary><b>PACKET</b></summary>

**Phan quyet**: episode_decision_utility | thang: `C1` | thua: `C5`

**Khac biet giua hai ben**

| ref | strength | noi gi | so kem theo |
|---|---|---|---|
| `contrast:component_differs:2` | **context** | the two stacks differ in global_planner, local_controller, local_controller_config; a mechanism that explains the difference has to live in one of those | - |
| `contrast:detection_worse_on_loser:1` | **support** | stuck_cluster fired on both, and materially worse on C5 | severity ratio = 4.64; stopped seconds = 5.8; stops = 1 |
| `contrast:divergence_precedes_outcome:3` | **context** | the two runs parted at 3.1 m along the route | - |
| `contrast:outcome_differs:4` | **context** | C1 ended this episode ahead of C5 on travel time | travel time s loser = 25.9; travel time s winner = 25 |

**Detector da ban**

| ref | tren ai | so kem theo |
|---|---|---|
| `obs:stuck_cluster:C1@75974f6bd2c9` | `C1` | stopped_seconds = 1.25; stops = 1; window.end_m = 7.28739; window.end_s = 16.9; window.start_m = 7.27997; window.start_s = 15.65 |
| `obs:stuck_cluster:C5@75974f6bd2c9` | `C5` | stopped_seconds = 5.8; stops = 1; window.end_m = 3.64367; window.end_s = 11.95; window.start_m = 3.62659; window.start_s = 6.15 |

**So do duoc cua tung ben**

- `C1`: collision_count = 0 | min_clearance = 0.217474 | p99_latency_ms = 0 | replan_count = 0 | success = 1 | travel_time_s = 25
- `C5`: collision_count = 0 | min_clearance = 0.231619 | p99_latency_ms = 22.8166 | replan_count = 1 | success = 1 | travel_time_s = 25.9

**Khong biet duoc tu episode nay**

- no planning-input sidecar was recorded for this episode
- this episode records no measured passage width or no inflated footprint, so no passage can be compared against one
- h4_not_complete
- h0_debt

**Thanh phan moi ben**

- `C1`: global planner = `C2` | local controller = `C3` | local controller config = `C4`
- `C5`: global planner = `C6` | local controller = `C7` | local controller config = `C8`

> One episode. There is no confidence interval on a single sample, and this is not the run's verdict: the decision card ranks candidates over every episode that was run.

</details>

### 010 - **khong de xuat gi**

> every proposal was refused before submission (quantity_in_statement); an abstention with a reason beats a claim the platform would refuse

| R1 | R2 | R3 | R5 |
|---|---|---|---|
| n/a | n/a | n/a |  |

---

# Episode `7764fd5de7a5`

> **Khong dung lai duoc packet cho episode nay.**

### 011

> The local_controller on C5 experienced a local minimum entrapment via a stuck_cluster that lasted {obs:stuck_cluster:C5@7764fd5de7a5/stopped_seconds}, delaying C5 more than C1

- register: `contrast` | subject: `local_controller` | type: `local_minimum_entrapment`
- refs: `contrast:detection_worse_on_loser:1`, `obs:stuck_cluster:C5@7764fd5de7a5`
- contract: `contrast_support`, `occurrence_evidence`, `subject_match`, `polarity_match`

| R1 | R2 | R3 | R5 |
|---|---|---|---|
|  |  |  | n/a |

### 012

> The local_controller on C1 experienced a local minimum entrapment via a stuck_cluster that lasted {obs:stuck_cluster:C1@7764fd5de7a5/stopped_seconds}, causing a minor delay

- register: `diagnosis` | subject: `local_controller` | type: `local_minimum_entrapment`
- refs: `obs:stuck_cluster:C1@7764fd5de7a5`

| R1 | R2 | R3 | R5 |
|---|---|---|---|
|  |  |  | n/a |

---

# Episode `8c3bfce9bb13`

> **Khong dung lai duoc packet cho episode nay.**

### 013

> The local_controller on C5 experienced a local minimum entrapment in this episode, as shown by a stuck cluster lasting {obs:stuck_cluster:C5@8c3bfce9bb13/stopped_seconds} seconds, which is materially worse than on C1

- register: `diagnosis` | subject: `local_controller` | type: `local_minimum_entrapment`
- refs: `contrast:component_differs:2`, `contrast:detection_worse_on_loser:1`
- contract: `contrast_support`, `subject_match`, `polarity_match`

| R1 | R2 | R3 | R5 |
|---|---|---|---|
|  |  |  | n/a |

---

# Episode `8ca3fa8191d8`

> **Khong dung lai duoc packet cho episode nay.**

### 014 - **khong de xuat gi**

> every proposal was refused before submission (claim_blocked_by_packet, quantity_in_statement); an abstention with a reason beats a claim the platform would refuse

| R1 | R2 | R3 | R5 |
|---|---|---|---|
| n/a | n/a | n/a |  |

---

# Episode `91ec9d58e922`

> **Khong dung lai duoc packet cho episode nay.**

### 015

> costmap_inflation refused to maintain clearance above the minimum threshold {contrast:detection_only_on_loser:1/min_clearance_m}, leading to the near miss cluster on C1

- register: `diagnosis` | subject: `costmap_inflation` | type: `clearance_refusal`
- refs: `contrast:detection_only_on_loser:1`
- contract: `contrast_support`, `subject_match`, `polarity_match`

| R1 | R2 | R3 | R5 |
|---|---|---|---|
|  |  |  | n/a |

---

# Episode `9c30ffabf757`

> **Khong dung lai duoc packet cho episode nay.**

### 016

> The local_controller of C5 initiated a replan during the episode, with a replan count of {diag:C5.replan_count}.

- register: `diagnosis` | subject: `local_controller` | type: `replan_instability`
- refs: `diag:C5.replan_count`

| R1 | R2 | R3 | R5 |
|---|---|---|---|
|  |  |  | n/a |

---

# Episode `b219dbb9c044`

> **Khong dung lai duoc packet cho episode nay.**

### 017

> C1 experienced a stuck cluster that halted its progress for {obs:stuck_cluster:C1@b219dbb9c044/stopped_seconds}

- register: `diagnosis` | subject: `local_controller` | type: `local_minimum_entrapment`
- refs: `obs:stuck_cluster:C1@b219dbb9c044/stopped_seconds`

| R1 | R2 | R3 | R5 |
|---|---|---|---|
|  |  |  | n/a |

### 018

> C5 triggered a single replan during the episode ({diag:C5.replan_count})

- register: `diagnosis` | subject: `global_planner` | type: `replan_instability`
- refs: `diag:C5.replan_count`

| R1 | R2 | R3 | R5 |
|---|---|---|---|
|  |  |  | n/a |

---

# Episode `b7a810e6fc00`

> **Khong dung lai duoc packet cho episode nay.**

### 019 - **khong de xuat gi**

> every proposal was refused before submission (quantity_in_statement); an abstention with a reason beats a claim the platform would refuse

| R1 | R2 | R3 | R5 |
|---|---|---|---|
| n/a | n/a | n/a |  |

---

# Episode `b94539aed2d1`

> **Khong dung lai duoc packet cho episode nay.**

### 020

> local_controller replan_count was {diag:C5.replan_count} on C5, while C1 had {diag:C1.replan_count}

- register: `diagnosis` | subject: `local_controller` | type: `replan_instability`
- refs: `diag:C5.replan_count`, `diag:C1.replan_count`

| R1 | R2 | R3 | R5 |
|---|---|---|---|
|  |  |  | n/a |

### 021

> local_controller experienced more severe entrapment on C5, with a stuck_cluster causing a stop of {obs:stuck_cluster:C5@b94539aed2d1/stopped_seconds} seconds, compared to {obs:stuck_cluster:C1@b94539aed2d1/stopped_seconds} seconds on C1

- register: `contrast` | subject: `local_controller` | type: `local_minimum_entrapment`
- refs: `contrast:detection_worse_on_loser:1`, `obs:stuck_cluster:C5@b94539aed2d1/stopped_seconds`, `obs:stuck_cluster:C1@b94539aed2d1/stopped_seconds`
- contract: `contrast_support`, `occurrence_evidence`, `subject_match`, `polarity_match`

| R1 | R2 | R3 | R5 |
|---|---|---|---|
|  |  |  | n/a |

---

# Episode `bdd393fb3bb8`

> **Khong dung lai duoc packet cho episode nay.**

### 022 - **khong de xuat gi**

> every proposal was refused before submission (wording_above_associated); an abstention with a reason beats a claim the platform would refuse

| R1 | R2 | R3 | R5 |
|---|---|---|---|
| n/a | n/a | n/a |  |

---

# Episode `c20848d51f24`

> **Khong dung lai duoc packet cho episode nay.**

### 023

> The global_planner of C1 generated a path with lower minimum clearance than C5, causing C1 to traverse closer to obstacles and slow down

- register: `diagnosis` | subject: `global_planner` | type: `component_specific_attribution`
- refs: `contrast:component_differs:1`, `contrast:outcome_differs:3/min_clearance_loser`, `contrast:outcome_differs:3/min_clearance_winner`
- contract: `subject_match`

| R1 | R2 | R3 | R5 |
|---|---|---|---|
|  |  |  | n/a |

---

# Episode `c31f07beacd6`

> **Khong dung lai duoc packet cho episode nay.**

### 024 - **khong de xuat gi**

> every proposal was refused before submission (quantity_in_statement); an abstention with a reason beats a claim the platform would refuse

| R1 | R2 | R3 | R5 |
|---|---|---|---|
| n/a | n/a | n/a |  |

---

# Episode `c697c0cac1bb`

> **Khong dung lai duoc packet cho episode nay.**

### 025

> local_controller on C1 triggered {diag:C1.replan_count} replans, indicating more frequent recovery actions after the entrapment

- register: `diagnosis` | subject: `local_controller` | type: `replan_instability`
- refs: `diag:C1.replan_count`

| R1 | R2 | R3 | R5 |
|---|---|---|---|
|  |  |  | n/a |

---

# Episode `d0a5c200c750`

> **Khong dung lai duoc packet cho episode nay.**

### 026

> Local_controller on C5 experienced more local_minimum_entrapment than C1, as shown by stuck_cluster on C5 lasting {contrast:detection_worse_on_loser:1/stopped_seconds}, which delayed C5 relative to C1.

- register: `diagnosis` | subject: `local_controller` | type: `local_minimum_entrapment`
- refs: `contrast:component_differs:2`, `contrast:detection_worse_on_loser:1`
- contract: `contrast_support`, `subject_match`, `polarity_match`

| R1 | R2 | R3 | R5 |
|---|---|---|---|
|  |  |  | n/a |

---

# Episode `d663910f7e0f`

> **Khong dung lai duoc packet cho episode nay.**

### 027

> The global_planner component difference explains why C5 achieved higher min clearance {contrast:outcome_differs:3/min_clearance_winner} and lower travel time {contrast:outcome_differs:3/travel_time_s_winner}.

- register: `diagnosis` | subject: `global_planner` | type: `component_specific_attribution`
- refs: `contrast:component_differs:1`, `contrast:outcome_differs:3`
- contract: `subject_match`

| R1 | R2 | R3 | R5 |
|---|---|---|---|
|  |  |  | n/a |

---

# Episode `e87fc5b937ab`

> **Khong dung lai duoc packet cho episode nay.**

### 028 - **khong de xuat gi**

> every proposal was refused before submission (quantity_in_statement); an abstention with a reason beats a claim the platform would refuse

| R1 | R2 | R3 | R5 |
|---|---|---|---|
| n/a | n/a | n/a |  |

---

# Episode `e9a1c89e9dbf`

> **Khong dung lai duoc packet cho episode nay.**

### 029

> The local_controller on C5 entrapped in a local minimum and triggered a stuck_cluster that delayed it by {obs:stuck_cluster:C5@e9a1c89e9dbf/stopped_seconds} seconds, compared to {obs:stuck_cluster:C1@e9a1c89e9dbf/stopped_seconds} seconds for C1

- register: `diagnosis` | subject: `local_controller` | type: `local_minimum_entrapment`
- refs: `contrast:detection_worse_on_loser:1`
- contract: `contrast_support`, `subject_match`, `polarity_match`

| R1 | R2 | R3 | R5 |
|---|---|---|---|
|  |  |  | n/a |

---

# Episode `f11b8bfc70ba`

*cluster: sudden_stop_custom_v2_full_stack_selection_06f40334 | vai: typical*

<details open><summary><b>PACKET</b></summary>

**Phan quyet**: episode_decision_utility | thang: `-` | thua: `-`

**Detector da ban**

| ref | tren ai | so kem theo |
|---|---|---|
| `obs:stuck_cluster:C1@f11b8bfc70ba` | `C1` | stopped_seconds = 10.25; stops = 1; window.end_m = 7.56298; window.end_s = 28.05; window.start_m = 7.55868; window.start_s = 17.8 |
| `obs:stuck_cluster:C5@f11b8bfc70ba` | `C5` | stopped_seconds = 5.75; stops = 1; window.end_m = 3.68527; window.end_s = 12; window.start_m = 3.67722; window.start_s = 6.25 |

**So do duoc cua tung ben**

- `C1`: collision_count = 0 | min_clearance = 0.214884 | p99_latency_ms = 0 | replan_count = 2 | success = 1 | travel_time_s = 35.75
- `C5`: collision_count = 0 | min_clearance = 0.260382 | p99_latency_ms = 20.5732 | replan_count = 1 | success = 1 | travel_time_s = 25.8

**Khong biet duoc tu episode nay**

- no planning-input sidecar was recorded for this episode
- this episode records no measured passage width or no inflated footprint, so no passage can be compared against one
- h4_not_complete
- h0_debt

**Thanh phan moi ben**

- `C1`: global planner = `C2` | local controller = `C3` | local controller config = `C4`
- `C5`: global planner = `C6` | local controller = `C7` | local controller config = `C8`

> One episode. There is no confidence interval on a single sample, and this is not the run's verdict: the decision card ranks candidates over every episode that was run.

</details>

### 030

> The local_controller for C1 experienced a local minimum entrapment lasting 10.25 seconds.

- register: `diagnosis` | subject: `local_controller` | type: `local_minimum_entrapment`
- refs: `obs:stuck_cluster:C1@f11b8bfc70ba`

| R1 | R2 | R3 | R5 |
|---|---|---|---|
|  |  |  | n/a |

### 031

> The global_planner for C1 initiated 2 replans in this episode.

- register: `diagnosis` | subject: `global_planner` | type: `replan_instability`
- refs: `diag:C1.replan_count`

| R1 | R2 | R3 | R5 |
|---|---|---|---|
|  |  |  | n/a |

---

# Episode `f4a50b33adf9`

> **Khong dung lai duoc packet cho episode nay.**

### 032

> local_controller of C5 performed a replan event with count {diag:C5.replan_count}

- register: `diagnosis` | subject: `local_controller` | type: `component_specific_attribution`
- refs: `diag:C5.replan_count`

| R1 | R2 | R3 | R5 |
|---|---|---|---|
|  |  |  | n/a |

### 033

> costmap_inflation prevented closer passage when C1 had a near miss cluster with minimum clearance {obs:near_miss_cluster:C1@f4a50b33adf9/min_clearance_m}

- register: `diagnosis` | subject: `costmap_inflation` | type: `clearance_refusal`
- refs: `obs:near_miss_cluster:C1@f4a50b33adf9/min_clearance_m`

| R1 | R2 | R3 | R5 |
|---|---|---|---|
|  |  |  | n/a |

---

# Episode `f56b11845b7e`

> **Khong dung lai duoc packet cho episode nay.**

### 034 - **khong de xuat gi**

> every proposal was refused before submission (quantity_in_statement); an abstention with a reason beats a claim the platform would refuse

| R1 | R2 | R3 | R5 |
|---|---|---|---|
| n/a | n/a | n/a |  |

---

# Episode `fd58ce16a90d`

> **Khong dung lai duoc packet cho episode nay.**

### 035

> Candidate C1 experienced a local minimum entrapment lasting {obs:stuck_cluster:C1@fd58ce16a90d/stopped_seconds} seconds.

- register: `diagnosis` | subject: `local_controller` | type: `local_minimum_entrapment`
- refs: `obs:stuck_cluster:C1@fd58ce16a90d`

| R1 | R2 | R3 | R5 |
|---|---|---|---|
|  |  |  | n/a |

### 036

> The global_planner of C5 invoked {diag:C5.replan_count} replanning attempts.

- register: `diagnosis` | subject: `global_planner` | type: `replan_instability`
- refs: `diag:C5.replan_count`

| R1 | R2 | R3 | R5 |
|---|---|---|---|
|  |  |  | n/a |

### 037

> Candidate C5 experienced a local minimum entrapment lasting {obs:stuck_cluster:C5@fd58ce16a90d/stopped_seconds} seconds.

- register: `diagnosis` | subject: `local_controller` | type: `local_minimum_entrapment`
- refs: `obs:stuck_cluster:C5@fd58ce16a90d`

| R1 | R2 | R3 | R5 |
|---|---|---|---|
|  |  |  | n/a |

---

# Episode `ff9c3d241c53`

> **Khong dung lai duoc packet cho episode nay.**

### 038

> local_controller on C5 experienced a local minimum entrapment in this episode, with a stuck_cluster detection lasting {obs:stuck_cluster:C5@ff9c3d241c53/stopped_seconds} s that delayed its progress and led to its slower travel time compared to C1

- register: `diagnosis` | subject: `local_controller` | type: `local_minimum_entrapment`
- refs: `contrast:component_differs:2`, `contrast:detection_worse_on_loser:1`
- contract: `contrast_support`, `subject_match`, `polarity_match`

| R1 | R2 | R3 | R5 |
|---|---|---|---|
|  |  |  | n/a |
