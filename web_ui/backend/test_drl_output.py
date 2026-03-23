import json
with open("variables.json", "r") as f:
    v = json.load(f)

var_lines = ["# --- DYNAMIC UI VARIABLES ---"]
for k, val in v.items():
    if isinstance(val, (int, float, str, list)):
        var_lines.append(f"{k} = {json.dumps(val)}")
var_lines.append("# ----------------------------\n")

drl_code = """
# ──────────────────────────────────────────────────────────────────
# HOMING Program
# ──────────────────────────────────────────────────────────────────
# This program moves the robot to the configured J01 position.
# The `J01` variable is automatically injected dynamically 
# into this script by the Web UI Backend before execution.
# ──────────────────────────────────────────────────────────────────

tp_print("Executing HOMING...")
tp_print("Target J01: " + str(J01))

# DRL requires posj format for joint moves.
target_pos = posj(J01[0], J01[1], J01[2], J01[3], J01[4], J01[5])

tp_print("Moving to Home...")
movej(target_pos, vel=30.0, acc=60.0)
tp_print("Homing complete.")
"""

injected_code = "\n".join(var_lines) + drl_code
print("TOTAL LINES: ", len(injected_code.split('\n')))
print("TOTAL BYTES: ", len(injected_code))
