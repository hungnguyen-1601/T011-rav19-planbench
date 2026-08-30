# Cham lai 28 muc — packet da sua

Nguoi cham: **Codex (AI-assisted manual review)** | phan loai: **exploratory** | ngay cham: **2026-08-29**

Ghi chu hieu chinh rubric: `proposition_type` la **ho hypothesis duoc de xuat**, khong phai claim da verified. **R1** cham mechanism/hypothesis doc lap voi ket qua episode; diagnosis khong can giai thich winner-loser. **R2** cham subject rieng, khong dung subject de tu dong ha R1. **R3** cham ref. Wording manh la loi guard rieng, khong tru diem manual. **R5** chi `correct` khi packet khong co detection/contrast dang bao.

Bon episode nay truoc day packet ghi `undecidable`. **Khong con nua.**

Ly do cu: mot candidate truot cong o cap run thi khong duoc cham utility o
bat ky episode nao, nen verdict roi xuong `undecidable` — du hai ben chenh
20-46% thoi gian ve dich. Downstream doc thanh "hai ben nhu nhau", khong co
huong nen khong contrast nao duoc gan, packet khong noi gi ve mot khac biet
nhin bang mat cung thay.

Da them co so `outcome_margin`: ca hai ve dich, ben cham hon >=10% thi thua.
Bon episode nay gio **co nguoi thang**, va moi cai co **1 contrast support**
cho ky truoc la 0.

Nen cham lai tren packet MOI ben duoi, khong phai tren tri nho ky truoc.
So thu tu muc giu nguyen de ghep voi key.

- **R1** `holds` / `plausible_other` / `wrong` — cau co dung vung truoc packet
- **R2** `yes` / `no` — subject dung thanh phan cau noi toi
- **R3** `all` / `some` / `none` — ref mo duoc VA noi dung co che
- **R5** `correct` / `should_have` — cho khong de xuat gi

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
