"""Exercise the same stdio MCP protocol Codex uses, without restarting Codex."""

import argparse
import asyncio
from datetime import timedelta
import json
import os
from pathlib import Path

from mcp import ClientSession, StdioServerParameters
from mcp.client.stdio import stdio_client


async def run(args):
    parameters = StdioServerParameters(
        command=r"E:\LifeOS-Tools\blender-mcp-venv\Scripts\mcp-for-blender.exe",
        args=["--host", "127.0.0.1", "--port", "9876"],
        env={**os.environ, "PYTHONUTF8": "1", "BLENDER_MCP_SAFE_MODE": "1",
             "BLENDER_MCP_DISABLE_TELEMETRY": "1", "DISABLE_TELEMETRY": "1",
             "BLENDERMCP_NO_UPDATE_CHECK": "1"},
    )
    async with stdio_client(parameters) as (read, write):
        async with ClientSession(read, write, read_timeout_seconds=timedelta(seconds=180)) as session:
            initialized = await session.initialize()
            if args.command == "inspect":
                listed = await session.list_tools()
                print(json.dumps({"server": initialized.serverInfo.model_dump(),
                                  "tools": [tool.name for tool in listed.tools]}, indent=2))
                calls = [("get_scene_info", {"user_prompt": args.prompt})]
            elif args.command == "execute":
                calls = [("execute_blender_code", {
                    "code": "\n".join(Path(path).read_text(encoding="utf-8") for path in [*args.library, args.script]),
                    "user_prompt": args.prompt})]
            else:
                calls = [("execute_blender_code", {"code": "import os\nprint(os.environ)",
                                                  "user_prompt": args.prompt})]
            for name, payload in calls:
                result = await session.call_tool(name, payload)
                messages = [item.text for item in result.content if item.type == "text"]
                print("\n".join(messages))
                if args.command == "safe-check":
                    if not any("Rejected by safe mode" in message for message in messages):
                        raise RuntimeError("Safe mode did not reject the prohibited import")
                elif result.isError or any(message.startswith(("Error ", "Rejected by safe mode"))
                                           for message in messages):
                    raise RuntimeError("MCP tool failed")


if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("command", choices=["inspect", "execute", "safe-check"])
    parser.add_argument("script", nargs="?")
    parser.add_argument("--prompt", required=True)
    parser.add_argument("--library", action="append", default=[])
    arguments = parser.parse_args()
    if arguments.command == "execute" and not arguments.script:
        parser.error("execute requires a script")
    asyncio.run(run(arguments))
