# Wire CodeGraph vào Claude Code (MCP, global)

Ngày: 2026-08-15
Nhánh: `tongduyan_plannerselector`

## Bối cảnh

An đã chạy `codegraph init` cho P-011, tạo ra `.codegraph/` với index đầy
đủ. Câu hỏi đặt ra: agent đã truy cập được index đó chưa.

## Hiện trạng trước khi sửa

Index khoẻ và đúng, kiểm chứng bằng `codegraph status`:

| Chỉ số | Giá trị |
|---|---|
| Files | 461 |
| Nodes | 10,099 |
| Edges | 23,263 |
| DB size | 17.80 MB |
| Backend | `node:sqlite` — full WAL |
| Journal | `wal` |

Phân bố theo ngôn ngữ: python 335, tsx 67, typescript 49, yaml 10.
Phân bố theo loại node: method 3,279 / import 2,658 / function 1,491 /
class 1,041 / variable 723 / file 451 / interface 159 / constant 150 /
route 100 / type_alias 47.

Truy vấn thật cho kết quả đúng, không phải suy đoán:

- `codegraph query "DeploymentForm"` trả về `DeploymentForm` tại
  `apps/web/src/components/DeploymentForm.tsx:139`, interface
  `DeploymentFormProps:125`, và call site tại
  `apps/web/src/app/deployments/page.tsx:25`.
- `codegraph context "moving obstacle trajectory validation"` trả về
  `TrajectoryPoint` (`apps/web/src/lib/types.ts:238`), `ValidationReport`
  (`types.ts:204`), và `_trajectory_point`
  (`services/simulator/planbench_simulator/engine.py:445`).

**Nhưng MCP chưa được đăng ký ở đâu cả.** Bằng chứng:

- Không có `.mcp.json` trong repo.
- `~/.claude.json`: `mcpServers` rỗng ở cả cấp global lẫn cả ba entry
  project của P-011.
- Session Claude Code không có tool `mcp__codegraph__*` nào.
- `~/.claude/CLAUDE.md` không có section CodeGraph.

Tức là `codegraph init` đã chạy (đã sinh `.cursor/rules/codegraph.mdc`)
nhưng `codegraph install` thì chưa. Agent chỉ tiếp cận được index bằng
cách shell-out qua Bash — chạy được, nhưng tốn hơn MCP native và mỗi lần
gọi có thể dính permission prompt.

## Quyết định: global thay vì local

Điểm mấu chốt là **DB luôn per-project bất kể chọn gì**. Server đọc
`.codegraph/codegraph.db` của project, xác định project bằng `rootUri`
client gửi sang. `--location` chỉ quyết định file config nằm ở đâu:

| | global | local |
|---|---|---|
| MCP server | `~/.claude.json` | config trong repo |
| Auto-allow | `~/.claude/settings.json` | `.claude/settings.json` của repo |
| Instruction block | `~/.claude/CLAUDE.md` | `CLAUDE.md` của repo |
| Phạm vi | mọi project | chỉ P-011 |
| Chạy `codegraph init` | không | có |

Chọn global vì An làm nhiều project và dùng cả CLI lẫn VSCode extension —
hai cái đọc cùng `~/.claude.json`, nên cài một lần là đủ. Project mới chỉ
cần `codegraph init -i`, không phải cài lại.

Đánh đổi đã cân nhắc và chấp nhận: block hướng dẫn CodeGraph nằm trong
`~/.claude/CLAUDE.md` nên tốn input token ở **mọi** session, kể cả project
không có index. Với local thì chỉ tốn ở P-011. Chọn global vì tiện hơn.
Cân nhắc thứ hai: local sẽ merge vào `.claude/settings.json` của repo —
file team dùng chung, đang chứa hook logging — nên tránh.

## Đã thay đổi

Lệnh chạy: `codegraph install --target=claude --location=global --yes`

Trước khi chạy đã sao lưu `~/.claude/CLAUDE.md` ra scratchpad để đối chiếu
diff sau đó.

1. `~/.claude.json` — thêm `mcpServers.codegraph`:
   ```json
   { "type": "stdio", "command": "codegraph", "args": ["serve", "--mcp"] }
   ```
2. `~/.claude/settings.json` — thêm `permissions.allow` cho các tool
   codegraph.
3. `~/.claude/CLAUDE.md` — append block giữa `<!-- CODEGRAPH_START -->` và
   `<!-- CODEGRAPH_END -->`, dài 35 dòng, mô tả khi nào dùng tool nào.
   File tăng từ 8,699 byte.

Không file nào trong repo bị đụng tới.

## Lỗ hổng của installer đã vá

Block hướng dẫn mà installer ghi vào `~/.claude/CLAUDE.md` có nhắc tới
`codegraph_files` và `codegraph_explore`, nhưng danh sách auto-allow nó
ghi vào `settings.json` **thiếu đúng hai tool đó** — chỉ có `search`,
`context`, `callers`, `callees`, `impact`, `node`, `status`.

Hệ quả nếu không vá: agent làm theo đúng hướng dẫn (dùng `codegraph_explore`
để lấy source nhiều symbol trong một lần gọi, thay vì lặp `codegraph_node`)
thì lại bị chặn hỏi quyền — đẩy agent về đúng cái pattern tốn kém mà hướng
dẫn bảo tránh.

Đã thêm `mcp__codegraph__codegraph_files` và
`mcp__codegraph__codegraph_explore` vào allow list. Giờ đủ 9 tool.

## Việc còn lại

**Cần restart Claude Code** thì tool `mcp__codegraph__*` mới nạp. Trước khi
restart, agent vẫn phải shell-out qua Bash.

Sau restart, verify bằng cách gọi `codegraph_status` như một MCP tool (không
phải Bash) — nếu trả về đúng 461 files thì đường MCP đã thông.

## Ghi chú cho repo

`.codegraph/` và `.cursor/rules/` đang untracked. `.codegraph/.gitignore`
tự ignore nội dung của nó (`*.db`, `*.db-wal`, `*.db-shm`, `cache/`,
`*.log`, `.dirty`) nên DB không lọt vào git. Cần quyết định riêng xem
`.cursor/rules/codegraph.mdc` có commit cho team hay không — file này là
hướng dẫn cho Cursor, không phải dữ liệu máy.
