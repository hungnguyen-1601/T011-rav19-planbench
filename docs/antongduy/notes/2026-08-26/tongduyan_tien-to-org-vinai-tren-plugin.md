# Vì sao thuật toán import có tiền tố `org.vinai`

**Ngày:** 2026-08-26
**Loại:** khảo sát, không đổi dòng mã nào

## Câu hỏi

An hỏi: *"Tại sao khi tôi import thuật toán vfh lại có org.vinai ở trước
tên thuật toán? Bỏ đi được không?"*

## Kết luận ngắn

Platform **không** thêm tiền tố nào. Chuỗi đó nằm trong manifest của
chính bundle An import.

`vfh_plus_iterated/vfh_plus/.planbench-plugin/plugin.json`:

```json
{
  "plugin_api": "1.2.0",
  "id": "org.vinai.vfh-plus",
  "version": "0.2.0",
  "role": "local"
}
```

## Nó lan đi đâu

`packages/benchmark/planbench_benchmark/plugin_stacks.py` lấy nguyên
`manifest.id` rồi ghép ra mọi thứ hiển thị:

```python
def stack_id_for(plugin_id: str, global_planner: str) -> str:
    return f"{global_planner}+{plugin_id}"          # astar+org.vinai.vfh-plus

def controller_configs_for(plugin_id, config_schema):
    return {f"{plugin_id}_defaults": declared}      # org.vinai.vfh-plus_defaults
```

`packages/plugin_sdk/planbench_plugin_sdk/manifest.py` chỉ kiểm dạng chữ,
không sửa nội dung:

```python
if not _ID_PATTERN.match(self.id):
    raise ValueError(
        f"plugin id {self.id!r} must be lowercase [a-z0-9_.-], starting with "
        "a letter or digit — it becomes part of candidate identity"
    )
```

`vfh-plus` (không tiền tố) hợp lệ với pattern này.

## Bỏ được, nhưng không bỏ bằng cách cắt chuỗi lúc render

Comment ngay tại `stack_id_for` nói rõ stack id là thứ **candidate
identity hash lên**, cố tình không phải display name. Giấu nửa id trên
màn hình nghĩa là picker và report gọi cùng một thuật toán bằng hai tên
khác nhau — mà report là thứ được trích dẫn khi so sánh hai run.

Manifest cũng không có trường tên hiển thị riêng (`PluginManifest` chỉ có
`id`, `version`, `role`, `runtime`, `requirements`, `supports`,
`config_schema`), nên không có chỗ nào hợp lệ để đặt một cái tên ngắn
song song với id.

## Cách đúng, và giá phải trả

Sửa `"id"` thành `"vfh-plus"` trong `plugin.json`, nén lại `.zip`, import
lại.

Hai hệ quả:

1. **Identity mới.** 19 comparison run đã chạy vẫn ghi
   `org.vinai.vfh-plus` trong report đã lưu. Artifact không đổi ngược
   được, nên so run cũ với run mới sẽ là so hai cái tên khác nhau.
2. **Phải xoá bundle cũ**, không thì catalogue giữ cả hai và picker hiện
   hai dòng gần giống hệt nhau.

## Trạng thái

An trả lời *"phần này sẽ xử lý sau"*. Chưa đổi gì.
