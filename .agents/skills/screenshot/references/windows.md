# Windows capture

Read the canonical screenshot skill first. Resolve helper paths relative to that skill's directory.

Use `powershell -NoProfile -File "<skill>/scripts/take_screenshot.ps1"` with one of these task-scoped targets:

```powershell
# A known, visible application region: x,y,width,height.
powershell -NoProfile -File "<skill>/scripts/take_screenshot.ps1" -Mode temp -Region "100,200,800,600"

# A verified visible window; obtain its handle from the requested app.
powershell -NoProfile -File "<skill>/scripts/take_screenshot.ps1" -Mode temp -WindowHandle 123456

# Only when the intended window is confirmed active.
powershell -NoProfile -File "<skill>/scripts/take_screenshot.ps1" -Mode temp -ActiveWindow

# A user-selected output file and region.
powershell -NoProfile -File "<skill>/scripts/take_screenshot.ps1" -Path "C:\Temp\app.png" -Region "100,200,800,600"
```

The helper accepts PNG, JPEG and BMP using `-Format`. Use its default or full-screen capture only when that scope is actually authorized; without a target it captures the virtual desktop, potentially including multiple displays.

The helper uses `GetWindowRect` and `CopyFromScreen`, not a private offscreen window renderer. A minimized, covered, offscreen or incorrectly focused window can therefore expose unrelated pixels or fail. Confirm visibility and bounds before running it; ask the user to focus the requested app only when that state cannot otherwise be established. Do not force a click or capture a different foreground app when activation fails.

Do not change PowerShell execution policy or add bypass flags to overcome an execution error. Use a permitted capture method or report the missing authority under the current client policy. Validate integer region coordinates and positive width/height; avoid constructing shell commands from untrusted window titles or paths.

For an agent inspection, keep images outside Git in the temporary directory. View each returned path before interpreting the UI, and return only the task-relevant findings or requested image path.
