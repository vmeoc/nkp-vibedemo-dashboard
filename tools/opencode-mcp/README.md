# opencode-mcp

A small MCP server that lets **Claude Desktop drive Opencode** on this repository.
Claude plans and verifies; Opencode (with the local LLM, e.g. Reflection Beam on
Nutanix Enterprise AI) writes the code.

## Tools

| Tool          | What it does                                                        |
|---------------|---------------------------------------------------------------------|
| `start_task`  | Runs `opencode run --agent <build\|plan> "<prompt>"` in the background |
| `get_task`    | Status, exit code, changed files, last log lines                     |
| `cancel_task` | Stops the running task                                              |
| `run_tests`   | Runs unittest, returns only the verdict and failing test names      |
| `git_status`  | Changed files + diff stat (no content)                              |
| `git_diff`    | Diff of ONE file (only when a failure needs it)                     |
| `git_commit`  | `git add -A && git commit` (only after the human approved)           |

Results are deliberately short, to keep the frontier model's token usage low.
Logs live in `.orchestrator/tasks/` (git-ignored).

## Install (macOS, once)

1. Install `uv` if needed: `brew install uv`
2. Find the absolute paths (Claude Desktop does not use your shell PATH):

   ```
   which uv
   which opencode
   ```

3. Edit `~/Library/Application Support/Claude/claude_desktop_config.json`
   and add (replace the three paths):

   ```json
   {
     "mcpServers": {
       "opencode": {
         "command": "/opt/homebrew/bin/uv",
         "args": [
           "run", "--python", "3.12", "--with", "mcp<2",
           "python",
           "/Users/vincent.meoc/Library/CloudStorage/OneDrive-Nutanix/Dev/nkp-vibedemo-dashboard/tools/opencode-mcp/opencode_mcp.py"
         ],
         "env": {
           "OPENCODE_REPO": "/Users/vincent.meoc/Library/CloudStorage/OneDrive-Nutanix/Dev/nkp-vibedemo-dashboard",
           "OPENCODE_BIN": "/Users/vincent.meoc/.opencode/bin/opencode",
           "OPENCODE_TIMEOUT": "1200"
         }
       }
     }
   }
   ```

   If the file already has `mcpServers`, add the `"opencode"` entry inside it.

4. Quit Claude Desktop completely (Cmd+Q) and reopen it.
5. Check: Claude Desktop > Settings > Developer shows `opencode` as running.
   Logs if it fails: `~/Library/Logs/Claude/mcp-server-opencode.log`

## Headless permissions

`opencode run` has no one to answer permission prompts. If a task stalls or
reports a denied action, allow what the coding agent needs in the project
`opencode.json` (edit files, run the tests), and keep dangerous commands denied.
