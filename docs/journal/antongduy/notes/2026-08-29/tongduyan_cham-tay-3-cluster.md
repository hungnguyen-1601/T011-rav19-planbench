# Cham tay, mu arm - gom theo episode (rubric r0.1.0)

188 muc | 17 episode | nguon: `stage3-three-clusters`, `stage4-cite-two`

Nguoi cham: **An Tong** | phan loai: **exploratory** | ngay cham: **2026-08-29**

Ghi chu hieu chinh rubric: `proposition_type` la **ho hypothesis duoc de xuat**, khong phai claim da verified. **R1** cham mechanism/hypothesis doc lap voi ket qua episode; diagnosis khong can giai thich winner-loser. **R2** cham subject rieng, khong dung subject de tu dong ha R1. **R3** cham ref. Wording manh la loi guard rieng, khong tru diem manual. **R5** chi `correct` khi packet khong co detection/contrast dang bao.

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

> global_planner in C5 experienced a replanning storm, indicated by multiple replans in a short segment, suggesting replan instability

- register: `diagnosis` | subject: `global_planner` | type: `replan_instability`
- refs: `contrast:detection_only_on_loser:1`

| R1 | R2 | R3 | R5 |
|---|---|---|---|
| holds | yes | all | n/a |

### 002

> global_planner exhibited replan_instability, firing a replan_storm with multiple replans on C5

- register: `diagnosis` | subject: `global_planner` | type: `replan_instability`
- refs: `obs:replan_storm:C5@1d18a81ba501`

| R1 | R2 | R3 | R5 |
|---|---|---|---|
| holds | yes | all | n/a |

### 003

> global_planner of C5 triggered unstable planning (replan_storm) in this episode, causing multiple replans

- register: `diagnosis` | subject: `global_planner` | type: `replan_instability`
- refs: `obs:replan_storm:C5@1d18a81ba501`

| R1 | R2 | R3 | R5 |
|---|---|---|---|
| holds | yes | all | n/a |

### 004

> local_controller suffered local_minimum_entrapment, as indicated by the stuck_cluster event on C5 that did not occur on C1

- register: `diagnosis` | subject: `local_controller` | type: `local_minimum_entrapment`
- refs: `contrast:component_differs:3`, `obs:stuck_cluster:C5@1d18a81ba501`
- contract: `occurrence_evidence`, `subject_match`, `polarity_match`

| R1 | R2 | R3 | R5 |
|---|---|---|---|
| holds | yes | all | n/a |

### 005 - **khong de xuat gi**

> every proposal was refused before submission (quantity_in_statement); an abstention with a reason beats a claim the platform would refuse

| R1 | R2 | R3 | R5 |
|---|---|---|---|
| n/a | n/a | n/a | should_have |

### 006 - **khong de xuat gi**

> every proposal was refused before submission (quantity_in_statement); an abstention with a reason beats a claim the platform would refuse

| R1 | R2 | R3 | R5 |
|---|---|---|---|
| n/a | n/a | n/a | should_have |

### 007

> local_controller in C5 got entrapped in a local minimum, leading to several stops as indicated by stuck_cluster detection

- register: `diagnosis` | subject: `local_controller` | type: `local_minimum_entrapment`
- refs: `contrast:detection_only_on_loser:2`

| R1 | R2 | R3 | R5 |
|---|---|---|---|
| holds | yes | all | n/a |

### 008

> local_controller of C5 triggered a local minimum entrapment (stuck_cluster) in this episode, causing C5 to stop repeatedly

- register: `diagnosis` | subject: `local_controller` | type: `local_minimum_entrapment`
- refs: `obs:stuck_cluster:C5@1d18a81ba501`

| R1 | R2 | R3 | R5 |
|---|---|---|---|
| holds | yes | all | n/a |

### 009

> The local_controller on C5 experienced local minimum entrapment, indicated by stuck_cluster firing on C5 but not on C1, which hindered C5

- register: `diagnosis` | subject: `local_controller` | type: `local_minimum_entrapment`
- refs: `contrast:detection_only_on_loser:2`
- contract: `contrast_support`, `subject_match`, `polarity_match`

| R1 | R2 | R3 | R5 |
|---|---|---|---|
| holds | yes | all | n/a |

### 010

> the local_controller in C5 triggered stuck_cluster events in this episode, resulting in multiple stops and increased travel time compared to C1

- register: `diagnosis` | subject: `local_controller` | type: `component_specific_attribution`
- refs: `contrast:component_differs:3`, `obs:stuck_cluster:C5@1d18a81ba501`
- contract: `occurrence_evidence`, `subject_match`

| R1 | R2 | R3 | R5 |
|---|---|---|---|
| holds | yes | all | n/a |

### 011

> global_planner exhibited replan instability on C5, as indicated by replan_storm firing only on C5

- register: `diagnosis` | subject: `global_planner` | type: `replan_instability`
- refs: `contrast:detection_only_on_loser:1`

| R1 | R2 | R3 | R5 |
|---|---|---|---|
| holds | yes | all | n/a |

### 012

> local_controller on C5 became entrapped in a local minimum during this episode, as indicated by the stuck_cluster detector

- register: `diagnosis` | subject: `local_controller` | type: `local_minimum_entrapment`
- refs: `contrast:detection_only_on_loser:2`
- contract: `contrast_support`, `subject_match`, `polarity_match`

| R1 | R2 | R3 | R5 |
|---|---|---|---|
| holds | yes | all | n/a |

### 013

> local_controller experienced local minimum entrapment on the losing run, as indicated by stuck_cluster firing only on C5

- register: `diagnosis` | subject: `local_controller` | type: `local_minimum_entrapment`
- refs: `contrast:detection_only_on_loser:2`
- contract: `contrast_support`, `subject_match`, `polarity_match`

| R1 | R2 | R3 | R5 |
|---|---|---|---|
| holds | yes | all | n/a |

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

### 014 - **khong de xuat gi**

> every proposal was refused before submission (quantity_in_statement); an abstention with a reason beats a claim the platform would refuse

| R1 | R2 | R3 | R5 |
|---|---|---|---|
| n/a | n/a | n/a | should_have |

### 015 - **khong de xuat gi**

> every proposal was refused before submission (quantity_in_statement); an abstention with a reason beats a claim the platform would refuse

| R1 | R2 | R3 | R5 |
|---|---|---|---|
| n/a | n/a | n/a | should_have |

### 016 - **khong de xuat gi**

> Both stacks finished successfully with no collisions, and there is no episode-specific evidence linking any component difference to the outcome.

| R1 | R2 | R3 | R5 |
|---|---|---|---|
| n/a | n/a | n/a | should_have |

### 017 - **khong de xuat gi**

> every proposal was refused before submission (quantity_in_statement); an abstention with a reason beats a claim the platform would refuse

| R1 | R2 | R3 | R5 |
|---|---|---|---|
| n/a | n/a | n/a | should_have |

### 018

> C1 experienced a local minimum entrapment in its local_controller, as indicated by a stuck cluster detected in this episode

- register: `diagnosis` | subject: `local_controller` | type: `local_minimum_entrapment`
- refs: `obs:stuck_cluster:C1@31a398df5569`

| R1 | R2 | R3 | R5 |
|---|---|---|---|
| holds | yes | all | n/a |

### 019

> The local_controller_config in C1 (C4) may have applied a tighter clearance parameter than the configuration in C5 (C8), allowing C1 to follow a more direct trajectory

- register: `diagnosis` | subject: `local_controller` | type: `component_specific_attribution`
- refs: `contrast:component_differs:1`

| R1 | R2 | R3 | R5 |
|---|---|---|---|
| wrong | no | none | n/a |

### 020 - **khong de xuat gi**

> every proposal was refused before submission (quantity_in_statement); an abstention with a reason beats a claim the platform would refuse

| R1 | R2 | R3 | R5 |
|---|---|---|---|
| n/a | n/a | n/a | should_have |

### 021

> local_controller on C1 became stuck in a local minimum, causing a stop recorded by the stuck_cluster detector

- register: `diagnosis` | subject: `local_controller` | type: `local_minimum_entrapment`
- refs: `obs:stuck_cluster:C1@31a398df5569`

| R1 | R2 | R3 | R5 |
|---|---|---|---|
| holds | yes | all | n/a |

### 022

> local_controller on C1 triggered a replan during execution

- register: `diagnosis` | subject: `local_controller` | type: `replan_instability`
- refs: `diag:C1.replan_count`

| R1 | R2 | R3 | R5 |
|---|---|---|---|
| wrong | no | all | n/a |

### 023 - **khong de xuat gi**

> every proposal was refused before submission (quantity_in_statement); an abstention with a reason beats a claim the platform would refuse

| R1 | R2 | R3 | R5 |
|---|---|---|---|
| n/a | n/a | n/a | should_have |

---

# Episode `3e3973656a9d`

*cluster: doorway_v1_full_stack_selection_c23dddbd | vai: cardless*

<details open><summary><b>PACKET</b></summary>

**Phan quyet**: undecidable | thang: `-` | thua: `-`

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

### 024

> Local_controller of C5 experienced a stuck_cluster that paused the run for several seconds

- register: `diagnosis` | subject: `local_controller` | type: `candidate_latency_attribution`
- refs: `obs:stuck_cluster:C5@3e3973656a9d`

| R1 | R2 | R3 | R5 |
|---|---|---|---|
| wrong | yes | none | n/a |

### 025

> The local_controller of C5 performed a replan, showing replan_instability.

- register: `diagnosis` | subject: `local_controller` | type: `replan_instability`
- refs: `diag:C5.replan_count`

| R1 | R2 | R3 | R5 |
|---|---|---|---|
| wrong | no | all | n/a |

### 026

> C5 had higher observed latency than C1, pointing to candidate_latency_attribution.

- register: `diagnosis` | subject: `runtime_transport` | type: `candidate_latency_attribution`
- refs: `diag:C5.p99_latency_ms`, `diag:C1.p99_latency_ms`

| R1 | R2 | R3 | R5 |
|---|---|---|---|
| wrong | no | all | n/a |

### 027 - **khong de xuat gi**

> every proposal was refused before submission (quantity_in_statement); an abstention with a reason beats a claim the platform would refuse

| R1 | R2 | R3 | R5 |
|---|---|---|---|
| n/a | n/a | n/a | should_have |

### 028

> The global_planner of C5 issued a replan

- register: `diagnosis` | subject: `global_planner` | type: `replan_instability`
- refs: `diag:C5.replan_count`

| R1 | R2 | R3 | R5 |
|---|---|---|---|
| wrong | yes | all | n/a |

### 029 - **khong de xuat gi**

> every proposal was refused before submission (quantity_in_statement); an abstention with a reason beats a claim the platform would refuse

| R1 | R2 | R3 | R5 |
|---|---|---|---|
| n/a | n/a | n/a | should_have |

### 030 - **khong de xuat gi**

> every proposal was refused before submission (quantity_in_statement); an abstention with a reason beats a claim the platform would refuse

| R1 | R2 | R3 | R5 |
|---|---|---|---|
| n/a | n/a | n/a | should_have |

### 031 - **khong de xuat gi**

> every proposal was refused before submission (quantity_in_statement); an abstention with a reason beats a claim the platform would refuse

| R1 | R2 | R3 | R5 |
|---|---|---|---|
| n/a | n/a | n/a | should_have |

### 032

> Local_controller of C1 did not require any replanning during the run

- register: `diagnosis` | subject: `local_controller` | type: `replan_instability`
- refs: `diag:C1.replan_count`

| R1 | R2 | R3 | R5 |
|---|---|---|---|
| wrong | no | all | n/a |

### 033 - **khong de xuat gi**

> every proposal was refused before submission (quantity_in_statement); an abstention with a reason beats a claim the platform would refuse

| R1 | R2 | R3 | R5 |
|---|---|---|---|
| n/a | n/a | n/a | should_have |

### 034

> The local_controller of C5 experienced a stuck cluster, indicating local_minimum_entrapment.

- register: `diagnosis` | subject: `local_controller` | type: `local_minimum_entrapment`
- refs: `obs:stuck_cluster:C5@3e3973656a9d`

| R1 | R2 | R3 | R5 |
|---|---|---|---|
| holds | yes | all | n/a |

### 035

> The local_controller of C5 experienced a stuck cluster

- register: `diagnosis` | subject: `local_controller` | type: `local_minimum_entrapment`
- refs: `obs:stuck_cluster:C5@3e3973656a9d`

| R1 | R2 | R3 | R5 |
|---|---|---|---|
| holds | yes | all | n/a |

### 036 - **khong de xuat gi**

> every proposal was refused before submission (quantity_in_statement); an abstention with a reason beats a claim the platform would refuse

| R1 | R2 | R3 | R5 |
|---|---|---|---|
| n/a | n/a | n/a | should_have |

---

# Episode `3f3271808c9d`

*cluster: doorway_v1_full_stack_selection_c23dddbd | vai: cardless*

<details open><summary><b>PACKET</b></summary>

**Phan quyet**: undecidable | thang: `-` | thua: `-`

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

### 037

> local_controller of C5 had to replan in this episode

- register: `diagnosis` | subject: `local_controller` | type: `replan_instability`
- refs: `diag:C5.replan_count`

| R1 | R2 | R3 | R5 |
|---|---|---|---|
| wrong | no | all | n/a |

### 038

> The local_controller of C5 experienced a stuck_cluster in this episode, indicating local_minimum_entrapment.

- register: `diagnosis` | subject: `local_controller` | type: `local_minimum_entrapment`
- refs: `fact:candidate:C5.local_controller`, `obs:stuck_cluster:C5@3f3271808c9d`

| R1 | R2 | R3 | R5 |
|---|---|---|---|
| holds | yes | all | n/a |

### 039

> local_controller of C5 experienced a stuck cluster in this episode

- register: `diagnosis` | subject: `local_controller` | type: `local_minimum_entrapment`
- refs: `obs:stuck_cluster:C5@3f3271808c9d`

| R1 | R2 | R3 | R5 |
|---|---|---|---|
| holds | yes | all | n/a |

### 040 - **khong de xuat gi**

> every proposal was refused before submission (quantity_in_statement); an abstention with a reason beats a claim the platform would refuse

| R1 | R2 | R3 | R5 |
|---|---|---|---|
| n/a | n/a | n/a | should_have |

### 041 - **khong de xuat gi**

> every proposal was refused before submission (quantity_in_statement); an abstention with a reason beats a claim the platform would refuse

| R1 | R2 | R3 | R5 |
|---|---|---|---|
| n/a | n/a | n/a | should_have |

### 042

> runtime_transport of C5 took longer in this episode

- register: `diagnosis` | subject: `runtime_transport` | type: `candidate_latency_attribution`
- refs: `diag:C5.travel_time_s`

| R1 | R2 | R3 | R5 |
|---|---|---|---|
| wrong | no | none | n/a |

### 043

> runtime_transport of C1 took less time in this episode

- register: `diagnosis` | subject: `runtime_transport` | type: `candidate_latency_attribution`
- refs: `diag:C1.travel_time_s`

| R1 | R2 | R3 | R5 |
|---|---|---|---|
| wrong | no | none | n/a |

### 044 - **khong de xuat gi**

> every proposal was refused before submission (quantity_in_statement); an abstention with a reason beats a claim the platform would refuse

| R1 | R2 | R3 | R5 |
|---|---|---|---|
| n/a | n/a | n/a | should_have |

### 045 - **khong de xuat gi**

> every proposal was refused before submission (quantity_in_statement); an abstention with a reason beats a claim the platform would refuse

| R1 | R2 | R3 | R5 |
|---|---|---|---|
| n/a | n/a | n/a | should_have |

### 046 - **khong de xuat gi**

> every proposal was refused before submission (quantity_in_statement); an abstention with a reason beats a claim the platform would refuse

| R1 | R2 | R3 | R5 |
|---|---|---|---|
| n/a | n/a | n/a | should_have |

### 047

> The local_controller of C5 triggered a replan in this episode, indicating replan_instability.

- register: `diagnosis` | subject: `local_controller` | type: `replan_instability`
- refs: `fact:candidate:C5.local_controller`, `diag:C5.replan_count`

| R1 | R2 | R3 | R5 |
|---|---|---|---|
| wrong | no | all | n/a |

### 048

> The local_controller of C5 experienced a stuck cluster indicative of local minimum entrapment

- register: `diagnosis` | subject: `local_controller` | type: `local_minimum_entrapment`
- refs: `obs:stuck_cluster:C5@3f3271808c9d`

| R1 | R2 | R3 | R5 |
|---|---|---|---|
| holds | yes | all | n/a |

### 049 - **khong de xuat gi**

> Neither candidate lost this episode; both succeeded with no decisive mechanism to contrast.

| R1 | R2 | R3 | R5 |
|---|---|---|---|
| n/a | n/a | n/a | should_have |

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

### 050

> The local_controller on C5 experienced a local_minimum_entrapment, leading to multiple stops and eventual failure, while C1 did not.

- register: `diagnosis` | subject: `local_controller` | type: `local_minimum_entrapment`
- refs: `contrast:detection_only_on_loser:2`
- contract: `contrast_support`, `subject_match`, `polarity_match`

| R1 | R2 | R3 | R5 |
|---|---|---|---|
| holds | yes | all | n/a |

### 051

> The local_controller on C5 got stuck in a cluster, trapping it in a local minimum and preventing progress

- register: `contrast` | subject: `local_controller` | type: `local_minimum_entrapment`
- refs: `contrast:detection_only_on_loser:2`, `obs:stuck_cluster:C5@4ec011c9a0c3`
- contract: `contrast_support`, `occurrence_evidence`, `subject_match`, `polarity_match`

| R1 | R2 | R3 | R5 |
|---|---|---|---|
| holds | yes | all | n/a |

### 052 - **khong de xuat gi**

> every proposal was refused before submission (quantity_in_statement); an abstention with a reason beats a claim the platform would refuse

| R1 | R2 | R3 | R5 |
|---|---|---|---|
| n/a | n/a | n/a | should_have |

### 053

> The local_controller encountered a local minimum, leading to a stuck_cluster that stopped C5 multiple times and delayed progress

- register: `diagnosis` | subject: `local_controller` | type: `local_minimum_entrapment`
- refs: `contrast:detection_only_on_loser:2`
- contract: `contrast_support`, `subject_match`, `polarity_match`

| R1 | R2 | R3 | R5 |
|---|---|---|---|
| holds | yes | all | n/a |

### 054

> local_controller experienced a stuck_cluster on C5 but not on C1, causing C5 to stall and C1 to reach the goal first

- register: `diagnosis` | subject: `local_controller` | type: `local_minimum_entrapment`
- refs: `contrast:detection_only_on_loser:2`
- contract: `contrast_support`, `subject_match`, `polarity_match`

| R1 | R2 | R3 | R5 |
|---|---|---|---|
| holds | yes | all | n/a |

### 055

> The global_planner on C5 performed a replan_storm with multiple replans, indicating unstable replanning

- register: `diagnosis` | subject: `global_planner` | type: `replan_instability`
- refs: `contrast:detection_only_on_loser:1`

| R1 | R2 | R3 | R5 |
|---|---|---|---|
| holds | yes | all | n/a |

### 056

> local_controller experienced local minimum entrapment on the losing side in this episode, which did not occur on the winning side

- register: `diagnosis` | subject: `local_controller` | type: `local_minimum_entrapment`
- refs: `contrast:component_differs:3`, `obs:stuck_cluster:C5@4ec011c9a0c3`
- contract: `occurrence_evidence`, `subject_match`, `polarity_match`

| R1 | R2 | R3 | R5 |
|---|---|---|---|
| holds | yes | all | n/a |

### 057

> The local_controller component of C5 experienced a stuck_cluster, indicating a local minimum entrapment that contributed to its loss.

- register: `diagnosis` | subject: `local_controller` | type: `local_minimum_entrapment`
- refs: `contrast:component_differs:3`, `contrast:detection_only_on_loser:2`
- contract: `contrast_support`, `subject_match`, `polarity_match`

| R1 | R2 | R3 | R5 |
|---|---|---|---|
| holds | yes | all | n/a |

### 058

> local_controller encountered local_minimum_entrapment on C5, as indicated by stuck_cluster detection, causing the candidate to stop and lose

- register: `diagnosis` | subject: `local_controller` | type: `local_minimum_entrapment`
- refs: `contrast:detection_only_on_loser:2`
- contract: `contrast_support`, `subject_match`, `polarity_match`

| R1 | R2 | R3 | R5 |
|---|---|---|---|
| holds | yes | all | n/a |

### 059

> global_planner triggered multiple replan_storm events on the losing side, causing repeated replans that slowed its progress

- register: `diagnosis` | subject: `global_planner` | type: `replan_instability`
- refs: `obs:replan_storm:C5@4ec011c9a0c3#1`, `obs:replan_storm:C5@4ec011c9a0c3#2`

| R1 | R2 | R3 | R5 |
|---|---|---|---|
| holds | yes | all | n/a |

### 060

> The local_controller on C5 became entrapped in a stuck cluster indicating local minimum entrapment, causing C5 to stop and fail while C1 did not

- register: `diagnosis` | subject: `local_controller` | type: `local_minimum_entrapment`
- refs: `contrast:component_differs:3`, `contrast:detection_only_on_loser:2`
- contract: `contrast_support`, `subject_match`, `polarity_match`

| R1 | R2 | R3 | R5 |
|---|---|---|---|
| holds | yes | all | n/a |

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

### 061 - **khong de xuat gi**

> every proposal was refused before submission (quantity_in_statement); an abstention with a reason beats a claim the platform would refuse

| R1 | R2 | R3 | R5 |
|---|---|---|---|
| n/a | n/a | n/a | should_have |

### 062

> C5 experienced a stuck_cluster in this episode causing a temporary halt

- register: `diagnosis` | subject: `local_controller` | type: `component_specific_attribution`
- refs: `obs:stuck_cluster:C5@501a98d1fd9a`

| R1 | R2 | R3 | R5 |
|---|---|---|---|
| holds | yes | all | n/a |

### 063 - **khong de xuat gi**

> every proposal was refused before submission (quantity_in_statement); an abstention with a reason beats a claim the platform would refuse

| R1 | R2 | R3 | R5 |
|---|---|---|---|
| n/a | n/a | n/a | should_have |

### 064

> local_controller of C5 performed a replan once in this episode

- register: `diagnosis` | subject: `local_controller` | type: `replan_instability`
- refs: `diag:C5.replan_count`

| R1 | R2 | R3 | R5 |
|---|---|---|---|
| wrong | no | all | n/a |

### 065

> The local_controller_config of C5 differs from that of C1

- register: `diagnosis` | subject: `local_controller` | type: `component_specific_attribution`
- refs: `fact:candidate:C1.local_controller_config`, `fact:candidate:C5.local_controller_config`

| R1 | R2 | R3 | R5 |
|---|---|---|---|
| holds | no | all | n/a |

### 066

> local_controller_config of C1 refused to maintain clearance from obstacles

- register: `diagnosis` | subject: `local_controller` | type: `clearance_refusal`
- refs: `contrast:component_differs:1`
- contract: `subject_match`, `polarity_match`

| R1 | R2 | R3 | R5 |
|---|---|---|---|
| plausible_other | no | none | n/a |

### 067

> The local_controller C3 of the losing candidate C1 guided the robot closer to obstacles than the local_controller C6 of the winning candidate C5, resulting in the lower minimum clearance

- register: `diagnosis` | subject: `local_controller` | type: `component_specific_attribution`
- refs: `contrast:component_differs:1`, `contrast:outcome_differs:3`

| R1 | R2 | R3 | R5 |
|---|---|---|---|
| plausible_other | yes | all | n/a |

### 068 - **khong de xuat gi**

> every proposal was refused before submission (quantity_in_statement); an abstention with a reason beats a claim the platform would refuse

| R1 | R2 | R3 | R5 |
|---|---|---|---|
| n/a | n/a | n/a | should_have |

### 069

> A stuck_cluster was detected on C5 in this episode, indicating it encountered a local minimum entrapment

- register: `diagnosis` | subject: `local_controller` | type: `local_minimum_entrapment`
- refs: `obs:stuck_cluster:C5@501a98d1fd9a`

| R1 | R2 | R3 | R5 |
|---|---|---|---|
| holds | yes | all | n/a |

### 070

> the local_controller_config difference led C1 to maintain a smaller clearance margin than C5

- register: `diagnosis` | subject: `local_controller` | type: `component_specific_attribution`
- refs: `contrast:component_differs:1`, `diag:C1.min_clearance`
- contract: `occurrence_evidence`, `subject_match`

| R1 | R2 | R3 | R5 |
|---|---|---|---|
| plausible_other | no | all | n/a |

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

### 071

> local_controller of C5 performed a replan in this episode

- register: `diagnosis` | subject: `local_controller` | type: `replan_instability`
- refs: `diag:C5.replan_count`

| R1 | R2 | R3 | R5 |
|---|---|---|---|
| wrong | no | all | n/a |

### 072 - **khong de xuat gi**

> every proposal was refused before submission (quantity_in_statement); an abstention with a reason beats a claim the platform would refuse

| R1 | R2 | R3 | R5 |
|---|---|---|---|
| n/a | n/a | n/a | should_have |

### 073 - **khong de xuat gi**

> every proposal was refused before submission (wording_above_associated); an abstention with a reason beats a claim the platform would refuse

| R1 | R2 | R3 | R5 |
|---|---|---|---|
| n/a | n/a | n/a | should_have |

### 074

> Stuck cluster detected on C5 reveals that its local_controller got trapped in a local minimum during this episode

- register: `contrast` | subject: `local_controller` | type: `local_minimum_entrapment`
- refs: `contrast:detection_only_on_loser:2`, `obs:stuck_cluster:C5@50f9cae5941c`
- contract: `contrast_support`, `occurrence_evidence`, `subject_match`, `polarity_match`

| R1 | R2 | R3 | R5 |
|---|---|---|---|
| holds | yes | all | n/a |

### 075 - **khong de xuat gi**

> every proposal was refused before submission (quantity_in_statement); an abstention with a reason beats a claim the platform would refuse

| R1 | R2 | R3 | R5 |
|---|---|---|---|
| n/a | n/a | n/a | should_have |

### 076

> The local_controller of C5 experienced local minimum entrapment causing it to stop and slow down relative to C1

- register: `diagnosis` | subject: `local_controller` | type: `local_minimum_entrapment`
- refs: `contrast:detection_only_on_loser:2`
- contract: `contrast_support`, `subject_match`, `polarity_match`

| R1 | R2 | R3 | R5 |
|---|---|---|---|
| holds | yes | all | n/a |

### 077 - **khong de xuat gi**

> every proposal was refused before submission (quantity_in_statement); an abstention with a reason beats a claim the platform would refuse

| R1 | R2 | R3 | R5 |
|---|---|---|---|
| n/a | n/a | n/a | should_have |

### 078

> local_controller on C5 experienced replan_instability, as evidenced by stuck_cluster firing on C5 and not on C1, causing C5 to stop without progress and lose time relative to C1

- register: `diagnosis` | subject: `local_controller` | type: `replan_instability`
- refs: `contrast:component_differs:3`, `contrast:detection_only_on_loser:2`
- contract: `contrast_support`, `subject_match`, `polarity_match`

| R1 | R2 | R3 | R5 |
|---|---|---|---|
| wrong | yes | none | n/a |

### 079 - **khong de xuat gi**

> every proposal was refused before submission (quantity_in_statement, wording_above_associated); an abstention with a reason beats a claim the platform would refuse

| R1 | R2 | R3 | R5 |
|---|---|---|---|
| n/a | n/a | n/a | should_have |

### 080

> local_controller of C5 experienced local minimum entrapment in this episode

- register: `diagnosis` | subject: `local_controller` | type: `local_minimum_entrapment`
- refs: `contrast:component_differs:3`
- contract: `subject_match`, `polarity_match`

| R1 | R2 | R3 | R5 |
|---|---|---|---|
| holds | yes | none | n/a |

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

### 081

> The local_controller of C5 became entrapped in a local minimum, as indicated by a stuck_cluster detection not seen on C1.

- register: `diagnosis` | subject: `local_controller` | type: `local_minimum_entrapment`
- refs: `contrast:detection_only_on_loser:2`
- contract: `contrast_support`, `subject_match`, `polarity_match`

| R1 | R2 | R3 | R5 |
|---|---|---|---|
| holds | yes | all | n/a |

### 082

> The local_controller on C5 experienced a stuck_cluster event (local minimum entrapment), causing multiple stops and delaying C5, whereas the local_controller on C1 did not exhibit such entrapment

- register: `diagnosis` | subject: `local_controller` | type: `local_minimum_entrapment`
- refs: `contrast:detection_only_on_loser:2`
- contract: `contrast_support`, `subject_match`, `polarity_match`

| R1 | R2 | R3 | R5 |
|---|---|---|---|
| holds | yes | all | n/a |

### 083

> local_controller became trapped in a local minimum on C5, as indicated by stuck_cluster firing only on the loser

- register: `diagnosis` | subject: `local_controller` | type: `local_minimum_entrapment`
- refs: `contrast:component_differs:3`, `contrast:detection_only_on_loser:2`
- contract: `contrast_support`, `subject_match`, `polarity_match`

| R1 | R2 | R3 | R5 |
|---|---|---|---|
| holds | yes | all | n/a |

### 084

> The global_planner on C5 triggered a replan_storm, issuing multiple replans that did not occur on C1 and contributing to increased travel time for C5

- register: `diagnosis` | subject: `global_planner` | type: `replan_instability`
- refs: `contrast:detection_only_on_loser:1`

| R1 | R2 | R3 | R5 |
|---|---|---|---|
| holds | yes | all | n/a |

### 085 - **khong de xuat gi**

> every proposal was refused before submission (quantity_in_statement); an abstention with a reason beats a claim the platform would refuse

| R1 | R2 | R3 | R5 |
|---|---|---|---|
| n/a | n/a | n/a | should_have |

### 086 - **khong de xuat gi**

> every proposal was refused before submission (quantity_in_statement, wording_above_associated); an abstention with a reason beats a claim the platform would refuse

| R1 | R2 | R3 | R5 |
|---|---|---|---|
| n/a | n/a | n/a | should_have |

### 087

> The local_controller experienced a stuck_cluster on the losing run, trapping the robot and causing it to stop for seconds.

- register: `contrast` | subject: `local_controller` | type: `local_minimum_entrapment`
- refs: `contrast:detection_only_on_loser:2`, `obs:stuck_cluster:C5@6637b6e1f8e1`
- contract: `contrast_support`, `occurrence_evidence`, `subject_match`, `polarity_match`

| R1 | R2 | R3 | R5 |
|---|---|---|---|
| holds | yes | all | n/a |

### 088

> The global_planner on C5 experienced a replan instability ‘replan_storm’ in this episode, issuing multiple replans before C5 diverged

- register: `diagnosis` | subject: `global_planner` | type: `replan_instability`
- refs: `contrast:detection_only_on_loser:1`

| R1 | R2 | R3 | R5 |
|---|---|---|---|
| holds | yes | all | n/a |

### 089

> The global_planner on the losing candidate underwent a replan_storm, triggering multiple replans that indicate instability.

- register: `diagnosis` | subject: `global_planner` | type: `replan_instability`
- refs: `contrast:detection_only_on_loser:1`

| R1 | R2 | R3 | R5 |
|---|---|---|---|
| holds | yes | all | n/a |

### 090 - **khong de xuat gi**

> every proposal was refused before submission (quantity_in_statement); an abstention with a reason beats a claim the platform would refuse

| R1 | R2 | R3 | R5 |
|---|---|---|---|
| n/a | n/a | n/a | should_have |

### 091

> The local_controller on C5 became trapped in a local minimum during this episode, causing C5 to stop repeatedly and lose to C1

- register: `diagnosis` | subject: `local_controller` | type: `local_minimum_entrapment`
- refs: `contrast:detection_only_on_loser:2`
- contract: `contrast_support`, `subject_match`, `polarity_match`

| R1 | R2 | R3 | R5 |
|---|---|---|---|
| holds | yes | all | n/a |

---

# Episode `685501eb617d`

*cluster: doorway_v1_full_stack_selection_c23dddbd | vai: cardless*

<details open><summary><b>PACKET</b></summary>

**Phan quyet**: undecidable | thang: `-` | thua: `-`

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

### 092

> Candidate C5 used a different local_controller (C6) than C1 (C3).

- register: `diagnosis` | subject: `local_controller` | type: `component_specific_attribution`
- refs: `fact:candidate:C5.local_controller`, `fact:candidate:C1.local_controller`

| R1 | R2 | R3 | R5 |
|---|---|---|---|
| holds | yes | all | n/a |

### 093 - **khong de xuat gi**

> every proposal was refused before submission (quantity_in_statement); an abstention with a reason beats a claim the platform would refuse

| R1 | R2 | R3 | R5 |
|---|---|---|---|
| n/a | n/a | n/a | should_have |

### 094 - **khong de xuat gi**

> every proposal was refused before submission (quantity_in_statement); an abstention with a reason beats a claim the platform would refuse

| R1 | R2 | R3 | R5 |
|---|---|---|---|
| n/a | n/a | n/a | should_have |

### 095 - **khong de xuat gi**

> every proposal was refused before submission (quantity_in_statement); an abstention with a reason beats a claim the platform would refuse

| R1 | R2 | R3 | R5 |
|---|---|---|---|
| n/a | n/a | n/a | should_have |

### 096

> The local_controller of C5 experienced a stuck_cluster event indicative of local minimum entrapment in this episode

- register: `diagnosis` | subject: `local_controller` | type: `local_minimum_entrapment`
- refs: `obs:stuck_cluster:C5@685501eb617d`

| R1 | R2 | R3 | R5 |
|---|---|---|---|
| holds | yes | all | n/a |

### 097 - **khong de xuat gi**

> every proposal was refused before submission (quantity_in_statement); an abstention with a reason beats a claim the platform would refuse

| R1 | R2 | R3 | R5 |
|---|---|---|---|
| n/a | n/a | n/a | should_have |

### 098

> Candidate C5 experienced a stuck_cluster causing it to stop for seconds.

- register: `diagnosis` | subject: `local_controller` | type: `local_minimum_entrapment`
- refs: `obs:stuck_cluster:C5@685501eb617d`, `obs:stuck_cluster:C5@685501eb617d/stopped_seconds`

| R1 | R2 | R3 | R5 |
|---|---|---|---|
| holds | yes | all | n/a |

### 099 - **khong de xuat gi**

> every proposal was refused before submission (quantity_in_statement); an abstention with a reason beats a claim the platform would refuse

| R1 | R2 | R3 | R5 |
|---|---|---|---|
| n/a | n/a | n/a | should_have |

### 100

> The local_controller of C5 triggered a stuck_cluster detection in this episode, halting movement.

- register: `diagnosis` | subject: `local_controller` | type: `component_specific_attribution`
- refs: `obs:stuck_cluster:C5@685501eb617d`

| R1 | R2 | R3 | R5 |
|---|---|---|---|
| holds | yes | all | n/a |

### 101 - **khong de xuat gi**

> every proposal was refused before submission (quantity_in_statement); an abstention with a reason beats a claim the platform would refuse

| R1 | R2 | R3 | R5 |
|---|---|---|---|
| n/a | n/a | n/a | should_have |

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

### 102

> runtime_transport of C1 experienced a latency_spike in this episode

- register: `diagnosis` | subject: `runtime_transport` | type: `candidate_latency_attribution`
- refs: `obs:latency_spike:C1@76db6b6c6ca1`

| R1 | R2 | R3 | R5 |
|---|---|---|---|
| wrong | no | all | n/a |

### 103

> local_controller performed a replan on C1 in this episode

- register: `diagnosis` | subject: `local_controller` | type: `replan_instability`
- refs: `diag:C1.replan_count`

| R1 | R2 | R3 | R5 |
|---|---|---|---|
| wrong | no | all | n/a |

### 104

> Candidate C1 experienced a significant latency spike in its local_controller.

- register: `diagnosis` | subject: `local_controller` | type: `candidate_latency_attribution`
- refs: `obs:latency_spike:C1@76db6b6c6ca1`

| R1 | R2 | R3 | R5 |
|---|---|---|---|
| wrong | no | all | n/a |

### 105

> Candidate C1 initiated a replanning event once during the episode.

- register: `diagnosis` | subject: `global_planner` | type: `replan_instability`
- refs: `diag:C1.replan_count`

| R1 | R2 | R3 | R5 |
|---|---|---|---|
| wrong | yes | all | n/a |

### 106

> local_controller of C1 experienced a latency spike in this episode

- register: `diagnosis` | subject: `local_controller` | type: `candidate_latency_attribution`
- refs: `obs:latency_spike:C1@76db6b6c6ca1`

| R1 | R2 | R3 | R5 |
|---|---|---|---|
| wrong | no | all | n/a |

### 107

> local_controller experienced a stuck cluster on C1 in this episode

- register: `diagnosis` | subject: `local_controller` | type: `local_minimum_entrapment`
- refs: `obs:stuck_cluster:C1@76db6b6c6ca1`

| R1 | R2 | R3 | R5 |
|---|---|---|---|
| holds | yes | all | n/a |

### 108

> local_controller of C1 experienced a stuck_cluster, indicating local minimum entrapment in this episode

- register: `diagnosis` | subject: `local_controller` | type: `local_minimum_entrapment`
- refs: `obs:stuck_cluster:C1@76db6b6c6ca1`

| R1 | R2 | R3 | R5 |
|---|---|---|---|
| holds | yes | all | n/a |

### 109 - **khong de xuat gi**

> every proposal was refused before submission (quantity_in_statement); an abstention with a reason beats a claim the platform would refuse

| R1 | R2 | R3 | R5 |
|---|---|---|---|
| n/a | n/a | n/a | should_have |

### 110

> local_controller experienced a stuck cluster causing the robot to stop in this episode for C1

- register: `diagnosis` | subject: `local_controller` | type: `local_minimum_entrapment`
- refs: `obs:stuck_cluster:C1@76db6b6c6ca1`

| R1 | R2 | R3 | R5 |
|---|---|---|---|
| holds | yes | all | n/a |

### 111

> the runtime_transport of C1 experienced a latency spike during this episode

- register: `diagnosis` | subject: `runtime_transport` | type: `candidate_latency_attribution`
- refs: `obs:latency_spike:C1@76db6b6c6ca1`, `obs:latency_spike:C1@76db6b6c6ca1/peak_latency_ms`

| R1 | R2 | R3 | R5 |
|---|---|---|---|
| wrong | no | all | n/a |

### 112

> local_controller of C1 experienced a stuck cluster during this episode

- register: `diagnosis` | subject: `local_controller` | type: `component_specific_attribution`
- refs: `obs:stuck_cluster:C1@76db6b6c6ca1`

| R1 | R2 | R3 | R5 |
|---|---|---|---|
| holds | yes | all | n/a |

### 113

> the local_controller of C1 encountered a stuck_cluster that halted progress

- register: `diagnosis` | subject: `local_controller` | type: `local_minimum_entrapment`
- refs: `obs:stuck_cluster:C1@76db6b6c6ca1`, `obs:stuck_cluster:C1@76db6b6c6ca1/stopped_seconds`

| R1 | R2 | R3 | R5 |
|---|---|---|---|
| holds | yes | all | n/a |

### 114 - **khong de xuat gi**

> every proposal was refused before submission (quantity_in_statement); an abstention with a reason beats a claim the platform would refuse

| R1 | R2 | R3 | R5 |
|---|---|---|---|
| n/a | n/a | n/a | should_have |

### 115

> local_controller of C1 encountered a stuck cluster in this episode

- register: `diagnosis` | subject: `local_controller` | type: `local_minimum_entrapment`
- refs: `obs:stuck_cluster:C1@76db6b6c6ca1`

| R1 | R2 | R3 | R5 |
|---|---|---|---|
| holds | yes | all | n/a |

### 116

> runtime_transport experienced a latency spike on C1 in this episode

- register: `diagnosis` | subject: `runtime_transport` | type: `candidate_latency_attribution`
- refs: `obs:latency_spike:C1@76db6b6c6ca1`

| R1 | R2 | R3 | R5 |
|---|---|---|---|
| wrong | no | all | n/a |

### 117

> local_controller of C1 experienced a latency spike during this episode

- register: `diagnosis` | subject: `local_controller` | type: `component_specific_attribution`
- refs: `obs:latency_spike:C1@76db6b6c6ca1`

| R1 | R2 | R3 | R5 |
|---|---|---|---|
| holds | no | all | n/a |

### 118

> local_controller exhibited a latency spike in this episode for C1

- register: `diagnosis` | subject: `local_controller` | type: `candidate_latency_attribution`
- refs: `obs:latency_spike:C1@76db6b6c6ca1`

| R1 | R2 | R3 | R5 |
|---|---|---|---|
| wrong | no | all | n/a |

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

### 119

> local_controller on C5 encountered local minimum entrapment (stuck_cluster) in this episode but local_controller on C1 did not

- register: `diagnosis` | subject: `local_controller` | type: `local_minimum_entrapment`
- refs: `contrast:component_differs:3`, `obs:stuck_cluster:C5@7c2cc3d5019f`
- contract: `occurrence_evidence`, `subject_match`, `polarity_match`

| R1 | R2 | R3 | R5 |
|---|---|---|---|
| holds | yes | all | n/a |

### 120

> The local_controller on C5 became stuck in a local minimum in this episode, as shown by the stuck_cluster detection.

- register: `diagnosis` | subject: `local_controller` | type: `local_minimum_entrapment`
- refs: `contrast:component_differs:3`, `obs:stuck_cluster:C5@7c2cc3d5019f`
- contract: `occurrence_evidence`, `subject_match`, `polarity_match`

| R1 | R2 | R3 | R5 |
|---|---|---|---|
| holds | yes | all | n/a |

### 121

> local_controller on C5 experienced local minimum entrapment, as indicated by the stuck_cluster detector that fired on C5 and not on C1, slowing C5 and causing the outcome difference

- register: `diagnosis` | subject: `local_controller` | type: `local_minimum_entrapment`
- refs: `contrast:component_differs:3`, `contrast:detection_only_on_loser:2`
- contract: `contrast_support`, `subject_match`, `polarity_match`

| R1 | R2 | R3 | R5 |
|---|---|---|---|
| holds | yes | all | n/a |

### 122

> local_controller encountered a local minimum and became stuck on C5 in this episode

- register: `contrast` | subject: `local_controller` | type: `local_minimum_entrapment`
- refs: `contrast:detection_only_on_loser:2`, `obs:stuck_cluster:C5@7c2cc3d5019f`
- contract: `contrast_support`, `occurrence_evidence`, `subject_match`, `polarity_match`

| R1 | R2 | R3 | R5 |
|---|---|---|---|
| holds | yes | all | n/a |

### 123

> local_controller on C5 experienced local minimum entrapment, as indicated by stuck_cluster firing, which did not occur on C1

- register: `diagnosis` | subject: `local_controller` | type: `local_minimum_entrapment`
- refs: `contrast:detection_only_on_loser:2`
- contract: `contrast_support`, `subject_match`, `polarity_match`

| R1 | R2 | R3 | R5 |
|---|---|---|---|
| holds | yes | all | n/a |

### 124

> the local_controller_config difference on C5 may have contributed to its difficulty by providing parameters that interact poorly with the route geometry

- register: `diagnosis` | subject: `local_controller` | type: `component_specific_attribution`
- refs: `contrast:component_differs:3`

| R1 | R2 | R3 | R5 |
|---|---|---|---|
| plausible_other | no | none | n/a |

### 125

> local_controller of C5 experienced a local minimum entrapment, as shown by stuck_cluster firing on C5 and not on C1 in this episode, causing C5 to stop repeatedly and lose time

- register: `contrast` | subject: `local_controller` | type: `local_minimum_entrapment`
- refs: `contrast:detection_only_on_loser:2`, `obs:stuck_cluster:C5@7c2cc3d5019f`
- contract: `contrast_support`, `occurrence_evidence`, `subject_match`, `polarity_match`

| R1 | R2 | R3 | R5 |
|---|---|---|---|
| holds | yes | all | n/a |

### 126

> The local_controller of C5 suffered a local minimum entrapment that manifested as a stuck_cluster on that candidate in this episode, delaying it

- register: `diagnosis` | subject: `local_controller` | type: `local_minimum_entrapment`
- refs: `contrast:detection_only_on_loser:2`
- contract: `contrast_support`, `subject_match`, `polarity_match`

| R1 | R2 | R3 | R5 |
|---|---|---|---|
| holds | yes | all | n/a |

### 127 - **khong de xuat gi**

> every proposal was refused before submission (quantity_in_statement); an abstention with a reason beats a claim the platform would refuse

| R1 | R2 | R3 | R5 |
|---|---|---|---|
| n/a | n/a | n/a | should_have |

### 128

> global_planner of C5 fired a replan_storm, triggering multiple replans in this episode

- register: `diagnosis` | subject: `global_planner` | type: `replan_instability`
- refs: `contrast:detection_only_on_loser:1`

| R1 | R2 | R3 | R5 |
|---|---|---|---|
| holds | yes | all | n/a |

---

# Episode `a646b0f7b414`

*cluster: doorway_v1_full_stack_selection_c23dddbd | vai: cardless*

<details open><summary><b>PACKET</b></summary>

**Phan quyet**: undecidable | thang: `-` | thua: `-`

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

### 129

> local_controller of C5 experienced a local minimum entrapment detected by a stuck cluster

- register: `diagnosis` | subject: `local_controller` | type: `local_minimum_entrapment`
- refs: `obs:stuck_cluster:C5@a646b0f7b414`, `obs:stuck_cluster:C5@a646b0f7b414/stopped_seconds`

| R1 | R2 | R3 | R5 |
|---|---|---|---|
| holds | yes | all | n/a |

### 130

> The local_controller of C5 became trapped in a stuck_cluster for an extended period

- register: `diagnosis` | subject: `local_controller` | type: `local_minimum_entrapment`
- refs: `obs:stuck_cluster:C5@a646b0f7b414`, `obs:stuck_cluster:C5@a646b0f7b414/stopped_seconds`

| R1 | R2 | R3 | R5 |
|---|---|---|---|
| holds | yes | all | n/a |

### 131

> The local_controller of C5 experienced a stuck cluster during the episode

- register: `diagnosis` | subject: `local_controller` | type: `component_specific_attribution`
- refs: `obs:stuck_cluster:C5@a646b0f7b414`, `obs:stuck_cluster:C5@a646b0f7b414/stopped_seconds`

| R1 | R2 | R3 | R5 |
|---|---|---|---|
| holds | yes | all | n/a |

### 132

> local_controller experienced a stuck_cluster in this episode

- register: `diagnosis` | subject: `local_controller` | type: `component_specific_attribution`
- refs: `obs:stuck_cluster:C5@a646b0f7b414`

| R1 | R2 | R3 | R5 |
|---|---|---|---|
| holds | yes | all | n/a |

### 133 - **khong de xuat gi**

> every proposal was refused before submission (quantity_in_statement); an abstention with a reason beats a claim the platform would refuse

| R1 | R2 | R3 | R5 |
|---|---|---|---|
| n/a | n/a | n/a | should_have |

### 134 - **khong de xuat gi**

> every proposal was refused before submission (quantity_in_statement, wording_above_associated); an abstention with a reason beats a claim the platform would refuse

| R1 | R2 | R3 | R5 |
|---|---|---|---|
| n/a | n/a | n/a | should_have |

### 135

> local_controller experienced local_minimum_entrapment as evidenced by the stuck_cluster on C5 in this episode

- register: `diagnosis` | subject: `local_controller` | type: `local_minimum_entrapment`
- refs: `obs:stuck_cluster:C5@a646b0f7b414`

| R1 | R2 | R3 | R5 |
|---|---|---|---|
| holds | yes | all | n/a |

### 136

> The local_controller of C5 performed multiple replans during this episode

- register: `diagnosis` | subject: `local_controller` | type: `replan_instability`
- refs: `diag:C5.replan_count`

| R1 | R2 | R3 | R5 |
|---|---|---|---|
| wrong | no | all | n/a |

### 137

> The local_controller of C5 experienced a stuck_cluster lasting for an extended period, suggesting local minimum entrapment not seen on C1

- register: `diagnosis` | subject: `local_controller` | type: `local_minimum_entrapment`
- refs: `obs:stuck_cluster:C5@a646b0f7b414`, `obs:stuck_cluster:C5@a646b0f7b414/stopped_seconds`

| R1 | R2 | R3 | R5 |
|---|---|---|---|
| holds | yes | all | n/a |

### 138

> The local_controller for C5 experienced a stuck_cluster in this episode

- register: `diagnosis` | subject: `local_controller` | type: `local_minimum_entrapment`
- refs: `obs:stuck_cluster:C5@a646b0f7b414`

| R1 | R2 | R3 | R5 |
|---|---|---|---|
| holds | yes | all | n/a |

### 139

> global_planner triggered no replans in this episode

- register: `diagnosis` | subject: `global_planner` | type: `component_specific_attribution`
- refs: `diag:C1.replan_count`

| R1 | R2 | R3 | R5 |
|---|---|---|---|
| holds | yes | all | n/a |

### 140

> global_planner triggered multiple replans in this episode

- register: `diagnosis` | subject: `global_planner` | type: `component_specific_attribution`
- refs: `diag:C5.replan_count`

| R1 | R2 | R3 | R5 |
|---|---|---|---|
| holds | yes | all | n/a |

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

### 141 - **khong de xuat gi**

> every proposal was refused before submission (quantity_in_statement); an abstention with a reason beats a claim the platform would refuse

| R1 | R2 | R3 | R5 |
|---|---|---|---|
| n/a | n/a | n/a | should_have |

### 142

> local_controller of C1 did not trigger any replanning during this episode

- register: `diagnosis` | subject: `local_controller` | type: `component_specific_attribution`
- refs: `diag:C1.replan_count`

| R1 | R2 | R3 | R5 |
|---|---|---|---|
| holds | no | all | n/a |

### 143 - **khong de xuat gi**

> every proposal was refused before submission (quantity_in_statement); an abstention with a reason beats a claim the platform would refuse

| R1 | R2 | R3 | R5 |
|---|---|---|---|
| n/a | n/a | n/a | should_have |

### 144 - **khong de xuat gi**

> every proposal was refused before submission (quantity_in_statement); an abstention with a reason beats a claim the platform would refuse

| R1 | R2 | R3 | R5 |
|---|---|---|---|
| n/a | n/a | n/a | should_have |

### 145 - **khong de xuat gi**

> every proposal was refused before submission (quantity_in_statement); an abstention with a reason beats a claim the platform would refuse

| R1 | R2 | R3 | R5 |
|---|---|---|---|
| n/a | n/a | n/a | should_have |

### 146 - **khong de xuat gi**

> every proposal was refused before submission (quantity_in_statement); an abstention with a reason beats a claim the platform would refuse

| R1 | R2 | R3 | R5 |
|---|---|---|---|
| n/a | n/a | n/a | should_have |

### 147 - **khong de xuat gi**

> every proposal was refused before submission (quantity_in_statement); an abstention with a reason beats a claim the platform would refuse

| R1 | R2 | R3 | R5 |
|---|---|---|---|
| n/a | n/a | n/a | should_have |

### 148 - **khong de xuat gi**

> every proposal was refused before submission (quantity_in_statement); an abstention with a reason beats a claim the platform would refuse

| R1 | R2 | R3 | R5 |
|---|---|---|---|
| n/a | n/a | n/a | should_have |

### 149 - **khong de xuat gi**

> every proposal was refused before submission (quantity_in_statement); an abstention with a reason beats a claim the platform would refuse

| R1 | R2 | R3 | R5 |
|---|---|---|---|
| n/a | n/a | n/a | should_have |

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

### 150

> The local_controller of C5 experienced local minimum entrapment, as evidenced by stuck_cluster firing only on C5 in this episode, causing it to stop and lose progress.

- register: `diagnosis` | subject: `local_controller` | type: `local_minimum_entrapment`
- refs: `contrast:detection_only_on_loser:2`
- contract: `contrast_support`, `subject_match`, `polarity_match`

| R1 | R2 | R3 | R5 |
|---|---|---|---|
| holds | yes | all | n/a |

### 151 - **khong de xuat gi**

> every proposal was refused before submission (quantity_in_statement); an abstention with a reason beats a claim the platform would refuse

| R1 | R2 | R3 | R5 |
|---|---|---|---|
| n/a | n/a | n/a | should_have |

### 152 - **khong de xuat gi**

> every proposal was refused before submission (quantity_in_statement); an abstention with a reason beats a claim the platform would refuse

| R1 | R2 | R3 | R5 |
|---|---|---|---|
| n/a | n/a | n/a | should_have |

### 153

> The local_controller encountered local minimum entrapment on C5 that delayed progress and led to failure in this episode.

- register: `diagnosis` | subject: `local_controller` | type: `local_minimum_entrapment`
- refs: `contrast:component_differs:3`, `obs:stuck_cluster:C5@d3265359df38`
- contract: `occurrence_evidence`, `subject_match`, `polarity_match`

| R1 | R2 | R3 | R5 |
|---|---|---|---|
| holds | yes | all | n/a |

### 154

> local_controller on C5 experienced entrapment in a stuck cluster, as shown by stuck_cluster detection that did not occur on C1, causing multiple stops and delaying completion

- register: `diagnosis` | subject: `local_controller` | type: `local_minimum_entrapment`
- refs: `contrast:detection_only_on_loser:2`
- contract: `contrast_support`, `subject_match`, `polarity_match`

| R1 | R2 | R3 | R5 |
|---|---|---|---|
| holds | yes | all | n/a |

### 155 - **khong de xuat gi**

> every proposal was refused before submission (quantity_in_statement); an abstention with a reason beats a claim the platform would refuse

| R1 | R2 | R3 | R5 |
|---|---|---|---|
| n/a | n/a | n/a | should_have |

### 156

> The global_planner experienced replanning storms on C5, executing multiple replans at the same location in this episode.

- register: `diagnosis` | subject: `global_planner` | type: `replan_instability`
- refs: `obs:replan_storm:C5@d3265359df38#1`, `obs:replan_storm:C5@d3265359df38#2`

| R1 | R2 | R3 | R5 |
|---|---|---|---|
| holds | yes | all | n/a |

### 157 - **khong de xuat gi**

> the model proposed nothing this module could build a proposal from

| R1 | R2 | R3 | R5 |
|---|---|---|---|
| n/a | n/a | n/a | should_have |

### 158

> Replan instability in the global_planner led C5 to replan excessively and lose this episode

- register: `diagnosis` | subject: `global_planner` | type: `replan_instability`
- refs: `contrast:detection_only_on_loser:1`
- contract: `contrast_support`, `subject_match`, `polarity_match`

| R1 | R2 | R3 | R5 |
|---|---|---|---|
| holds | yes | all | n/a |

### 159

> global_planner experienced replan instability on C5, manifesting as a replan storm with multiple replans

- register: `diagnosis` | subject: `global_planner` | type: `replan_instability`
- refs: `contrast:detection_only_on_loser:1`

| R1 | R2 | R3 | R5 |
|---|---|---|---|
| holds | yes | all | n/a |

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

### 160 - **khong de xuat gi**

> every proposal was refused before submission (quantity_in_statement); an abstention with a reason beats a claim the platform would refuse

| R1 | R2 | R3 | R5 |
|---|---|---|---|
| n/a | n/a | n/a | should_have |

### 161

> local_controller of C1 experienced a local minimum entrapment (stuck_cluster) in this episode

- register: `diagnosis` | subject: `local_controller` | type: `local_minimum_entrapment`
- refs: `obs:stuck_cluster:C1@d4de2e64507f`

| R1 | R2 | R3 | R5 |
|---|---|---|---|
| holds | yes | all | n/a |

### 162

> The local_controller triggered a stuck_cluster (local minimum entrapment) on C1 but not on C5, causing the losing candidate to delay and have a longer travel time

- register: `diagnosis` | subject: `local_controller` | type: `local_minimum_entrapment`
- refs: `contrast:detection_only_on_loser:1`
- contract: `contrast_support`, `subject_match`, `polarity_match`

| R1 | R2 | R3 | R5 |
|---|---|---|---|
| holds | yes | all | n/a |

### 163

> The local_controller on C1 experienced a local_minimum_entrapment as indicated by the stuck_cluster detection firing only on C1, delaying its progress and causing C5 to complete faster

- register: `diagnosis` | subject: `local_controller` | type: `local_minimum_entrapment`
- refs: `contrast:detection_only_on_loser:1`
- contract: `contrast_support`, `subject_match`, `polarity_match`

| R1 | R2 | R3 | R5 |
|---|---|---|---|
| holds | yes | all | n/a |

### 164

> the difference in local_controller components between C1 and C5 led to a stuck_cluster only on C1 in this episode, delaying C1 relative to C5

- register: `diagnosis` | subject: `local_controller` | type: `component_specific_attribution`
- refs: `contrast:component_differs:2`, `contrast:detection_only_on_loser:1`
- contract: `contrast_support`, `subject_match`

| R1 | R2 | R3 | R5 |
|---|---|---|---|
| holds | yes | all | n/a |

### 165 - **khong de xuat gi**

> every proposal was refused before submission (quantity_in_statement); an abstention with a reason beats a claim the platform would refuse

| R1 | R2 | R3 | R5 |
|---|---|---|---|
| n/a | n/a | n/a | should_have |

### 166 - **khong de xuat gi**

> the model proposed nothing this module could build a proposal from

| R1 | R2 | R3 | R5 |
|---|---|---|---|
| n/a | n/a | n/a | should_have |

### 167 - **khong de xuat gi**

> every proposal was refused before submission (wording_above_associated); an abstention with a reason beats a claim the platform would refuse

| R1 | R2 | R3 | R5 |
|---|---|---|---|
| n/a | n/a | n/a | should_have |

### 168

> The local_controller entered a local minimum entrapment in the losing stack, as indicated by a stuck_cluster detection on C1 that did not occur on C5

- register: `diagnosis` | subject: `local_controller` | type: `local_minimum_entrapment`
- refs: `contrast:component_differs:2`, `obs:stuck_cluster:C1@d4de2e64507f`
- contract: `occurrence_evidence`, `subject_match`, `polarity_match`

| R1 | R2 | R3 | R5 |
|---|---|---|---|
| holds | yes | all | n/a |

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

### 169

> The local_controller on C5 experienced a more severe stuck cluster, stopping longer than C1 and delaying C5 relative to C1

- register: `diagnosis` | subject: `local_controller` | type: `local_minimum_entrapment`
- refs: `contrast:detection_worse_on_loser:2`
- contract: `contrast_support`, `subject_match`, `polarity_match`

| R1 | R2 | R3 | R5 |
|---|---|---|---|
| holds | yes | all | n/a |

### 170

> The C5 local_controller_config failed to maintain clearance causing a near_miss_cluster event that did not occur on C1

- register: `diagnosis` | subject: `local_controller` | type: `clearance_refusal`
- refs: `contrast:component_differs:3`, `obs:near_miss_cluster:C5@e87fc5b937ab`
- contract: `occurrence_evidence`, `subject_match`, `polarity_match`

| R1 | R2 | R3 | R5 |
|---|---|---|---|
| plausible_other | no | all | n/a |

### 171

> In this episode, the local_controller of the losing candidate experienced a local minimum entrapment, as shown by the more severe stuck cluster on C5

- register: `diagnosis` | subject: `local_controller` | type: `local_minimum_entrapment`
- refs: `contrast:component_differs:3`, `contrast:detection_worse_on_loser:2`
- contract: `contrast_support`, `subject_match`, `polarity_match`

| R1 | R2 | R3 | R5 |
|---|---|---|---|
| holds | yes | all | n/a |

### 172 - **khong de xuat gi**

> every proposal was refused before submission (quantity_in_statement); an abstention with a reason beats a claim the platform would refuse

| R1 | R2 | R3 | R5 |
|---|---|---|---|
| n/a | n/a | n/a | should_have |

### 173

> The C5 local_controller led to prolonged local entrapment (worse stuck_cluster) that increased travel time compared to C1

- register: `diagnosis` | subject: `local_controller` | type: `local_minimum_entrapment`
- refs: `contrast:component_differs:3`, `obs:stuck_cluster:C5@e87fc5b937ab`
- contract: `occurrence_evidence`, `subject_match`, `polarity_match`

| R1 | R2 | R3 | R5 |
|---|---|---|---|
| holds | yes | all | n/a |

### 174 - **khong de xuat gi**

> every proposal was refused before submission (no_citation); an abstention with a reason beats a claim the platform would refuse

| R1 | R2 | R3 | R5 |
|---|---|---|---|
| n/a | n/a | n/a | should_have |

### 175

> In this episode, the local_controller_config of the losing candidate triggered a near miss cluster that did not occur on the winner

- register: `diagnosis` | subject: `local_controller` | type: `component_specific_attribution`
- refs: `contrast:component_differs:3`, `contrast:detection_only_on_loser:1`
- contract: `contrast_support`, `subject_match`

| R1 | R2 | R3 | R5 |
|---|---|---|---|
| plausible_other | no | all | n/a |

### 176 - **khong de xuat gi**

> every proposal was refused before submission (quantity_in_statement); an abstention with a reason beats a claim the platform would refuse

| R1 | R2 | R3 | R5 |
|---|---|---|---|
| n/a | n/a | n/a | should_have |

### 177

> local_controller on C5 experienced a more severe stuck cluster, stopping longer in this episode

- register: `diagnosis` | subject: `local_controller` | type: `local_minimum_entrapment`
- refs: `contrast:detection_worse_on_loser:2`

| R1 | R2 | R3 | R5 |
|---|---|---|---|
| holds | yes | all | n/a |

### 178

> local_controller on C5 refused to maintain clearance after detecting a near_miss_cluster

- register: `diagnosis` | subject: `local_controller` | type: `clearance_refusal`
- refs: `obs:near_miss_cluster:C5@e87fc5b937ab`

| R1 | R2 | R3 | R5 |
|---|---|---|---|
| plausible_other | yes | all | n/a |

### 179

> The local_controller of C5 experienced local minimum entrapment, causing it to remain stalled longer than C1

- register: `diagnosis` | subject: `local_controller` | type: `local_minimum_entrapment`
- refs: `contrast:detection_worse_on_loser:2`, `contrast:component_differs:3`
- contract: `contrast_support`, `subject_match`, `polarity_match`

| R1 | R2 | R3 | R5 |
|---|---|---|---|
| holds | yes | all | n/a |

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

### 180

> local_controller of C1 experienced a local_minimum_entrapment, as indicated by the stuck_cluster detector

- register: `diagnosis` | subject: `local_controller` | type: `local_minimum_entrapment`
- refs: `obs:stuck_cluster:C1@fff606f44b13`

| R1 | R2 | R3 | R5 |
|---|---|---|---|
| holds | yes | all | n/a |

### 181 - **khong de xuat gi**

> every proposal was refused before submission (quantity_in_statement); an abstention with a reason beats a claim the platform would refuse

| R1 | R2 | R3 | R5 |
|---|---|---|---|
| n/a | n/a | n/a | should_have |

### 182

> local_controller experienced a local minimum entrapment in this episode, as indicated by a stuck_cluster detection for C1

- register: `diagnosis` | subject: `local_controller` | type: `local_minimum_entrapment`
- refs: `obs:stuck_cluster:C1@fff606f44b13`

| R1 | R2 | R3 | R5 |
|---|---|---|---|
| holds | yes | all | n/a |

### 183

> local_controller experienced a local_minimum_entrapment in this episode

- register: `diagnosis` | subject: `local_controller` | type: `local_minimum_entrapment`
- refs: `obs:stuck_cluster:C1@fff606f44b13`

| R1 | R2 | R3 | R5 |
|---|---|---|---|
| holds | yes | all | n/a |

### 184

> local_controller experienced local minimum entrapment on C1 in this episode

- register: `diagnosis` | subject: `local_controller` | type: `local_minimum_entrapment`
- refs: `obs:stuck_cluster:C1@fff606f44b13`

| R1 | R2 | R3 | R5 |
|---|---|---|---|
| holds | yes | all | n/a |

### 185

> local_controller experienced a local_minimum_entrapment in this episode

- register: `diagnosis` | subject: `local_controller` | type: `local_minimum_entrapment`
- refs: `obs:stuck_cluster:C1@fff606f44b13`

| R1 | R2 | R3 | R5 |
|---|---|---|---|
| holds | yes | all | n/a |

### 186

> local_controller experienced a local_minimum_entrapment in this episode, causing a stuck_cluster detection

- register: `diagnosis` | subject: `local_controller` | type: `local_minimum_entrapment`
- refs: `obs:stuck_cluster:C1@fff606f44b13`, `diag:C1.replan_count`

| R1 | R2 | R3 | R5 |
|---|---|---|---|
| holds | yes | some | n/a |

### 187 - **khong de xuat gi**

> No detected mechanism difference in global_planner, local_controller, or local_controller_config; both candidates succeeded with no collisions and no available evidence for geometric infeasibility, clearance refusal, or other supported mechanisms.

| R1 | R2 | R3 | R5 |
|---|---|---|---|
| n/a | n/a | n/a | should_have |

### 188 - **khong de xuat gi**

> every proposal was refused before submission (quantity_in_statement); an abstention with a reason beats a claim the platform would refuse

| R1 | R2 | R3 | R5 |
|---|---|---|---|
| n/a | n/a | n/a | should_have |
