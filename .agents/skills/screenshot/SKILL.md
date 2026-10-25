---
name: screenshot
description: Capture a requested desktop window or region, or inspect a task-relevant app when a more specific capture tool is unavailable.
---

# Screenshot capture

Follow [AGENTS.md](../../../AGENTS.md), existing task authority and current client permissions. Prefer the relevant app integration or Playwright for browser/Electron capture when available; use this skill for requested OS screenshots or a native-app inspection without a suitable capture tool.

Capture only the authorized application or region. Avoid unrelated windows, notifications, personal data and credentials. A request to inspect one app does not authorize a full-desktop capture. Selecting this skill grants no new account access, shell permission or security-policy override.

Save a user-requested screenshot to the specified path, or the OS screenshot location when none was supplied. Save an agent's own inspection artifact to a temporary path outside Git. Use the existing bundled helper rather than rebuilding platform-specific capture logic.

Read only the applicable platform reference:

- **Windows:** [Windows capture](references/windows.md), using `scripts/take_screenshot.ps1`.
- **macOS or Linux:** [macOS/Linux capture](references/macos-linux.md), using `scripts/take_screenshot.py` and the documented platform prerequisites.

Verify the intended app is visible and the selected bounds are correct before capture. Window-bound screen capture may include whatever covers that region, so a window handle alone does not prove the resulting pixels belong to that app. If visibility or permission prevents a scoped capture, report the actual limitation and obtain only the missing user input or authority.

View the resulting image before interpreting it. Report the saved path and distinguish observed pixels from inferred state. Do not publish the artifact or change the application as part of a screenshot-only request. Keep automatic startup/profile changes and broad permission workarounds out of capture workflows.
