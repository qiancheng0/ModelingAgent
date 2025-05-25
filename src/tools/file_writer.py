import os
from .base import BaseTool


class File_Writer_Tool(BaseTool):
    require_llm_engine = False

    def __init__(self):
        super().__init__(
            tool_name="File_Writer_Tool",
            tool_description="A tool that writes or appends content to a file.",
            tool_version="1.0.1",
            input_types={
                "file_path": "str - Path to the file (relative or starting with workspace/).",
                "content": "str - Text content to write or append.",
                "mode": "str - 'w' 覆盖写，'a' 追加写，默认 'a'。"
            },
            output_type="dict - { success: bool, message: str }",
            demo_commands=[
                {
                    "command": (
                        'tool.execute('
                        'file_path="workspace/experiments/sample.py", '
                        'content="print(\'Hello\')", mode="w")'
                    ),
                    "description": "写入实验脚本"
                }
            ],
            user_metadata={
                "limitation": "You cannot write binary file, your code write here will not be executed. Note that in your code, you should not use any things using g++. You can use numpy, pandas, scipy, etc.",
                "best_practice": "先确定正确目录，再写入；如需运行代码请调用 Code Executor。"
            },
        )

    def execute(self, file_path, content, mode="a"):
        """
        Write or append text to a file in the workspace.
        """
        if not file_path or not content:
            return {"success": False,
                    "message": "file_path 与 content 不能为空"}

        if mode not in ("w", "a"):
            return {"success": False,
                    "message": "mode 只能为 'w' 或 'a'"}

        try:
            # 1) 解析工作区路径
            workspace_root = os.getenv("WORKSPACE_PATH", "workspace")

            # 若用户给的是绝对路径 / 或其他 workspace 名称，进行处理
            if file_path.startswith("workspace/"):
                rel_path = file_path[len("workspace/"):]
            else:
                rel_path = file_path

            file_path = os.path.join(workspace_root, rel_path)

            # 2) 如果父目录不存在，先创建
            os.makedirs(os.path.dirname(file_path), exist_ok=True)

            # 3) 写或追加内容
            with open(file_path, mode, encoding="utf-8") as f:
                f.write(content)

            return {"success": True,
                    "message": f"Success: written to {file_path}"}

        except Exception as e:
            return {"success": False,
                    "message": f"Error writing file: {e}"}


if __name__ == "__main__":
    # Demo
    tool = File_Writer_Tool()
    res = tool.execute(
        file_path="workspace/experiments/test.py",
        content="print('Hello, World!')",
        mode="w"
    )
    print(res)