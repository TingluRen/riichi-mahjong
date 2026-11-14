Windows EXE Launcher — Setup Guide

BUILD THE EXECUTABLE

Copy the launcher files into your existing project folder, alongside server.py.
Keep your existing game files, static folder, and local development folders.

Requirements:
- Windows
- 64-bit Python 3.12 recommended
- Internet access during the build to download dependencies

Open PowerShell in the project folder and run:

cd F:\software-engineer-projects\mahjong
powershell -NoProfile -ExecutionPolicy Bypass -File .\build_exe.ps1

The script creates a separate .venv-build environment.
It does not modify your existing .venv environment.
ExecutionPolicy Bypass applies only to this PowerShell process.

If necessary, specify the full path to your Python 3.12 executable:

powershell -NoProfile -ExecutionPolicy Bypass -File .\build_exe.ps1 -Python "C:\path\to\Python312\python.exe"

The executable will be created at:

dist\RiichiMahjong.exe


RUN THE GAME

Double-click RiichiMahjong.exe.
The launcher starts a local server and opens your default browser.
Players do not need to install Python or connect to Render.

Keep the launcher window open while playing.
To exit, press Ctrl+C in the launcher window.
Closing the browser alone does not stop the server.

The launcher automatically selects an available local port.
The local URL may change between launches.
Do not use this local URL as a public demo link.

Starting a second instance displays an “already running” message.
The first launch may take a little longer because the executable
extracts its bundled files before starting.


SAVED GAMES AND LOGS

Saved games:

%LOCALAPPDATA%\TingluRen\RiichiMahjong\saved_game.json

Log file:

%LOCALAPPDATA%\TingluRen\RiichiMahjong\launcher.log

Desktop saves are separate from Render browser sessions and the
original project's data folder. Existing saves are not imported
automatically.

Replacing the executable does not overwrite the desktop save.
To reset progress manually, exit the game, back up the save file,
and move it out of the save folder.


RUN FROM SOURCE

After installing requirements.txt in your development environment:

.\.venv\Scripts\python.exe desktop_launcher.py


GIT IGNORE RULES

Append these lines to your existing .gitignore:

.venv-build/
build/
dist/
*.spec


RENDER COMPATIBILITY

Keep the Render start command unchanged:

uvicorn web_server:app --host 0.0.0.0 --port $PORT --workers 1

The desktop launcher runs independently of Render.
Both versions use the same game code but maintain separate saves.

After changing game code, push the changes to update Render and
rebuild the executable to update the desktop version.
Previously distributed executables do not update automatically.


WINDOWS VERIFICATION

This package contains launcher source code and a build script,
not a prebuilt Windows executable.

Local server startup, save restoration, and duplicate-instance
protection were checked on Linux. Windows-specific behavior and
the final executable still require testing on Windows.

Before distributing the executable, verify:
- Automatic browser opening
- Normal gameplay
- Save restoration after restarting
- Duplicate-instance protection
- Startup after moving the executable to another folder
- Offline gameplay
- Clean shutdown with Ctrl+C