import obspython as S
import glob, re, psutil, os, os.path, shutil
from pathlib import Path
from datetime import datetime, timedelta
import pathlib
import subprocess
import traceback
import json
import platform

import version
import playsound

# UTILS FUNCS
##############################

def strip_ext(path):
    lastIdx = path.rindex('.')
    if lastIdx == -1: return path
    return path[:lastIdx]

def get_ext(path):
    lastIdx = path.rindex('.')
    if lastIdx == -1 or lastIdx >= len(path)-1: return ''
    return path[lastIdx+1:]


def isQuote(ch):
    return ch == "\"" or ch == "'"

def isIgnorable(ch):
    return ch == ' ' or ch == '\n'

def getParam(inStr, n):
    res = None
    while len(inStr) > 0 and n >= 0:
        while(len(inStr) > 0 and isIgnorable(inStr[0])):
            inStr = inStr[1:]

        if len(inStr) > 0 and n == 0: res = ""

        if(len(inStr) > 0 and isQuote(inStr[0])):
            openingQuote = inStr[0]

            inStr = inStr[1:]
            while(len(inStr) > 0 and not inStr[0] == openingQuote):
                if n == 0: res += inStr[0]
                inStr = inStr[1:]
                
            if len(inStr) > 0: inStr = inStr[1:]
        else:
            while(len(inStr) > 0 and not isIgnorable(inStr[0])):
                if n == 0: res += inStr[0]
                inStr = inStr[1:]

        n-=1

    return res

def getParams(line):
    params = []

    n = 1
    param = getParam(line, 0)
    while param is not None:
        params.append(param)
        
        param = getParam(line, n)
        n+=1

    return params

def startProcess(command, onLine):
    print(command)

    args = None
    if not isinstance(command, list): args = getParams(command)
    else: args = command

    with subprocess.Popen(
        args, 
        stdout=subprocess.PIPE, 
        stderr=subprocess.STDOUT, 
        text=True, 
        shell=False, 
        encoding="utf-8"
    ) as proc:
        for line in proc.stdout:
            ret = onLine(line.strip())
            if ret: break
            
    return proc.returncode


##############################
# /UTILS FUNCS


# LINUX WINDOW DETECTION
##############################

def _is_wayland():
    """Check if we're running under Wayland."""
    return os.environ.get('WAYLAND_DISPLAY') is not None or \
           os.environ.get('XDG_SESSION_TYPE') == 'wayland'

def _run_cmd(cmd, timeout=2):
    """Run a command and return its stdout, or None on failure."""
    try:
        result = subprocess.run(
            cmd,
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            text=True,
            timeout=timeout
        )
        if result.returncode == 0:
            return result.stdout.strip()
        return None
    except (FileNotFoundError, subprocess.TimeoutExpired, Exception):
        return None

def _get_window_info_hyprland():
    """Get active window info from Hyprland compositor using hyprctl."""
    output = _run_cmd(['hyprctl', 'activewindow', '-j'])
    if output is None:
        return None
    
    try:
        data = json.loads(output)
        title = data.get('title', '')
        pid = data.get('pid', 0)
        is_fullscreen = data.get('fullscreen', False) or data.get('fullscreenClient', 0) != 0
        
        # Get window size and monitor size for fullscreen detection
        size = data.get('size', [0, 0])
        
        # Try to get monitor info for fullscreen comparison
        monitor_output = _run_cmd(['hyprctl', 'monitors', '-j'])
        screen_w, screen_h = 0, 0
        if monitor_output:
            try:
                monitors = json.loads(monitor_output)
                if monitors:
                    # Use the focused monitor
                    for m in monitors:
                        if m.get('focused', False):
                            screen_w = m.get('width', 0)
                            screen_h = m.get('height', 0)
                            break
                    if screen_w == 0 and monitors:
                        screen_w = monitors[0].get('width', 0)
                        screen_h = monitors[0].get('height', 0)
            except json.JSONDecodeError:
                pass
        
        if not is_fullscreen and screen_w > 0:
            is_fullscreen = (size[0] >= screen_w and size[1] >= screen_h)
        
        return {
            'title': title,
            'pid': pid,
            'is_fullscreen': is_fullscreen,
            'screen_w': screen_w,
            'screen_h': screen_h
        }
    except (json.JSONDecodeError, KeyError, IndexError):
        return None

def _get_window_info_sway():
    """Get active window info from Sway compositor using swaymsg."""
    output = _run_cmd(['swaymsg', '-t', 'get_tree'])
    if output is None:
        return None
    
    try:
        tree = json.loads(output)
        
        # Find the focused node in the tree
        def find_focused(node):
            if node.get('focused', False):
                return node
            for n in node.get('nodes', []) + node.get('floating_nodes', []):
                result = find_focused(n)
                if result:
                    return result
            return None
        
        focused = find_focused(tree)
        if focused is None:
            return None
        
        title = focused.get('name', '')
        pid = focused.get('pid', 0)
        
        # Fullscreen detection
        fullscreen_mode = focused.get('fullscreen_mode', 0)
        is_fullscreen = fullscreen_mode > 0
        
        # Get output (monitor) info
        screen_w, screen_h = 0, 0
        outputs_output = _run_cmd(['swaymsg', '-t', 'get_outputs'])
        if outputs_output:
            try:
                outputs = json.loads(outputs_output)
                for o in outputs:
                    if o.get('focused', False):
                        mode = o.get('current_mode', {})
                        screen_w = mode.get('width', 0)
                        screen_h = mode.get('height', 0)
                        break
            except json.JSONDecodeError:
                pass
        
        return {
            'title': title,
            'pid': pid,
            'is_fullscreen': is_fullscreen,
            'screen_w': screen_w,
            'screen_h': screen_h
        }
    except (json.JSONDecodeError, KeyError):
        return None

def _get_window_info_gnome():
    """Get active window info from GNOME/Mutter via gdbus."""
    # GNOME exposes window info through the eval interface (requires 'unsafe-mode' or extensions)
    # Try using gdbus to call org.gnome.Shell.Eval
    script = """
    const start = global.get_window_actors();
    let focused = null;
    for (let actor of start) {
        let win = actor.get_meta_window();
        if (win.has_focus()) {
            focused = win;
            break;
        }
    }
    if (focused) {
        JSON.stringify({
            title: focused.get_title(),
            pid: focused.get_pid(),
            is_fullscreen: focused.is_fullscreen(),
            wm_class: focused.get_wm_class()
        });
    } else {
        JSON.stringify({title: '', pid: 0, is_fullscreen: false, wm_class: ''});
    }
    """
    output = _run_cmd([
        'gdbus', 'call', '--session',
        '--dest', 'org.gnome.Shell',
        '--object-path', '/org/gnome/Shell',
        '--method', 'org.gnome.Shell.Eval',
        script
    ])
    
    if output is None:
        return None
    
    try:
        # gdbus returns something like: (true, '{"title":"...","pid":123,...}')
        # Extract the JSON string
        match = re.search(r"'(\{.*\})'", output)
        if not match:
            return None
        data = json.loads(match.group(1))
        
        # Get screen resolution
        screen_w, screen_h = 0, 0
        xrandr_output = _run_cmd(['xrandr', '--current'])
        if xrandr_output:
            for line in xrandr_output.split('\n'):
                if ' connected primary' in line or (' connected' in line and '*' not in line):
                    res_match = re.search(r'(\d+)x(\d+)', line)
                    if res_match:
                        screen_w = int(res_match.group(1))
                        screen_h = int(res_match.group(2))
                        break
        
        return {
            'title': data.get('title', ''),
            'pid': data.get('pid', 0),
            'is_fullscreen': data.get('is_fullscreen', False),
            'screen_w': screen_w,
            'screen_h': screen_h
        }
    except (json.JSONDecodeError, AttributeError):
        return None

def _get_window_info_kde():
    """Get active window info from KDE/KWin via D-Bus scripting.
    
    Uses KWin's JavaScript scripting API to query the active window.
    The script output goes to the system journal, which we read back
    using a unique marker to identify our output.
    """
    import time as _time
    import tempfile
    
    # Create a unique marker to find our output in the journal
    marker = f"OBS_REC_ORG_{int(_time.time()*1000)}"
    
    script_content = f"""
(function() {{
    var active = workspace.activeWindow;
    if (active) {{
        print("{marker}:" + JSON.stringify({{
            title: active.caption,
            pid: active.pid,
            fullscreen: active.fullScreen,
            resourceClass: active.resourceClass,
            width: active.width,
            height: active.height
        }}));
    }} else {{
        print("{marker}:" + JSON.stringify({{title: "", pid: 0, fullscreen: false, resourceClass: "", width: 0, height: 0}}));
    }}
}})();
"""
    
    # Write script to a temp file
    script_file = None
    try:
        script_file = os.path.join(tempfile.gettempdir(), f'obs_rec_org_kwin_{os.getpid()}.js')
        with open(script_file, 'w') as f:
            f.write(script_content)
        
        # Load script into KWin
        result = subprocess.run(
            ['gdbus', 'call', '--session', '--dest', 'org.kde.KWin',
             '--object-path', '/Scripting', '--method', 'org.kde.kwin.Scripting.loadScript',
             script_file, f'obs_rec_organizer_{os.getpid()}'],
            capture_output=True, text=True, timeout=2
        )
        
        script_id_match = re.search(r'\((\d+),\)', result.stdout)
        if not script_id_match:
            return None
        
        script_id = script_id_match.group(1)
        
        # Run the script
        subprocess.run(
            ['gdbus', 'call', '--session', '--dest', 'org.kde.KWin',
             '--object-path', f'/Scripting/Script{script_id}',
             '--method', 'org.kde.kwin.Script.run'],
            capture_output=True, text=True, timeout=2
        )
        
        _time.sleep(0.15)
        
        # Stop and unload the script
        subprocess.run(
            ['gdbus', 'call', '--session', '--dest', 'org.kde.KWin',
             '--object-path', f'/Scripting/Script{script_id}',
             '--method', 'org.kde.kwin.Script.stop'],
            capture_output=True, text=True, timeout=2
        )
        subprocess.run(
            ['gdbus', 'call', '--session', '--dest', 'org.kde.KWin',
             '--object-path', '/Scripting', '--method', 'org.kde.kwin.Scripting.unloadScript',
             script_file],
            capture_output=True, text=True, timeout=2
        )
        
        # Read the journal for our marker
        journal = subprocess.run(
            ['journalctl', '--user', '-t', 'kwin_wayland', '--since', '-5s',
             '--no-pager', '-o', 'cat'],
            capture_output=True, text=True, timeout=2
        )
        
        # Also try without --user flag (some distros)
        if marker not in journal.stdout:
            journal = subprocess.run(
                ['journalctl', '-t', 'kwin_wayland', '--since', '-5s',
                 '--no-pager', '-o', 'cat'],
                capture_output=True, text=True, timeout=2
            )
        
        for line in journal.stdout.split('\n'):
            if marker in line:
                json_str = line.split(marker + ':')[1].strip()
                data = json.loads(json_str)
                
                # Get screen resolution
                screen_w, screen_h = _get_screen_resolution()
                
                return {
                    'title': data.get('title', ''),
                    'pid': data.get('pid', 0),
                    'is_fullscreen': data.get('fullscreen', False),
                    'screen_w': screen_w,
                    'screen_h': screen_h
                }
        
        # Fallback: try kdotool
        output = _run_cmd(['kdotool', 'getactivewindow', 'getwindowname'])
        if output:
            return {
                'title': output,
                'pid': 0,
                'is_fullscreen': False,
                'screen_w': 0,
                'screen_h': 0
            }
        
        return None
    except Exception as e:
        print(f"KDE window detection error: {e}")
        return None
    finally:
        if script_file:
            try:
                os.remove(script_file)
            except OSError:
                pass

def _get_screen_resolution():
    """Get the primary screen resolution using available tools."""
    # Try xrandr first (works on both X11 and XWayland)
    xrandr_output = _run_cmd(['xrandr', '--current'])
    if xrandr_output:
        for line in xrandr_output.split('\n'):
            if ' connected primary' in line:
                res_match = re.search(r'(\d+)x(\d+)', line)
                if res_match:
                    return int(res_match.group(1)), int(res_match.group(2))
        # Fallback: find first connected output with a mode
        for line in xrandr_output.split('\n'):
            if ' connected' in line:
                res_match = re.search(r'(\d+)x(\d+)', line)
                if res_match:
                    return int(res_match.group(1)), int(res_match.group(2))
    
    # Try wlr-randr (wlroots compositors)
    wlr_output = _run_cmd(['wlr-randr'])
    if wlr_output:
        for line in wlr_output.split('\n'):
            res_match = re.search(r'(\d+)x(\d+)', line)
            if res_match:
                return int(res_match.group(1)), int(res_match.group(2))
    
    return 0, 0

def _get_window_info_x11():
    """Get active window info using X11 tools (xdotool, xprop)."""
    # Get active window ID
    win_id = _run_cmd(['xdotool', 'getactivewindow'])
    if win_id is None:
        return None
    
    win_id = win_id.strip()
    
    # Get window title
    title = _run_cmd(['xdotool', 'getactivewindow', 'getwindowname'])
    if title is None:
        title = ''
    
    # Get PID
    pid = 0
    pid_str = _run_cmd(['xdotool', 'getactivewindow', 'getwindowpid'])
    if pid_str:
        try:
            pid = int(pid_str.strip())
        except ValueError:
            pass
    
    # Get window geometry for fullscreen detection
    is_fullscreen = False
    geom_output = _run_cmd(['xdotool', 'getactivewindow', 'getwindowgeometry', '--shell'])
    win_w, win_h = 0, 0
    if geom_output:
        for line in geom_output.split('\n'):
            if line.startswith('WIDTH='):
                try: win_w = int(line.split('=')[1])
                except ValueError: pass
            elif line.startswith('HEIGHT='):
                try: win_h = int(line.split('=')[1])
                except ValueError: pass
    
    # Get screen resolution
    screen_w, screen_h = 0, 0
    xrandr_output = _run_cmd(['xrandr', '--current'])
    if xrandr_output:
        for line in xrandr_output.split('\n'):
            if '*' in line:
                res_match = re.search(r'(\d+)x(\d+)', line)
                if res_match:
                    screen_w = int(res_match.group(1))
                    screen_h = int(res_match.group(2))
                    break
    
    # Check fullscreen via _NET_WM_STATE
    xprop_output = _run_cmd(['xprop', '-id', win_id, '_NET_WM_STATE'])
    if xprop_output and '_NET_WM_STATE_FULLSCREEN' in xprop_output:
        is_fullscreen = True
    elif screen_w > 0 and win_w >= screen_w and win_h >= screen_h:
        is_fullscreen = True
    
    return {
        'title': title,
        'pid': pid,
        'is_fullscreen': is_fullscreen,
        'screen_w': screen_w,
        'screen_h': screen_h
    }

def _get_window_info_wlroots_generic():
    """Try wlrctl as a generic wlroots-based compositor fallback."""
    # wlrctl doesn't have a direct 'get active window' but we can try
    output = _run_cmd(['wlrctl', 'toplevel', 'find', 'state:activated'])
    if output:
        return {
            'title': output.split('\n')[0].strip(),
            'pid': 0,
            'is_fullscreen': False,
            'screen_w': 0,
            'screen_h': 0
        }
    return None

def get_active_window_info():
    """
    Get information about the currently active/focused window.
    Returns a dict with: title, pid, is_fullscreen, screen_w, screen_h
    Falls back through multiple methods depending on the desktop environment.
    """
    info = None
    
    if _is_wayland():
        # Try Hyprland first (most common tiling wlroots compositor)
        if os.environ.get('HYPRLAND_INSTANCE_SIGNATURE'):
            info = _get_window_info_hyprland()
        
        # Try Sway
        if info is None and os.environ.get('SWAYSOCK'):
            info = _get_window_info_sway()
        
        # Try KDE
        if info is None and os.environ.get('KDE_FULL_SESSION'):
            info = _get_window_info_kde()
        
        # Try GNOME
        if info is None and (os.environ.get('GNOME_DESKTOP_SESSION_ID') or 
                            os.environ.get('DESKTOP_SESSION', '').lower() in ('gnome', 'ubuntu', 'pop')):
            info = _get_window_info_gnome()
        
        # Try all in sequence as fallback
        if info is None:
            for method in [_get_window_info_hyprland, _get_window_info_sway, 
                          _get_window_info_kde, _get_window_info_gnome,
                          _get_window_info_wlroots_generic]:
                info = method()
                if info is not None:
                    break
    
    # X11 fallback (also works under XWayland in some cases)
    if info is None:
        info = _get_window_info_x11()
    
    # Final fallback
    if info is None:
        info = {
            'title': 'Unknown',
            'pid': 0,
            'is_fullscreen': False,
            'screen_w': 0,
            'screen_h': 0
        }
    
    return info

##############################
# /LINUX WINDOW DETECTION


class Data:
    OutputDir = None
    Extension = None
    ExtensionMask = None

    PrefixGameName = None
    DecollideClips = None
    DontReencodeClips = None

    FFMPEGExePath = None
    FFPROBEExePath = None

    PlaySoundSuccess = None
    DefaultSuccessSound = None

    PlaySoundError = None
    DefaultErrorSound = None

    # non-property vars
    LastEndTimeStamp = None

def get_data_prefix_game_name():
    return Data.PrefixGameName if Data.PrefixGameName is not None else False

def get_data_extension():
    return Data.Extension.replace(".", "")

def get_dontreencode_clips():
    return Data.DontReencodeClips if Data.DontReencodeClips is not None else False

def get_ffmpeg_exe_path():
    ffmpeg_path = Data.FFMPEGExePath
    if ffmpeg_path is None or ffmpeg_path == '' or ffmpeg_path == "DEFAULT":
        ffmpeg_path = os.path.join(script_path(), 'ffmpeg')
        if not os.path.exists(ffmpeg_path):
            ffmpeg_path = "ffmpeg"
    res = ffmpeg_path
    print("ffmpeg_path",res)
    return res

def get_ffprobe_exe_path():
    ffprobe_path = Data.FFPROBEExePath
    if ffprobe_path is None or ffprobe_path == '' or ffprobe_path == "DEFAULT":
        ffprobe_path = os.path.join(script_path(), 'ffprobe')
        if not os.path.exists(ffprobe_path):
            ffprobe_path = "ffprobe"
    res = ffprobe_path
    print("ffprobe_path",res)
    return res

def get_playsound_success_bool():
    return Data.PlaySoundSuccess if Data.PlaySoundSuccess is not None else False

def get_playsound_error_bool():
    return Data.PlaySoundError if Data.PlaySoundError is not None else False

def get_default_success_sound():
    default_success_sound = Data.DefaultSuccessSound
    if default_success_sound is None or default_success_sound == '' or default_success_sound == "DEFAULT":
        default_success_sound = os.path.join(script_path(), 'success.mp3')
        if not os.path.exists(default_success_sound):
            raise Exception("default success sound doesn't exist! (success.mp3 - in the script folder)")
    res = default_success_sound
    print("default_success_sound",res)
    return res

def get_default_error_sound():
    default_error_sound = Data.DefaultErrorSound
    if default_error_sound is None or default_error_sound == '' or default_error_sound == "DEFAULT":
        default_error_sound = os.path.join(script_path(), 'error.mp3')
        if not os.path.exists(default_error_sound):
            raise Exception("default error sound doesn't exist! (error.mp3 - in the script folder)")
    res = default_error_sound
    print("default_error_sound",res)
    return res

def get_video_metadata(video_path):
    """Get the metadata of a video file using ffprobe."""

    result = subprocess.run(
        [get_ffprobe_exe_path(), '-v', 'error', '-select_streams', 'v:0', '-show_entries', 'format=duration:format_tags=creation_time', 
         '-of', 'default=noprint_wrappers=1', video_path], 
        shell=False,
        stdout=subprocess.PIPE, 
        stderr=subprocess.STDOUT
    )
    output = result.stdout.decode('utf-8').strip().split('\n')
    
    duration = None
    creation_time = None

    for line in output:
        if line.startswith("duration="):
            duration = float(line.split('=')[1])
        if line.startswith("TAG:creation_time="):
            creation_time = line.split('=')[1]


    if creation_time:
        creation_time = datetime.strptime(creation_time, "%Y-%m-%dT%H:%M:%S.%fZ")

    if creation_time is None:
        creation_time = datetime.fromtimestamp(os.path.getmtime(video_path))

    return duration, creation_time

def cut_video(input_path, output_path, start_time, end_time):
    """Cut the video using ffmpeg."""

    os.makedirs(pathlib.Path(output_path).parent.resolve(), exist_ok=True)

    def onLine(line):
        pass
    return_code = 1
    if get_dontreencode_clips():
        return_code = startProcess([ 
            get_ffmpeg_exe_path(), 
            '-y', 
            '-ss', str(start_time), 
            '-to', str(end_time), 
            '-i', input_path,
            '-map', '0',
            '-c', 'copy', 
            output_path 
        ], onLine)
    else:
        return_code = startProcess([ 
            get_ffmpeg_exe_path(), 
            '-y',
            '-ss', str(start_time), 
            '-to', str(end_time), 
            '-map', '0',
            '-i', input_path, 
            output_path 
        ], onLine)

    if return_code != 0:
        print("ERROR!")

    return return_code


def find_previous_clip(target_clip, folder_path):
    target_clip_mtime = os.path.getmtime(target_clip)

    video_files = [ [ os.path.join(folder_path, f), os.path.getmtime(os.path.join(folder_path, f)) ] for f in os.listdir(folder_path)]

    if len(video_files) <= 1: return None

    video_files.sort(key=lambda x: x[1])  # Sort by creation date
    
    previous_clip = None
    for file in video_files:
        if file[1] >= target_clip_mtime:
            break

        previous_clip = file[0]

    if previous_clip == target_clip: return None

    return previous_clip


def decollide_clip(target_clip, folder_path):
    previous_clip = find_previous_clip(target_clip, folder_path)
    if previous_clip is None: return

    prev_duration, prev_modify_time = get_video_metadata(previous_clip)
    prev_start_time = prev_modify_time - timedelta(seconds=prev_duration)
    prev_end_time = prev_modify_time

    curr_duration, curr_modify_time = get_video_metadata(target_clip)
    curr_start_time = curr_modify_time - timedelta(seconds=curr_duration)
    curr_end_time = curr_modify_time

    if curr_start_time.timestamp() < prev_end_time.timestamp():
        overlap_start = prev_end_time - curr_start_time

        output_path = os.path.join(folder_path, f"{strip_ext(os.path.basename(target_clip))}_decollide_cut.{get_ext(target_clip)}")
        
        return_code = cut_video(target_clip, output_path, overlap_start.total_seconds(), curr_duration)

        if return_code == 0:
            os.remove(target_clip)
            print(f"Decollided clip '{target_clip}'.")
        else:
            print("error during clip decollision.")

def process_clip(event):
    try:
        target_clip = find_latest_file(Data.OutputDir, '/*')

        dir = os.path.dirname(target_clip)
        rawfile = os.path.basename(target_clip)
        title = get_window_title()
        newFolder = os.path.join(dir, title)

        name_prefix = f"{get_window_title()} " if get_data_prefix_game_name() else ""
        
        if not os.path.exists(newFolder):
            os.makedirs(newFolder)

        data_extension = get_data_extension()
        
        file =      f"{strip_ext(rawfile)}.{data_extension}"

        oldPath =   os.path.join(dir, file)
        newfile =   f"{name_prefix}{strip_ext(rawfile)}.{data_extension}"
        newPath =   os.path.join(newFolder, newfile)

        shutil.move(oldPath, newPath)
        print(f"moved '{oldPath}' to '{newPath}'")

        if(Data.DecollideClips):
            decollide_clip(newPath, newFolder)

        if(get_playsound_success_bool()):
            playsound.playsound(get_default_success_sound())
    except Exception as e:
        print(f"error during process_clip:{e}\n################\n", traceback.format_exc())

        if(get_playsound_error_bool()):
            playsound.playsound(get_default_error_sound())


def on_event(event):
    if event == S.OBS_FRONTEND_EVENT_RECORDING_STOPPED:
        print("Triggered when the recording stopped")
        process_clip(event)
    
    if event == S.OBS_FRONTEND_EVENT_REPLAY_BUFFER_SAVED:
        print("Triggered when the replay buffer saved")
        process_clip(event)


def get_window_title():
    """
    Get the title of the currently active/focused window.
    Works on Linux with Wayland (Hyprland, Sway, GNOME, KDE) and X11.
    """
    info = get_active_window_info()
    
    win_title = info['title']
    pid = info['pid']
    is_fullscreen = info['is_fullscreen']
    
    # Get executable name from PID
    exe = ''
    if pid > 0:
        try:
            p = psutil.Process(pid)
            exe = p.name()
        except (psutil.NoSuchProcess, psutil.AccessDenied):
            exe = ''

    desktopOverride = 0
    fullscreenOverride = 0

    try:
        with open(os.path.join(script_path(), 'DesktopOverride.cfg')) as dofile:
            if exe and exe in dofile.read():
                desktopOverride = 1
    except FileNotFoundError:
        pass
    
    try:
        with open(os.path.join(script_path(), 'FullscreenOverride.cfg')) as fsfile:
            if exe and exe in fsfile.read():
                fullscreenOverride = 1
    except FileNotFoundError:
        pass

    if win_title[:3] == 'OBS':
        title = "Manual Recording"
    elif desktopOverride == 1:
        title = win_title
    else:
        if is_fullscreen and fullscreenOverride == 0:
            title = win_title
        else:
            title = "Desktop"

    title = re.sub(r'[^0-9A-Za-z .\-]', '', title)
    title = title[:50]

    return title.strip()



def find_latest_file(folder_path, file_type):
    files = glob.glob(folder_path + file_type)
    max_file = max(files, key=os.path.getmtime)
    return max_file



def script_load(settings):
    S.obs_frontend_add_event_callback(on_event)



def script_update(settings):
    print("update script settings")

    Data.OutputDir = S.obs_data_get_string(settings, "outputdir")
    # Normalize path separators for Linux
    Data.OutputDir = Data.OutputDir.replace('\\', '/')
    Data.Extension = S.obs_data_get_string(settings, "extension")
    Data.ExtensionMask = '/*' + Data.Extension

    Data.PrefixGameName = S.obs_data_get_bool(settings, "prefixgamename")
    Data.DecollideClips = S.obs_data_get_bool(settings, "decollideclips")
    Data.DontReencodeClips = S.obs_data_get_bool(settings, "dontreencodeclips")

    ffmpeg_path = S.obs_data_get_string(settings, "ffmpegpath")
    if ffmpeg_path == "DEFAULT":
        ffmpeg_path = os.path.join(script_path(), 'ffmpeg')
        if not os.path.exists(ffmpeg_path):
            ffmpeg_path = "ffmpeg"
    Data.FFMPEGExePath = ffmpeg_path

    ffprobe_path = S.obs_data_get_string(settings, "ffprobepath")
    if ffprobe_path == "DEFAULT":
        ffprobe_path = os.path.join(script_path(), 'ffprobe')
        if not os.path.exists(ffprobe_path):
            ffprobe_path = "ffprobe"
    Data.FFPROBEExePath = ffprobe_path

    
    Data.PlaySoundSuccess = S.obs_data_get_bool(settings, "playsoundsuccess")

    default_success_sound = S.obs_data_get_string(settings, "defaultsuccesssound")
    if default_success_sound == "DEFAULT":
        default_success_sound = os.path.join(script_path(), 'success.mp3')
        if not os.path.exists(default_success_sound):
            raise Exception("default success sound doesn't exist! (success.mp3 - in the script folder)")
    Data.DefaultSuccessSound = default_success_sound


    Data.PlaySoundError = S.obs_data_get_bool(settings, "playsounderror")

    default_error_sound = S.obs_data_get_string(settings, "defaulterrorssound")
    if default_error_sound == "DEFAULT":
        default_error_sound = os.path.join(script_path(), 'error.mp3')
        if not os.path.exists(default_error_sound):
            raise Exception("default error sound doesn't exist! (error.mp3 - in the script folder)")
    Data.DefaultErrorSound = default_error_sound


def script_description():
    desc = (f"<h3>OBS Recording Organizer Upgraded <br> v.{version.get_version()}</h3>"
             "<hr>"
             "Renames and organizes recordings into subfolders similar to NVIDIA ShadowPlay (<i>NVIDIA GeForce Experience</i>).<br><br>"
             "<b>🐧 Linux (Wayland/X11) port</b><br>"
             "<small>Supports: Hyprland, Sway, GNOME, KDE, and X11</small><br><br>"
             "<small><a href='https://github.com/EnKhayzo/OBS-Recordings-Organizer'>GitHub repo link</a></small><br><br>"
             "<small>Original author:</small> <a href='https://obsproject.com/forum/resources/obs-recordings-organizer.1707/'><b>francedv23</b></a><br>"
             "<small>Updated by:</small> <b>enkhayzo</b><br>"
             "<small>Linux port by:</small> <b>community</b><br><br>"
             "<small>Markup description by </small> <a href='https://github.com/padiix/OBS-Recordings-Organizer'><b>padii</b></a><small>'s fork (thank you)</small><br><br>"
             "<small>❤️ If you wish to support my work, i have a <a href='https://ko-fi.com/enkhayzo'>Ko-fi</a> page, thank you💕</small><br><br>"
             "<h4>Settings:</h4>")
    return desc


def script_properties():
    props = S.obs_properties_create()

    S.obs_properties_add_path(
        props, 
        "outputdir", 
        "Recordings folder", 
        S.OBS_PATH_DIRECTORY,
        None, 
        str(Path.home())
    )

    S.obs_properties_add_text(
        props,
        "extension",
        "File extension",
        S.OBS_TEXT_DEFAULT
    )

    S.obs_properties_add_bool(
        props,
        "prefixgamename",
        "Add game name as prefix",
    )

    decollide_bool = S.obs_properties_add_bool(
        props,
        "decollideclips",
        "Decollide Saved clips",
    )
    S.obs_property_set_long_description(decollide_bool, "makes sure saved recordings don't 'overlap' (i.e the previous clip shares some footage with the current clip, it's the default behaviour for Replay Buffer), this setting cuts the clip using ffmpeg to cut and ffprobe to get the video duration/s. If you don't check the option 'Don't Re-Encode when Decolliding' the decollided clip will loose some quality upon re-encoding.")

    dont_reencode_bool = S.obs_properties_add_bool(
        props,
        "dontreencodeclips",
        "Don't Re-Encode when Decolliding",
    )
    S.obs_property_set_long_description(dont_reencode_bool, "makes sure that ffmpeg doesn't re-encode the clip when decolliding it, thus keeping the clip's original quality. The caveat is that the cut is not precise: either a few extra frames are cut or they are kept, depending on where the nearest encoding keyframe lands in the clip relative to the cut timestamp.")

    ffmpeg_exe_path = S.obs_properties_add_path(
        props, 
        "ffmpegpath", 
        "Custom ffmpeg path", 
        S.OBS_PATH_FILE,
        "*", 
        str("DEFAULT")
    )
    S.obs_property_set_long_description(ffmpeg_exe_path, "if not set, it looks for 'ffmpeg' in the script's folder; otherwise it checks for ffmpeg in your system PATH")

    ffprobe_exe_path = S.obs_properties_add_path(
        props, 
        "ffprobepath", 
        "Custom ffprobe path", 
        S.OBS_PATH_FILE,
        "*", 
        str("DEFAULT")
    )
    S.obs_property_set_long_description(ffprobe_exe_path, "if not set, it looks for 'ffprobe' in the script's folder; otherwise it checks for ffprobe in your system PATH")



    S.obs_properties_add_bool(
        props,
        "playsoundsuccess",
        "Play a sound when saving a clip",
    )

    default_success_sound = S.obs_properties_add_path(
        props, 
        "defaultsuccesssound", 
        "Custom Saved Clip Sound", 
        S.OBS_PATH_FILE,
        "*", 
        str("DEFAULT")
    )
    S.obs_property_set_long_description(default_success_sound, "the path of the sound file that will be played when you save a clip (through replay buffer or normal recording)")


    S.obs_properties_add_bool(
        props,
        "playsounderror",
        "Play a sound on error (during saving)",
    )

    default_error_sound = S.obs_properties_add_path(
        props, 
        "defaulterrorsound", 
        "Custom Clip Error Sound", 
        S.OBS_PATH_FILE,
        "*", 
        str("DEFAULT")
    )
    S.obs_property_set_long_description(default_error_sound, "the path of the sound file that will be played when an error occurs during saving")


    return props