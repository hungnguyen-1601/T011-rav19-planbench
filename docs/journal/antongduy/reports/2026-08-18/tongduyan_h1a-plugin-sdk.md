# H1a — plugin SDK: manifest tĩnh, capability URI, alias bridge

**Ngày:** 2026-08-18
**Plan:** `plans/2026-08-17/algorithm-host-mo-rong-cho-global-va-local-planner.md` §8 H1a
**Trạng thái:** xong, 28 test mới xanh, ruff sạch, **chưa commit**.

---

## 1. Đã tạo

Package mới `packages/plugin_sdk/planbench_plugin_sdk/` — tự chứa, chỉ
phụ thuộc stdlib + pydantic, plugin ngoài repo chỉ cần package này:

| File | Nội dung |
|---|---|
| `protocol_version.py` | `PLUGIN_API_VERSION = 1.0.0`; compatible = cùng major |
| `errors.py` | `ManifestError`, `IncompatibleProtocolError`, `UnknownCapabilityError` (mang suggestions), `DuplicatePluginError` |
| `capabilities.py` | URI `ns://channel/name@major`; alias bridge `lidar_2d`⇄`planbench://channel/lidar-2d@1`, `human_state_estimates`⇄`…/human-state-estimates@1`; builtin: + `robot-state@1`, `global-path@1`; `canonical_requirement()` — luật identity §5.2 |
| `requirements.py` | `RequirementSet` all_of/any_of/optional, canonical hoá lúc parse, `missing_from()` báo any_of thành một entry gộp |
| `channels.py` | `ChannelEnvelope`: capability canonical, cadence `per_tick\|on_change\|static`, **revision bắt buộc cho on_change/static** (chống re-stamp), provenance `deployment\|candidate\|oracle` |
| `requests.py` / `responses.py` | Contract versioned §5.5: `GlobalPlanRequest/Response`, `LocalResetRequest` (field `declared` thay probing kwargs §7.2), `LocalStepRequest/Response` (`reported_compute_ms` ghi rõ diagnostic — §5.9 luật 6) |
| `manifest.py` | `PluginManifest` + `RuntimeSpec` (supported_lanes/production_lane/profiles), `CapabilitySchemaDeclaration` (uri + schema + digest + codecs), `parse_manifest`/`load_manifest` (đọc JSON, **không import gì**), `manifest_checksum`, `ManifestIndex` |

`pyproject.toml`: thêm `packages/plugin_sdk` vào pythonpath.

## 2. DoD H1a đối chiếu — mỗi dòng một test ghim

| DoD | Test |
|---|---|
| Parse manifest không import plugin | bundle có `__init__.py` và `planner.py` **raise ngay khi import** — parse vẫn OK, `sys.modules` sạch |
| `all_of` / `any_of` / `optional` | semantics + any_of thiếu báo thành một entry "any of: a \| b" |
| Alias bridge + canonical → cùng `candidate_id` (§5.2 luật 1) | khai `lidar_2d` và khai `planbench://channel/lidar-2d@1` qua `canonical_requirements` → **một** candidate_id; kèm negative: URI thô đút thẳng vào `Candidate` vẫn bị từ chối — bridge là cửa duy nhất, identity v1 không bị chạm |
| URI lạ không kèm declaration → invalid manifest + gợi ý (§5.2 luật 2) | typo `lidar2d` → lỗi kèm gợi ý `lidar_2d`; `lidar-2d@2` (major chưa tồn tại) → `UnknownCapabilityError` trỏ tới `capability_schemas`; cùng URI **có** declaration → đăng ký được (ngoại lệ vòng 4) |
| Duplicate id/version/checksum fail loud | rescan cùng manifest = idempotent; hai body khác nhau cùng (id, version) → `DuplicatePluginError`; version mới = entry mới |
| `production_lane ∈ supported_lanes` lúc parse | + profile cho lane không khai cũng bị từ chối |

Ghim thêm ngoài DoD:

- **Drift guard hai chiều**: `set(V1_TOKEN_TO_URI) == set(KNOWN_OBSERVATIONS)` — thêm token G6 mà quên alias (hoặc ngược lại) là test đỏ.
- `ChannelEnvelope` on_change/static không revision → từ chối (nền của cadence invariant H3); capability không canonical → từ chối (một spelling toàn hệ).
- Plugin monolithic khai `requires_global_path=true` → từ chối (HĐ-1.2).
- Plugin không được redeclare schema của builtin capability.
- `plugin_api` khác major → `IncompatibleProtocolError`; cùng major minor mới → parse được.

## 3. Quyết định thiết kế đáng ghi

1. **Canonical hoá nằm trong SDK, không nằm trong `Candidate`.**
   `Candidate.observation_requirements` vẫn chỉ nhận token v1 như cũ —
   xác minh bằng test "bridge là cửa duy nhất". Đường URI đi qua
   `canonical_requirements()` trước khi chạm hash, nên **không một stored
   candidate_id nào đổi** trong H1a.
2. **SDK tự chứa.** Không import package repo nào; test drift-guard mới
   là chỗ nối hai vocabulary — chủ ý, để tác giả plugin ngoài repo chỉ
   cần cài SDK.
3. **Requests/responses dùng primitive thuần** (tuple/float/dict), không
   dùng model của `planbench_schemas` — payload phải sống qua codec ở
   H7, và plugin ngoài không nên phụ thuộc schemas nội bộ.
4. **`ManifestIndex` idempotent theo checksum** — discovery H5 quét
   chồng thư mục sẽ không tự bắn vào chân.

## 4. Kiểm chứng

| Kiểm | Kết quả |
|---|---|
| `tests/test_plugin_sdk.py` (mới, 28 test) | **28 passed**, 0.18s |
| `tests/test_candidate_identity.py` + SDK | **54 passed, 1 skipped** — identity không drift |
| `ruff check` + `ruff format` package + test | sạch |

## 5. Cho gate: H1 actual đang đo

H1a tiêu ~nửa buổi kỹ thuật. `H1_actual` chốt sau H1b (gate đo cả cụm
H1a+H1b so với ideal 2.5–3 ngày).

## 6. Kế tiếp

H1b — minimal legacy consumer: `registry entry → synthetic manifest →
parser → LegacyPluginLoader → factory hiện hành`, kèm monolithic loader
(`PolicyComponent.name` + `model_registry`) để trả A5. Chờ lệnh An.
