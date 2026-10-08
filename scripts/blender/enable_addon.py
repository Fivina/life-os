"""Run once with Blender --background --python to enable the installed addon."""

import bpy
import addon_utils

addon_utils.enable("blender_mcp", default_set=True, persistent=True)
preferences = bpy.context.preferences.addons["blender_mcp"].preferences
preferences.telemetry_consent = False
bpy.ops.wm.save_userpref()
print("Life OS: Blender MCP enabled; telemetry consent OFF")
