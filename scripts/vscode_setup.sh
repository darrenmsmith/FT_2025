#!/bin/bash
set -e

# VS Code Setup Script for FT_2025 Field Trainer Project
# This script configures VS Code for optimal Field Trainer development

echo "=== FT_2025 Field Trainer VS Code Setup ==="

# Check if VS Code is installed
if ! command -v code &> /dev/null; then
    echo "❌ VS Code not found. Please install VS Code first:"
    echo "   https://code.visualstudio.com/"
    exit 1
fi

# Check if we're in the right directory
if [ ! -f "field_trainer_main.py" ]; then
    echo "❌ Please run this script from the FT_2025 repository root directory"
    exit 1
fi

echo "✅ Found FT_2025 project directory"

# Create .vscode directory if it doesn't exist
mkdir -p .vscode

# Create VS Code configuration files
echo "📁 Creating VS Code configuration files..."

# Copy settings.json (you need to copy the content from the artifact)
cat > .vscode/settings.json << 'EOF'
{
    "python.defaultInterpreterPath": "./venv/bin/python",
    "python.linting.enabled": true,
    "python.linting.flake8Enabled": true,
    "python.linting.pylintEnabled": false,
    "python.formatting.provider": "black",
    "python.formatting.blackArgs": ["--line-length=88"],
    "python.sortImports.args": ["--profile", "black"],
    
    "files.exclude": {
        "**/__pycache__": true,
        "**/*.pyc": true,
        "**/venv": true,
        "**/env": true,
        "**/.pytest_cache": true,
        "**/data/logs": true,
        "**/data/backups": true,
        "**/*.log": true
    },
    
    "editor.rulers": [88],
    "editor.formatOnSave": true,
    "editor.codeActionsOnSave": {
        "source.organizeImports": true
    },
    "editor.insertSpaces": true,
    "editor.tabSize": 4,
    
    "git.autofetch": true,
    "git.enableSmartCommit": true,
    "git.confirmSync": false,
    
    "files.associations": {
        "*.service": "ini",
        "*.conf": "ini",
        "courses.json": "json"
    },
    
    "terminal.integrated.env.linux": {
        "PYTHONPATH": "${workspaceFolder}"
    },
    
    "python.testing.pytestEnabled": true,
    "python.testing.unittestEnabled": false,
    "python.testing.pytestArgs": ["tests"],
    
    "files.autoSave": "afterDelay",
    "files.autoSaveDelay": 1000,
    
    "editor.bracketPairColorization.enabled": true,
    "editor.guides.bracketPairs": true,
    
    "search.exclude": {
        "**/data/logs": true,
        "**/data/backups": true,
        "**/*.log": true,
        "**/venv": true,
        "**/env": true
    }
}
EOF

echo "✅ Created .vscode/settings.json"

# Install essential VS Code extensions
echo "🔌 Installing essential VS Code extensions..."

# Core Python development
code --install-extension ms-python.python
code --install-extension ms-python.flake8
code --install-extension ms-python.black-formatter

# Git and GitHub
code --install-extension github.vscode-pull-request-github
code --install-extension eamodio.gitlens

# Remote development
code --install-extension ms-vscode-remote.remote-ssh

# Web development (for Flask interface)
code --install-extension ms-vscode.vscode-html-css-json

# Productivity
code --install-extension aaron-bond.better-comments
code --install-extension alefragnani.bookmarks

echo "✅ Essential extensions installed"

# Set up Python virtual environment
echo "🐍 Setting up Python virtual environment..."

if [ ! -d "venv" ]; then
    python3 -m venv venv
    echo "✅ Created virtual environment"
else
    echo "✅ Virtual environment already exists"
fi

# Activate virtual environment and install dependencies
echo "📦 Installing Python dependencies..."
source venv/bin/activate
pip install --upgrade pip
pip install -r requirements.txt

echo "✅ Dependencies installed"

# Create a simple test file to verify setup
if [ ! -f "tests/test_basic.py" ]; then
    mkdir -p tests
    cat > tests/test_basic.py << 'EOF'
"""Basic tests for Field Trainer"""
import sys
import os

# Add parent directory to path for imports
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

def test_imports():
    """Test that core modules can be imported"""
    try:
        import field_trainer_core
        import field_trainer_web
        import field_trainer_main
        assert True
    except ImportError as e:
        assert False, f"Import failed: {e}"

def test_registry_creation():
    """Test that Registry can be created"""
    from field_trainer_core import Registry
    registry = Registry()
    assert registry is not None
    assert hasattr(registry, 'nodes')
    assert hasattr(registry, 'log')

if __name__ == "__main__":
    test_imports()
    test_registry_creation()
    print("✅ All basic tests passed!")
EOF
    echo "✅ Created basic test file"
fi

# Create .env.example for environment variables
if [ ! -f ".env.example" ]; then
    cat > .env.example << 'EOF'
# Field Trainer Environment Variables
# Copy this file to .env and customize for your environment

# Development settings
FLASK_ENV=development
FLASK_DEBUG=1

# Device 0 connection
DEVICE_0_IP=192.168.99.100
DEVICE_0_USER=pi

# Optional: Authentication (future use)
# DEVICE_AUTH_TOKEN=your-secret-token
# EMAIL_PASSWORD=your-email-password

# Optional: Logging
# LOG_LEVEL=DEBUG
EOF
    echo "✅ Created .env.example"
fi

# Add useful VS Code workspace snippets
mkdir -p .vscode
cat > .vscode/ft2025.code-snippets << 'EOF'
{
    "Field Trainer Log": {
        "prefix": "ftlog",
        "body": [
            "REGISTRY.log(\"$1\", level=\"$2\", source=\"$3\")"
        ],
        "description": "Field Trainer logging statement"
    },
    "Field Trainer Route": {
        "prefix": "ftroute",
        "body": [
            "@app.route('/$1', methods=['$2'])",
            "def $3():",
            "    \"\"\"$4\"\"\"",
            "    try:",
            "        $5",
            "        return jsonify({\"success\": True})",
            "    except Exception as e:",
            "        REGISTRY.log(f\"$3 error: {e}\", level=\"error\")",
            "        return jsonify({\"success\": False, \"error\": str(e)}), 500"
        ],
        "description": "Field Trainer Flask route with error handling"
    },
    "Field Trainer Test": {
        "prefix": "fttest",
        "body": [
            "def test_$1():",
            "    \"\"\"Test $2\"\"\"",
            "    # Arrange",
            "    $3",
            "    ",
            "    # Act",
            "    $4",
            "    ",
            "    # Assert",
            "    assert $5"
        ],
        "description": "Field Trainer test function template"
    }
}
EOF

echo "✅ Created VS Code snippets"

# Create SSH config template
mkdir -p ~/.ssh
if [ ! -f ~/.ssh/config ] || ! grep -q "Host device0" ~/.ssh/config; then
    echo "" >> ~/.ssh/config
    echo "# Field Trainer Device 0" >> ~/.ssh/config
    echo "Host device0" >> ~/.ssh/config
    echo "    HostName 192.168.99.100" >> ~/.ssh/config
    echo "    User pi" >> ~/.ssh/config
    echo "    IdentityFile ~/.ssh/id_rsa" >> ~/.ssh/config
    echo "✅ Added Device 0 SSH configuration"
fi

# Test the setup
echo "🧪 Testing setup..."

# Test Python imports
if python3 -c "import field_trainer_core, field_trainer_web, field_trainer_main; print('✅ Python imports successful')"; then
    echo "✅ Python modules import correctly"
else
    echo "⚠️  Python import test failed - check dependencies"
fi

# Test VS Code can open the project
echo "🚀 Opening VS Code..."
code .

echo ""
echo "=== Setup Complete! ==="
echo ""
echo "🎉 Your FT_2025 project is now configured for VS Code development!"
echo ""
echo "📋 What's been set up:"
echo "   ✅ VS Code settings optimized for Field Trainer development"
echo "   ✅ Essential extensions installed"
echo "   ✅ Python virtual environment with dependencies"
echo "   ✅ Code snippets for faster development"
echo "   ✅ SSH configuration for Device 0"
echo "   ✅ Basic test structure"
echo ""
echo "🎯 Next steps:"
echo "   1. VS Code should now be open with your project"
echo "   2. Select Python interpreter: Ctrl+Shift+P → 'Python: Select Interpreter' → Choose './venv/bin/python'"
echo "   3. Try debugging: F5 → 'Field Trainer - Full System'"
echo "   4. Deploy to Device 0: Ctrl+Shift+P → 'Tasks: Run Task' → 'Deploy to Device 0'"
echo ""
echo "📖 Read VSCODE_DEVELOPMENT.md for detailed usage guide"
echo ""
echo "Happy coding! 🚀"
