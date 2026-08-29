# Cham lai: 28 muc tren 4 episode `undecidable`

Cham lai vi mot ly do cu the, khong phai vi diem cu xau.

Bon episode nay deu co **ca hai ben ve dich**, va chenh nhau ro:

| episode | travel A / B | chenh |
|---|---|---|
| `3e3973656a9d` | 17,05s / 24,70s | **31,0%** |
| `3f3271808c9d` | 16,20s / 21,60s | **25,0%** |
| `685501eb617d` | 16,10s / 20,20s | **20,3%** |
| `a646b0f7b414` | 17,55s / 32,35s | **45,7%** |

Packet ghi `undecidable` **khong** vi hai ben ngang nhau, ma vi mot ben
khong duoc cham utility (no truot cong o cap run). Nen cau kieu "C5 gap
stuck_cluster" co the dung ve su kien du packet khong tuyen ai thang.

**R1 hoi: cau nay co dung vung truoc packet khong** — tuc doi chieu voi
so lieu trong packet, khong phai doi chieu voi phan quyet. Mot cau ke dung
cai da xay ra la `holds`, ke ca khi packet khong tuyen ai thang.

`wrong` danh cho cau **noi sai su that**: gan detector cho ben khong bi
no ban, doi chieu nguoc, hoac suy dien xa hon thu do duoc.

Cac muc giu nguyen so thu tu cu, de ghep lai voi key.

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
| wrong | yes | all | n/a |

### 026

> C5 had higher observed latency than C1, pointing to candidate_latency_attribution.

- register: `diagnosis` | subject: `runtime_transport` | type: `candidate_latency_attribution`
- refs: `diag:C5.p99_latency_ms`, `diag:C1.p99_latency_ms`

| R1 | R2 | R3 | R5 |
|---|---|---|---|
| wrong | yes | all | n/a |

### 027 - **khong de xuat gi**

> every proposal was refused before submission (quantity_in_statement); an abstention with a reason beats a claim the platform would refuse

| R1 | R2 | R3 | R5 |
|---|---|---|---|
| n/a | n/a | n/a | correct |

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
| n/a | n/a | n/a | correct |

### 030 - **khong de xuat gi**

> every proposal was refused before submission (quantity_in_statement); an abstention with a reason beats a claim the platform would refuse

| R1 | R2 | R3 | R5 |
|---|---|---|---|
| n/a | n/a | n/a | correct |

### 031 - **khong de xuat gi**

> every proposal was refused before submission (quantity_in_statement); an abstention with a reason beats a claim the platform would refuse

| R1 | R2 | R3 | R5 |
|---|---|---|---|
| n/a | n/a | n/a | correct |

### 032

> Local_controller of C1 did not require any replanning during the run

- register: `diagnosis` | subject: `local_controller` | type: `replan_instability`
- refs: `diag:C1.replan_count`

| R1 | R2 | R3 | R5 |
|---|---|---|---|
| wrong | yes | all | n/a |

### 033 - **khong de xuat gi**

> every proposal was refused before submission (quantity_in_statement); an abstention with a reason beats a claim the platform would refuse

| R1 | R2 | R3 | R5 |
|---|---|---|---|
| n/a | n/a | n/a | correct |

### 034

> The local_controller of C5 experienced a stuck cluster, indicating local_minimum_entrapment.

- register: `diagnosis` | subject: `local_controller` | type: `local_minimum_entrapment`
- refs: `obs:stuck_cluster:C5@3e3973656a9d`

| R1 | R2 | R3 | R5 |
|---|---|---|---|
| wrong | yes | all | n/a |

### 035

> The local_controller of C5 experienced a stuck cluster

- register: `diagnosis` | subject: `local_controller` | type: `local_minimum_entrapment`
- refs: `obs:stuck_cluster:C5@3e3973656a9d`

| R1 | R2 | R3 | R5 |
|---|---|---|---|
| wrong | yes | all | n/a |

### 036 - **khong de xuat gi**

> every proposal was refused before submission (quantity_in_statement); an abstention with a reason beats a claim the platform would refuse

| R1 | R2 | R3 | R5 |
|---|---|---|---|
| n/a | n/a | n/a | correct |

---

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
| wrong | yes | all | n/a |

### 038

> The local_controller of C5 experienced a stuck_cluster in this episode, indicating local_minimum_entrapment.

- register: `diagnosis` | subject: `local_controller` | type: `local_minimum_entrapment`
- refs: `fact:candidate:C5.local_controller`, `obs:stuck_cluster:C5@3f3271808c9d`

| R1 | R2 | R3 | R5 |
|---|---|---|---|
| wrong | yes | all | n/a |

### 039

> local_controller of C5 experienced a stuck cluster in this episode

- register: `diagnosis` | subject: `local_controller` | type: `local_minimum_entrapment`
- refs: `obs:stuck_cluster:C5@3f3271808c9d`

| R1 | R2 | R3 | R5 |
|---|---|---|---|
| wrong | yes | all | n/a |

### 040 - **khong de xuat gi**

> every proposal was refused before submission (quantity_in_statement); an abstention with a reason beats a claim the platform would refuse

| R1 | R2 | R3 | R5 |
|---|---|---|---|
| n/a | n/a | n/a | correct |

### 041 - **khong de xuat gi**

> every proposal was refused before submission (quantity_in_statement); an abstention with a reason beats a claim the platform would refuse

| R1 | R2 | R3 | R5 |
|---|---|---|---|
| n/a | n/a | n/a | correct |

### 042

> runtime_transport of C5 took longer in this episode

- register: `diagnosis` | subject: `runtime_transport` | type: `candidate_latency_attribution`
- refs: `diag:C5.travel_time_s`

| R1 | R2 | R3 | R5 |
|---|---|---|---|
| wrong | yes | none | n/a |

### 043

> runtime_transport of C1 took less time in this episode

- register: `diagnosis` | subject: `runtime_transport` | type: `candidate_latency_attribution`
- refs: `diag:C1.travel_time_s`

| R1 | R2 | R3 | R5 |
|---|---|---|---|
| wrong | yes | none | n/a |

### 044 - **khong de xuat gi**

> every proposal was refused before submission (quantity_in_statement); an abstention with a reason beats a claim the platform would refuse

| R1 | R2 | R3 | R5 |
|---|---|---|---|
| n/a | n/a | n/a | correct |

### 045 - **khong de xuat gi**

> every proposal was refused before submission (quantity_in_statement); an abstention with a reason beats a claim the platform would refuse

| R1 | R2 | R3 | R5 |
|---|---|---|---|
| n/a | n/a | n/a | correct |

### 046 - **khong de xuat gi**

> every proposal was refused before submission (quantity_in_statement); an abstention with a reason beats a claim the platform would refuse

| R1 | R2 | R3 | R5 |
|---|---|---|---|
| n/a | n/a | n/a | correct |

### 047

> The local_controller of C5 triggered a replan in this episode, indicating replan_instability.

- register: `diagnosis` | subject: `local_controller` | type: `replan_instability`
- refs: `fact:candidate:C5.local_controller`, `diag:C5.replan_count`

| R1 | R2 | R3 | R5 |
|---|---|---|---|
| wrong | yes | all | n/a |

### 048

> The local_controller of C5 experienced a stuck cluster indicative of local minimum entrapment

- register: `diagnosis` | subject: `local_controller` | type: `local_minimum_entrapment`
- refs: `obs:stuck_cluster:C5@3f3271808c9d`

| R1 | R2 | R3 | R5 |
|---|---|---|---|
| wrong | yes | all | n/a |

### 049 - **khong de xuat gi**

> Neither candidate lost this episode; both succeeded with no decisive mechanism to contrast.

| R1 | R2 | R3 | R5 |
|---|---|---|---|
| n/a | n/a | n/a | correct |

---

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
| wrong | yes | all | n/a |

### 093 - **khong de xuat gi**

> every proposal was refused before submission (quantity_in_statement); an abstention with a reason beats a claim the platform would refuse

| R1 | R2 | R3 | R5 |
|---|---|---|---|
| n/a | n/a | n/a | correct |

### 094 - **khong de xuat gi**

> every proposal was refused before submission (quantity_in_statement); an abstention with a reason beats a claim the platform would refuse

| R1 | R2 | R3 | R5 |
|---|---|---|---|
| n/a | n/a | n/a | correct |

### 095 - **khong de xuat gi**

> every proposal was refused before submission (quantity_in_statement); an abstention with a reason beats a claim the platform would refuse

| R1 | R2 | R3 | R5 |
|---|---|---|---|
| n/a | n/a | n/a | correct |

### 096

> The local_controller of C5 experienced a stuck_cluster event indicative of local minimum entrapment in this episode

- register: `diagnosis` | subject: `local_controller` | type: `local_minimum_entrapment`
- refs: `obs:stuck_cluster:C5@685501eb617d`

| R1 | R2 | R3 | R5 |
|---|---|---|---|
| wrong | yes | all | n/a |

### 097 - **khong de xuat gi**

> every proposal was refused before submission (quantity_in_statement); an abstention with a reason beats a claim the platform would refuse

| R1 | R2 | R3 | R5 |
|---|---|---|---|
| n/a | n/a | n/a | correct |

### 098

> Candidate C5 experienced a stuck_cluster causing it to stop for seconds.

- register: `diagnosis` | subject: `local_controller` | type: `local_minimum_entrapment`
- refs: `obs:stuck_cluster:C5@685501eb617d`, `obs:stuck_cluster:C5@685501eb617d/stopped_seconds`

| R1 | R2 | R3 | R5 |
|---|---|---|---|
| wrong | yes | all | n/a |

### 099 - **khong de xuat gi**

> every proposal was refused before submission (quantity_in_statement); an abstention with a reason beats a claim the platform would refuse

| R1 | R2 | R3 | R5 |
|---|---|---|---|
| n/a | n/a | n/a | correct |

### 100

> The local_controller of C5 triggered a stuck_cluster detection in this episode, halting movement.

- register: `diagnosis` | subject: `local_controller` | type: `component_specific_attribution`
- refs: `obs:stuck_cluster:C5@685501eb617d`

| R1 | R2 | R3 | R5 |
|---|---|---|---|
| wrong | yes | all | n/a |

### 101 - **khong de xuat gi**

> every proposal was refused before submission (quantity_in_statement); an abstention with a reason beats a claim the platform would refuse

| R1 | R2 | R3 | R5 |
|---|---|---|---|
| n/a | n/a | n/a | correct |

---

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
| wrong | yes | all | n/a |

### 130

> The local_controller of C5 became trapped in a stuck_cluster for an extended period

- register: `diagnosis` | subject: `local_controller` | type: `local_minimum_entrapment`
- refs: `obs:stuck_cluster:C5@a646b0f7b414`, `obs:stuck_cluster:C5@a646b0f7b414/stopped_seconds`

| R1 | R2 | R3 | R5 |
|---|---|---|---|
| wrong | yes | all | n/a |

### 131

> The local_controller of C5 experienced a stuck cluster during the episode

- register: `diagnosis` | subject: `local_controller` | type: `component_specific_attribution`
- refs: `obs:stuck_cluster:C5@a646b0f7b414`, `obs:stuck_cluster:C5@a646b0f7b414/stopped_seconds`

| R1 | R2 | R3 | R5 |
|---|---|---|---|
| wrong | yes | all | n/a |

### 132

> local_controller experienced a stuck_cluster in this episode

- register: `diagnosis` | subject: `local_controller` | type: `component_specific_attribution`
- refs: `obs:stuck_cluster:C5@a646b0f7b414`

| R1 | R2 | R3 | R5 |
|---|---|---|---|
| wrong | yes | all | n/a |

### 133 - **khong de xuat gi**

> every proposal was refused before submission (quantity_in_statement); an abstention with a reason beats a claim the platform would refuse

| R1 | R2 | R3 | R5 |
|---|---|---|---|
| n/a | n/a | n/a | correct |

### 134 - **khong de xuat gi**

> every proposal was refused before submission (quantity_in_statement, wording_above_associated); an abstention with a reason beats a claim the platform would refuse

| R1 | R2 | R3 | R5 |
|---|---|---|---|
| n/a | n/a | n/a | correct |

### 135

> local_controller experienced local_minimum_entrapment as evidenced by the stuck_cluster on C5 in this episode

- register: `diagnosis` | subject: `local_controller` | type: `local_minimum_entrapment`
- refs: `obs:stuck_cluster:C5@a646b0f7b414`

| R1 | R2 | R3 | R5 |
|---|---|---|---|
| wrong | yes | all | n/a |

### 136

> The local_controller of C5 performed multiple replans during this episode

- register: `diagnosis` | subject: `local_controller` | type: `replan_instability`
- refs: `diag:C5.replan_count`

| R1 | R2 | R3 | R5 |
|---|---|---|---|
| wrong | yes | all | n/a |

### 137

> The local_controller of C5 experienced a stuck_cluster lasting for an extended period, suggesting local minimum entrapment not seen on C1

- register: `diagnosis` | subject: `local_controller` | type: `local_minimum_entrapment`
- refs: `obs:stuck_cluster:C5@a646b0f7b414`, `obs:stuck_cluster:C5@a646b0f7b414/stopped_seconds`

| R1 | R2 | R3 | R5 |
|---|---|---|---|
| wrong | yes | all | n/a |

### 138

> The local_controller for C5 experienced a stuck_cluster in this episode

- register: `diagnosis` | subject: `local_controller` | type: `local_minimum_entrapment`
- refs: `obs:stuck_cluster:C5@a646b0f7b414`

| R1 | R2 | R3 | R5 |
|---|---|---|---|
| wrong | yes | all | n/a |

### 139

> global_planner triggered no replans in this episode

- register: `diagnosis` | subject: `global_planner` | type: `component_specific_attribution`
- refs: `diag:C1.replan_count`

| R1 | R2 | R3 | R5 |
|---|---|---|---|
| wrong | yes | all | n/a |

### 140

> global_planner triggered multiple replans in this episode

- register: `diagnosis` | subject: `global_planner` | type: `component_specific_attribution`
- refs: `diag:C5.replan_count`

| R1 | R2 | R3 | R5 |
|---|---|---|---|
| wrong | yes | all | n/a |

---
