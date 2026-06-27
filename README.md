<div align="center">
  <a href="https://www.youtube.com/@EnKhayzo">
        <img src="https://img.shields.io/youtube/channel/subscribers/UCsQQB2f90XGFyr_qtNikbCw?logoColor=red&logo=youtube&style=for-the-badge"
            alt="Youtube"></a>
  <a href="https://discord.gg/nZDkBDbHjU">
        <img src="https://img.shields.io/discord/1324804381610213407?color=blue&labelColor=555555&label=&logo=discord&style=for-the-badge"
            alt="Chat on Discord"></a>
  <a href="https://x.com/EnKhayzo">
        <img src="https://img.shields.io/twitter/follow/EnKhayzo?logo=x&logoColor=black&style=for-the-badge"
            alt="X / Twitter"></a>
  <a href="https://bsky.app/profile/enkhayzo.bsky.social">
        <img src="https://img.shields.io/badge/-Bluesky-3686f7?logo=icloud&logoColor=white&style=for-the-badge"
            alt="Bluesky"></a>
</div>

# OBS-Recording-Organizer

> **🔀 Fork Notice:** This is a fork of [EnKhayzo's OBS Recordings Organizer](https://github.com/EnKhayzo/OBS-Recordings-Organizer), which is itself a fork of [francdv23's original OBS Recordings Organizer](https://github.com/francdv23/OBS-Recordings-Organizer). This fork adds **Linux (Wayland/X11) support**.

## Description
####
This is a fork of [francdv23's OBS Recordings Organizer](https://github.com/francdv23/OBS-Recordings-Organizer) and adds a few features, namely:
####
-The possibility to automatically cut replay buffer clips that overlap (with or without re-encoding the clips); it uses ffmpeg/ffprobe when saving a clip, thus in order to properly function it requires the built executables (i have put an already built binary inside the full release version).
### 
-The ability to choose whether to prefix the clip title with the game name or not (got the idea from [padiix](https://github.com/padiix/OBS-Recordings-Organizer)'s fork, thank you).
#### 
*Original Description:*
#### 
This is an improved and simplified version of [pjw29's OBS Rec Rename](https://github.com/pjw29/obs-rec-rename) Python script, that, similarly to NVidia ShadowPlay, allows OBS to rename and organize into folders video recordings based on the window title on focus whenever a replay buffer or a recording is saved, unlike from the previous version where it periodically checked for new clips.

---

## 🐧 Linux (Wayland / X11) — Installation & Usage

This version has been ported to work on **Linux** with support for **Wayland** compositors (Hyprland, Sway, GNOME/Mutter, KDE/KWin) and **X11** as a fallback.

### Requirements

#### System packages

Make sure you have the following installed:

```bash
# Python 3.11+ (usually bundled with OBS on Linux)
python3 --version

# ffmpeg and ffprobe (required for decollide feature)
sudo apt install ffmpeg          # Debian/Ubuntu
sudo pacman -S ffmpeg            # Arch Linux
sudo dnf install ffmpeg          # Fedora

# psutil Python library
pip install psutil
# or
pip3 install psutil
```

#### Window detection tools

Depending on your desktop environment/compositor, you need **one** of the following:

| Compositor | Required tool | Install command |
|---|---|---|
| **Hyprland** | `hyprctl` (bundled with Hyprland) | Already included with Hyprland |
| **Sway** | `swaymsg` (bundled with Sway) | Already included with Sway |
| **GNOME** | `gdbus` (bundled with GNOME) | Already included with GNOME |
| **KDE Plasma** | `kdotool` or `gdbus` | `sudo pacman -S kdotool` / `sudo apt install kdotool` |
| **X11 (any)** | `xdotool` + `xprop` | `sudo apt install xdotool x11-utils` / `sudo pacman -S xdotool xorg-xprop` |
| **Other wlroots** | `wlrctl` | `sudo pacman -S wlrctl` / build from source |

> **Note:** The script automatically detects your compositor and uses the appropriate tool. If you use Hyprland or Sway, no extra tools need to be installed.

#### Sound notifications (optional)

If you want sound notifications when clips are saved, you need GStreamer:

```bash
# Debian/Ubuntu
sudo apt install python3-gi gstreamer1.0-plugins-base gstreamer1.0-plugins-good

# Arch Linux
sudo pacman -S python-gobject gst-plugins-base gst-plugins-good

# Fedora
sudo dnf install python3-gobject gstreamer1-plugins-base gstreamer1-plugins-good
```

### Step-by-step installation

1. **Clone or download** this repository:
   ```bash
   git clone https://github.com/EnKhayzo/OBS-Recordings-Organizer.git
   ```
   Or download and extract the ZIP to a folder of your choice, for example:
   ```
   ~/scripts/obs-rec-organizer/
   ```

2. **Configure Python in OBS Studio:**
   - Open OBS Studio
   - Go to `Tools > Scripts > Python Settings`
   - Set the Python install path. On most Linux distros this is automatically detected. If not, try:
     ```
     /usr
     ```
     or
     ```
     /usr/lib/python3.XX
     ```
     (replace `XX` with your Python version, e.g., `3.12`)

3. **Load the script in OBS:**
   - Go to `Tools > Scripts`
   - Click the **"+"** button
   - Navigate to where you saved the files and select **`OBS-RecOrganizer.py`**
   - The script settings panel will appear

4. **Configure the script:**
   - **Recordings folder**: Set to your OBS recordings output folder (same as in `Settings > Output > Recording > Recording Path`)
   - **File extension**: Set to your recording format (e.g., `.mkv`, `.mp4`)
   - Other settings are optional (see "Settings and configurations" section below)

5. **Test it:**
   - Start a replay buffer or recording in OBS
   - Open a game or application window
   - Save the replay buffer (or stop the recording)
   - Check your recordings folder — a subfolder named after the active window should have been created with the clip inside!

### Troubleshooting (Linux)

1. **"Unknown" folder created instead of game name:**
   - Make sure the required window detection tool is installed for your compositor (see table above)
   - For Hyprland: verify `hyprctl activewindow -j` works in a terminal
   - For Sway: verify `swaymsg -t get_tree` works in a terminal
   - For X11: verify `xdotool getactivewindow getwindowname` works

2. **Script not loading in OBS:**
   - Make sure `psutil` is installed for the same Python version OBS is using
   - Check the OBS log (`Help > Log Files > View Current Log`) for Python errors

3. **Sound not playing:**
   - Install GStreamer packages (see "Sound notifications" section above)
   - Test in a terminal: `python3 -c "import gi; gi.require_version('Gst', '1.0'); from gi.repository import Gst; print('GStreamer OK')"`

4. **Decollide not working:**
   - Make sure `ffmpeg` and `ffprobe` are installed and accessible from PATH
   - Test: `ffmpeg -version` and `ffprobe -version`

5. **Permission errors:**
   - Make sure OBS has write permissions to the recordings folder
   - If using Flatpak OBS, you may need to grant filesystem access:
     ```bash
     flatpak override --user --filesystem=home com.obsproject.Studio
     ```

### ⌨️ Global hotkeys on Wayland (Replay Buffer shortcut)

On Wayland, OBS Studio may not be able to capture global hotkeys — meaning you need OBS focused to use shortcuts like "Save Replay Buffer". To work around this, you can use **[obs-cmd](https://github.com/gribd/obs-cmd)** combined with a **system-level shortcut**.

#### 1. Install obs-cmd

```bash
# Arch Linux / CachyOS (AUR)
yay -S obs-cmd

# Or via Cargo (Rust)
cargo install obs-cmd
```

#### 2. Enable the OBS WebSocket Server

- In OBS, go to **Tools → WebSocket Server Settings**
- Check **"Enable WebSocket Server"**
- Optionally uncheck **"Enable Authentication"** (simpler for local use)
- Click **OK**

#### 3. Test it

With OBS open and the Replay Buffer running:
```bash
obs-cmd replay save
```

#### 4. Create a system-level global shortcut

**KDE Plasma:**
1. Open **System Settings → Shortcuts → Custom Shortcuts**
2. Click **Edit → New → Global Shortcut → Command/URL**
3. In the **Trigger** tab: set your desired key (e.g., `F9`)
4. In the **Action** tab: enter `obs-cmd replay save`
5. Apply

**Hyprland** (add to `hyprland.conf`):
```
bind = , F9, exec, obs-cmd replay save
```

**Sway** (add to `~/.config/sway/config`):
```
bindsym F9 exec obs-cmd replay save
```

Now you can save replay buffer clips from **any window** without switching to OBS!

> **Other useful obs-cmd commands:**
> ```bash
> obs-cmd replay save       # Save replay buffer
> obs-cmd recording start   # Start recording
> obs-cmd recording stop    # Stop recording
> obs-cmd recording toggle  # Toggle recording
> obs-cmd --help            # See all commands
> ```

---

## 🪟 Windows — Installation & Usage

### Requirements
#### 
This script has been tested on Python 3.12 [(3.12.3 recommended)](https://www.python.org/downloads/release/python-3123/), as well as [pywin32](https://pypi.org/project/pywin32/) and [psutil](https://pypi.org/project/psutil/) libraries which can be installed via command line:
```
pip install pywin32
pip install psutil
```
Python can now be loaded in OBS by `Tools > Scripts > Python Settings` and choosing Python3123 path.
### Next steps
#### 
After the previous indications the actual script can be now installed. It doesn't need to be placed in a specific directory, for convenience the scripts folder located at `C:\Program Files\obs-studio\data\obs-plugins\frontend-tools\scripts\obs-rec-organizer` is ideal. It can be loaded into OBS by `Tools > Scripts` hit the *__"+"__* sign and search for _OBS-RecOrganizer.py_ from the previous path.

> **Note:** The Windows version of this script is available in the `windows` branch or from the original release. The `main` branch contains the Linux-compatible version.

---

## Settings and configurations
### Basic
#### 
-Recordings folder: Default output folder when you hit Save Recording or Save Replay Buffer, can be found in your OBS settings.
#### 
-File extension: Default extension for the clip you save (the dot '.' is optional), this can be found in your OBS settings.
### Advanced
-Decollide Saved clips: makes sure saved recordings don't 'overlap' (i.e the previous clip shares some footage with the current clip, it's the default behaviour for Replay Buffer), this setting cuts the clip using ffmpeg to cut and ffprobe to get the video duration/s. If you don't check the option 'Don't Re-Encode when Decolliding' the decollided clip will loose some quality upon re-encoding.
#### 
-Don't Re-Encode when Decolliding: makes sure that ffmpeg doesn't re-encode the clip when decolliding it, thus keeping the clip's original quality. The caveat is that the cut is not precise: either a few extra frames are cut or they are kept, depending on where the nearest encoding keyframe lands in the clip relative to the cut timestamp.
#### 
-Custom ffmpeg path: path to the ffmpeg binary; optional if ffmpeg is in your system PATH (which it usually is on Linux).
#### 
-Custom ffprobe path: path to the ffprobe binary; optional if ffprobe is in your system PATH (which it usually is on Linux).
#### 
### Overrides
#### 
Within the scripts are included two *cfg* files named *DesktopOverride.cfg* and *FullscreenOverride.cfg*, you can write the executable name in them to respectively override a windowed game targetting it correctly or to tweak a fullscreen program in *"Desktop"* recording.

## Supported Linux compositors

| Compositor | Detection method | Fullscreen detection |
|---|---|---|
| **Hyprland** | `hyprctl activewindow -j` | ✅ via `fullscreen` field + monitor size comparison |
| **Sway** | `swaymsg -t get_tree` (finds focused node) | ✅ via `fullscreen_mode` field |
| **GNOME/Mutter** | `gdbus` call to `org.gnome.Shell.Eval` | ✅ via `is_fullscreen()` method |
| **KDE/KWin** | KWin Scripting API via `gdbus` (fallback: `kdotool`) | ✅ via `fullScreen` property |
| **X11** | `xdotool` + `xprop` | ✅ via `_NET_WM_STATE_FULLSCREEN` + geometry |
| **wlroots (generic)** | `wlrctl toplevel find` | ❌ Not available |

## Common problems
#### 
1) If you experience any problems installing the libraries, the first thing I recommend to do is update pip with: 
```
python -m pip install --upgrade pip
```
2) **Linux:** If `psutil` installation fails, try installing the system package instead:
```bash
# Debian/Ubuntu
sudo apt install python3-psutil

# Arch Linux
sudo pacman -S python-psutil
```
3) **Windows:** If Pywin32 gives you any troubles, first uninstall it with ```pip uninstall pywin32``` and then download it from [here](https://github.com/mhammond/pywin32/releases/tag/b306) choosing *py312* version.
####
4) Recordings not organized into subfolder or not renamed: it can occur in the first/second recording or buffer replay, but no more further because the script only needed to create its cache.
## Credits
All credit for the default sounds (success.mp3 and error.mp3) go to [Sjonas88](https://freesound.org/people/Sjonas88/) on freesound.org
