import os, re, difflib, shutil
from .base import BaseTool


class File_Edit_Tool(BaseTool):
    require_llm_engine = False

    def __init__(self):
        super().__init__(
            tool_name="File_Edit_Tool",
            tool_description="Edit an existing text file via regex or line-number operations.",
            tool_version="1.0.0",
            input_types={
                "file_path":     "str – path relative to workspace/",
                "operation":     "str – one of replace|insert_after|insert_before|delete",
                "target":        "str|int – regex (string) **or** 1-based line number",
                "content":       "str – text to insert / replace with (ignored for delete)",
                "occurrence":    "str – 'first' (default) or 'all'"
            },
            output_type="dict – {success: bool, message: str, diff_preview: str}",
            demo_commands=[
                {
                    "command": (
                        'tool.execute('
                        'file_path="workspace/experiments/solver.py", '
                        'operation="replace", '
                        'target="def step\\(", '
                        'content="# TODO: refactor step()", '
                        'occurrence="first")'
                    ),
                    "description": "Replace the first occurrence of `def step(`"
                }
            ],
            user_metadata={
                "limitation": (
                    "Text-only. Binary files are not supported. Keep each edit focused and small "
                    "to minimise merge conflicts or unintended changes."
                ),
                "best_practice": (
                    "Pinpoint the edit with a unique regex or an exact line number. "
                    "Always inspect the `diff_preview` the tool returns, and, if you "
                    "need to run the modified code, follow up with the Code_Execution_Tool."
                ),
            }
        )

    # ---------- internal helpers ----------
    def _make_backup(self, path):
        bak = path + ".bak"
        shutil.copy2(path, bak)

    def _build_diff(self, before_lines, after_lines, ctx=3):
        diff = difflib.unified_diff(
            before_lines, after_lines, lineterm="", n=ctx,
            fromfile="before", tofile="after"
        )
        # Only return first 200 lines of diff preview to prevent excessive length
        return "\n".join(list(diff)[:200])

    # ---------- main entry ----------
    def execute(
        self,
        file_path: str,
        operation: str,
        target,
        content: str = "",
        occurrence: str = "first"
    ):
        try:
            if operation not in {"replace", "insert_after", "insert_before", "delete"}:
                return {"success": False, "message": f"unknown operation: {operation}"}

            # Parse workspace absolute path
            ws_root = os.getenv("WORKSPACE_PATH", "workspace")
            if file_path.startswith("workspace/"):
                file_path = file_path[len("workspace/"):]
            abs_path = os.path.join(ws_root, file_path)

            if not os.path.exists(abs_path):
                return {"success": False, "message": f"file not found: {abs_path}"}

            with open(abs_path, "r", encoding="utf-8") as f:
                lines = f.readlines()

            self._make_backup(abs_path)  # Backup

            # ---- Locate lines ----
            # target is int -> exact line number
            matches = []
            if isinstance(target, int):
                idx = target - 1  # Convert to 0-base
                if 0 <= idx < len(lines):
                    matches = [idx]
            else:  # regex
                pattern = re.compile(str(target))
                matches = [i for i, ln in enumerate(lines) if pattern.search(ln)]

            if not matches:
                return {"success": False, "message": "no match found"}

            if occurrence == "first":
                matches = matches[:1]

            # ---- Execute changes ----
            for i in (sorted(matches, reverse=True)  # Process in reverse order to avoid index shifting
                      if operation.startswith("insert") else matches):
                if operation == "replace":
                    lines[i] = content if content.endswith("\n") else content + "\n"
                elif operation == "insert_after":
                    insert = content if content.endswith("\n") else content + "\n"
                    lines.insert(i + 1, insert)
                elif operation == "insert_before":
                    insert = content if content.endswith("\n") else content + "\n"
                    lines.insert(i, insert)
                elif operation == "delete":
                    lines.pop(i)

            # ---- Write back ----
            with open(abs_path, "w", encoding="utf-8") as f:
                f.writelines(lines)

            diff_preview = self._build_diff(before_lines=[], after_lines=[])  # optional: skip large diff
            diff_preview = self._build_diff(
                before_lines=open(abs_path + ".bak", encoding="utf-8").read().splitlines(),
                after_lines=lines
            )

            return {
                "success": True,
                "message": f"{operation} on {len(matches)} occurrence(s) done.",
                "diff_preview": diff_preview
            }

        except Exception as e:
            return {"success": False, "message": f"edit error: {e}"}
