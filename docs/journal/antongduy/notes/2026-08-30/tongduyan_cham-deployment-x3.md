# Cham tay, mu arm - giai thich vi sao A hon B trong mot episode (rubric r0.2.0)

180 muc | 30 episode | 3 luot | nguon: `holdout-deployment-x3`

Nguoi cham: **An Tong** | ngay cham: **2026-08-30** |
trang thai: **complete - R1-R6, 90/90 luot**

- **R1:** `supported_explanation` / `plausible_explanation` /
  `descriptive_only` / `wrong`.
- **R2:** `yes` / `no` / `n/a` cho subject, candidate va polarity.
- **R3:** `all` / `some` / `none` cho bundle outcome + occurrence + contrast.
- **R4:** `exact` / `rounded` / `wrong` / `n/a` cho magnitude.
- **R5:** `correct` / `should_have` / `n/a` cho abstention.
- **R6 theo tung luot:** `explains` / `describes_only` / `silent_wrongly` /
  `silent_correctly` / `wrong`.

**Floor khong phai model.** Cau floor van duoc cham R1-R5 nhu noi dung hien thi,
nhung R6 cham analyst la silent. Floor diagnosis dung candidate ID tho trong khi
PACKET render alias `C1/C5` thi R3=`none`.

Diagnosis dung nhung khong noi mechanism vao ket qua la `descriptive_only`.
`component_differs` mot minh chi la context. Khong mo key/arm truoc khi cham xong.

---

# Episode `307c6a94d0f0`

*cluster: sudden_stop_custom_v2_full_stack_selection_06f40334 | vai: holdout*

<details open><summary><b>PACKET</b></summary>

**Phan quyet**: episode_decision_utility | thang: `C1` | thua: `C5`

**Khac biet giua hai ben**

| ref | strength | noi gi | so kem theo |
|---|---|---|---|
| `contrast:component_differs:2` | **context** | the two stacks differ in global_planner, local_controller, local_controller_config; a mechanism that explains the difference has to live in one of those | - |
| `contrast:detection_worse_on_loser:1` | **support** | stuck_cluster fired on both, and materially worse on C5 | severity ratio = 4.13793; stopped seconds = 6; stops = 1 |
| `contrast:divergence_precedes_outcome:3` | **context** | the two runs parted at 3.1 m along the route | - |

**Detector da ban**

| ref | tren ai | so kem theo |
|---|---|---|
| `obs:stuck_cluster:C1@307c6a94d0f0` | `C1` | stopped_seconds = 1.45; stops = 1; window.end_m = 7.52161; window.end_s = 19.2; window.start_m = 7.51891; window.start_s = 17.75 |
| `obs:stuck_cluster:C5@307c6a94d0f0` | `C5` | stopped_seconds = 6; stops = 1; window.end_m = 3.63794; window.end_s = 12.7; window.start_m = 3.58324; window.start_s = 6.7 |

**So do duoc cua tung ben**

- `C1`: collision_count = 0 | min_clearance = 0.2141 | p99_latency_ms = 0 | replan_count = 0 | success = 1 | travel_time_s = 26.9
- `C5`: collision_count = 0 | min_clearance = 0.253726 | p99_latency_ms = 20.9835 | replan_count = 1 | success = 1 | travel_time_s = 26.5

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

## Luot 1/3

**R6 - episode nay co giai thich duoc vi sao ben thang hon khong?**

> **packet co the tra loi why** - co contrast `support`.

| R6 |
|---|
| describes_only |

### 001

> The local_controller in C5 experienced more severe local minimum entrapment than in C1, indicated by stopped seconds in the stuck_cluster of 6 versus 1.45.

- register: `diagnosis` | subject: `local_controller` | type: `local_minimum_entrapment`
- refs: `contrast:component_differs:2`, `contrast:detection_worse_on_loser:1`
- contract: `contrast_support`, `subject_match`, `polarity_match`

| R1 | R2 | R3 | R4 | R5 |
|---|---|---|---|---|
| descriptive_only | n/a | none | exact | n/a |

## Luot 2/3

**R6 - episode nay co giai thich duoc vi sao ben thang hon khong?**

> **packet co the tra loi why** - co contrast `support`.

| R6 |
|---|
| explains |

### 002

> local_controller on C5 experienced a more severe local minimum entrapment than on C1, delaying progress by 6 seconds, which led to the episode being won by C1.

- register: `diagnosis` | subject: `local_controller` | type: `local_minimum_entrapment`
- refs: `contrast:component_differs:2`, `contrast:detection_worse_on_loser:1`
- contract: `contrast_support`, `subject_match`, `polarity_match`

| R1 | R2 | R3 | R4 | R5 |
|---|---|---|---|---|
| supported_explanation | yes | some | exact | n/a |

## Luot 3/3

**R6 - episode nay co giai thich duoc vi sao ben thang hon khong?**

> **packet co the tra loi why** - co contrast `support`.

| R6 |
|---|
| explains |

### 003

> The local_controller on C5 experienced a local minimum entrapment lasting 6, which slowed it relative to C1

- register: `diagnosis` | subject: `local_controller` | type: `local_minimum_entrapment`
- refs: `contrast:detection_worse_on_loser:1`
- contract: `contrast_support`, `subject_match`, `polarity_match`

| R1 | R2 | R3 | R4 | R5 |
|---|---|---|---|---|
| supported_explanation | yes | some | exact | n/a |

---

# Episode `40b620398486`

*cluster: sudden_stop_custom_v2_full_stack_selection_06f40334 | vai: holdout*

<details open><summary><b>PACKET</b></summary>

**Phan quyet**: episode_decision_utility | thang: `C1` | thua: `C5`

**Khac biet giua hai ben**

| ref | strength | noi gi | so kem theo |
|---|---|---|---|
| `contrast:component_differs:2` | **context** | the two stacks differ in global_planner, local_controller, local_controller_config; a mechanism that explains the difference has to live in one of those | - |
| `contrast:detection_worse_on_loser:1` | **support** | stuck_cluster fired on both, and materially worse on C5 | severity ratio = 4.53571; stopped seconds = 6.35; stops = 1 |
| `contrast:divergence_precedes_outcome:3` | **context** | the two runs parted at 3.1 m along the route | - |

**Detector da ban**

| ref | tren ai | so kem theo |
|---|---|---|
| `obs:stuck_cluster:C1@40b620398486` | `C1` | stopped_seconds = 1.4; stops = 1; window.end_m = 7.4548; window.end_s = 17.9; window.start_m = 7.45161; window.start_s = 16.5 |
| `obs:stuck_cluster:C5@40b620398486` | `C5` | stopped_seconds = 6.35; stops = 1; window.end_m = 3.6381; window.end_s = 13; window.start_m = 3.57675; window.start_s = 6.65 |

**So do duoc cua tung ben**

- `C1`: collision_count = 0 | min_clearance = 0.191114 | p99_latency_ms = 0 | replan_count = 0 | success = 1 | travel_time_s = 27.25
- `C5`: collision_count = 0 | min_clearance = 0.244628 | p99_latency_ms = 22.753 | replan_count = 1 | success = 1 | travel_time_s = 27

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

## Luot 1/3

**R6 - episode nay co giai thich duoc vi sao ben thang hon khong?**

> **packet co the tra loi why** - co contrast `support`.
>
> **KHONG PHAI MODEL VIET.** Moi de xuat cua model deu bi tu choi; cac cau duoi day do floor sinh tu packet. Voi R6 day la analyst **im lang** - `explains` khong the cham o day.

| R6 |
|---|
| silent_wrongly |

### 004

> a pattern worse on e1251e42a20b than on the other side is consistent with local minimum entrapment

- register: `contrast` | subject: `local_controller` | type: `local_minimum_entrapment`
- refs: `contrast:detection_worse_on_loser:1`

| R1 | R2 | R3 | R4 | R5 |
|---|---|---|---|---|
| descriptive_only | yes | some | n/a | n/a |

### 005

> stuck cluster was detected on dcda195ffe5e in this episode

- register: `diagnosis` | subject: `task_geometry` | type: `component_specific_attribution`
- refs: `obs:stuck_cluster:dcda195ffe5e@40b620398486`

| R1 | R2 | R3 | R4 | R5 |
|---|---|---|---|---|
| descriptive_only | yes | some | n/a | n/a |

### 006

> stuck cluster was detected on e1251e42a20b in this episode

- register: `diagnosis` | subject: `task_geometry` | type: `component_specific_attribution`
- refs: `obs:stuck_cluster:e1251e42a20b@40b620398486`

| R1 | R2 | R3 | R4 | R5 |
|---|---|---|---|---|
| descriptive_only | n/a | none | n/a | n/a |

## Luot 2/3

**R6 - episode nay co giai thich duoc vi sao ben thang hon khong?**

> **packet co the tra loi why** - co contrast `support`.
>
> **KHONG PHAI MODEL VIET.** Moi de xuat cua model deu bi tu choi; cac cau duoi day do floor sinh tu packet. Voi R6 day la analyst **im lang** - `explains` khong the cham o day.

| R6 |
|---|
| silent_wrongly |

### 007

> a pattern worse on e1251e42a20b than on the other side is consistent with local minimum entrapment

- register: `contrast` | subject: `local_controller` | type: `local_minimum_entrapment`
- refs: `contrast:detection_worse_on_loser:1`

| R1 | R2 | R3 | R4 | R5 |
|---|---|---|---|---|
| descriptive_only | n/a | none | n/a | n/a |

### 008

> stuck cluster was detected on dcda195ffe5e in this episode

- register: `diagnosis` | subject: `task_geometry` | type: `component_specific_attribution`
- refs: `obs:stuck_cluster:dcda195ffe5e@40b620398486`

| R1 | R2 | R3 | R4 | R5 |
|---|---|---|---|---|
| descriptive_only | yes | some | exact | n/a |

### 009

> stuck cluster was detected on e1251e42a20b in this episode

- register: `diagnosis` | subject: `task_geometry` | type: `component_specific_attribution`
- refs: `obs:stuck_cluster:e1251e42a20b@40b620398486`

| R1 | R2 | R3 | R4 | R5 |
|---|---|---|---|---|
| descriptive_only | n/a | none | exact | n/a |

## Luot 3/3

**R6 - episode nay co giai thich duoc vi sao ben thang hon khong?**

> **packet co the tra loi why** - co contrast `support`.

| R6 |
|---|
| explains |

### 010

> local_controller_config hindered escape from local minima on C5, causing it to accumulate 6.35 of stuck time versus 1.4 on C1, slowing its progress and leading to its loss

- register: `diagnosis` | subject: `local_controller` | type: `local_minimum_entrapment`
- refs: `contrast:component_differs:2`, `contrast:detection_worse_on_loser:1`
- contract: `contrast_support`, `subject_match`, `polarity_match`

| R1 | R2 | R3 | R4 | R5 |
|---|---|---|---|---|
| plausible_explanation | n/a | none | exact | n/a |

---

# Episode `4874a8da74e7`

*cluster: sudden_stop_custom_v2_full_stack_selection_06f40334 | vai: holdout*

<details open><summary><b>PACKET</b></summary>

**Phan quyet**: episode_decision_utility | thang: `C5` | thua: `C1`

**Khac biet giua hai ben**

| ref | strength | noi gi | so kem theo |
|---|---|---|---|
| `contrast:component_differs:1` | **context** | the two stacks differ in global_planner, local_controller, local_controller_config; a mechanism that explains the difference has to live in one of those | - |
| `contrast:divergence_precedes_outcome:2` | **context** | the two runs parted at 3.8 m along the route | - |
| `contrast:outcome_differs:3` | **context** | C5 ended this episode ahead of C1 on worst clearance, travel time | min clearance loser = 0.198404; min clearance winner = 0.241494; travel time s loser = 32.75; travel time s winner = 25.9 |

**Detector da ban**

| ref | tren ai | so kem theo |
|---|---|---|
| `obs:stuck_cluster:C1@4874a8da74e7#1` | `C1` | stopped_seconds = 2.1; stops = 1; window.end_m = 3.35491; window.end_s = 10.25; window.start_m = 3.34828; window.start_s = 8.15 |
| `obs:stuck_cluster:C1@4874a8da74e7#2` | `C1` | stopped_seconds = 1.35; stops = 1; window.end_m = 8.22568; window.end_s = 23.15; window.start_m = 8.22049; window.start_s = 21.8 |
| `obs:stuck_cluster:C5@4874a8da74e7` | `C5` | stopped_seconds = 5.65; stops = 1; window.end_m = 3.63642; window.end_s = 11.8; window.start_m = 3.61589; window.start_s = 6.15 |

**So do duoc cua tung ben**

- `C1`: collision_count = 0 | min_clearance = 0.198404 | p99_latency_ms = 0 | replan_count = 0 | success = 1 | travel_time_s = 32.75
- `C5`: collision_count = 0 | min_clearance = 0.241494 | p99_latency_ms = 24.7126 | replan_count = 1 | success = 1 | travel_time_s = 25.9

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

## Luot 1/3

**R6 - episode nay co giai thich duoc vi sao ben thang hon khong?**

> packet khong co contrast `support`.
>
> **KHONG PHAI MODEL VIET.** Moi de xuat cua model deu bi tu choi; cac cau duoi day do floor sinh tu packet. Voi R6 day la analyst **im lang** - `explains` khong the cham o day.

| R6 |
|---|
| silent_correctly |

### 011

> stuck cluster was detected on e1251e42a20b in this episode

- register: `diagnosis` | subject: `task_geometry` | type: `component_specific_attribution`
- refs: `obs:stuck_cluster:e1251e42a20b@4874a8da74e7`

| R1 | R2 | R3 | R4 | R5 |
|---|---|---|---|---|
| wrong | no | some | exact | n/a |

### 012

> stuck cluster was detected on dcda195ffe5e in this episode

- register: `diagnosis` | subject: `task_geometry` | type: `component_specific_attribution`
- refs: `obs:stuck_cluster:dcda195ffe5e@4874a8da74e7`

| R1 | R2 | R3 | R4 | R5 |
|---|---|---|---|---|
| descriptive_only | n/a | none | n/a | n/a |

### 013

> stuck cluster was detected on dcda195ffe5e in this episode

- register: `diagnosis` | subject: `task_geometry` | type: `component_specific_attribution`
- refs: `obs:stuck_cluster:dcda195ffe5e@4874a8da74e7`

| R1 | R2 | R3 | R4 | R5 |
|---|---|---|---|---|
| descriptive_only | n/a | none | n/a | n/a |

## Luot 2/3

**R6 - episode nay co giai thich duoc vi sao ben thang hon khong?**

> packet khong co contrast `support`.
>
> **KHONG PHAI MODEL VIET.** Moi de xuat cua model deu bi tu choi; cac cau duoi day do floor sinh tu packet. Voi R6 day la analyst **im lang** - `explains` khong the cham o day.

| R6 |
|---|
| silent_correctly |

### 014

> stuck cluster was detected on dcda195ffe5e in this episode

- register: `diagnosis` | subject: `task_geometry` | type: `component_specific_attribution`
- refs: `obs:stuck_cluster:dcda195ffe5e@4874a8da74e7`

| R1 | R2 | R3 | R4 | R5 |
|---|---|---|---|---|
| descriptive_only | n/a | none | n/a | n/a |

### 015

> stuck cluster was detected on dcda195ffe5e in this episode

- register: `diagnosis` | subject: `task_geometry` | type: `component_specific_attribution`
- refs: `obs:stuck_cluster:dcda195ffe5e@4874a8da74e7`

| R1 | R2 | R3 | R4 | R5 |
|---|---|---|---|---|
| descriptive_only | n/a | none | n/a | n/a |

### 016

> stuck cluster was detected on e1251e42a20b in this episode

- register: `diagnosis` | subject: `task_geometry` | type: `component_specific_attribution`
- refs: `obs:stuck_cluster:e1251e42a20b@4874a8da74e7`

| R1 | R2 | R3 | R4 | R5 |
|---|---|---|---|---|
| descriptive_only | n/a | none | n/a | n/a |

## Luot 3/3

**R6 - episode nay co giai thich duoc vi sao ben thang hon khong?**

> packet khong co contrast `support`.
>
> **KHONG PHAI MODEL VIET.** Moi de xuat cua model deu bi tu choi; cac cau duoi day do floor sinh tu packet. Voi R6 day la analyst **im lang** - `explains` khong the cham o day.

| R6 |
|---|
| silent_correctly |

### 017

> stuck cluster was detected on dcda195ffe5e in this episode

- register: `diagnosis` | subject: `task_geometry` | type: `component_specific_attribution`
- refs: `obs:stuck_cluster:dcda195ffe5e@4874a8da74e7`

| R1 | R2 | R3 | R4 | R5 |
|---|---|---|---|---|
| descriptive_only | n/a | none | n/a | n/a |

### 018

> stuck cluster was detected on dcda195ffe5e in this episode

- register: `diagnosis` | subject: `task_geometry` | type: `component_specific_attribution`
- refs: `obs:stuck_cluster:dcda195ffe5e@4874a8da74e7`

| R1 | R2 | R3 | R4 | R5 |
|---|---|---|---|---|
| descriptive_only | n/a | none | exact | n/a |

### 019

> stuck cluster was detected on e1251e42a20b in this episode

- register: `diagnosis` | subject: `task_geometry` | type: `component_specific_attribution`
- refs: `obs:stuck_cluster:e1251e42a20b@4874a8da74e7`

| R1 | R2 | R3 | R4 | R5 |
|---|---|---|---|---|
| descriptive_only | n/a | none | exact | n/a |

---

# Episode `501a98d1fd9a`

*cluster: sudden_stop_custom_v2_full_stack_selection_06f40334 | vai: holdout*

<details open><summary><b>PACKET</b></summary>

**Phan quyet**: episode_decision_utility | thang: `-` | thua: `-`

**Detector da ban**

| ref | tren ai | so kem theo |
|---|---|---|
| `obs:near_miss_cluster:C1@501a98d1fd9a` | `C1` | min_clearance_m = 0.144209; samples = 6; window.end_m = 8.34555; window.end_s = 21.1; window.start_m = 8.2268; window.start_s = 20.85 |
| `obs:stuck_cluster:C1@501a98d1fd9a` | `C1` | stopped_seconds = 1.55; stops = 1; window.end_m = 7.66055; window.end_s = 18.95; window.start_m = 7.64646; window.start_s = 17.4 |
| `obs:stuck_cluster:C5@501a98d1fd9a` | `C5` | stopped_seconds = 5.9; stops = 1; window.end_m = 3.63672; window.end_s = 12.1; window.start_m = 3.59883; window.start_s = 6.2 |

**So do duoc cua tung ben**

- `C1`: collision_count = 0 | min_clearance = 0.144209 | p99_latency_ms = 0 | replan_count = 0 | success = 1 | travel_time_s = 27.1
- `C5`: collision_count = 0 | min_clearance = 0.250112 | p99_latency_ms = 19.4555 | replan_count = 1 | success = 1 | travel_time_s = 26.15

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

## Luot 1/3

**R6 - episode nay co giai thich duoc vi sao ben thang hon khong?**

> packet khong co contrast `support`.
>
> **KHONG PHAI MODEL VIET.** Moi de xuat cua model deu bi tu choi; cac cau duoi day do floor sinh tu packet. Voi R6 day la analyst **im lang** - `explains` khong the cham o day.

| R6 |
|---|
| silent_correctly |

### 020

> stuck cluster was detected on dcda195ffe5e in this episode

- register: `diagnosis` | subject: `task_geometry` | type: `component_specific_attribution`
- refs: `obs:stuck_cluster:dcda195ffe5e@501a98d1fd9a`

| R1 | R2 | R3 | R4 | R5 |
|---|---|---|---|---|
| descriptive_only | n/a | none | exact | n/a |

### 021

> stuck cluster was detected on e1251e42a20b in this episode

- register: `diagnosis` | subject: `task_geometry` | type: `component_specific_attribution`
- refs: `obs:stuck_cluster:e1251e42a20b@501a98d1fd9a`

| R1 | R2 | R3 | R4 | R5 |
|---|---|---|---|---|
| descriptive_only | n/a | none | rounded | n/a |

### 022

> near miss cluster was detected on dcda195ffe5e in this episode

- register: `diagnosis` | subject: `task_geometry` | type: `component_specific_attribution`
- refs: `obs:near_miss_cluster:dcda195ffe5e@501a98d1fd9a`

| R1 | R2 | R3 | R4 | R5 |
|---|---|---|---|---|
| descriptive_only | n/a | none | n/a | n/a |

## Luot 2/3

**R6 - episode nay co giai thich duoc vi sao ben thang hon khong?**

> packet khong co contrast `support`.

| R6 |
|---|
| describes_only |

### 023

> local_controller of C5 experienced a stuck cluster lasting 5.9 seconds

- register: `diagnosis` | subject: `local_controller` | type: `local_minimum_entrapment`
- refs: `obs:stuck_cluster:C5@501a98d1fd9a/stopped_seconds`

| R1 | R2 | R3 | R4 | R5 |
|---|---|---|---|---|
| descriptive_only | n/a | none | exact | n/a |

### 024

> local_controller of C1 experienced a stuck cluster lasting 1.55 seconds

- register: `diagnosis` | subject: `local_controller` | type: `local_minimum_entrapment`
- refs: `obs:stuck_cluster:C1@501a98d1fd9a/stopped_seconds`

| R1 | R2 | R3 | R4 | R5 |
|---|---|---|---|---|
| descriptive_only | yes | some | exact | n/a |

## Luot 3/3

**R6 - episode nay co giai thich duoc vi sao ben thang hon khong?**

> packet khong co contrast `support`.

| R6 |
|---|
| describes_only |

### 025

> local_controller of C1 was stuck for 1.55 seconds

- register: `diagnosis` | subject: `local_controller` | type: `local_minimum_entrapment`
- refs: `obs:stuck_cluster:C1@501a98d1fd9a/stopped_seconds`

| R1 | R2 | R3 | R4 | R5 |
|---|---|---|---|---|
| descriptive_only | yes | some | exact | n/a |

### 026

> local_controller of C5 was stuck for 5.9 seconds

- register: `diagnosis` | subject: `local_controller` | type: `local_minimum_entrapment`
- refs: `obs:stuck_cluster:C5@501a98d1fd9a/stopped_seconds`

| R1 | R2 | R3 | R4 | R5 |
|---|---|---|---|---|
| descriptive_only | yes | some | exact | n/a |

### 027

> local_controller experienced a clearance refusal with minimum clearance of 0.14m in a near-miss event

- register: `diagnosis` | subject: `local_controller` | type: `clearance_refusal`
- refs: `obs:near_miss_cluster:C1@501a98d1fd9a`, `obs:near_miss_cluster:C1@501a98d1fd9a/min_clearance_m`

| R1 | R2 | R3 | R4 | R5 |
|---|---|---|---|---|
| descriptive_only | yes | some | rounded | n/a |

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

## Luot 1/3

**R6 - episode nay co giai thich duoc vi sao ben thang hon khong?**

> **packet co the tra loi why** - co contrast `support`.

| R6 |
|---|
| describes_only |

### 028

> global_planner experienced a replan storm of 3 replans not observed on the winner, leading to unstable planning behavior

- register: `diagnosis` | subject: `global_planner` | type: `replan_instability`
- refs: `contrast:detection_only_on_loser:2`
- contract: `contrast_support`, `subject_match`, `polarity_match`

| R1 | R2 | R3 | R4 | R5 |
|---|---|---|---|---|
| descriptive_only | yes | some | exact | n/a |

## Luot 2/3

**R6 - episode nay co giai thich duoc vi sao ben thang hon khong?**

> **packet co the tra loi why** - co contrast `support`.
>
> **KHONG PHAI MODEL VIET.** Moi de xuat cua model deu bi tu choi; cac cau duoi day do floor sinh tu packet. Voi R6 day la analyst **im lang** - `explains` khong the cham o day.

| R6 |
|---|
| silent_wrongly |

### 029

> latency spike was detected on dcda195ffe5e in this episode

- register: `diagnosis` | subject: `task_geometry` | type: `component_specific_attribution`
- refs: `obs:latency_spike:dcda195ffe5e@50f9cae5941c`

| R1 | R2 | R3 | R4 | R5 |
|---|---|---|---|---|
| descriptive_only | yes | some | n/a | n/a |

### 030

> near miss cluster was detected on e1251e42a20b in this episode

- register: `diagnosis` | subject: `task_geometry` | type: `component_specific_attribution`
- refs: `obs:near_miss_cluster:e1251e42a20b@50f9cae5941c`

| R1 | R2 | R3 | R4 | R5 |
|---|---|---|---|---|
| descriptive_only | n/a | none | n/a | n/a |

### 031

> replan storm was detected on dcda195ffe5e in this episode

- register: `diagnosis` | subject: `task_geometry` | type: `component_specific_attribution`
- refs: `obs:replan_storm:dcda195ffe5e@50f9cae5941c`

| R1 | R2 | R3 | R4 | R5 |
|---|---|---|---|---|
| descriptive_only | n/a | none | n/a | n/a |

### 032

> stuck cluster was detected on e1251e42a20b in this episode

- register: `diagnosis` | subject: `task_geometry` | type: `component_specific_attribution`
- refs: `obs:stuck_cluster:e1251e42a20b@50f9cae5941c`

| R1 | R2 | R3 | R4 | R5 |
|---|---|---|---|---|
| descriptive_only | n/a | none | n/a | n/a |

### 033

> a pattern worse on dcda195ffe5e than on the other side is consistent with local minimum entrapment

- register: `contrast` | subject: `local_controller` | type: `local_minimum_entrapment`
- refs: `contrast:detection_worse_on_loser:3`

| R1 | R2 | R3 | R4 | R5 |
|---|---|---|---|---|
| descriptive_only | n/a | none | n/a | n/a |

### 034

> a pattern present on dcda195ffe5e and absent on the other side is consistent with replan instability

- register: `contrast` | subject: `global_planner` | type: `replan_instability`
- refs: `contrast:detection_only_on_loser:2`

| R1 | R2 | R3 | R4 | R5 |
|---|---|---|---|---|
| descriptive_only | yes | some | n/a | n/a |

### 035

> stuck cluster was detected on dcda195ffe5e in this episode

- register: `diagnosis` | subject: `task_geometry` | type: `component_specific_attribution`
- refs: `obs:stuck_cluster:dcda195ffe5e@50f9cae5941c`

| R1 | R2 | R3 | R4 | R5 |
|---|---|---|---|---|
| descriptive_only | yes | some | n/a | n/a |

### 036

> a pattern present on dcda195ffe5e and absent on the other side is consistent with expansion latency association

- register: `contrast` | subject: `global_planner` | type: `expansion_latency_association`
- refs: `contrast:detection_only_on_loser:1`

| R1 | R2 | R3 | R4 | R5 |
|---|---|---|---|---|
| descriptive_only | n/a | none | n/a | n/a |

## Luot 3/3

**R6 - episode nay co giai thich duoc vi sao ben thang hon khong?**

> **packet co the tra loi why** - co contrast `support`.

| R6 |
|---|
| explains |

### 037

> local_controller on C1 had a stuck cluster where C1 stopped for 21.7 seconds across 2 stops, more severe than on C5 and slowing C1

- register: `diagnosis` | subject: `local_controller` | type: `local_minimum_entrapment`
- refs: `contrast:detection_worse_on_loser:3`
- contract: `contrast_support`, `subject_match`, `polarity_match`

| R1 | R2 | R3 | R4 | R5 |
|---|---|---|---|---|
| supported_explanation | yes | some | exact | n/a |

### 038

> global_planner on C1 fired a replan storm of 3 replans that did not occur on C5, delaying C1 compared to C5

- register: `diagnosis` | subject: `global_planner` | type: `replan_instability`
- refs: `contrast:detection_only_on_loser:2`
- contract: `contrast_support`, `subject_match`, `polarity_match`

| R1 | R2 | R3 | R4 | R5 |
|---|---|---|---|---|
| supported_explanation | yes | some | exact | n/a |

---

# Episode `56f2bbdf0e74`

*cluster: sudden_stop_custom_v2_full_stack_selection_06f40334 | vai: holdout*

<details open><summary><b>PACKET</b></summary>

**Phan quyet**: episode_decision_utility | thang: `C1` | thua: `C5`

**Khac biet giua hai ben**

| ref | strength | noi gi | so kem theo |
|---|---|---|---|
| `contrast:component_differs:3` | **context** | the two stacks differ in global_planner, local_controller, local_controller_config; a mechanism that explains the difference has to live in one of those | - |
| `contrast:detection_only_on_loser:1` | **support** | latency_spike fired on C5 and not on C1 | peak latency ms = 242.448; ticks = 1 |
| `contrast:detection_worse_on_loser:2` | **support** | stuck_cluster fired on both, and materially worse on C5 | severity ratio = 5.22727; stopped seconds = 5.75; stops = 1 |
| `contrast:divergence_precedes_outcome:4` | **context** | the two runs parted at 3.0 m along the route | - |
| `contrast:outcome_differs:5` | **context** | C1 ended this episode ahead of C5 on worst clearance, travel time | min clearance loser = 0.224466; min clearance winner = 0.243828; travel time s loser = 26.05; travel time s winner = 24.75 |

**Detector da ban**

| ref | tren ai | so kem theo |
|---|---|---|
| `obs:latency_spike:C5@56f2bbdf0e74` | `C5` | peak_latency_ms = 242.448; ticks = 1; window.end_m = 6.61745; window.end_s = 17.8; window.start_m = 6.61745; window.start_s = 17.8 |
| `obs:stuck_cluster:C1@56f2bbdf0e74` | `C1` | stopped_seconds = 1.1; stops = 1; window.end_m = 7.31703; window.end_s = 16.7; window.start_m = 7.31243; window.start_s = 15.6 |
| `obs:stuck_cluster:C5@56f2bbdf0e74` | `C5` | stopped_seconds = 5.75; stops = 1; window.end_m = 3.68342; window.end_s = 12; window.start_m = 3.67445; window.start_s = 6.25 |

**So do duoc cua tung ben**

- `C1`: collision_count = 0 | min_clearance = 0.243828 | p99_latency_ms = 0 | replan_count = 0 | success = 1 | travel_time_s = 24.75
- `C5`: collision_count = 0 | min_clearance = 0.224466 | p99_latency_ms = 20.0534 | replan_count = 1 | success = 1 | travel_time_s = 26.05

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

## Luot 1/3

**R6 - episode nay co giai thich duoc vi sao ben thang hon khong?**

> **packet co the tra loi why** - co contrast `support`.
>
> **KHONG PHAI MODEL VIET.** Moi de xuat cua model deu bi tu choi; cac cau duoi day do floor sinh tu packet. Voi R6 day la analyst **im lang** - `explains` khong the cham o day.

| R6 |
|---|
| silent_wrongly |

### 039

> latency spike was detected on e1251e42a20b in this episode

- register: `diagnosis` | subject: `task_geometry` | type: `component_specific_attribution`
- refs: `obs:latency_spike:e1251e42a20b@56f2bbdf0e74`

| R1 | R2 | R3 | R4 | R5 |
|---|---|---|---|---|
| descriptive_only | yes | some | n/a | n/a |

### 040

> stuck cluster was detected on dcda195ffe5e in this episode

- register: `diagnosis` | subject: `task_geometry` | type: `component_specific_attribution`
- refs: `obs:stuck_cluster:dcda195ffe5e@56f2bbdf0e74`

| R1 | R2 | R3 | R4 | R5 |
|---|---|---|---|---|
| descriptive_only | n/a | none | n/a | n/a |

### 041

> stuck cluster was detected on e1251e42a20b in this episode

- register: `diagnosis` | subject: `task_geometry` | type: `component_specific_attribution`
- refs: `obs:stuck_cluster:e1251e42a20b@56f2bbdf0e74`

| R1 | R2 | R3 | R4 | R5 |
|---|---|---|---|---|
| descriptive_only | n/a | none | n/a | n/a |

### 042

> a pattern worse on e1251e42a20b than on the other side is consistent with local minimum entrapment

- register: `contrast` | subject: `local_controller` | type: `local_minimum_entrapment`
- refs: `contrast:detection_worse_on_loser:2`

| R1 | R2 | R3 | R4 | R5 |
|---|---|---|---|---|
| descriptive_only | n/a | none | n/a | n/a |

### 043

> a pattern present on e1251e42a20b and absent on the other side is consistent with expansion latency association

- register: `contrast` | subject: `global_planner` | type: `expansion_latency_association`
- refs: `contrast:detection_only_on_loser:1`

| R1 | R2 | R3 | R4 | R5 |
|---|---|---|---|---|
| descriptive_only | yes | some | n/a | n/a |

## Luot 2/3

**R6 - episode nay co giai thich duoc vi sao ben thang hon khong?**

> **packet co the tra loi why** - co contrast `support`.
>
> **KHONG PHAI MODEL VIET.** Moi de xuat cua model deu bi tu choi; cac cau duoi day do floor sinh tu packet. Voi R6 day la analyst **im lang** - `explains` khong the cham o day.

| R6 |
|---|
| silent_wrongly |

### 044

> stuck cluster was detected on dcda195ffe5e in this episode

- register: `diagnosis` | subject: `task_geometry` | type: `component_specific_attribution`
- refs: `obs:stuck_cluster:dcda195ffe5e@56f2bbdf0e74`

| R1 | R2 | R3 | R4 | R5 |
|---|---|---|---|---|
| descriptive_only | yes | some | n/a | n/a |

### 045

> latency spike was detected on e1251e42a20b in this episode

- register: `diagnosis` | subject: `task_geometry` | type: `component_specific_attribution`
- refs: `obs:latency_spike:e1251e42a20b@56f2bbdf0e74`

| R1 | R2 | R3 | R4 | R5 |
|---|---|---|---|---|
| descriptive_only | n/a | none | n/a | n/a |

### 046

> a pattern worse on e1251e42a20b than on the other side is consistent with local minimum entrapment

- register: `contrast` | subject: `local_controller` | type: `local_minimum_entrapment`
- refs: `contrast:detection_worse_on_loser:2`

| R1 | R2 | R3 | R4 | R5 |
|---|---|---|---|---|
| descriptive_only | n/a | none | n/a | n/a |

### 047

> stuck cluster was detected on e1251e42a20b in this episode

- register: `diagnosis` | subject: `task_geometry` | type: `component_specific_attribution`
- refs: `obs:stuck_cluster:e1251e42a20b@56f2bbdf0e74`

| R1 | R2 | R3 | R4 | R5 |
|---|---|---|---|---|
| descriptive_only | yes | some | n/a | n/a |

### 048

> a pattern present on e1251e42a20b and absent on the other side is consistent with expansion latency association

- register: `contrast` | subject: `global_planner` | type: `expansion_latency_association`
- refs: `contrast:detection_only_on_loser:1`

| R1 | R2 | R3 | R4 | R5 |
|---|---|---|---|---|
| descriptive_only | n/a | none | n/a | n/a |

## Luot 3/3

**R6 - episode nay co giai thich duoc vi sao ben thang hon khong?**

> **packet co the tra loi why** - co contrast `support`.

| R6 |
|---|
| explains |

### 049

> local_controller on C5 became stuck for 5.75 seconds in a stuck_cluster, delaying its motion more than on C1

- register: `diagnosis` | subject: `local_controller` | type: `local_minimum_entrapment`
- refs: `contrast:detection_worse_on_loser:2`
- contract: `contrast_support`, `subject_match`, `polarity_match`

| R1 | R2 | R3 | R4 | R5 |
|---|---|---|---|---|
| supported_explanation | yes | some | exact | n/a |

---

# Episode `6a4888cdcf9e`

*cluster: sudden_stop_custom_v2_full_stack_selection_06f40334 | vai: holdout*

<details open><summary><b>PACKET</b></summary>

**Phan quyet**: episode_decision_utility | thang: `C5` | thua: `C1`

**Khac biet giua hai ben**

| ref | strength | noi gi | so kem theo |
|---|---|---|---|
| `contrast:component_differs:1` | **context** | the two stacks differ in global_planner, local_controller, local_controller_config; a mechanism that explains the difference has to live in one of those | - |
| `contrast:divergence_precedes_outcome:2` | **context** | the two runs parted at 3.1 m along the route | - |
| `contrast:outcome_differs:3` | **context** | C5 ended this episode ahead of C1 on worst clearance, travel time | min clearance loser = 0.195778; min clearance winner = 0.24637; travel time s loser = 28.5; travel time s winner = 26.2 |

**Detector da ban**

| ref | tren ai | so kem theo |
|---|---|---|
| `obs:stuck_cluster:C1@6a4888cdcf9e` | `C1` | stopped_seconds = 2.05; stops = 1; window.end_m = 7.50602; window.end_s = 19.35; window.start_m = 7.50288; window.start_s = 17.3 |
| `obs:stuck_cluster:C5@6a4888cdcf9e` | `C5` | stopped_seconds = 5.9; stops = 1; window.end_m = 3.69722; window.end_s = 12.15; window.start_m = 3.68313; window.start_s = 6.25 |

**So do duoc cua tung ben**

- `C1`: collision_count = 0 | min_clearance = 0.195778 | p99_latency_ms = 0 | replan_count = 0 | success = 1 | travel_time_s = 28.5
- `C5`: collision_count = 0 | min_clearance = 0.24637 | p99_latency_ms = 19.3955 | replan_count = 1 | success = 1 | travel_time_s = 26.2

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

## Luot 1/3

**R6 - episode nay co giai thich duoc vi sao ben thang hon khong?**

> packet khong co contrast `support`.

| R6 |
|---|
| describes_only |

### 050

> The local_controller in C1 entered a stuck cluster and stopped for 2.05 seconds, indicating a local minimum entrapment.

- register: `diagnosis` | subject: `local_controller` | type: `local_minimum_entrapment`
- refs: `obs:stuck_cluster:C1@6a4888cdcf9e`, `obs:stuck_cluster:C1@6a4888cdcf9e/stopped_seconds`

| R1 | R2 | R3 | R4 | R5 |
|---|---|---|---|---|
| descriptive_only | yes | some | exact | n/a |

### 051

> The local_controller in C5 entered a stuck cluster and stopped for 5.9 seconds, indicating a local minimum entrapment.

- register: `diagnosis` | subject: `local_controller` | type: `local_minimum_entrapment`
- refs: `obs:stuck_cluster:C5@6a4888cdcf9e`, `obs:stuck_cluster:C5@6a4888cdcf9e/stopped_seconds`

| R1 | R2 | R3 | R4 | R5 |
|---|---|---|---|---|
| descriptive_only | yes | some | exact | n/a |

## Luot 2/3

**R6 - episode nay co giai thich duoc vi sao ben thang hon khong?**

> packet khong co contrast `support`.
>
> **KHONG PHAI MODEL VIET.** Moi de xuat cua model deu bi tu choi; cac cau duoi day do floor sinh tu packet. Voi R6 day la analyst **im lang** - `explains` khong the cham o day.

| R6 |
|---|
| silent_correctly |

### 052

> stuck cluster was detected on dcda195ffe5e in this episode

- register: `diagnosis` | subject: `task_geometry` | type: `component_specific_attribution`
- refs: `obs:stuck_cluster:dcda195ffe5e@6a4888cdcf9e`

| R1 | R2 | R3 | R4 | R5 |
|---|---|---|---|---|
| descriptive_only | yes | some | n/a | n/a |

### 053

> stuck cluster was detected on e1251e42a20b in this episode

- register: `diagnosis` | subject: `task_geometry` | type: `component_specific_attribution`
- refs: `obs:stuck_cluster:e1251e42a20b@6a4888cdcf9e`

| R1 | R2 | R3 | R4 | R5 |
|---|---|---|---|---|
| descriptive_only | n/a | none | n/a | n/a |

## Luot 3/3

**R6 - episode nay co giai thich duoc vi sao ben thang hon khong?**

> packet khong co contrast `support`.

| R6 |
|---|
| describes_only |

### 054

> C5 experienced a stuck cluster lasting 5.9 seconds

- register: `diagnosis` | subject: `local_controller` | type: `local_minimum_entrapment`
- refs: `obs:stuck_cluster:C5@6a4888cdcf9e`, `obs:stuck_cluster:C5@6a4888cdcf9e/stopped_seconds`

| R1 | R2 | R3 | R4 | R5 |
|---|---|---|---|---|
| descriptive_only | n/a | none | exact | n/a |

---

# Episode `7323e60af732`

*cluster: sudden_stop_custom_v2_full_stack_selection_06f40334 | vai: holdout*

<details open><summary><b>PACKET</b></summary>

**Phan quyet**: episode_decision_utility | thang: `C1` | thua: `C5`

**Khac biet giua hai ben**

| ref | strength | noi gi | so kem theo |
|---|---|---|---|
| `contrast:component_differs:2` | **context** | the two stacks differ in global_planner, local_controller, local_controller_config; a mechanism that explains the difference has to live in one of those | - |
| `contrast:detection_worse_on_loser:1` | **support** | stuck_cluster fired on both, and materially worse on C5 | severity ratio = 4.5; stopped seconds = 5.85; stops = 1 |
| `contrast:divergence_precedes_outcome:3` | **context** | the two runs parted at 3.2 m along the route | - |

**Detector da ban**

| ref | tren ai | so kem theo |
|---|---|---|
| `obs:stuck_cluster:C1@7323e60af732` | `C1` | stopped_seconds = 1.3; stops = 1; window.end_m = 7.4769; window.end_s = 18.1; window.start_m = 7.47253; window.start_s = 16.8 |
| `obs:stuck_cluster:C5@7323e60af732` | `C5` | stopped_seconds = 5.85; stops = 1; window.end_m = 3.65162; window.end_s = 12.05; window.start_m = 3.63715; window.start_s = 6.2 |

**So do duoc cua tung ben**

- `C1`: collision_count = 0 | min_clearance = 0.204662 | p99_latency_ms = 0 | replan_count = 0 | success = 1 | travel_time_s = 26.25
- `C5`: collision_count = 0 | min_clearance = 0.260035 | p99_latency_ms = 20.3536 | replan_count = 1 | success = 1 | travel_time_s = 25.85

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

## Luot 1/3

**R6 - episode nay co giai thich duoc vi sao ben thang hon khong?**

> **packet co the tra loi why** - co contrast `support`.

| R6 |
|---|
| describes_only |

### 055

> The local_controller in C5 led to a worse stuck_cluster stop time than in C1, as shown by a severity ratio of 4.5.

- register: `diagnosis` | subject: `local_controller` | type: `local_minimum_entrapment`
- refs: `contrast:detection_worse_on_loser:1`
- contract: `contrast_support`, `subject_match`, `polarity_match`

| R1 | R2 | R3 | R4 | R5 |
|---|---|---|---|---|
| descriptive_only | yes | some | exact | n/a |

## Luot 2/3

**R6 - episode nay co giai thich duoc vi sao ben thang hon khong?**

> **packet co the tra loi why** - co contrast `support`.

| R6 |
|---|
| wrong |

### 056

> The local_controller triggered a replan on C5 while no replan occurred on C1 (1 vs 0), indicating extra replanning overhead on C5.

- register: `diagnosis` | subject: `local_controller` | type: `component_specific_attribution`
- refs: `diag:C5.replan_count`, `diag:C1.replan_count`

| R1 | R2 | R3 | R4 | R5 |
|---|---|---|---|---|
| plausible_explanation | no | some | exact | n/a |

## Luot 3/3

**R6 - episode nay co giai thich duoc vi sao ben thang hon khong?**

> **packet co the tra loi why** - co contrast `support`.

| R6 |
|---|
| explains |

### 057

> local_controller on C5 entered a deeper local minimum entrapment, with stuck_cluster lasting 5.85 whereas on C1 it lasted 1.3, delaying C5

- register: `contrast` | subject: `local_controller` | type: `local_minimum_entrapment`
- refs: `contrast:detection_worse_on_loser:1`, `obs:stuck_cluster:C5@7323e60af732`, `obs:stuck_cluster:C1@7323e60af732`
- contract: `contrast_support`, `occurrence_evidence`, `subject_match`, `polarity_match`

| R1 | R2 | R3 | R4 | R5 |
|---|---|---|---|---|
| supported_explanation | yes | some | exact | n/a |

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

## Luot 1/3

**R6 - episode nay co giai thich duoc vi sao ben thang hon khong?**

> **packet co the tra loi why** - co contrast `support`.
>
> **KHONG PHAI MODEL VIET.** Moi de xuat cua model deu bi tu choi; cac cau duoi day do floor sinh tu packet. Voi R6 day la analyst **im lang** - `explains` khong the cham o day.

| R6 |
|---|
| silent_wrongly |

### 058

> stuck cluster was detected on dcda195ffe5e in this episode

- register: `diagnosis` | subject: `task_geometry` | type: `component_specific_attribution`
- refs: `obs:stuck_cluster:dcda195ffe5e@75974f6bd2c9`

| R1 | R2 | R3 | R4 | R5 |
|---|---|---|---|---|
| descriptive_only | yes | some | n/a | n/a |

### 059

> a pattern worse on e1251e42a20b than on the other side is consistent with local minimum entrapment

- register: `contrast` | subject: `local_controller` | type: `local_minimum_entrapment`
- refs: `contrast:detection_worse_on_loser:1`

| R1 | R2 | R3 | R4 | R5 |
|---|---|---|---|---|
| descriptive_only | n/a | none | n/a | n/a |

### 060

> stuck cluster was detected on e1251e42a20b in this episode

- register: `diagnosis` | subject: `task_geometry` | type: `component_specific_attribution`
- refs: `obs:stuck_cluster:e1251e42a20b@75974f6bd2c9`

| R1 | R2 | R3 | R4 | R5 |
|---|---|---|---|---|
| descriptive_only | yes | some | n/a | n/a |

## Luot 2/3

**R6 - episode nay co giai thich duoc vi sao ben thang hon khong?**

> **packet co the tra loi why** - co contrast `support`.
>
> **KHONG PHAI MODEL VIET.** Moi de xuat cua model deu bi tu choi; cac cau duoi day do floor sinh tu packet. Voi R6 day la analyst **im lang** - `explains` khong the cham o day.

| R6 |
|---|
| silent_wrongly |

### 061

> stuck cluster was detected on dcda195ffe5e in this episode

- register: `diagnosis` | subject: `task_geometry` | type: `component_specific_attribution`
- refs: `obs:stuck_cluster:dcda195ffe5e@75974f6bd2c9`

| R1 | R2 | R3 | R4 | R5 |
|---|---|---|---|---|
| descriptive_only | n/a | none | n/a | n/a |

### 062

> stuck cluster was detected on e1251e42a20b in this episode

- register: `diagnosis` | subject: `task_geometry` | type: `component_specific_attribution`
- refs: `obs:stuck_cluster:e1251e42a20b@75974f6bd2c9`

| R1 | R2 | R3 | R4 | R5 |
|---|---|---|---|---|
| descriptive_only | n/a | none | n/a | n/a |

### 063

> a pattern worse on e1251e42a20b than on the other side is consistent with local minimum entrapment

- register: `contrast` | subject: `local_controller` | type: `local_minimum_entrapment`
- refs: `contrast:detection_worse_on_loser:1`

| R1 | R2 | R3 | R4 | R5 |
|---|---|---|---|---|
| descriptive_only | n/a | none | n/a | n/a |

## Luot 3/3

**R6 - episode nay co giai thich duoc vi sao ben thang hon khong?**

> **packet co the tra loi why** - co contrast `support`.
>
> **KHONG PHAI MODEL VIET.** Moi de xuat cua model deu bi tu choi; cac cau duoi day do floor sinh tu packet. Voi R6 day la analyst **im lang** - `explains` khong the cham o day.

| R6 |
|---|
| silent_wrongly |

### 064

> a pattern worse on e1251e42a20b than on the other side is consistent with local minimum entrapment

- register: `contrast` | subject: `local_controller` | type: `local_minimum_entrapment`
- refs: `contrast:detection_worse_on_loser:1`

| R1 | R2 | R3 | R4 | R5 |
|---|---|---|---|---|
| descriptive_only | yes | some | n/a | n/a |

### 065

> stuck cluster was detected on e1251e42a20b in this episode

- register: `diagnosis` | subject: `task_geometry` | type: `component_specific_attribution`
- refs: `obs:stuck_cluster:e1251e42a20b@75974f6bd2c9`

| R1 | R2 | R3 | R4 | R5 |
|---|---|---|---|---|
| descriptive_only | yes | some | n/a | n/a |

### 066

> stuck cluster was detected on dcda195ffe5e in this episode

- register: `diagnosis` | subject: `task_geometry` | type: `component_specific_attribution`
- refs: `obs:stuck_cluster:dcda195ffe5e@75974f6bd2c9`

| R1 | R2 | R3 | R4 | R5 |
|---|---|---|---|---|
| descriptive_only | n/a | none | n/a | n/a |

---

# Episode `7764fd5de7a5`

*cluster: sudden_stop_custom_v2_full_stack_selection_06f40334 | vai: holdout*

<details open><summary><b>PACKET</b></summary>

**Phan quyet**: episode_decision_utility | thang: `C1` | thua: `C5`

**Khac biet giua hai ben**

| ref | strength | noi gi | so kem theo |
|---|---|---|---|
| `contrast:component_differs:2` | **context** | the two stacks differ in global_planner, local_controller, local_controller_config; a mechanism that explains the difference has to live in one of those | - |
| `contrast:detection_worse_on_loser:1` | **support** | stuck_cluster fired on both, and materially worse on C5 | severity ratio = 4.46154; stopped seconds = 5.8; stops = 1 |
| `contrast:divergence_precedes_outcome:3` | **context** | the two runs parted at 3.1 m along the route | - |

**Detector da ban**

| ref | tren ai | so kem theo |
|---|---|---|
| `obs:stuck_cluster:C1@7764fd5de7a5` | `C1` | stopped_seconds = 1.3; stops = 1; window.end_m = 7.4842; window.end_s = 20.05; window.start_m = 7.47962; window.start_s = 18.75 |
| `obs:stuck_cluster:C5@7764fd5de7a5` | `C5` | stopped_seconds = 5.8; stops = 1; window.end_m = 3.65597; window.end_s = 11.95; window.start_m = 3.64425; window.start_s = 6.15 |

**So do duoc cua tung ben**

- `C1`: collision_count = 0 | min_clearance = 0.215321 | p99_latency_ms = 0 | replan_count = 0 | success = 1 | travel_time_s = 27.95
- `C5`: collision_count = 0 | min_clearance = 0.227563 | p99_latency_ms = 24.2508 | replan_count = 1 | success = 1 | travel_time_s = 26

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

## Luot 1/3

**R6 - episode nay co giai thich duoc vi sao ben thang hon khong?**

> **packet co the tra loi why** - co contrast `support`.
>
> **KHONG PHAI MODEL VIET.** Moi de xuat cua model deu bi tu choi; cac cau duoi day do floor sinh tu packet. Voi R6 day la analyst **im lang** - `explains` khong the cham o day.

| R6 |
|---|
| silent_wrongly |

### 067

> a pattern worse on e1251e42a20b than on the other side is consistent with local minimum entrapment

- register: `contrast` | subject: `local_controller` | type: `local_minimum_entrapment`
- refs: `contrast:detection_worse_on_loser:1`

| R1 | R2 | R3 | R4 | R5 |
|---|---|---|---|---|
| descriptive_only | n/a | none | n/a | n/a |

### 068

> stuck cluster was detected on dcda195ffe5e in this episode

- register: `diagnosis` | subject: `task_geometry` | type: `component_specific_attribution`
- refs: `obs:stuck_cluster:dcda195ffe5e@7764fd5de7a5`

| R1 | R2 | R3 | R4 | R5 |
|---|---|---|---|---|
| descriptive_only | yes | some | n/a | n/a |

### 069

> stuck cluster was detected on e1251e42a20b in this episode

- register: `diagnosis` | subject: `task_geometry` | type: `component_specific_attribution`
- refs: `obs:stuck_cluster:e1251e42a20b@7764fd5de7a5`

| R1 | R2 | R3 | R4 | R5 |
|---|---|---|---|---|
| descriptive_only | n/a | none | n/a | n/a |

## Luot 2/3

**R6 - episode nay co giai thich duoc vi sao ben thang hon khong?**

> **packet co the tra loi why** - co contrast `support`.
>
> **KHONG PHAI MODEL VIET.** Moi de xuat cua model deu bi tu choi; cac cau duoi day do floor sinh tu packet. Voi R6 day la analyst **im lang** - `explains` khong the cham o day.

| R6 |
|---|
| silent_wrongly |

### 070

> stuck cluster was detected on e1251e42a20b in this episode

- register: `diagnosis` | subject: `task_geometry` | type: `component_specific_attribution`
- refs: `obs:stuck_cluster:e1251e42a20b@7764fd5de7a5`

| R1 | R2 | R3 | R4 | R5 |
|---|---|---|---|---|
| descriptive_only | n/a | none | n/a | n/a |

### 071

> a pattern worse on e1251e42a20b than on the other side is consistent with local minimum entrapment

- register: `contrast` | subject: `local_controller` | type: `local_minimum_entrapment`
- refs: `contrast:detection_worse_on_loser:1`

| R1 | R2 | R3 | R4 | R5 |
|---|---|---|---|---|
| descriptive_only | n/a | none | n/a | n/a |

### 072

> stuck cluster was detected on dcda195ffe5e in this episode

- register: `diagnosis` | subject: `task_geometry` | type: `component_specific_attribution`
- refs: `obs:stuck_cluster:dcda195ffe5e@7764fd5de7a5`

| R1 | R2 | R3 | R4 | R5 |
|---|---|---|---|---|
| descriptive_only | yes | some | n/a | n/a |

## Luot 3/3

**R6 - episode nay co giai thich duoc vi sao ben thang hon khong?**

> **packet co the tra loi why** - co contrast `support`.

| R6 |
|---|
| explains |

### 073

> local_controller on C5 experienced a more severe local minimum entrapment, as shown by its stuck_cluster causing a 5.8-second delay compared to C1

- register: `diagnosis` | subject: `local_controller` | type: `local_minimum_entrapment`
- refs: `contrast:detection_worse_on_loser:1`
- contract: `contrast_support`, `subject_match`, `polarity_match`

| R1 | R2 | R3 | R4 | R5 |
|---|---|---|---|---|
| supported_explanation | n/a | none | exact | n/a |

---

# Episode `8c3bfce9bb13`

*cluster: sudden_stop_custom_v2_full_stack_selection_06f40334 | vai: holdout*

<details open><summary><b>PACKET</b></summary>

**Phan quyet**: episode_decision_utility | thang: `C1` | thua: `C5`

**Khac biet giua hai ben**

| ref | strength | noi gi | so kem theo |
|---|---|---|---|
| `contrast:component_differs:2` | **context** | the two stacks differ in global_planner, local_controller, local_controller_config; a mechanism that explains the difference has to live in one of those | - |
| `contrast:detection_worse_on_loser:1` | **support** | stuck_cluster fired on both, and materially worse on C5 | severity ratio = 4.37037; stopped seconds = 5.9; stops = 1 |
| `contrast:divergence_precedes_outcome:3` | **context** | the two runs parted at 3.0 m along the route | - |

**Detector da ban**

| ref | tren ai | so kem theo |
|---|---|---|
| `obs:stuck_cluster:C1@8c3bfce9bb13` | `C1` | stopped_seconds = 1.35; stops = 1; window.end_m = 7.41253; window.end_s = 18.35; window.start_m = 7.40803; window.start_s = 17 |
| `obs:stuck_cluster:C5@8c3bfce9bb13` | `C5` | stopped_seconds = 5.9; stops = 1; window.end_m = 3.64148; window.end_s = 12.05; window.start_m = 3.61055; window.start_s = 6.15 |

**So do duoc cua tung ben**

- `C1`: collision_count = 0 | min_clearance = 0.216311 | p99_latency_ms = 0 | replan_count = 0 | success = 1 | travel_time_s = 26.2
- `C5`: collision_count = 0 | min_clearance = 0.286078 | p99_latency_ms = 22.2857 | replan_count = 1 | success = 1 | travel_time_s = 25.7

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

## Luot 1/3

**R6 - episode nay co giai thich duoc vi sao ben thang hon khong?**

> **packet co the tra loi why** - co contrast `support`.

| R6 |
|---|
| explains |

### 074

> The local_controller on C5 experienced a local minimum entrapment that kept it stuck for 5.9 seconds, exceeding the 1.35 seconds observed on C1, contributing to C5 losing the episode.

- register: `diagnosis` | subject: `local_controller` | type: `local_minimum_entrapment`
- refs: `contrast:detection_worse_on_loser:1`
- contract: `contrast_support`, `subject_match`, `polarity_match`

| R1 | R2 | R3 | R4 | R5 |
|---|---|---|---|---|
| supported_explanation | yes | some | exact | n/a |

## Luot 2/3

**R6 - episode nay co giai thich duoc vi sao ben thang hon khong?**

> **packet co the tra loi why** - co contrast `support`.

| R6 |
|---|
| explains |

### 075

> local_controller on C5 experienced a longer local minimum entrapment than on C1, delaying C5 by 5.9 compared to 1.35

- register: `diagnosis` | subject: `local_controller` | type: `local_minimum_entrapment`
- refs: `contrast:detection_worse_on_loser:1`
- contract: `contrast_support`, `subject_match`, `polarity_match`

| R1 | R2 | R3 | R4 | R5 |
|---|---|---|---|---|
| supported_explanation | yes | some | exact | n/a |

## Luot 3/3

**R6 - episode nay co giai thich duoc vi sao ben thang hon khong?**

> **packet co the tra loi why** - co contrast `support`.

| R6 |
|---|
| explains |

### 076

> The stuck_cluster event under the local_controller produced 5.9 of stopped time on the losing candidate, exceeding the 1.35 on the winner, implicating the local_controller in the performance difference.

- register: `contrast` | subject: `local_controller` | type: `local_minimum_entrapment`
- refs: `contrast:detection_worse_on_loser:1`, `obs:stuck_cluster:C1@8c3bfce9bb13/stopped_seconds`, `obs:stuck_cluster:C5@8c3bfce9bb13/stopped_seconds`
- contract: `contrast_support`, `occurrence_evidence`, `subject_match`, `polarity_match`

| R1 | R2 | R3 | R4 | R5 |
|---|---|---|---|---|
| supported_explanation | yes | some | exact | n/a |

### 077

> The local_controller on the losing candidate experienced a stuck_cluster entrapment lasting 5.9 seconds during this episode.

- register: `diagnosis` | subject: `local_controller` | type: `local_minimum_entrapment`
- refs: `obs:stuck_cluster:C5@8c3bfce9bb13/stopped_seconds`

| R1 | R2 | R3 | R4 | R5 |
|---|---|---|---|---|
| descriptive_only | yes | some | exact | n/a |

---

# Episode `8ca3fa8191d8`

*cluster: sudden_stop_custom_v2_full_stack_selection_06f40334 | vai: holdout*

<details open><summary><b>PACKET</b></summary>

**Phan quyet**: episode_decision_utility | thang: `C5` | thua: `C1`

**Khac biet giua hai ben**

| ref | strength | noi gi | so kem theo |
|---|---|---|---|
| `contrast:component_differs:3` | **context** | the two stacks differ in global_planner, local_controller, local_controller_config; a mechanism that explains the difference has to live in one of those | - |
| `contrast:detection_only_on_loser:1` | **support** | latency_spike fired on C1 and not on C5 | peak latency ms = 3385.04; ticks = 1 |
| `contrast:detection_worse_on_loser:2` | **support** | stuck_cluster fired on both, and materially worse on C1 | severity ratio = 2.5431; stopped seconds = 14.75; stops = 1 |
| `contrast:divergence_precedes_outcome:4` | **context** | the two runs parted at 3.2 m along the route | - |
| `contrast:outcome_differs:5` | **context** | C5 ended this episode ahead of C1 on travel time | travel time s loser = 41.95; travel time s winner = 27.05 |

**Detector da ban**

| ref | tren ai | so kem theo |
|---|---|---|
| `obs:latency_spike:C1@8ca3fa8191d8` | `C1` | peak_latency_ms = 3385.04; ticks = 1; window.end_m = 7.55288; window.end_s = 33.35; window.start_m = 7.55288; window.start_s = 33.35 |
| `obs:stuck_cluster:C1@8ca3fa8191d8` | `C1` | stopped_seconds = 14.75; stops = 1; window.end_m = 7.55413; window.end_s = 33.4; window.start_m = 7.54949; window.start_s = 18.65 |
| `obs:stuck_cluster:C5@8ca3fa8191d8` | `C5` | stopped_seconds = 5.8; stops = 1; window.end_m = 3.63791; window.end_s = 11.95; window.start_m = 3.59699; window.start_s = 6.15 |

**So do duoc cua tung ben**

- `C1`: collision_count = 0 | min_clearance = 0.206774 | p99_latency_ms = 0 | replan_count = 3 | success = 1 | travel_time_s = 41.95
- `C5`: collision_count = 0 | min_clearance = 0.157682 | p99_latency_ms = 18.7668 | replan_count = 1 | success = 1 | travel_time_s = 27.05

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

## Luot 1/3

**R6 - episode nay co giai thich duoc vi sao ben thang hon khong?**

> **packet co the tra loi why** - co contrast `support`.

| R6 |
|---|
| explains |

### 078

> The local_controller on C1 encountered a more severe stuck_cluster than on C5, stopping C1 for 14.75 seconds, further delaying its run.

- register: `diagnosis` | subject: `local_controller` | type: `local_minimum_entrapment`
- refs: `contrast:detection_worse_on_loser:2`
- contract: `contrast_support`, `subject_match`, `polarity_match`

| R1 | R2 | R3 | R4 | R5 |
|---|---|---|---|---|
| supported_explanation | yes | some | exact | n/a |

## Luot 2/3

**R6 - episode nay co giai thich duoc vi sao ben thang hon khong?**

> **packet co the tra loi why** - co contrast `support`.

| R6 |
|---|
| explains |

### 079

> The local_controller on C1 was caught in a stuck cluster that stopped the robot for 14.75 seconds, delaying it relative to C5

- register: `diagnosis` | subject: `local_controller` | type: `local_minimum_entrapment`
- refs: `contrast:detection_worse_on_loser:2`
- contract: `contrast_support`, `subject_match`, `polarity_match`

| R1 | R2 | R3 | R4 | R5 |
|---|---|---|---|---|
| supported_explanation | yes | some | exact | n/a |

## Luot 3/3

**R6 - episode nay co giai thich duoc vi sao ben thang hon khong?**

> **packet co the tra loi why** - co contrast `support`.
>
> **KHONG PHAI MODEL VIET.** Moi de xuat cua model deu bi tu choi; cac cau duoi day do floor sinh tu packet. Voi R6 day la analyst **im lang** - `explains` khong the cham o day.

| R6 |
|---|
| silent_wrongly |

### 080

> a pattern present on dcda195ffe5e and absent on the other side is consistent with expansion latency association

- register: `contrast` | subject: `global_planner` | type: `expansion_latency_association`
- refs: `contrast:detection_only_on_loser:1`

| R1 | R2 | R3 | R4 | R5 |
|---|---|---|---|---|
| descriptive_only | yes | some | n/a | n/a |

### 081

> a pattern worse on dcda195ffe5e than on the other side is consistent with local minimum entrapment

- register: `contrast` | subject: `local_controller` | type: `local_minimum_entrapment`
- refs: `contrast:detection_worse_on_loser:2`

| R1 | R2 | R3 | R4 | R5 |
|---|---|---|---|---|
| descriptive_only | yes | some | n/a | n/a |

### 082

> latency spike was detected on dcda195ffe5e in this episode

- register: `diagnosis` | subject: `task_geometry` | type: `component_specific_attribution`
- refs: `obs:latency_spike:dcda195ffe5e@8ca3fa8191d8`

| R1 | R2 | R3 | R4 | R5 |
|---|---|---|---|---|
| descriptive_only | yes | some | n/a | n/a |

### 083

> stuck cluster was detected on dcda195ffe5e in this episode

- register: `diagnosis` | subject: `task_geometry` | type: `component_specific_attribution`
- refs: `obs:stuck_cluster:dcda195ffe5e@8ca3fa8191d8`

| R1 | R2 | R3 | R4 | R5 |
|---|---|---|---|---|
| descriptive_only | n/a | none | n/a | n/a |

### 084

> stuck cluster was detected on e1251e42a20b in this episode

- register: `diagnosis` | subject: `task_geometry` | type: `component_specific_attribution`
- refs: `obs:stuck_cluster:e1251e42a20b@8ca3fa8191d8`

| R1 | R2 | R3 | R4 | R5 |
|---|---|---|---|---|
| descriptive_only | n/a | none | n/a | n/a |

---

# Episode `91ec9d58e922`

*cluster: sudden_stop_custom_v2_full_stack_selection_06f40334 | vai: holdout*

<details open><summary><b>PACKET</b></summary>

**Phan quyet**: episode_decision_utility | thang: `C5` | thua: `C1`

**Khac biet giua hai ben**

| ref | strength | noi gi | so kem theo |
|---|---|---|---|
| `contrast:component_differs:2` | **context** | the two stacks differ in global_planner, local_controller, local_controller_config; a mechanism that explains the difference has to live in one of those | - |
| `contrast:detection_only_on_loser:1` | **support** | near_miss_cluster fired on C1 and not on C5 | min clearance m = 0.148568; samples = 3 |
| `contrast:divergence_precedes_outcome:3` | **context** | the two runs parted at 3.0 m along the route | - |
| `contrast:outcome_differs:4` | **context** | C5 ended this episode ahead of C1 on worst clearance, travel time | min clearance loser = 0.148568; min clearance winner = 0.244688; travel time s loser = 29.45; travel time s winner = 26.9 |

**Detector da ban**

| ref | tren ai | so kem theo |
|---|---|---|
| `obs:near_miss_cluster:C1@91ec9d58e922` | `C1` | min_clearance_m = 0.148568; samples = 3; window.end_m = 8.19859; window.end_s = 23.35; window.start_m = 8.13984; window.start_s = 23.25 |
| `obs:stuck_cluster:C1@91ec9d58e922` | `C1` | stopped_seconds = 2.45; stops = 1; window.end_m = 7.54859; window.end_s = 21.5; window.start_m = 7.54609; window.start_s = 19.05 |
| `obs:stuck_cluster:C5@91ec9d58e922` | `C5` | stopped_seconds = 6.2; stops = 1; window.end_m = 3.63874; window.end_s = 12.95; window.start_m = 3.57926; window.start_s = 6.75 |

**So do duoc cua tung ben**

- `C1`: collision_count = 0 | min_clearance = 0.148568 | p99_latency_ms = 0 | replan_count = 0 | success = 1 | travel_time_s = 29.45
- `C5`: collision_count = 0 | min_clearance = 0.244688 | p99_latency_ms = 19.5977 | replan_count = 1 | success = 1 | travel_time_s = 26.9

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

## Luot 1/3

**R6 - episode nay co giai thich duoc vi sao ben thang hon khong?**

> **packet co the tra loi why** - co contrast `support`.
>
> **KHONG PHAI MODEL VIET.** Moi de xuat cua model deu bi tu choi; cac cau duoi day do floor sinh tu packet. Voi R6 day la analyst **im lang** - `explains` khong the cham o day.

| R6 |
|---|
| silent_wrongly |

### 085

> stuck cluster was detected on dcda195ffe5e in this episode

- register: `diagnosis` | subject: `task_geometry` | type: `component_specific_attribution`
- refs: `obs:stuck_cluster:dcda195ffe5e@91ec9d58e922`

| R1 | R2 | R3 | R4 | R5 |
|---|---|---|---|---|
| descriptive_only | n/a | none | n/a | n/a |

### 086

> stuck cluster was detected on e1251e42a20b in this episode

- register: `diagnosis` | subject: `task_geometry` | type: `component_specific_attribution`
- refs: `obs:stuck_cluster:e1251e42a20b@91ec9d58e922`

| R1 | R2 | R3 | R4 | R5 |
|---|---|---|---|---|
| descriptive_only | n/a | none | n/a | n/a |

### 087

> near miss cluster was detected on dcda195ffe5e in this episode

- register: `diagnosis` | subject: `task_geometry` | type: `component_specific_attribution`
- refs: `obs:near_miss_cluster:dcda195ffe5e@91ec9d58e922`

| R1 | R2 | R3 | R4 | R5 |
|---|---|---|---|---|
| descriptive_only | n/a | none | n/a | n/a |

## Luot 2/3

**R6 - episode nay co giai thich duoc vi sao ben thang hon khong?**

> **packet co the tra loi why** - co contrast `support`.

| R6 |
|---|
| describes_only |

### 088

> The local_controller on C1 produced a near miss cluster with minimum clearance 0.15.

- register: `diagnosis` | subject: `local_controller` | type: `component_specific_attribution`
- refs: `obs:near_miss_cluster:C1@91ec9d58e922`

| R1 | R2 | R3 | R4 | R5 |
|---|---|---|---|---|
| descriptive_only | n/a | none | rounded | n/a |

## Luot 3/3

**R6 - episode nay co giai thich duoc vi sao ben thang hon khong?**

> **packet co the tra loi why** - co contrast `support`.

| R6 |
|---|
| describes_only |

### 089

> The global_planner of C5 performed 1 replans during this episode

- register: `diagnosis` | subject: `global_planner` | type: `component_specific_attribution`
- refs: `diag:C5.replan_count`

| R1 | R2 | R3 | R4 | R5 |
|---|---|---|---|---|
| descriptive_only | yes | some | exact | n/a |

### 090

> The local_controller refused close clearance on C1, as indicated by the near_miss_cluster firing on C1 and not on C5 in this episode

- register: `diagnosis` | subject: `local_controller` | type: `clearance_refusal`
- refs: `contrast:detection_only_on_loser:1`
- contract: `contrast_support`, `subject_match`, `polarity_match`

| R1 | R2 | R3 | R4 | R5 |
|---|---|---|---|---|
| plausible_explanation | yes | some | n/a | n/a |

---

# Episode `9c30ffabf757`

*cluster: sudden_stop_custom_v2_full_stack_selection_06f40334 | vai: holdout*

<details open><summary><b>PACKET</b></summary>

**Phan quyet**: episode_decision_utility | thang: `C5` | thua: `C1`

**Khac biet giua hai ben**

| ref | strength | noi gi | so kem theo |
|---|---|---|---|
| `contrast:component_differs:1` | **context** | the two stacks differ in global_planner, local_controller, local_controller_config; a mechanism that explains the difference has to live in one of those | - |
| `contrast:divergence_precedes_outcome:2` | **context** | the two runs parted at 3.1 m along the route | - |
| `contrast:outcome_differs:3` | **context** | C5 ended this episode ahead of C1 on worst clearance | min clearance loser = 0.236064; min clearance winner = 0.258631 |

**Detector da ban**

| ref | tren ai | so kem theo |
|---|---|---|
| `obs:stuck_cluster:C1@9c30ffabf757` | `C1` | stopped_seconds = 1.25; stops = 1; window.end_m = 7.28549; window.end_s = 17.3; window.start_m = 7.28159; window.start_s = 16.05 |
| `obs:stuck_cluster:C5@9c30ffabf757` | `C5` | stopped_seconds = 5.9; stops = 1; window.end_m = 3.63882; window.end_s = 12.05; window.start_m = 3.59958; window.start_s = 6.15 |

**So do duoc cua tung ben**

- `C1`: collision_count = 0 | min_clearance = 0.236064 | p99_latency_ms = 0 | replan_count = 0 | success = 1 | travel_time_s = 25
- `C5`: collision_count = 0 | min_clearance = 0.258631 | p99_latency_ms = 19.1811 | replan_count = 1 | success = 1 | travel_time_s = 25.8

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

## Luot 1/3

**R6 - episode nay co giai thich duoc vi sao ben thang hon khong?**

> packet khong co contrast `support`.
>
> **KHONG PHAI MODEL VIET.** Moi de xuat cua model deu bi tu choi; cac cau duoi day do floor sinh tu packet. Voi R6 day la analyst **im lang** - `explains` khong the cham o day.

| R6 |
|---|
| silent_correctly |

### 091

> stuck cluster was detected on dcda195ffe5e in this episode

- register: `diagnosis` | subject: `task_geometry` | type: `component_specific_attribution`
- refs: `obs:stuck_cluster:dcda195ffe5e@9c30ffabf757`

| R1 | R2 | R3 | R4 | R5 |
|---|---|---|---|---|
| descriptive_only | yes | some | n/a | n/a |

### 092

> stuck cluster was detected on e1251e42a20b in this episode

- register: `diagnosis` | subject: `task_geometry` | type: `component_specific_attribution`
- refs: `obs:stuck_cluster:e1251e42a20b@9c30ffabf757`

| R1 | R2 | R3 | R4 | R5 |
|---|---|---|---|---|
| descriptive_only | n/a | none | n/a | n/a |

## Luot 2/3

**R6 - episode nay co giai thich duoc vi sao ben thang hon khong?**

> packet khong co contrast `support`.
>
> **KHONG PHAI MODEL VIET.** Moi de xuat cua model deu bi tu choi; cac cau duoi day do floor sinh tu packet. Voi R6 day la analyst **im lang** - `explains` khong the cham o day.

| R6 |
|---|
| silent_correctly |

### 093

> stuck cluster was detected on dcda195ffe5e in this episode

- register: `diagnosis` | subject: `task_geometry` | type: `component_specific_attribution`
- refs: `obs:stuck_cluster:dcda195ffe5e@9c30ffabf757`

| R1 | R2 | R3 | R4 | R5 |
|---|---|---|---|---|
| descriptive_only | n/a | none | n/a | n/a |

### 094

> stuck cluster was detected on e1251e42a20b in this episode

- register: `diagnosis` | subject: `task_geometry` | type: `component_specific_attribution`
- refs: `obs:stuck_cluster:e1251e42a20b@9c30ffabf757`

| R1 | R2 | R3 | R4 | R5 |
|---|---|---|---|---|
| descriptive_only | n/a | none | n/a | n/a |

## Luot 3/3

**R6 - episode nay co giai thich duoc vi sao ben thang hon khong?**

> packet khong co contrast `support`.

| R6 |
|---|
| describes_only |

### 095

> C1 experienced a local minimum entrapment, stopping for 1.25 seconds without replanning.

- register: `diagnosis` | subject: `local_controller` | type: `local_minimum_entrapment`
- refs: `obs:stuck_cluster:C1@9c30ffabf757`, `obs:stuck_cluster:C1@9c30ffabf757/stopped_seconds`

| R1 | R2 | R3 | R4 | R5 |
|---|---|---|---|---|
| descriptive_only | n/a | none | exact | n/a |

---

# Episode `b219dbb9c044`

*cluster: sudden_stop_custom_v2_full_stack_selection_06f40334 | vai: holdout*

<details open><summary><b>PACKET</b></summary>

**Phan quyet**: episode_decision_utility | thang: `C5` | thua: `C1`

**Khac biet giua hai ben**

| ref | strength | noi gi | so kem theo |
|---|---|---|---|
| `contrast:component_differs:1` | **context** | the two stacks differ in global_planner, local_controller, local_controller_config; a mechanism that explains the difference has to live in one of those | - |
| `contrast:divergence_precedes_outcome:2` | **context** | the two runs parted at 3.1 m along the route | - |
| `contrast:outcome_differs:3` | **context** | C5 ended this episode ahead of C1 on worst clearance, travel time | min clearance loser = 0.194227; min clearance winner = 0.245643; travel time s loser = 30.4; travel time s winner = 25.95 |

**Detector da ban**

| ref | tren ai | so kem theo |
|---|---|---|
| `obs:stuck_cluster:C1@b219dbb9c044` | `C1` | stopped_seconds = 3.1; stops = 1; window.end_m = 7.54669; window.end_s = 21.4; window.start_m = 7.54295; window.start_s = 18.3 |
| `obs:stuck_cluster:C5@b219dbb9c044` | `C5` | stopped_seconds = 6; stops = 1; window.end_m = 3.63953; window.end_s = 12.15; window.start_m = 3.60748; window.start_s = 6.15 |

**So do duoc cua tung ben**

- `C1`: collision_count = 0 | min_clearance = 0.194227 | p99_latency_ms = 0 | replan_count = 0 | success = 1 | travel_time_s = 30.4
- `C5`: collision_count = 0 | min_clearance = 0.245643 | p99_latency_ms = 20.7161 | replan_count = 1 | success = 1 | travel_time_s = 25.95

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

## Luot 1/3

**R6 - episode nay co giai thich duoc vi sao ben thang hon khong?**

> packet khong co contrast `support`.
>
> **KHONG PHAI MODEL VIET.** Moi de xuat cua model deu bi tu choi; cac cau duoi day do floor sinh tu packet. Voi R6 day la analyst **im lang** - `explains` khong the cham o day.

| R6 |
|---|
| silent_correctly |

### 096

> stuck cluster was detected on e1251e42a20b in this episode

- register: `diagnosis` | subject: `task_geometry` | type: `component_specific_attribution`
- refs: `obs:stuck_cluster:e1251e42a20b@b219dbb9c044`

| R1 | R2 | R3 | R4 | R5 |
|---|---|---|---|---|
| descriptive_only | yes | some | n/a | n/a |

### 097

> stuck cluster was detected on dcda195ffe5e in this episode

- register: `diagnosis` | subject: `task_geometry` | type: `component_specific_attribution`
- refs: `obs:stuck_cluster:dcda195ffe5e@b219dbb9c044`

| R1 | R2 | R3 | R4 | R5 |
|---|---|---|---|---|
| descriptive_only | n/a | none | n/a | n/a |

## Luot 2/3

**R6 - episode nay co giai thich duoc vi sao ben thang hon khong?**

> packet khong co contrast `support`.

| R6 |
|---|
| describes_only |

### 098

> C1 remained stopped in a stuck cluster for 3.1 seconds starting at 18.3 and ending at 21.4.

- register: `diagnosis` | subject: `local_controller` | type: `local_minimum_entrapment`
- refs: `obs:stuck_cluster:C1@b219dbb9c044/stopped_seconds`, `obs:stuck_cluster:C1@b219dbb9c044/window.start_s`, `obs:stuck_cluster:C1@b219dbb9c044/window.end_s`

| R1 | R2 | R3 | R4 | R5 |
|---|---|---|---|---|
| descriptive_only | n/a | none | exact | n/a |

## Luot 3/3

**R6 - episode nay co giai thich duoc vi sao ben thang hon khong?**

> packet khong co contrast `support`.
>
> **KHONG PHAI MODEL VIET.** Moi de xuat cua model deu bi tu choi; cac cau duoi day do floor sinh tu packet. Voi R6 day la analyst **im lang** - `explains` khong the cham o day.

| R6 |
|---|
| silent_correctly |

### 099

> stuck cluster was detected on dcda195ffe5e in this episode

- register: `diagnosis` | subject: `task_geometry` | type: `component_specific_attribution`
- refs: `obs:stuck_cluster:dcda195ffe5e@b219dbb9c044`

| R1 | R2 | R3 | R4 | R5 |
|---|---|---|---|---|
| descriptive_only | yes | some | n/a | n/a |

### 100

> stuck cluster was detected on e1251e42a20b in this episode

- register: `diagnosis` | subject: `task_geometry` | type: `component_specific_attribution`
- refs: `obs:stuck_cluster:e1251e42a20b@b219dbb9c044`

| R1 | R2 | R3 | R4 | R5 |
|---|---|---|---|---|
| descriptive_only | n/a | none | n/a | n/a |

---

# Episode `b7a810e6fc00`

*cluster: sudden_stop_custom_v2_full_stack_selection_06f40334 | vai: holdout*

<details open><summary><b>PACKET</b></summary>

**Phan quyet**: episode_decision_utility | thang: `-` | thua: `-`

**Detector da ban**

| ref | tren ai | so kem theo |
|---|---|---|
| `obs:stuck_cluster:C1@b7a810e6fc00` | `C1` | stopped_seconds = 3.95; stops = 1; window.end_m = 7.43485; window.end_s = 22.4; window.start_m = 7.43008; window.start_s = 18.45 |
| `obs:stuck_cluster:C5@b7a810e6fc00` | `C5` | stopped_seconds = 5.85; stops = 1; window.end_m = 3.63958; window.end_s = 13.1; window.start_m = 3.59611; window.start_s = 7.25 |

**So do duoc cua tung ben**

- `C1`: collision_count = 0 | min_clearance = 0.187913 | p99_latency_ms = 0 | replan_count = 0 | success = 1 | travel_time_s = 31.25
- `C5`: collision_count = 0 | min_clearance = 0.24734 | p99_latency_ms = 21.4252 | replan_count = 1 | success = 1 | travel_time_s = 26.95

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

## Luot 1/3

**R6 - episode nay co giai thich duoc vi sao ben thang hon khong?**

> packet khong co contrast `support`.
>
> **KHONG PHAI MODEL VIET.** Moi de xuat cua model deu bi tu choi; cac cau duoi day do floor sinh tu packet. Voi R6 day la analyst **im lang** - `explains` khong the cham o day.

| R6 |
|---|
| silent_correctly |

### 101

> stuck cluster was detected on e1251e42a20b in this episode

- register: `diagnosis` | subject: `task_geometry` | type: `component_specific_attribution`
- refs: `obs:stuck_cluster:e1251e42a20b@b7a810e6fc00`

| R1 | R2 | R3 | R4 | R5 |
|---|---|---|---|---|
| descriptive_only | n/a | none | n/a | n/a |

### 102

> stuck cluster was detected on dcda195ffe5e in this episode

- register: `diagnosis` | subject: `task_geometry` | type: `component_specific_attribution`
- refs: `obs:stuck_cluster:dcda195ffe5e@b7a810e6fc00`

| R1 | R2 | R3 | R4 | R5 |
|---|---|---|---|---|
| descriptive_only | n/a | none | n/a | n/a |

## Luot 2/3

**R6 - episode nay co giai thich duoc vi sao ben thang hon khong?**

> packet khong co contrast `support`.
>
> **KHONG PHAI MODEL VIET.** Moi de xuat cua model deu bi tu choi; cac cau duoi day do floor sinh tu packet. Voi R6 day la analyst **im lang** - `explains` khong the cham o day.

| R6 |
|---|
| silent_correctly |

### 103

> stuck cluster was detected on dcda195ffe5e in this episode

- register: `diagnosis` | subject: `task_geometry` | type: `component_specific_attribution`
- refs: `obs:stuck_cluster:dcda195ffe5e@b7a810e6fc00`

| R1 | R2 | R3 | R4 | R5 |
|---|---|---|---|---|
| descriptive_only | n/a | none | n/a | n/a |

### 104

> stuck cluster was detected on e1251e42a20b in this episode

- register: `diagnosis` | subject: `task_geometry` | type: `component_specific_attribution`
- refs: `obs:stuck_cluster:e1251e42a20b@b7a810e6fc00`

| R1 | R2 | R3 | R4 | R5 |
|---|---|---|---|---|
| descriptive_only | n/a | none | n/a | n/a |

## Luot 3/3

**R6 - episode nay co giai thich duoc vi sao ben thang hon khong?**

> packet khong co contrast `support`.

| R6 |
|---|
| describes_only |

### 105

> local_controller for C5 experienced a local minimum entrapment, stopping for 5.85

- register: `diagnosis` | subject: `local_controller` | type: `local_minimum_entrapment`
- refs: `obs:stuck_cluster:C5@b7a810e6fc00`, `obs:stuck_cluster:C5@b7a810e6fc00/stopped_seconds`

| R1 | R2 | R3 | R4 | R5 |
|---|---|---|---|---|
| descriptive_only | n/a | none | exact | n/a |

### 106

> local_controller for C1 experienced a local minimum entrapment, stopping for 3.95

- register: `diagnosis` | subject: `local_controller` | type: `local_minimum_entrapment`
- refs: `obs:stuck_cluster:C1@b7a810e6fc00`, `obs:stuck_cluster:C1@b7a810e6fc00/stopped_seconds`

| R1 | R2 | R3 | R4 | R5 |
|---|---|---|---|---|
| descriptive_only | yes | some | exact | n/a |

---

# Episode `b94539aed2d1`

*cluster: sudden_stop_custom_v2_full_stack_selection_06f40334 | vai: holdout*

<details open><summary><b>PACKET</b></summary>

**Phan quyet**: episode_decision_utility | thang: `C1` | thua: `C5`

**Khac biet giua hai ben**

| ref | strength | noi gi | so kem theo |
|---|---|---|---|
| `contrast:component_differs:2` | **context** | the two stacks differ in global_planner, local_controller, local_controller_config; a mechanism that explains the difference has to live in one of those | - |
| `contrast:detection_worse_on_loser:1` | **support** | stuck_cluster fired on both, and materially worse on C5 | severity ratio = 3.45455; stopped seconds = 5.7; stops = 1 |
| `contrast:divergence_precedes_outcome:3` | **context** | the two runs parted at 3.1 m along the route | - |

**Detector da ban**

| ref | tren ai | so kem theo |
|---|---|---|
| `obs:stuck_cluster:C1@b94539aed2d1` | `C1` | stopped_seconds = 1.65; stops = 1; window.end_m = 7.4158; window.end_s = 18.05; window.start_m = 7.41328; window.start_s = 16.4 |
| `obs:stuck_cluster:C5@b94539aed2d1` | `C5` | stopped_seconds = 5.7; stops = 1; window.end_m = 3.64374; window.end_s = 11.85; window.start_m = 3.62643; window.start_s = 6.15 |

**So do duoc cua tung ben**

- `C1`: collision_count = 0 | min_clearance = 0.227241 | p99_latency_ms = 0 | replan_count = 0 | success = 1 | travel_time_s = 26.15
- `C5`: collision_count = 0 | min_clearance = 0.275038 | p99_latency_ms = 22.5477 | replan_count = 1 | success = 1 | travel_time_s = 25.6

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

## Luot 1/3

**R6 - episode nay co giai thich duoc vi sao ben thang hon khong?**

> **packet co the tra loi why** - co contrast `support`.

| R6 |
|---|
| describes_only |

### 107

> local_controller on C5 performed 1 replans, whereas local_controller on C1 performed 0 replans

- register: `diagnosis` | subject: `local_controller` | type: `component_specific_attribution`
- refs: `diag:C5.replan_count`, `diag:C1.replan_count`

| R1 | R2 | R3 | R4 | R5 |
|---|---|---|---|---|
| descriptive_only | no | some | exact | n/a |

## Luot 2/3

**R6 - episode nay co giai thich duoc vi sao ben thang hon khong?**

> **packet co the tra loi why** - co contrast `support`.

| R6 |
|---|
| describes_only |

### 108

> The local_controller on C5 experienced a more severe stuck_cluster than on C1, as evidenced by 3.45, indicating potential local_minimum_entrapment.

- register: `diagnosis` | subject: `local_controller` | type: `local_minimum_entrapment`
- refs: `contrast:detection_worse_on_loser:1/severity_ratio`
- contract: `subject_match`, `polarity_match`

| R1 | R2 | R3 | R4 | R5 |
|---|---|---|---|---|
| descriptive_only | yes | some | rounded | n/a |

## Luot 3/3

**R6 - episode nay co giai thich duoc vi sao ben thang hon khong?**

> **packet co the tra loi why** - co contrast `support`.

| R6 |
|---|
| describes_only |

### 109

> The local_controller on C5 incurred a more severe local_minimum_entrapment in this episode than on C1, as shown by stuck_cluster severity ratio 3.45.

- register: `diagnosis` | subject: `local_controller` | type: `local_minimum_entrapment`
- refs: `contrast:detection_worse_on_loser:1`
- contract: `contrast_support`, `subject_match`, `polarity_match`

| R1 | R2 | R3 | R4 | R5 |
|---|---|---|---|---|
| descriptive_only | yes | some | rounded | n/a |

---

# Episode `bdd393fb3bb8`

*cluster: sudden_stop_custom_v2_full_stack_selection_06f40334 | vai: holdout*

<details open><summary><b>PACKET</b></summary>

**Phan quyet**: episode_decision_utility | thang: `C1` | thua: `C5`

**Khac biet giua hai ben**

| ref | strength | noi gi | so kem theo |
|---|---|---|---|
| `contrast:component_differs:2` | **context** | the two stacks differ in global_planner, local_controller, local_controller_config; a mechanism that explains the difference has to live in one of those | - |
| `contrast:detection_worse_on_loser:1` | **support** | stuck_cluster fired on both, and materially worse on C5 | severity ratio = 4.79167; stopped seconds = 5.75; stops = 1 |
| `contrast:divergence_precedes_outcome:3` | **context** | the two runs parted at 3.2 m along the route | - |

**Detector da ban**

| ref | tren ai | so kem theo |
|---|---|---|
| `obs:stuck_cluster:C1@bdd393fb3bb8` | `C1` | stopped_seconds = 1.2; stops = 1; window.end_m = 7.37558; window.end_s = 16.45; window.start_m = 7.3693; window.start_s = 15.25 |
| `obs:stuck_cluster:C5@bdd393fb3bb8` | `C5` | stopped_seconds = 5.75; stops = 1; window.end_m = 3.63774; window.end_s = 11.85; window.start_m = 3.6125; window.start_s = 6.1 |

**So do duoc cua tung ben**

- `C1`: collision_count = 0 | min_clearance = 0.202962 | p99_latency_ms = 0 | replan_count = 0 | success = 1 | travel_time_s = 26.05
- `C5`: collision_count = 0 | min_clearance = 0.242527 | p99_latency_ms = 22.438 | replan_count = 1 | success = 1 | travel_time_s = 25.7

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

## Luot 1/3

**R6 - episode nay co giai thich duoc vi sao ben thang hon khong?**

> **packet co the tra loi why** - co contrast `support`.

| R6 |
|---|
| explains |

### 110

> The local_controller of C5 got stuck in a local minimum, causing a stuck_cluster that stopped progress for 5.75 seconds, which was more severe than the interruption on C1 and led to worse performance in this episode.

- register: `diagnosis` | subject: `local_controller` | type: `local_minimum_entrapment`
- refs: `contrast:detection_worse_on_loser:1`
- contract: `contrast_support`, `subject_match`, `polarity_match`

| R1 | R2 | R3 | R4 | R5 |
|---|---|---|---|---|
| supported_explanation | yes | some | exact | n/a |

## Luot 2/3

**R6 - episode nay co giai thich duoc vi sao ben thang hon khong?**

> **packet co the tra loi why** - co contrast `support`.
>
> **KHONG PHAI MODEL VIET.** Moi de xuat cua model deu bi tu choi; cac cau duoi day do floor sinh tu packet. Voi R6 day la analyst **im lang** - `explains` khong the cham o day.

| R6 |
|---|
| silent_wrongly |

### 111

> a pattern worse on e1251e42a20b than on the other side is consistent with local minimum entrapment

- register: `contrast` | subject: `local_controller` | type: `local_minimum_entrapment`
- refs: `contrast:detection_worse_on_loser:1`

| R1 | R2 | R3 | R4 | R5 |
|---|---|---|---|---|
| descriptive_only | yes | some | n/a | n/a |

### 112

> stuck cluster was detected on dcda195ffe5e in this episode

- register: `diagnosis` | subject: `task_geometry` | type: `component_specific_attribution`
- refs: `obs:stuck_cluster:dcda195ffe5e@bdd393fb3bb8`

| R1 | R2 | R3 | R4 | R5 |
|---|---|---|---|---|
| descriptive_only | yes | some | n/a | n/a |

### 113

> stuck cluster was detected on e1251e42a20b in this episode

- register: `diagnosis` | subject: `task_geometry` | type: `component_specific_attribution`
- refs: `obs:stuck_cluster:e1251e42a20b@bdd393fb3bb8`

| R1 | R2 | R3 | R4 | R5 |
|---|---|---|---|---|
| descriptive_only | n/a | none | n/a | n/a |

## Luot 3/3

**R6 - episode nay co giai thich duoc vi sao ben thang hon khong?**

> **packet co the tra loi why** - co contrast `support`.

| R6 |
|---|
| explains |

### 114

> The local_controller on C5 experienced local minimum entrapment, causing it to remain stalled for 5.75 seconds as detected by the stuck_cluster detector, which delayed it relative to C1

- register: `diagnosis` | subject: `local_controller` | type: `local_minimum_entrapment`
- refs: `contrast:detection_worse_on_loser:1`
- contract: `contrast_support`, `subject_match`, `polarity_match`

| R1 | R2 | R3 | R4 | R5 |
|---|---|---|---|---|
| supported_explanation | n/a | none | exact | n/a |

---

# Episode `c20848d51f24`

*cluster: sudden_stop_custom_v2_full_stack_selection_06f40334 | vai: holdout*

<details open><summary><b>PACKET</b></summary>

**Phan quyet**: episode_decision_utility | thang: `C5` | thua: `C1`

**Khac biet giua hai ben**

| ref | strength | noi gi | so kem theo |
|---|---|---|---|
| `contrast:component_differs:1` | **context** | the two stacks differ in global_planner, local_controller, local_controller_config; a mechanism that explains the difference has to live in one of those | - |
| `contrast:divergence_precedes_outcome:2` | **context** | the two runs parted at 3.1 m along the route | - |
| `contrast:outcome_differs:3` | **context** | C5 ended this episode ahead of C1 on worst clearance, travel time | min clearance loser = 0.194436; min clearance winner = 0.240215; travel time s loser = 29.85; travel time s winner = 26.1 |

**Detector da ban**

| ref | tren ai | so kem theo |
|---|---|---|
| `obs:stuck_cluster:C1@c20848d51f24` | `C1` | stopped_seconds = 2.6; stops = 1; window.end_m = 7.43527; window.end_s = 20.4; window.start_m = 7.4322; window.start_s = 17.8 |
| `obs:stuck_cluster:C5@c20848d51f24` | `C5` | stopped_seconds = 5.9; stops = 1; window.end_m = 3.6365; window.end_s = 12.05; window.start_m = 3.59349; window.start_s = 6.15 |

**So do duoc cua tung ben**

- `C1`: collision_count = 0 | min_clearance = 0.194436 | p99_latency_ms = 0 | replan_count = 0 | success = 1 | travel_time_s = 29.85
- `C5`: collision_count = 0 | min_clearance = 0.240215 | p99_latency_ms = 18.303 | replan_count = 1 | success = 1 | travel_time_s = 26.1

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

## Luot 1/3

**R6 - episode nay co giai thich duoc vi sao ben thang hon khong?**

> packet khong co contrast `support`.
>
> **KHONG PHAI MODEL VIET.** Moi de xuat cua model deu bi tu choi; cac cau duoi day do floor sinh tu packet. Voi R6 day la analyst **im lang** - `explains` khong the cham o day.

| R6 |
|---|
| silent_correctly |

### 115

> stuck cluster was detected on dcda195ffe5e in this episode

- register: `diagnosis` | subject: `task_geometry` | type: `component_specific_attribution`
- refs: `obs:stuck_cluster:dcda195ffe5e@c20848d51f24`

| R1 | R2 | R3 | R4 | R5 |
|---|---|---|---|---|
| descriptive_only | yes | some | n/a | n/a |

### 116

> stuck cluster was detected on e1251e42a20b in this episode

- register: `diagnosis` | subject: `task_geometry` | type: `component_specific_attribution`
- refs: `obs:stuck_cluster:e1251e42a20b@c20848d51f24`

| R1 | R2 | R3 | R4 | R5 |
|---|---|---|---|---|
| descriptive_only | n/a | none | n/a | n/a |

## Luot 2/3

**R6 - episode nay co giai thich duoc vi sao ben thang hon khong?**

> packet khong co contrast `support`.

| R6 |
|---|
| describes_only |

### 117

> The local_controller got stuck for 2.6s, delaying progress

- register: `diagnosis` | subject: `local_controller` | type: `local_minimum_entrapment`
- refs: `obs:stuck_cluster:C1@c20848d51f24/stopped_seconds`

| R1 | R2 | R3 | R4 | R5 |
|---|---|---|---|---|
| descriptive_only | n/a | none | exact | n/a |

## Luot 3/3

**R6 - episode nay co giai thich duoc vi sao ben thang hon khong?**

> packet khong co contrast `support`.
>
> **KHONG PHAI MODEL VIET.** Moi de xuat cua model deu bi tu choi; cac cau duoi day do floor sinh tu packet. Voi R6 day la analyst **im lang** - `explains` khong the cham o day.

| R6 |
|---|
| silent_correctly |

### 118

> stuck cluster was detected on e1251e42a20b in this episode

- register: `diagnosis` | subject: `task_geometry` | type: `component_specific_attribution`
- refs: `obs:stuck_cluster:e1251e42a20b@c20848d51f24`

| R1 | R2 | R3 | R4 | R5 |
|---|---|---|---|---|
| descriptive_only | yes | some | n/a | n/a |

### 119

> stuck cluster was detected on dcda195ffe5e in this episode

- register: `diagnosis` | subject: `task_geometry` | type: `component_specific_attribution`
- refs: `obs:stuck_cluster:dcda195ffe5e@c20848d51f24`

| R1 | R2 | R3 | R4 | R5 |
|---|---|---|---|---|
| descriptive_only | n/a | none | n/a | n/a |

---

# Episode `c31f07beacd6`

*cluster: sudden_stop_custom_v2_full_stack_selection_06f40334 | vai: holdout*

<details open><summary><b>PACKET</b></summary>

**Phan quyet**: episode_decision_utility | thang: `C1` | thua: `C5`

**Khac biet giua hai ben**

| ref | strength | noi gi | so kem theo |
|---|---|---|---|
| `contrast:component_differs:2` | **context** | the two stacks differ in global_planner, local_controller, local_controller_config; a mechanism that explains the difference has to live in one of those | - |
| `contrast:detection_worse_on_loser:1` | **support** | stuck_cluster fired on both, and materially worse on C5 | severity ratio = 2.94872; stopped seconds = 5.75; stops = 1 |
| `contrast:divergence_precedes_outcome:3` | **context** | the two runs parted at 3.0 m along the route | - |

**Detector da ban**

| ref | tren ai | so kem theo |
|---|---|---|
| `obs:near_miss_cluster:C1@c31f07beacd6` | `C1` | min_clearance_m = 0.145338; samples = 6; window.end_m = 8.35427; window.end_s = 22.75; window.start_m = 8.22927; window.start_s = 22.5 |
| `obs:stuck_cluster:C1@c31f07beacd6` | `C1` | stopped_seconds = 1.95; stops = 1; window.end_m = 7.65052; window.end_s = 20.6; window.start_m = 7.64589; window.start_s = 18.65 |
| `obs:stuck_cluster:C5@c31f07beacd6` | `C5` | stopped_seconds = 5.75; stops = 1; window.end_m = 3.67041; window.end_s = 12; window.start_m = 3.66076; window.start_s = 6.25 |

**So do duoc cua tung ben**

- `C1`: collision_count = 0 | min_clearance = 0.145338 | p99_latency_ms = 0 | replan_count = 0 | success = 1 | travel_time_s = 28.5
- `C5`: collision_count = 0 | min_clearance = 0.245476 | p99_latency_ms = 20.3213 | replan_count = 1 | success = 1 | travel_time_s = 25.85

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

## Luot 1/3

**R6 - episode nay co giai thich duoc vi sao ben thang hon khong?**

> **packet co the tra loi why** - co contrast `support`.

| R6 |
|---|
| describes_only |

### 120

> The local_controller on C5 experienced a more severe local_minimum_entrapment in this episode, taking longer to recover from a stuck cluster than C1, as shown by the stoppage lasting 5.75.

- register: `diagnosis` | subject: `local_controller` | type: `local_minimum_entrapment`
- refs: `contrast:detection_worse_on_loser:1`
- contract: `contrast_support`, `subject_match`, `polarity_match`

| R1 | R2 | R3 | R4 | R5 |
|---|---|---|---|---|
| descriptive_only | n/a | none | exact | n/a |

## Luot 2/3

**R6 - episode nay co giai thich duoc vi sao ben thang hon khong?**

> **packet co the tra loi why** - co contrast `support`.

| R6 |
|---|
| explains |

### 121

> local_controller of C5 led to worse local_minimum_entrapment, incurring 5.75 stopped_seconds and tipping the episode outcome to C1

- register: `diagnosis` | subject: `local_controller` | type: `local_minimum_entrapment`
- refs: `contrast:detection_worse_on_loser:1`, `contrast:component_differs:2`
- contract: `contrast_support`, `subject_match`, `polarity_match`

| R1 | R2 | R3 | R4 | R5 |
|---|---|---|---|---|
| supported_explanation | yes | some | exact | n/a |

## Luot 3/3

**R6 - episode nay co giai thich duoc vi sao ben thang hon khong?**

> **packet co the tra loi why** - co contrast `support`.
>
> **KHONG PHAI MODEL VIET.** Moi de xuat cua model deu bi tu choi; cac cau duoi day do floor sinh tu packet. Voi R6 day la analyst **im lang** - `explains` khong the cham o day.

| R6 |
|---|
| silent_wrongly |

### 122

> stuck cluster was detected on e1251e42a20b in this episode

- register: `diagnosis` | subject: `task_geometry` | type: `component_specific_attribution`
- refs: `obs:stuck_cluster:e1251e42a20b@c31f07beacd6`

| R1 | R2 | R3 | R4 | R5 |
|---|---|---|---|---|
| descriptive_only | yes | some | n/a | n/a |

### 123

> near miss cluster was detected on dcda195ffe5e in this episode

- register: `diagnosis` | subject: `task_geometry` | type: `component_specific_attribution`
- refs: `obs:near_miss_cluster:dcda195ffe5e@c31f07beacd6`

| R1 | R2 | R3 | R4 | R5 |
|---|---|---|---|---|
| descriptive_only | n/a | none | n/a | n/a |

### 124

> a pattern worse on e1251e42a20b than on the other side is consistent with local minimum entrapment

- register: `contrast` | subject: `local_controller` | type: `local_minimum_entrapment`
- refs: `contrast:detection_worse_on_loser:1`

| R1 | R2 | R3 | R4 | R5 |
|---|---|---|---|---|
| descriptive_only | n/a | none | n/a | n/a |

### 125

> stuck cluster was detected on dcda195ffe5e in this episode

- register: `diagnosis` | subject: `task_geometry` | type: `component_specific_attribution`
- refs: `obs:stuck_cluster:dcda195ffe5e@c31f07beacd6`

| R1 | R2 | R3 | R4 | R5 |
|---|---|---|---|---|
| descriptive_only | yes | some | n/a | n/a |

---

# Episode `c697c0cac1bb`

*cluster: sudden_stop_custom_v2_full_stack_selection_06f40334 | vai: holdout*

<details open><summary><b>PACKET</b></summary>

**Phan quyet**: episode_decision_utility | thang: `C5` | thua: `C1`

**Khac biet giua hai ben**

| ref | strength | noi gi | so kem theo |
|---|---|---|---|
| `contrast:component_differs:2` | **context** | the two stacks differ in global_planner, local_controller, local_controller_config; a mechanism that explains the difference has to live in one of those | - |
| `contrast:detection_worse_on_loser:1` | **support** | stuck_cluster fired on both, and materially worse on C1 | severity ratio = 3.2087; stopped seconds = 18.45; stops = 1 |
| `contrast:divergence_precedes_outcome:3` | **context** | the two runs parted at 3.0 m along the route | - |
| `contrast:outcome_differs:4` | **context** | C5 ended this episode ahead of C1 on worst clearance, travel time | min clearance loser = 0.196028; min clearance winner = 0.260823; travel time s loser = 44.35; travel time s winner = 25.8 |

**Detector da ban**

| ref | tren ai | so kem theo |
|---|---|---|
| `obs:stuck_cluster:C1@c697c0cac1bb` | `C1` | stopped_seconds = 18.45; stops = 1; window.end_m = 7.40872; window.end_s = 34.85; window.start_m = 7.40403; window.start_s = 16.4 |
| `obs:stuck_cluster:C5@c697c0cac1bb` | `C5` | stopped_seconds = 5.75; stops = 1; window.end_m = 3.65565; window.end_s = 12; window.start_m = 3.64415; window.start_s = 6.25 |

**So do duoc cua tung ben**

- `C1`: collision_count = 0 | min_clearance = 0.196028 | p99_latency_ms = 0 | replan_count = 3 | success = 1 | travel_time_s = 44.35
- `C5`: collision_count = 0 | min_clearance = 0.260823 | p99_latency_ms = 20.8425 | replan_count = 1 | success = 1 | travel_time_s = 25.8

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

## Luot 1/3

**R6 - episode nay co giai thich duoc vi sao ben thang hon khong?**

> **packet co the tra loi why** - co contrast `support`.
>
> **KHONG PHAI MODEL VIET.** Moi de xuat cua model deu bi tu choi; cac cau duoi day do floor sinh tu packet. Voi R6 day la analyst **im lang** - `explains` khong the cham o day.

| R6 |
|---|
| silent_wrongly |

### 126

> a pattern worse on dcda195ffe5e than on the other side is consistent with local minimum entrapment

- register: `contrast` | subject: `local_controller` | type: `local_minimum_entrapment`
- refs: `contrast:detection_worse_on_loser:1`

| R1 | R2 | R3 | R4 | R5 |
|---|---|---|---|---|
| descriptive_only | n/a | none | n/a | n/a |

### 127

> stuck cluster was detected on e1251e42a20b in this episode

- register: `diagnosis` | subject: `task_geometry` | type: `component_specific_attribution`
- refs: `obs:stuck_cluster:e1251e42a20b@c697c0cac1bb`

| R1 | R2 | R3 | R4 | R5 |
|---|---|---|---|---|
| descriptive_only | yes | some | n/a | n/a |

### 128

> stuck cluster was detected on dcda195ffe5e in this episode

- register: `diagnosis` | subject: `task_geometry` | type: `component_specific_attribution`
- refs: `obs:stuck_cluster:dcda195ffe5e@c697c0cac1bb`

| R1 | R2 | R3 | R4 | R5 |
|---|---|---|---|---|
| descriptive_only | n/a | none | n/a | n/a |

## Luot 2/3

**R6 - episode nay co giai thich duoc vi sao ben thang hon khong?**

> **packet co the tra loi why** - co contrast `support`.

| R6 |
|---|
| explains |

### 129

> local_controller on C1 experienced a local_minimum_entrapment of 18.45 seconds, increasing its travel time and contributing to its loss.

- register: `diagnosis` | subject: `local_controller` | type: `local_minimum_entrapment`
- refs: `contrast:component_differs:2`, `contrast:detection_worse_on_loser:1`
- contract: `contrast_support`, `subject_match`, `polarity_match`

| R1 | R2 | R3 | R4 | R5 |
|---|---|---|---|---|
| supported_explanation | n/a | none | exact | n/a |

## Luot 3/3

**R6 - episode nay co giai thich duoc vi sao ben thang hon khong?**

> **packet co the tra loi why** - co contrast `support`.

| R6 |
|---|
| describes_only |

### 130

> The local_controller of candidate C1 experienced a local_minimum_entrapment causing it to remain stopped for 18.45 seconds.

- register: `diagnosis` | subject: `local_controller` | type: `local_minimum_entrapment`
- refs: `obs:stuck_cluster:C1@c697c0cac1bb`

| R1 | R2 | R3 | R4 | R5 |
|---|---|---|---|---|
| descriptive_only | yes | some | exact | n/a |

---

# Episode `d0a5c200c750`

*cluster: sudden_stop_custom_v2_full_stack_selection_06f40334 | vai: holdout*

<details open><summary><b>PACKET</b></summary>

**Phan quyet**: episode_decision_utility | thang: `C1` | thua: `C5`

**Khac biet giua hai ben**

| ref | strength | noi gi | so kem theo |
|---|---|---|---|
| `contrast:component_differs:2` | **context** | the two stacks differ in global_planner, local_controller, local_controller_config; a mechanism that explains the difference has to live in one of those | - |
| `contrast:detection_worse_on_loser:1` | **support** | stuck_cluster fired on both, and materially worse on C5 | severity ratio = 4.75; stopped seconds = 5.7; stops = 1 |
| `contrast:divergence_precedes_outcome:3` | **context** | the two runs parted at 3.1 m along the route | - |
| `contrast:outcome_differs:4` | **context** | C1 ended this episode ahead of C5 on travel time | travel time s loser = 26.15; travel time s winner = 25.95 |

**Detector da ban**

| ref | tren ai | so kem theo |
|---|---|---|
| `obs:stuck_cluster:C1@d0a5c200c750` | `C1` | stopped_seconds = 1.2; stops = 1; window.end_m = 7.43802; window.end_s = 18.05; window.start_m = 7.43407; window.start_s = 16.85 |
| `obs:stuck_cluster:C5@d0a5c200c750` | `C5` | stopped_seconds = 5.7; stops = 1; window.end_m = 3.68339; window.end_s = 12.05; window.start_m = 3.67444; window.start_s = 6.35 |

**So do duoc cua tung ben**

- `C1`: collision_count = 0 | min_clearance = 0.224789 | p99_latency_ms = 0 | replan_count = 0 | success = 1 | travel_time_s = 25.95
- `C5`: collision_count = 0 | min_clearance = 0.2376 | p99_latency_ms = 25.9049 | replan_count = 1 | success = 1 | travel_time_s = 26.15

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

## Luot 1/3

**R6 - episode nay co giai thich duoc vi sao ben thang hon khong?**

> **packet co the tra loi why** - co contrast `support`.

| R6 |
|---|
| explains |

### 131

> local_controller of C5 became entrapped in a local minimum for 5.7, delaying its progress relative to C1 and contributing to slower travel time in this episode

- register: `contrast` | subject: `local_controller` | type: `local_minimum_entrapment`
- refs: `contrast:component_differs:2`, `contrast:detection_worse_on_loser:1`, `obs:stuck_cluster:C5@d0a5c200c750`
- contract: `contrast_support`, `occurrence_evidence`, `subject_match`, `polarity_match`

| R1 | R2 | R3 | R4 | R5 |
|---|---|---|---|---|
| supported_explanation | yes | some | exact | n/a |

## Luot 2/3

**R6 - episode nay co giai thich duoc vi sao ben thang hon khong?**

> **packet co the tra loi why** - co contrast `support`.
>
> **KHONG PHAI MODEL VIET.** Moi de xuat cua model deu bi tu choi; cac cau duoi day do floor sinh tu packet. Voi R6 day la analyst **im lang** - `explains` khong the cham o day.

| R6 |
|---|
| silent_wrongly |

### 132

> stuck cluster was detected on e1251e42a20b in this episode

- register: `diagnosis` | subject: `task_geometry` | type: `component_specific_attribution`
- refs: `obs:stuck_cluster:e1251e42a20b@d0a5c200c750`

| R1 | R2 | R3 | R4 | R5 |
|---|---|---|---|---|
| descriptive_only | yes | some | n/a | n/a |

### 133

> a pattern worse on e1251e42a20b than on the other side is consistent with local minimum entrapment

- register: `contrast` | subject: `local_controller` | type: `local_minimum_entrapment`
- refs: `contrast:detection_worse_on_loser:1`

| R1 | R2 | R3 | R4 | R5 |
|---|---|---|---|---|
| descriptive_only | n/a | none | n/a | n/a |

### 134

> stuck cluster was detected on dcda195ffe5e in this episode

- register: `diagnosis` | subject: `task_geometry` | type: `component_specific_attribution`
- refs: `obs:stuck_cluster:dcda195ffe5e@d0a5c200c750`

| R1 | R2 | R3 | R4 | R5 |
|---|---|---|---|---|
| descriptive_only | yes | some | n/a | n/a |

## Luot 3/3

**R6 - episode nay co giai thich duoc vi sao ben thang hon khong?**

> **packet co the tra loi why** - co contrast `support`.
>
> **KHONG PHAI MODEL VIET.** Moi de xuat cua model deu bi tu choi; cac cau duoi day do floor sinh tu packet. Voi R6 day la analyst **im lang** - `explains` khong the cham o day.

| R6 |
|---|
| silent_wrongly |

### 135

> a pattern worse on e1251e42a20b than on the other side is consistent with local minimum entrapment

- register: `contrast` | subject: `local_controller` | type: `local_minimum_entrapment`
- refs: `contrast:detection_worse_on_loser:1`

| R1 | R2 | R3 | R4 | R5 |
|---|---|---|---|---|
| descriptive_only | n/a | none | n/a | n/a |

### 136

> stuck cluster was detected on dcda195ffe5e in this episode

- register: `diagnosis` | subject: `task_geometry` | type: `component_specific_attribution`
- refs: `obs:stuck_cluster:dcda195ffe5e@d0a5c200c750`

| R1 | R2 | R3 | R4 | R5 |
|---|---|---|---|---|
| descriptive_only | yes | some | n/a | n/a |

### 137

> stuck cluster was detected on e1251e42a20b in this episode

- register: `diagnosis` | subject: `task_geometry` | type: `component_specific_attribution`
- refs: `obs:stuck_cluster:e1251e42a20b@d0a5c200c750`

| R1 | R2 | R3 | R4 | R5 |
|---|---|---|---|---|
| descriptive_only | n/a | none | n/a | n/a |

---

# Episode `d663910f7e0f`

*cluster: sudden_stop_custom_v2_full_stack_selection_06f40334 | vai: holdout*

<details open><summary><b>PACKET</b></summary>

**Phan quyet**: episode_decision_utility | thang: `C5` | thua: `C1`

**Khac biet giua hai ben**

| ref | strength | noi gi | so kem theo |
|---|---|---|---|
| `contrast:component_differs:1` | **context** | the two stacks differ in global_planner, local_controller, local_controller_config; a mechanism that explains the difference has to live in one of those | - |
| `contrast:divergence_precedes_outcome:2` | **context** | the two runs parted at 3.2 m along the route | - |
| `contrast:outcome_differs:3` | **context** | C5 ended this episode ahead of C1 on worst clearance, travel time | min clearance loser = 0.19736; min clearance winner = 0.215551; travel time s loser = 28.4; travel time s winner = 26.2 |

**Detector da ban**

| ref | tren ai | so kem theo |
|---|---|---|
| `obs:stuck_cluster:C1@d663910f7e0f` | `C1` | stopped_seconds = 3.1; stops = 2; window.end_m = 7.75162; window.end_s = 21.15; window.start_m = 7.5283; window.start_s = 16.95 |
| `obs:stuck_cluster:C5@d663910f7e0f` | `C5` | stopped_seconds = 5.75; stops = 1; window.end_m = 3.71768; window.end_s = 12.05; window.start_m = 3.70573; window.start_s = 6.3 |

**So do duoc cua tung ben**

- `C1`: collision_count = 0 | min_clearance = 0.19736 | p99_latency_ms = 0 | replan_count = 0 | success = 1 | travel_time_s = 28.4
- `C5`: collision_count = 0 | min_clearance = 0.215551 | p99_latency_ms = 19.3669 | replan_count = 1 | success = 1 | travel_time_s = 26.2

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

## Luot 1/3

**R6 - episode nay co giai thich duoc vi sao ben thang hon khong?**

> packet khong co contrast `support`.
>
> **KHONG PHAI MODEL VIET.** Moi de xuat cua model deu bi tu choi; cac cau duoi day do floor sinh tu packet. Voi R6 day la analyst **im lang** - `explains` khong the cham o day.

| R6 |
|---|
| silent_correctly |

### 138

> stuck cluster was detected on e1251e42a20b in this episode

- register: `diagnosis` | subject: `task_geometry` | type: `component_specific_attribution`
- refs: `obs:stuck_cluster:e1251e42a20b@d663910f7e0f`

| R1 | R2 | R3 | R4 | R5 |
|---|---|---|---|---|
| descriptive_only | n/a | none | n/a | n/a |

### 139

> stuck cluster was detected on dcda195ffe5e in this episode

- register: `diagnosis` | subject: `task_geometry` | type: `component_specific_attribution`
- refs: `obs:stuck_cluster:dcda195ffe5e@d663910f7e0f`

| R1 | R2 | R3 | R4 | R5 |
|---|---|---|---|---|
| descriptive_only | n/a | none | n/a | n/a |

## Luot 2/3

**R6 - episode nay co giai thich duoc vi sao ben thang hon khong?**

> packet khong co contrast `support`.
>
> **KHONG PHAI MODEL VIET.** Moi de xuat cua model deu bi tu choi; cac cau duoi day do floor sinh tu packet. Voi R6 day la analyst **im lang** - `explains` khong the cham o day.

| R6 |
|---|
| silent_correctly |

### 140

> stuck cluster was detected on e1251e42a20b in this episode

- register: `diagnosis` | subject: `task_geometry` | type: `component_specific_attribution`
- refs: `obs:stuck_cluster:e1251e42a20b@d663910f7e0f`

| R1 | R2 | R3 | R4 | R5 |
|---|---|---|---|---|
| descriptive_only | n/a | none | n/a | n/a |

### 141

> stuck cluster was detected on dcda195ffe5e in this episode

- register: `diagnosis` | subject: `task_geometry` | type: `component_specific_attribution`
- refs: `obs:stuck_cluster:dcda195ffe5e@d663910f7e0f`

| R1 | R2 | R3 | R4 | R5 |
|---|---|---|---|---|
| descriptive_only | n/a | none | n/a | n/a |

## Luot 3/3

**R6 - episode nay co giai thich duoc vi sao ben thang hon khong?**

> packet khong co contrast `support`.

| R6 |
|---|
| describes_only |

### 142

> C1 experienced a local minimum entrapment in the local_controller, indicated by a stuck_cluster event lasting 3.1 seconds

- register: `diagnosis` | subject: `local_controller` | type: `local_minimum_entrapment`
- refs: `obs:stuck_cluster:C1@d663910f7e0f`

| R1 | R2 | R3 | R4 | R5 |
|---|---|---|---|---|
| descriptive_only | n/a | none | exact | n/a |

---

# Episode `e87fc5b937ab`

*cluster: sudden_stop_custom_v2_full_stack_selection_06f40334 | vai: holdout*

<details open><summary><b>PACKET</b></summary>

**Phan quyet**: episode_decision_utility | thang: `C1` | thua: `C5`

**Khac biet giua hai ben**

| ref | strength | noi gi | so kem theo |
|---|---|---|---|
| `contrast:component_differs:3` | **context** | the two stacks differ in global_planner, local_controller, local_controller_config; a mechanism that explains the difference has to live in one of those | - |
| `contrast:detection_only_on_loser:1` | **support** | near_miss_cluster fired on C5 and not on C1 | min clearance m = 0.145266; samples = 8 |
| `contrast:detection_worse_on_loser:2` | **support** | stuck_cluster fired on both, and materially worse on C5 | severity ratio = 1.94915; stopped seconds = 5.75; stops = 1 |
| `contrast:divergence_precedes_outcome:4` | **context** | the two runs parted at 3.1 m along the route | - |
| `contrast:outcome_differs:5` | **context** | C1 ended this episode ahead of C5 on worst clearance | min clearance loser = 0.145266; min clearance winner = 0.189623 |

**Detector da ban**

| ref | tren ai | so kem theo |
|---|---|---|
| `obs:near_miss_cluster:C5@e87fc5b937ab` | `C5` | min_clearance_m = 0.145266; samples = 8; window.end_m = 7.46425; window.end_s = 20.35; window.start_m = 7.33514; window.start_s = 20 |
| `obs:stuck_cluster:C1@e87fc5b937ab` | `C1` | stopped_seconds = 2.95; stops = 1; window.end_m = 7.48938; window.end_s = 21.25; window.start_m = 7.48673; window.start_s = 18.3 |
| `obs:stuck_cluster:C5@e87fc5b937ab` | `C5` | stopped_seconds = 5.75; stops = 1; window.end_m = 3.7532; window.end_s = 12.1; window.start_m = 3.7433; window.start_s = 6.35 |

**So do duoc cua tung ben**

- `C1`: collision_count = 0 | min_clearance = 0.189623 | p99_latency_ms = 0 | replan_count = 0 | success = 1 | travel_time_s = 30.55
- `C5`: collision_count = 0 | min_clearance = 0.145266 | p99_latency_ms = 20.6731 | replan_count = 1 | success = 1 | travel_time_s = 27.4

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

## Luot 1/3

**R6 - episode nay co giai thich duoc vi sao ben thang hon khong?**

> **packet co the tra loi why** - co contrast `support`.

| R6 |
|---|
| explains |

### 143

> local_controller on C5 entered a deeper local minimum than on C1, shown by severity ratio 1.95, leading to worse clearance on C5

- register: `diagnosis` | subject: `local_controller` | type: `local_minimum_entrapment`
- refs: `contrast:detection_worse_on_loser:2`
- contract: `contrast_support`, `subject_match`, `polarity_match`

| R1 | R2 | R3 | R4 | R5 |
|---|---|---|---|---|
| supported_explanation | yes | some | rounded | n/a |

## Luot 2/3

**R6 - episode nay co giai thich duoc vi sao ben thang hon khong?**

> **packet co the tra loi why** - co contrast `support`.

| R6 |
|---|
| describes_only |

### 144

> local_controller refused to maintain safe clearance on C5, causing a near_miss_cluster to fire on C5 but not on C1

- register: `diagnosis` | subject: `local_controller` | type: `clearance_refusal`
- refs: `contrast:detection_only_on_loser:1`
- contract: `contrast_support`, `subject_match`, `polarity_match`

| R1 | R2 | R3 | R4 | R5 |
|---|---|---|---|---|
| plausible_explanation | yes | some | n/a | n/a |

### 145

> local_controller became stuck longer on C5 (5.75) than on C1 (2.95), indicating more severe local_minimum_entrapment on C5

- register: `contrast` | subject: `local_controller` | type: `local_minimum_entrapment`
- refs: `contrast:detection_worse_on_loser:2`, `obs:stuck_cluster:C1@e87fc5b937ab/stopped_seconds`
- contract: `contrast_support`, `occurrence_evidence`, `subject_match`, `polarity_match`

| R1 | R2 | R3 | R4 | R5 |
|---|---|---|---|---|
| descriptive_only | yes | some | exact | n/a |

## Luot 3/3

**R6 - episode nay co giai thich duoc vi sao ben thang hon khong?**

> **packet co the tra loi why** - co contrast `support`.
>
> **KHONG PHAI MODEL VIET.** Moi de xuat cua model deu bi tu choi; cac cau duoi day do floor sinh tu packet. Voi R6 day la analyst **im lang** - `explains` khong the cham o day.

| R6 |
|---|
| silent_wrongly |

### 146

> stuck cluster was detected on dcda195ffe5e in this episode

- register: `diagnosis` | subject: `task_geometry` | type: `component_specific_attribution`
- refs: `obs:stuck_cluster:dcda195ffe5e@e87fc5b937ab`

| R1 | R2 | R3 | R4 | R5 |
|---|---|---|---|---|
| descriptive_only | yes | some | n/a | n/a |

### 147

> stuck cluster was detected on e1251e42a20b in this episode

- register: `diagnosis` | subject: `task_geometry` | type: `component_specific_attribution`
- refs: `obs:stuck_cluster:e1251e42a20b@e87fc5b937ab`

| R1 | R2 | R3 | R4 | R5 |
|---|---|---|---|---|
| descriptive_only | n/a | none | n/a | n/a |

### 148

> near miss cluster was detected on e1251e42a20b in this episode

- register: `diagnosis` | subject: `task_geometry` | type: `component_specific_attribution`
- refs: `obs:near_miss_cluster:e1251e42a20b@e87fc5b937ab`

| R1 | R2 | R3 | R4 | R5 |
|---|---|---|---|---|
| descriptive_only | n/a | none | n/a | n/a |

### 149

> a pattern worse on e1251e42a20b than on the other side is consistent with local minimum entrapment

- register: `contrast` | subject: `local_controller` | type: `local_minimum_entrapment`
- refs: `contrast:detection_worse_on_loser:2`

| R1 | R2 | R3 | R4 | R5 |
|---|---|---|---|---|
| descriptive_only | n/a | none | n/a | n/a |

---

# Episode `e9a1c89e9dbf`

*cluster: sudden_stop_custom_v2_full_stack_selection_06f40334 | vai: holdout*

<details open><summary><b>PACKET</b></summary>

**Phan quyet**: episode_decision_utility | thang: `C1` | thua: `C5`

**Khac biet giua hai ben**

| ref | strength | noi gi | so kem theo |
|---|---|---|---|
| `contrast:component_differs:2` | **context** | the two stacks differ in global_planner, local_controller, local_controller_config; a mechanism that explains the difference has to live in one of those | - |
| `contrast:detection_worse_on_loser:1` | **support** | stuck_cluster fired on both, and materially worse on C5 | severity ratio = 4.42308; stopped seconds = 5.75; stops = 1 |
| `contrast:divergence_precedes_outcome:3` | **context** | the two runs parted at 3.1 m along the route | - |
| `contrast:outcome_differs:4` | **context** | C1 ended this episode ahead of C5 on travel time | travel time s loser = 26.1; travel time s winner = 25.8 |

**Detector da ban**

| ref | tren ai | so kem theo |
|---|---|---|
| `obs:stuck_cluster:C1@e9a1c89e9dbf` | `C1` | stopped_seconds = 1.3; stops = 1; window.end_m = 7.41082; window.end_s = 17.85; window.start_m = 7.40654; window.start_s = 16.55 |
| `obs:stuck_cluster:C5@e9a1c89e9dbf` | `C5` | stopped_seconds = 5.75; stops = 1; window.end_m = 3.66648; window.end_s = 12; window.start_m = 3.65617; window.start_s = 6.25 |

**So do duoc cua tung ben**

- `C1`: collision_count = 0 | min_clearance = 0.225293 | p99_latency_ms = 0 | replan_count = 0 | success = 1 | travel_time_s = 25.8
- `C5`: collision_count = 0 | min_clearance = 0.237349 | p99_latency_ms = 20.3952 | replan_count = 1 | success = 1 | travel_time_s = 26.1

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

## Luot 1/3

**R6 - episode nay co giai thich duoc vi sao ben thang hon khong?**

> **packet co the tra loi why** - co contrast `support`.

| R6 |
|---|
| explains |

### 150

> In this episode, local_controller of C5 was trapped in a local minimum for 5.75 seconds, slowing C5 relative to C1.

- register: `diagnosis` | subject: `local_controller` | type: `local_minimum_entrapment`
- refs: `contrast:detection_worse_on_loser:1/stopped_seconds`
- contract: `subject_match`, `polarity_match`

| R1 | R2 | R3 | R4 | R5 |
|---|---|---|---|---|
| supported_explanation | yes | some | exact | n/a |

## Luot 2/3

**R6 - episode nay co giai thich duoc vi sao ben thang hon khong?**

> **packet co the tra loi why** - co contrast `support`.

| R6 |
|---|
| explains |

### 151

> The local_controller of C5 experienced a longer stuck_cluster entrapment than C1, delaying C5 by 5.75 compared to 1.3.

- register: `diagnosis` | subject: `local_controller` | type: `local_minimum_entrapment`
- refs: `contrast:detection_worse_on_loser:1`
- contract: `contrast_support`, `subject_match`, `polarity_match`

| R1 | R2 | R3 | R4 | R5 |
|---|---|---|---|---|
| supported_explanation | yes | some | exact | n/a |

## Luot 3/3

**R6 - episode nay co giai thich duoc vi sao ben thang hon khong?**

> **packet co the tra loi why** - co contrast `support`.

| R6 |
|---|
| describes_only |

### 152

> The local_controller on C5 experienced more severe local minimum entrapment, resulting in longer stoppages

- register: `diagnosis` | subject: `local_controller` | type: `local_minimum_entrapment`
- refs: `contrast:detection_worse_on_loser:1`
- contract: `contrast_support`, `subject_match`, `polarity_match`

| R1 | R2 | R3 | R4 | R5 |
|---|---|---|---|---|
| descriptive_only | yes | some | n/a | n/a |

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

## Luot 1/3

**R6 - episode nay co giai thich duoc vi sao ben thang hon khong?**

> packet khong co contrast `support`.

| R6 |
|---|
| describes_only |

### 153

> C1 experienced local minimum entrapment in its local_controller, remaining stuck for 10.25 seconds.

- register: `diagnosis` | subject: `local_controller` | type: `local_minimum_entrapment`
- refs: `obs:stuck_cluster:C1@f11b8bfc70ba/stopped_seconds`

| R1 | R2 | R3 | R4 | R5 |
|---|---|---|---|---|
| descriptive_only | yes | some | exact | n/a |

## Luot 2/3

**R6 - episode nay co giai thich duoc vi sao ben thang hon khong?**

> packet khong co contrast `support`.

| R6 |
|---|
| describes_only |

### 154

> local_controller for C1 experienced a local minimum entrapment lasting 10.25

- register: `diagnosis` | subject: `local_controller` | type: `local_minimum_entrapment`
- refs: `obs:stuck_cluster:C1@f11b8bfc70ba`

| R1 | R2 | R3 | R4 | R5 |
|---|---|---|---|---|
| descriptive_only | yes | some | exact | n/a |

### 155

> local_controller for C5 experienced a local minimum entrapment lasting 5.75

- register: `diagnosis` | subject: `local_controller` | type: `local_minimum_entrapment`
- refs: `obs:stuck_cluster:C5@f11b8bfc70ba`

| R1 | R2 | R3 | R4 | R5 |
|---|---|---|---|---|
| descriptive_only | yes | some | exact | n/a |

## Luot 3/3

**R6 - episode nay co giai thich duoc vi sao ben thang hon khong?**

> packet khong co contrast `support`.
>
> **KHONG PHAI MODEL VIET.** Moi de xuat cua model deu bi tu choi; cac cau duoi day do floor sinh tu packet. Voi R6 day la analyst **im lang** - `explains` khong the cham o day.

| R6 |
|---|
| silent_correctly |

### 156

> stuck cluster was detected on e1251e42a20b in this episode

- register: `diagnosis` | subject: `task_geometry` | type: `component_specific_attribution`
- refs: `obs:stuck_cluster:e1251e42a20b@f11b8bfc70ba`

| R1 | R2 | R3 | R4 | R5 |
|---|---|---|---|---|
| descriptive_only | yes | some | n/a | n/a |

### 157

> stuck cluster was detected on dcda195ffe5e in this episode

- register: `diagnosis` | subject: `task_geometry` | type: `component_specific_attribution`
- refs: `obs:stuck_cluster:dcda195ffe5e@f11b8bfc70ba`

| R1 | R2 | R3 | R4 | R5 |
|---|---|---|---|---|
| descriptive_only | n/a | none | n/a | n/a |

---

# Episode `f4a50b33adf9`

*cluster: sudden_stop_custom_v2_full_stack_selection_06f40334 | vai: holdout*

<details open><summary><b>PACKET</b></summary>

**Phan quyet**: episode_decision_utility | thang: `-` | thua: `-`

**Detector da ban**

| ref | tren ai | so kem theo |
|---|---|---|
| `obs:near_miss_cluster:C1@f4a50b33adf9` | `C1` | min_clearance_m = 0.145192; samples = 8; window.end_m = 8.1935; window.end_s = 22.25; window.start_m = 8.081; window.start_s = 21.9 |
| `obs:stuck_cluster:C1@f4a50b33adf9` | `C1` | stopped_seconds = 1.5; stops = 1; window.end_m = 7.5085; window.end_s = 18.1; window.start_m = 7.49032; window.start_s = 16.6 |
| `obs:stuck_cluster:C5@f4a50b33adf9` | `C5` | stopped_seconds = 5.85; stops = 1; window.end_m = 3.64005; window.end_s = 12.4; window.start_m = 3.59279; window.start_s = 6.55 |

**So do duoc cua tung ben**

- `C1`: collision_count = 0 | min_clearance = 0.145192 | p99_latency_ms = 0 | replan_count = 0 | success = 1 | travel_time_s = 28.55
- `C5`: collision_count = 0 | min_clearance = 0.249649 | p99_latency_ms = 20.9986 | replan_count = 1 | success = 1 | travel_time_s = 26.25

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

## Luot 1/3

**R6 - episode nay co giai thich duoc vi sao ben thang hon khong?**

> packet khong co contrast `support`.

| R6 |
|---|
| describes_only |

### 158

> C5 experienced a stuck cluster lasting 5.85 seconds, indicating a local minimum entrapment by the controller.

- register: `diagnosis` | subject: `local_controller` | type: `local_minimum_entrapment`
- refs: `obs:stuck_cluster:C5@f4a50b33adf9`, `obs:stuck_cluster:C5@f4a50b33adf9/stopped_seconds`

| R1 | R2 | R3 | R4 | R5 |
|---|---|---|---|---|
| descriptive_only | n/a | none | exact | n/a |

### 159

> C1 had a stuck cluster where it remained stopped for 1.5 seconds, suggesting a local controller entrapment.

- register: `diagnosis` | subject: `local_controller` | type: `local_minimum_entrapment`
- refs: `obs:stuck_cluster:C1@f4a50b33adf9`, `obs:stuck_cluster:C1@f4a50b33adf9/stopped_seconds`

| R1 | R2 | R3 | R4 | R5 |
|---|---|---|---|---|
| descriptive_only | yes | some | exact | n/a |

## Luot 2/3

**R6 - episode nay co giai thich duoc vi sao ben thang hon khong?**

> packet khong co contrast `support`.

| R6 |
|---|
| describes_only |

### 160

> The local_controller of C5 got stuck in a local minimum for 5.85 seconds in this episode.

- register: `diagnosis` | subject: `local_controller` | type: `local_minimum_entrapment`
- refs: `obs:stuck_cluster:C5@f4a50b33adf9/stopped_seconds`

| R1 | R2 | R3 | R4 | R5 |
|---|---|---|---|---|
| descriptive_only | yes | some | exact | n/a |

## Luot 3/3

**R6 - episode nay co giai thich duoc vi sao ben thang hon khong?**

> packet khong co contrast `support`.

| R6 |
|---|
| describes_only |

### 161

> local_controller experienced a local_minimum_entrapment on C1, stopping for 1.5

- register: `diagnosis` | subject: `local_controller` | type: `local_minimum_entrapment`
- refs: `obs:stuck_cluster:C1@f4a50b33adf9`

| R1 | R2 | R3 | R4 | R5 |
|---|---|---|---|---|
| descriptive_only | yes | some | exact | n/a |

### 162

> local_controller experienced a local_minimum_entrapment on C5, stopping for 5.85

- register: `diagnosis` | subject: `local_controller` | type: `local_minimum_entrapment`
- refs: `obs:stuck_cluster:C5@f4a50b33adf9`

| R1 | R2 | R3 | R4 | R5 |
|---|---|---|---|---|
| descriptive_only | yes | some | exact | n/a |

---

# Episode `f56b11845b7e`

*cluster: sudden_stop_custom_v2_full_stack_selection_06f40334 | vai: holdout*

<details open><summary><b>PACKET</b></summary>

**Phan quyet**: episode_decision_utility | thang: `C5` | thua: `C1`

**Khac biet giua hai ben**

| ref | strength | noi gi | so kem theo |
|---|---|---|---|
| `contrast:component_differs:1` | **context** | the two stacks differ in global_planner, local_controller, local_controller_config; a mechanism that explains the difference has to live in one of those | - |
| `contrast:divergence_precedes_outcome:2` | **context** | the two runs parted at 3.0 m along the route | - |
| `contrast:outcome_differs:3` | **context** | C5 ended this episode ahead of C1 on worst clearance, travel time | min clearance loser = 0.191273; min clearance winner = 0.231319; travel time s loser = 31.95; travel time s winner = 25.8 |

**Detector da ban**

| ref | tren ai | so kem theo |
|---|---|---|
| `obs:stuck_cluster:C1@f56b11845b7e` | `C1` | stopped_seconds = 5.1; stops = 2; window.end_m = 7.42387; window.end_s = 22.5; window.start_m = 6.21641; window.start_s = 14.15 |
| `obs:stuck_cluster:C5@f56b11845b7e` | `C5` | stopped_seconds = 5.75; stops = 1; window.end_m = 3.65322; window.end_s = 11.95; window.start_m = 3.64097; window.start_s = 6.2 |

**So do duoc cua tung ben**

- `C1`: collision_count = 0 | min_clearance = 0.191273 | p99_latency_ms = 0 | replan_count = 0 | success = 1 | travel_time_s = 31.95
- `C5`: collision_count = 0 | min_clearance = 0.231319 | p99_latency_ms = 22.4549 | replan_count = 1 | success = 1 | travel_time_s = 25.8

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

## Luot 1/3

**R6 - episode nay co giai thich duoc vi sao ben thang hon khong?**

> packet khong co contrast `support`.
>
> **KHONG PHAI MODEL VIET.** Moi de xuat cua model deu bi tu choi; cac cau duoi day do floor sinh tu packet. Voi R6 day la analyst **im lang** - `explains` khong the cham o day.

| R6 |
|---|
| silent_correctly |

### 163

> stuck cluster was detected on dcda195ffe5e in this episode

- register: `diagnosis` | subject: `task_geometry` | type: `component_specific_attribution`
- refs: `obs:stuck_cluster:dcda195ffe5e@f56b11845b7e`

| R1 | R2 | R3 | R4 | R5 |
|---|---|---|---|---|
| descriptive_only | yes | some | n/a | n/a |

### 164

> stuck cluster was detected on e1251e42a20b in this episode

- register: `diagnosis` | subject: `task_geometry` | type: `component_specific_attribution`
- refs: `obs:stuck_cluster:e1251e42a20b@f56b11845b7e`

| R1 | R2 | R3 | R4 | R5 |
|---|---|---|---|---|
| descriptive_only | n/a | none | n/a | n/a |

## Luot 2/3

**R6 - episode nay co giai thich duoc vi sao ben thang hon khong?**

> packet khong co contrast `support`.
>
> **KHONG PHAI MODEL VIET.** Moi de xuat cua model deu bi tu choi; cac cau duoi day do floor sinh tu packet. Voi R6 day la analyst **im lang** - `explains` khong the cham o day.

| R6 |
|---|
| silent_correctly |

### 165

> stuck cluster was detected on dcda195ffe5e in this episode

- register: `diagnosis` | subject: `task_geometry` | type: `component_specific_attribution`
- refs: `obs:stuck_cluster:dcda195ffe5e@f56b11845b7e`

| R1 | R2 | R3 | R4 | R5 |
|---|---|---|---|---|
| descriptive_only | n/a | none | n/a | n/a |

### 166

> stuck cluster was detected on e1251e42a20b in this episode

- register: `diagnosis` | subject: `task_geometry` | type: `component_specific_attribution`
- refs: `obs:stuck_cluster:e1251e42a20b@f56b11845b7e`

| R1 | R2 | R3 | R4 | R5 |
|---|---|---|---|---|
| descriptive_only | n/a | none | n/a | n/a |

## Luot 3/3

**R6 - episode nay co giai thich duoc vi sao ben thang hon khong?**

> packet khong co contrast `support`.
>
> **KHONG PHAI MODEL VIET.** Moi de xuat cua model deu bi tu choi; cac cau duoi day do floor sinh tu packet. Voi R6 day la analyst **im lang** - `explains` khong the cham o day.

| R6 |
|---|
| silent_correctly |

### 167

> stuck cluster was detected on dcda195ffe5e in this episode

- register: `diagnosis` | subject: `task_geometry` | type: `component_specific_attribution`
- refs: `obs:stuck_cluster:dcda195ffe5e@f56b11845b7e`

| R1 | R2 | R3 | R4 | R5 |
|---|---|---|---|---|
| descriptive_only | n/a | none | n/a | n/a |

### 168

> stuck cluster was detected on e1251e42a20b in this episode

- register: `diagnosis` | subject: `task_geometry` | type: `component_specific_attribution`
- refs: `obs:stuck_cluster:e1251e42a20b@f56b11845b7e`

| R1 | R2 | R3 | R4 | R5 |
|---|---|---|---|---|
| descriptive_only | n/a | none | n/a | n/a |

---

# Episode `fd58ce16a90d`

*cluster: sudden_stop_custom_v2_full_stack_selection_06f40334 | vai: holdout*

<details open><summary><b>PACKET</b></summary>

**Phan quyet**: episode_decision_utility | thang: `-` | thua: `-`

**Detector da ban**

| ref | tren ai | so kem theo |
|---|---|---|
| `obs:stuck_cluster:C1@fd58ce16a90d` | `C1` | stopped_seconds = 2.1; stops = 1; window.end_m = 7.4684; window.end_s = 19.1; window.start_m = 7.46194; window.start_s = 17 |
| `obs:stuck_cluster:C5@fd58ce16a90d` | `C5` | stopped_seconds = 5.85; stops = 1; window.end_m = 3.65634; window.end_s = 12.05; window.start_m = 3.64662; window.start_s = 6.2 |

**So do duoc cua tung ben**

- `C1`: collision_count = 0 | min_clearance = 0.191668 | p99_latency_ms = 0 | replan_count = 0 | success = 1 | travel_time_s = 28
- `C5`: collision_count = 0 | min_clearance = 0.260387 | p99_latency_ms = 21.3111 | replan_count = 1 | success = 1 | travel_time_s = 25.85

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

## Luot 1/3

**R6 - episode nay co giai thich duoc vi sao ben thang hon khong?**

> packet khong co contrast `support`.
>
> **KHONG PHAI MODEL VIET.** Moi de xuat cua model deu bi tu choi; cac cau duoi day do floor sinh tu packet. Voi R6 day la analyst **im lang** - `explains` khong the cham o day.

| R6 |
|---|
| silent_correctly |

### 169

> stuck cluster was detected on e1251e42a20b in this episode

- register: `diagnosis` | subject: `task_geometry` | type: `component_specific_attribution`
- refs: `obs:stuck_cluster:e1251e42a20b@fd58ce16a90d`

| R1 | R2 | R3 | R4 | R5 |
|---|---|---|---|---|
| descriptive_only | n/a | none | n/a | n/a |

### 170

> stuck cluster was detected on dcda195ffe5e in this episode

- register: `diagnosis` | subject: `task_geometry` | type: `component_specific_attribution`
- refs: `obs:stuck_cluster:dcda195ffe5e@fd58ce16a90d`

| R1 | R2 | R3 | R4 | R5 |
|---|---|---|---|---|
| descriptive_only | n/a | none | n/a | n/a |

## Luot 2/3

**R6 - episode nay co giai thich duoc vi sao ben thang hon khong?**

> packet khong co contrast `support`.

| R6 |
|---|
| describes_only |

### 171

> C1 encountered a local minimum entrapment causing a stop lasting 2.1 s

- register: `diagnosis` | subject: `local_controller` | type: `local_minimum_entrapment`
- refs: `obs:stuck_cluster:C1@fd58ce16a90d/stopped_seconds`

| R1 | R2 | R3 | R4 | R5 |
|---|---|---|---|---|
| descriptive_only | n/a | none | exact | n/a |

### 172

> C5 encountered a local minimum entrapment causing a stop lasting 5.85 s

- register: `diagnosis` | subject: `local_controller` | type: `local_minimum_entrapment`
- refs: `obs:stuck_cluster:C5@fd58ce16a90d/stopped_seconds`

| R1 | R2 | R3 | R4 | R5 |
|---|---|---|---|---|
| descriptive_only | yes | some | exact | n/a |

## Luot 3/3

**R6 - episode nay co giai thich duoc vi sao ben thang hon khong?**

> packet khong co contrast `support`.
>
> **KHONG PHAI MODEL VIET.** Moi de xuat cua model deu bi tu choi; cac cau duoi day do floor sinh tu packet. Voi R6 day la analyst **im lang** - `explains` khong the cham o day.

| R6 |
|---|
| silent_correctly |

### 173

> stuck cluster was detected on e1251e42a20b in this episode

- register: `diagnosis` | subject: `task_geometry` | type: `component_specific_attribution`
- refs: `obs:stuck_cluster:e1251e42a20b@fd58ce16a90d`

| R1 | R2 | R3 | R4 | R5 |
|---|---|---|---|---|
| descriptive_only | yes | some | n/a | n/a |

### 174

> stuck cluster was detected on dcda195ffe5e in this episode

- register: `diagnosis` | subject: `task_geometry` | type: `component_specific_attribution`
- refs: `obs:stuck_cluster:dcda195ffe5e@fd58ce16a90d`

| R1 | R2 | R3 | R4 | R5 |
|---|---|---|---|---|
| descriptive_only | n/a | none | n/a | n/a |

---

# Episode `ff9c3d241c53`

*cluster: sudden_stop_custom_v2_full_stack_selection_06f40334 | vai: holdout*

<details open><summary><b>PACKET</b></summary>

**Phan quyet**: episode_decision_utility | thang: `C1` | thua: `C5`

**Khac biet giua hai ben**

| ref | strength | noi gi | so kem theo |
|---|---|---|---|
| `contrast:component_differs:2` | **context** | the two stacks differ in global_planner, local_controller, local_controller_config; a mechanism that explains the difference has to live in one of those | - |
| `contrast:detection_worse_on_loser:1` | **support** | stuck_cluster fired on both, and materially worse on C5 | severity ratio = 4.32143; stopped seconds = 6.05; stops = 1 |
| `contrast:divergence_precedes_outcome:3` | **context** | the two runs parted at 3.1 m along the route | - |
| `contrast:outcome_differs:4` | **context** | C1 ended this episode ahead of C5 on travel time | travel time s loser = 26.05; travel time s winner = 25.25 |

**Detector da ban**

| ref | tren ai | so kem theo |
|---|---|---|
| `obs:stuck_cluster:C1@ff9c3d241c53` | `C1` | stopped_seconds = 1.4; stops = 1; window.end_m = 7.37085; window.end_s = 17.65; window.start_m = 7.36377; window.start_s = 16.25 |
| `obs:stuck_cluster:C5@ff9c3d241c53` | `C5` | stopped_seconds = 6.05; stops = 1; window.end_m = 3.63887; window.end_s = 12.15; window.start_m = 3.57815; window.start_s = 6.1 |

**So do duoc cua tung ben**

- `C1`: collision_count = 0 | min_clearance = 0.237999 | p99_latency_ms = 0 | replan_count = 0 | success = 1 | travel_time_s = 25.25
- `C5`: collision_count = 0 | min_clearance = 0.241275 | p99_latency_ms = 19.4381 | replan_count = 1 | success = 1 | travel_time_s = 26.05

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

## Luot 1/3

**R6 - episode nay co giai thich duoc vi sao ben thang hon khong?**

> **packet co the tra loi why** - co contrast `support`.
>
> **KHONG PHAI MODEL VIET.** Moi de xuat cua model deu bi tu choi; cac cau duoi day do floor sinh tu packet. Voi R6 day la analyst **im lang** - `explains` khong the cham o day.

| R6 |
|---|
| silent_wrongly |

### 175

> a pattern worse on e1251e42a20b than on the other side is consistent with local minimum entrapment

- register: `contrast` | subject: `local_controller` | type: `local_minimum_entrapment`
- refs: `contrast:detection_worse_on_loser:1`

| R1 | R2 | R3 | R4 | R5 |
|---|---|---|---|---|
| descriptive_only | n/a | none | n/a | n/a |

### 176

> stuck cluster was detected on e1251e42a20b in this episode

- register: `diagnosis` | subject: `task_geometry` | type: `component_specific_attribution`
- refs: `obs:stuck_cluster:e1251e42a20b@ff9c3d241c53`

| R1 | R2 | R3 | R4 | R5 |
|---|---|---|---|---|
| descriptive_only | yes | some | n/a | n/a |

### 177

> stuck cluster was detected on dcda195ffe5e in this episode

- register: `diagnosis` | subject: `task_geometry` | type: `component_specific_attribution`
- refs: `obs:stuck_cluster:dcda195ffe5e@ff9c3d241c53`

| R1 | R2 | R3 | R4 | R5 |
|---|---|---|---|---|
| descriptive_only | n/a | none | n/a | n/a |

## Luot 2/3

**R6 - episode nay co giai thich duoc vi sao ben thang hon khong?**

> **packet co the tra loi why** - co contrast `support`.

| R6 |
|---|
| explains |

### 178

> The global_planner component differs between C1 and C5, suggesting it could underlie the slower performance of C5 in this episode.

- register: `diagnosis` | subject: `global_planner` | type: `component_specific_attribution`
- refs: `fact:candidate:C1.global_planner`, `fact:candidate:C5.global_planner`

| R1 | R2 | R3 | R4 | R5 |
|---|---|---|---|---|
| plausible_explanation | yes | some | n/a | n/a |

### 179

> The local_controller of C5 experienced a more severe local minimum entrapment than that of C1 in this episode, delaying its progress.

- register: `diagnosis` | subject: `local_controller` | type: `local_minimum_entrapment`
- refs: `contrast:detection_worse_on_loser:1`
- contract: `contrast_support`, `subject_match`, `polarity_match`

| R1 | R2 | R3 | R4 | R5 |
|---|---|---|---|---|
| supported_explanation | yes | some | n/a | n/a |

## Luot 3/3

**R6 - episode nay co giai thich duoc vi sao ben thang hon khong?**

> **packet co the tra loi why** - co contrast `support`.

| R6 |
|---|
| explains |

### 180

> The local_controller on C5 allowed the robot to remain stuck for 6.05 seconds, delaying travel time relative to C1.

- register: `diagnosis` | subject: `local_controller` | type: `local_minimum_entrapment`
- refs: `obs:stuck_cluster:C5@ff9c3d241c53`
- contract: `occurrence_evidence`, `subject_match`, `polarity_match`

| R1 | R2 | R3 | R4 | R5 |
|---|---|---|---|---|
| supported_explanation | yes | some | exact | n/a |
