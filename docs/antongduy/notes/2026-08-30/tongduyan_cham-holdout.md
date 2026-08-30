# Cham tay, mu arm - gom theo episode (rubric r0.1.0)

37 muc | 30 episode | nguon: `holdout-b1`

Nguoi cham: **An Tong** | phan loai: **holdout** |
ngay cham: **2026-08-30** | trang thai: **complete - 30/30 packet da doi chieu**

> **Nguon dung lai:** DB run `c6a068e66ad0` (snapshot report 30 episode) + trace
> set `54cddd584af44636` (60 Parquet va sidecar). File report tren disk khong
> khop snapshot DB nen sheet ban dau chi nhung duoc 3 packet; 27 packet con lai
> da duoc dung truc tiep tu snapshot + trace truoc khi cham. Moi packet deu mang
> standing unknown `h4_not_complete` va `h0_debt`.

Moi episode: doc khoi **PACKET** mot lan, roi cham moi muc duoi no.

- **R1** hypothesis dung vung truoc packet khong - `holds` / `plausible_other` / `wrong`
- **R2** `subject` co dung thanh phan cau noi toi khong - `yes` / `no`
- **R3** moi ref mo duoc trong packet **va** noi ve dung mechanism - `all` / `some` / `none`
- **R5** cho khong de xuat gi: im lang co dung cho khong - `correct` / `should_have`

Khong muc nao noi arm nao viet no, cung khong noi no thuoc luot chay nao.
Dung doan.

---

# Episode `307c6a94d0f0`

> **Packet da dung lai tu run `c6a068e66ad0` va trace set `54cddd584af44636`; khong nhung lai tai day.**

### 001 - **khong de xuat gi**

> every proposal was refused before submission (quantity_in_statement); an abstention with a reason beats a claim the platform would refuse

| R1 | R2 | R3 | R5 |
|---|---|---|---|
| n/a | n/a | n/a | should_have |

---

# Episode `40b620398486`

> **Packet da dung lai tu run `c6a068e66ad0` va trace set `54cddd584af44636`; khong nhung lai tai day.**

### 002 - **khong de xuat gi**

> every proposal was refused before submission (quantity_in_statement); an abstention with a reason beats a claim the platform would refuse

| R1 | R2 | R3 | R5 |
|---|---|---|---|
| n/a | n/a | n/a | should_have |

---

# Episode `4874a8da74e7`

> **Packet da dung lai tu run `c6a068e66ad0` va trace set `54cddd584af44636`; khong nhung lai tai day.**

### 003 - **khong de xuat gi**

> every proposal was refused before submission (quantity_in_statement); an abstention with a reason beats a claim the platform would refuse

| R1 | R2 | R3 | R5 |
|---|---|---|---|
| n/a | n/a | n/a | should_have |

---

# Episode `501a98d1fd9a`

> **Packet da dung lai tu run `c6a068e66ad0` va trace set `54cddd584af44636`; khong nhung lai tai day.**

### 004 - **khong de xuat gi**

> every proposal was refused before submission (quantity_in_statement); an abstention with a reason beats a claim the platform would refuse

| R1 | R2 | R3 | R5 |
|---|---|---|---|
| n/a | n/a | n/a | should_have |

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

### 005 - **khong de xuat gi**

> every proposal was refused before submission (quantity_in_statement); an abstention with a reason beats a claim the platform would refuse

| R1 | R2 | R3 | R5 |
|---|---|---|---|
| n/a | n/a | n/a | should_have |

---

# Episode `56f2bbdf0e74`

> **Packet da dung lai tu run `c6a068e66ad0` va trace set `54cddd584af44636`; khong nhung lai tai day.**

### 006

> The local_controller in C5 encountered a stuck_cluster detection with greater severity, resulting in longer stops than C1 in this episode

- register: `diagnosis` | subject: `local_controller` | type: `local_minimum_entrapment`
- refs: `contrast:detection_worse_on_loser:2`
- contract: `contrast_support`, `subject_match`, `polarity_match`

| R1 | R2 | R3 | R5 |
|---|---|---|---|
| holds | yes | all | n/a |

---

# Episode `6a4888cdcf9e`

> **Packet da dung lai tu run `c6a068e66ad0` va trace set `54cddd584af44636`; khong nhung lai tai day.**

### 007 - **khong de xuat gi**

> every proposal was refused before submission (quantity_in_statement); an abstention with a reason beats a claim the platform would refuse

| R1 | R2 | R3 | R5 |
|---|---|---|---|
| n/a | n/a | n/a | should_have |

---

# Episode `7323e60af732`

> **Packet da dung lai tu run `c6a068e66ad0` va trace set `54cddd584af44636`; khong nhung lai tai day.**

### 008 - **khong de xuat gi**

> every proposal was refused before submission (quantity_in_statement); an abstention with a reason beats a claim the platform would refuse

| R1 | R2 | R3 | R5 |
|---|---|---|---|
| n/a | n/a | n/a | should_have |

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

### 009 - **khong de xuat gi**

> every proposal was refused before submission (quantity_in_statement); an abstention with a reason beats a claim the platform would refuse

| R1 | R2 | R3 | R5 |
|---|---|---|---|
| n/a | n/a | n/a | should_have |

---

# Episode `7764fd5de7a5`

> **Packet da dung lai tu run `c6a068e66ad0` va trace set `54cddd584af44636`; khong nhung lai tai day.**

### 010 - **khong de xuat gi**

> every proposal was refused before submission (quantity_in_statement); an abstention with a reason beats a claim the platform would refuse

| R1 | R2 | R3 | R5 |
|---|---|---|---|
| n/a | n/a | n/a | should_have |

---

# Episode `8c3bfce9bb13`

> **Packet da dung lai tu run `c6a068e66ad0` va trace set `54cddd584af44636`; khong nhung lai tai day.**

### 011 - **khong de xuat gi**

> every proposal was refused before submission (quantity_in_statement); an abstention with a reason beats a claim the platform would refuse

| R1 | R2 | R3 | R5 |
|---|---|---|---|
| n/a | n/a | n/a | should_have |

---

# Episode `8ca3fa8191d8`

> **Packet da dung lai tu run `c6a068e66ad0` va trace set `54cddd584af44636`; khong nhung lai tai day.**

### 012

> Local_controller on C1 was trapped in a local minimum longer than on C5, causing C1 to lose to C5

- register: `diagnosis` | subject: `local_controller` | type: `local_minimum_entrapment`
- refs: `contrast:detection_worse_on_loser:2`
- contract: `contrast_support`, `subject_match`, `polarity_match`

| R1 | R2 | R3 | R5 |
|---|---|---|---|
| holds | yes | all | n/a |

### 013

> Global_planner on C1 experienced a latency spike in this episode

- register: `diagnosis` | subject: `global_planner` | type: `component_specific_attribution`
- refs: `obs:latency_spike:C1@8ca3fa8191d8`

| R1 | R2 | R3 | R5 |
|---|---|---|---|
| holds | yes | all | n/a |

---

# Episode `91ec9d58e922`

> **Packet da dung lai tu run `c6a068e66ad0` va trace set `54cddd584af44636`; khong nhung lai tai day.**

### 014 - **khong de xuat gi**

> every proposal was refused before submission (quantity_in_statement); an abstention with a reason beats a claim the platform would refuse

| R1 | R2 | R3 | R5 |
|---|---|---|---|
| n/a | n/a | n/a | should_have |

---

# Episode `9c30ffabf757`

> **Packet da dung lai tu run `c6a068e66ad0` va trace set `54cddd584af44636`; khong nhung lai tai day.**

### 015

> global_planner of C5 maintained a larger minimum clearance than the global_planner of C1 in this episode

- register: `diagnosis` | subject: `global_planner` | type: `component_specific_attribution`
- refs: `contrast:component_differs:1`, `diag:C1.min_clearance`, `diag:C5.min_clearance`
- contract: `occurrence_evidence`, `subject_match`

| R1 | R2 | R3 | R5 |
|---|---|---|---|
| plausible_other | yes | some | n/a |

---

# Episode `b219dbb9c044`

> **Packet da dung lai tu run `c6a068e66ad0` va trace set `54cddd584af44636`; khong nhung lai tai day.**

### 016

> The global_planner of C5 was C6, whereas C1 used C2

- register: `diagnosis` | subject: `global_planner` | type: `component_specific_attribution`
- refs: `fact:candidate:C5.global_planner`, `fact:candidate:C1.global_planner`

| R1 | R2 | R3 | R5 |
|---|---|---|---|
| holds | yes | all | n/a |

### 017

> The local_controller of C5 was C7, whereas C1 used C3

- register: `diagnosis` | subject: `local_controller` | type: `component_specific_attribution`
- refs: `fact:candidate:C5.local_controller`, `fact:candidate:C1.local_controller`

| R1 | R2 | R3 | R5 |
|---|---|---|---|
| holds | yes | all | n/a |

---

# Episode `b7a810e6fc00`

> **Packet da dung lai tu run `c6a068e66ad0` va trace set `54cddd584af44636`; khong nhung lai tai day.**

### 018 - **khong de xuat gi**

> every proposal was refused before submission (quantity_in_statement); an abstention with a reason beats a claim the platform would refuse

| R1 | R2 | R3 | R5 |
|---|---|---|---|
| n/a | n/a | n/a | should_have |

---

# Episode `b94539aed2d1`

> **Packet da dung lai tu run `c6a068e66ad0` va trace set `54cddd584af44636`; khong nhung lai tai day.**

### 019 - **khong de xuat gi**

> every proposal was refused before submission (quantity_in_statement); an abstention with a reason beats a claim the platform would refuse

| R1 | R2 | R3 | R5 |
|---|---|---|---|
| n/a | n/a | n/a | should_have |

---

# Episode `bdd393fb3bb8`

> **Packet da dung lai tu run `c6a068e66ad0` va trace set `54cddd584af44636`; khong nhung lai tai day.**

### 020 - **khong de xuat gi**

> every proposal was refused before submission (quantity_in_statement); an abstention with a reason beats a claim the platform would refuse

| R1 | R2 | R3 | R5 |
|---|---|---|---|
| n/a | n/a | n/a | should_have |

---

# Episode `c20848d51f24`

> **Packet da dung lai tu run `c6a068e66ad0` va trace set `54cddd584af44636`; khong nhung lai tai day.**

### 021

> The global_planner of C5 produced a path with higher minimum clearance than the global_planner of C1

- register: `diagnosis` | subject: `global_planner` | type: `component_specific_attribution`
- refs: `fact:candidate:C1.global_planner`, `fact:candidate:C5.global_planner`, `contrast:outcome_differs:3/min_clearance_loser`, `contrast:outcome_differs:3/min_clearance_winner`

| R1 | R2 | R3 | R5 |
|---|---|---|---|
| plausible_other | yes | all | n/a |

### 022

> The local_controller of C5 achieved a faster traversal to the goal than the local_controller of C1

- register: `diagnosis` | subject: `local_controller` | type: `component_specific_attribution`
- refs: `fact:candidate:C1.local_controller`, `fact:candidate:C5.local_controller`, `contrast:outcome_differs:3/travel_time_s_loser`, `contrast:outcome_differs:3/travel_time_s_winner`

| R1 | R2 | R3 | R5 |
|---|---|---|---|
| plausible_other | yes | all | n/a |

---

# Episode `c31f07beacd6`

> **Packet da dung lai tu run `c6a068e66ad0` va trace set `54cddd584af44636`; khong nhung lai tai day.**

### 023 - **khong de xuat gi**

> every proposal was refused before submission (quantity_in_statement); an abstention with a reason beats a claim the platform would refuse

| R1 | R2 | R3 | R5 |
|---|---|---|---|
| n/a | n/a | n/a | should_have |

---

# Episode `c697c0cac1bb`

> **Packet da dung lai tu run `c6a068e66ad0` va trace set `54cddd584af44636`; khong nhung lai tai day.**

### 024

> local_controller on the losing candidate replanned more frequently than on the winning candidate, indicating potential instability

- register: `diagnosis` | subject: `local_controller` | type: `replan_instability`
- refs: `diag:C1.replan_count`, `diag:C5.replan_count`

| R1 | R2 | R3 | R5 |
|---|---|---|---|
| plausible_other | no | all | n/a |

---

# Episode `d0a5c200c750`

> **Packet da dung lai tu run `c6a068e66ad0` va trace set `54cddd584af44636`; khong nhung lai tai day.**

### 025

> The local_controller on C5 triggered a replan during the stuck_cluster delay, introducing instability that C1 did not experience

- register: `contrast` | subject: `local_controller` | type: `replan_instability`
- refs: `contrast:detection_worse_on_loser:1`, `diag:C5.replan_count`, `diag:C1.replan_count`
- contract: `contrast_support`, `occurrence_evidence`, `subject_match`, `polarity_match`

| R1 | R2 | R3 | R5 |
|---|---|---|---|
| wrong | no | some | n/a |

---

# Episode `d663910f7e0f`

> **Packet da dung lai tu run `c6a068e66ad0` va trace set `54cddd584af44636`; khong nhung lai tai day.**

### 026

> global_planner of C5 produced trajectories with higher minimum clearance than global_planner of C1 in this episode

- register: `diagnosis` | subject: `global_planner` | type: `component_specific_attribution`
- refs: `contrast:component_differs:1`, `contrast:outcome_differs:3/min_clearance_winner`, `contrast:outcome_differs:3/min_clearance_loser`
- contract: `subject_match`

| R1 | R2 | R3 | R5 |
|---|---|---|---|
| plausible_other | yes | all | n/a |

---

# Episode `e87fc5b937ab`

> **Packet da dung lai tu run `c6a068e66ad0` va trace set `54cddd584af44636`; khong nhung lai tai day.**

### 027 - **khong de xuat gi**

> every proposal was refused before submission (quantity_in_statement, wording_above_associated); an abstention with a reason beats a claim the platform would refuse

| R1 | R2 | R3 | R5 |
|---|---|---|---|
| n/a | n/a | n/a | should_have |

---

# Episode `e9a1c89e9dbf`

> **Packet da dung lai tu run `c6a068e66ad0` va trace set `54cddd584af44636`; khong nhung lai tai day.**

### 028 - **khong de xuat gi**

> every proposal was refused before submission (quantity_in_statement); an abstention with a reason beats a claim the platform would refuse

| R1 | R2 | R3 | R5 |
|---|---|---|---|
| n/a | n/a | n/a | should_have |

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

### 029 - **khong de xuat gi**

> every proposal was refused before submission (quantity_in_statement); an abstention with a reason beats a claim the platform would refuse

| R1 | R2 | R3 | R5 |
|---|---|---|---|
| n/a | n/a | n/a | should_have |

---

# Episode `f4a50b33adf9`

> **Packet da dung lai tu run `c6a068e66ad0` va trace set `54cddd584af44636`; khong nhung lai tai day.**

### 030

> local_controller of C5 experienced a stuck cluster in this episode

- register: `diagnosis` | subject: `local_controller` | type: `local_minimum_entrapment`
- refs: `obs:stuck_cluster:C5@f4a50b33adf9`

| R1 | R2 | R3 | R5 |
|---|---|---|---|
| holds | yes | all | n/a |

### 031

> local_controller of C1 experienced a stuck cluster in this episode

- register: `diagnosis` | subject: `local_controller` | type: `local_minimum_entrapment`
- refs: `obs:stuck_cluster:C1@f4a50b33adf9`

| R1 | R2 | R3 | R5 |
|---|---|---|---|
| holds | yes | all | n/a |

### 032

> local_controller of C1 encountered a near miss cluster in this episode

- register: `diagnosis` | subject: `costmap_inflation` | type: `clearance_refusal`
- refs: `obs:near_miss_cluster:C1@f4a50b33adf9`

| R1 | R2 | R3 | R5 |
|---|---|---|---|
| holds | no | all | n/a |

---

# Episode `f56b11845b7e`

> **Packet da dung lai tu run `c6a068e66ad0` va trace set `54cddd584af44636`; khong nhung lai tai day.**

### 033

> global_planner of C5 produced a path with higher minimum clearance than global_planner of C1 in this episode

- register: `diagnosis` | subject: `global_planner` | type: `component_specific_attribution`
- refs: `contrast:component_differs:1`, `contrast:outcome_differs:3/min_clearance_winner`, `contrast:outcome_differs:3/min_clearance_loser`, `fact:candidate:C1.global_planner`, `fact:candidate:C5.global_planner`
- contract: `subject_match`

| R1 | R2 | R3 | R5 |
|---|---|---|---|
| plausible_other | yes | all | n/a |

---

# Episode `fd58ce16a90d`

> **Packet da dung lai tu run `c6a068e66ad0` va trace set `54cddd584af44636`; khong nhung lai tai day.**

### 034

> The local_controller of C5 encountered a local minimum entrapment, as indicated by the stuck_cluster detection

- register: `diagnosis` | subject: `local_controller` | type: `local_minimum_entrapment`
- refs: `obs:stuck_cluster:C5@fd58ce16a90d`

| R1 | R2 | R3 | R5 |
|---|---|---|---|
| holds | yes | all | n/a |

### 035

> The local_controller of C1 encountered a local minimum entrapment, as indicated by the stuck_cluster detection

- register: `diagnosis` | subject: `local_controller` | type: `local_minimum_entrapment`
- refs: `obs:stuck_cluster:C1@fd58ce16a90d`

| R1 | R2 | R3 | R5 |
|---|---|---|---|
| holds | yes | all | n/a |

---

# Episode `ff9c3d241c53`

> **Packet da dung lai tu run `c6a068e66ad0` va trace set `54cddd584af44636`; khong nhung lai tai day.**

### 036

> local_controller on C5 experienced a more severe stuck_cluster event, stopping for more seconds than on C1 in this episode

- register: `diagnosis` | subject: `local_controller` | type: `component_specific_attribution`
- refs: `contrast:detection_worse_on_loser:1`

| R1 | R2 | R3 | R5 |
|---|---|---|---|
| holds | yes | all | n/a |

### 037

> The local_controller difference explains the slower travel time on C5 because it triggered a longer stuck_cluster stop in this episode

- register: `diagnosis` | subject: `local_controller` | type: `component_specific_attribution`
- refs: `contrast:component_differs:2`, `contrast:detection_worse_on_loser:1`, `contrast:outcome_differs:4`
- contract: `contrast_support`, `subject_match`

| R1 | R2 | R3 | R5 |
|---|---|---|---|
| holds | yes | all | n/a |
