@echo off
REM VS Code Setup Script for FT_2025 Field Trainer Project (Windows)
REM This script configures VS Code for optimal Field Trainer development on Windows

echo === FT_2025 Field Trainer VS Code Setup (Windows) ===

REM Check if VS Code is installed
where code >nul 2>nul
if %errorlevel% neq 0 (
    echo ❌ VS Code not found. Please install VS Code first:
    echo    https://code.visualstudio.com/
    pause
    exit /b 1
)

REM Check if we're in the right directory
if not exist "field_trainer_main.py" (
    echo ❌ Please run this script from the FT_2025 repository root directory
    pause
    exit /b 1
)

echo ✅ Found FT_2025 project directory

REM Create .vscode directory if it doesn't exist
if not exist ".vscode" mkdir .vscode

REM Create VS Code configuration files
echo 📁 Creating VS Code configuration files...

REM Create settings.json
echo Creating .vscode\settings.json...
(
echo {
echo     "python.defaultInterpreterPath": "./venv/Scripts/python.exe",
echo     "python.linting.enabled": true,
echo     "python.linting.flake8Enabled": true,
echo     "python.linting.pylintEnabled": false,
echo     "python.formatting.provider": "black",
echo     "python.formatting.blackArgs": ["--line-length=88"],
echo     "python.sortImports.args": ["--profile", "black"],
echo     
echo     "files.exclude": {
echo         "**/__pycache__": true,
echo         "**/*.pyc": true,
echo         "**/venv": true,
echo         "**/env": true,
echo         "**/.pytest_cache": true,
echo         "**/data/logs": true,
echo         "**/data/backups": true,
echo         "**/*.log": true
echo     },
echo     
echo     "editor.rulers": [88],
echo     "editor.formatOnSave": true,
echo     "editor.codeActionsOnSave": {
echo         "source.organizeImports": true
echo     },
echo     "editor.insertSpaces": true,
echo     "editor.tabSize": 4,
echo     
echo     "git.autofetch": true,
echo     "git.enableSmartCommit": true,
echo     "git.confirmSync": false,
echo     
echo     "files.associations": {
echo         "*.service": "ini",
echo         "*.conf": "ini",
echo         "courses.json": "json"
echo     },
echo     
echo     "terminal.integrated.env.windows": {
echo         "PYTHONPATH": "${workspaceFolder}"
echo     },
echo     
echo     "python.testing.pytestEnabled": true,
echo     "python.testing.unittestEnabled": false,
echo     "python.testing.pytestArgs": ["tests"],
echo     
echo     "files.autoSave": "afterDelay",
echo     "files.autoSaveDelay": 1000,
echo     
echo     "editor.bracketPairColorization.enabled": true,
echo     "editor.guides.bracketPairs": true,
echo     
echo     "search.exclude": {
echo         "**/data/logs": true,
echo         "**/data/backups": true,
echo         "**/*.log": true,
echo         "**/venv": true,
echo         "**/env": true
echo     },
echo     
echo     "terminal.integrated.defaultProfile.windows": "PowerShell"
echo }
) > .vscode\settings.json

echo ✅ Created .vscode\settings.json

REM Install essential VS Code extensions
echo 🔌 Installing essential VS Code extensions...

REM Core Python development
code --install-extension ms-python.python
code --install-extension ms-python.flake8
code --install-extension ms-python.black-formatter

REM Git and GitHub
code --install-extension github.vscode-pull-request-github
code --install-extension eamodio.gitlens

REM Remote development
code --install-extension ms-vscode-remote.remote-ssh

REM Web development (for Flask interface)
code --install-extension ms-vscode.vscode-html-css-json

REM Productivity
code --install-extension aaron-bond.better-comments
code --install-extension alefragnani.bookmarks

echo ✅ Essential extensions installed

REM Set up Python virtual environment
echo 🐍 Setting up Python virtual environment...

if not exist "venv" (
    python -m venv venv
    echo ✅ Created virtual environment
) else (
    echo ✅ Virtual environment already exists
)

REM Activate virtual environment and install dependencies
echo 📦 Installing Python dependencies...
call venv\Scripts\activate.bat
python -m pip install --upgrade pip
pip install -r requirements.txt

echo ✅ Dependencies installed

REM Create a simple test file to verify setup
if not exist "tests" mkdir tests
if not exist "tests\test_basic.py" (
echo Creating basic test file...
(
echo """Basic tests for Field Trainer"""
echo import sys
echo import os
echo 
echo # Add parent directory to path for imports
echo sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__^^^^)^^^)^^^)
echo 
echo def test_imports(^^^^):
echo     """Test that core modules can be imported"""
echo     try:
echo         import field_trainer_core
echo         import field_trainer_web
echo         import field_trainer_main
echo         assert True
echo     except ImportError as e:
echo         assert False, f"Import failed: {e}"
echo 
echo def test_registry_creation(^^^^):
echo     """Test that Registry can be created"""
echo     from field_trainer_core import Registry
echo     registry = Registry(^^^^)
echo     assert registry is not None
echo     assert hasattr(registry, 'nodes'^^^^)
echo     assert hasattr(registry, 'log'^^^^)
echo 
echo if __name__ == "__main__":
echo     test_imports(^^^^)
echo     test_registry_creation(^^^^)
echo     print("✅ All basic tests passed!"^^^^)
) > tests\test_basic.py
echo ✅ Created basic test file
)

REM Create .env.example for environment variables
if not exist ".env.example" (
echo Creating .env.example...
(
echo # Field Trainer Environment Variables
echo # Copy this file to .env and customize for your environment
echo 
echo # Development settings
echo FLASK_ENV=development
echo FLASK_DEBUG=1
echo 
echo # Device 0 connection
echo DEVICE_0_IP=192.168.99.100
echo DEVICE_0_USER=pi
echo 
echo # Optional: Authentication (future use^^^^)
echo # DEVICE_AUTH_TOKEN=your-secret-token
echo # EMAIL_PASSWORD=your-email-password
echo 
echo # Optional: Logging
echo # LOG_LEVEL=DEBUG
) > .env.example
echo ✅ Created .env.example
)

REM Test the setup
echo 🧪 Testing setup...

REM Test Python imports
python -c "import field_trainer_core, field_trainer_web, field_trainer_main; print('✅ Python imports successful')" 2>nul
if %errorlevel% equ 0 (
    echo ✅ Python modules import correctly
) else (
    echo ⚠️  Python import test failed - check dependencies
)

REM Open VS Code
echo 🚀 Opening VS Code...
code .

echo.
echo === Setup Complete! ===
echo.
echo 🎉 Your FT_2025 project is now configured for VS Code development on Windows!
echo.
echo 📋 What's been set up:
echo    ✅ VS Code settings optimized for Field Trainer development
echo    ✅ Essential extensions installed
echo    ✅ Python virtual environment with dependencies
echo    ✅ Basic test structure
echo.
echo 🎯 Next steps:
echo    1. VS Code should now be open with your project
echo    2. Select Python interpreter: Ctrl+Shift+P → 'Python: Select Interpreter' → Choose '.\venv\Scripts\python.exe'
echo    3. Try debugging: F5 → 'Field Trainer - Full System'
echo    4. Set up SSH for Device 0 deployment (see WINDOWS_DEVELOPMENT.md^^^^)
echo.
echo 📖 Read WINDOWS_DEVELOPMENT.md for detailed Windows-specific usage guide
echo.
echo Happy coding! 🚀
pause
