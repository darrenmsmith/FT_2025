# PowerShell Script to Setup SSH for Device 0 Connection
# This script generates SSH keys and configures connection to Device 0

Write-Host "=== FT_2025 SSH Setup for Device 0 ===" -ForegroundColor Cyan

# Check if OpenSSH client is available
$sshClient = Get-Command ssh -ErrorAction SilentlyContinue
if (-not $sshClient) {
    Write-Host "❌ SSH client not found. Installing OpenSSH..." -ForegroundColor Red
    
    # Try to install OpenSSH client (requires admin rights)
    try {
        Add-WindowsCapability -Online -Name OpenSSH.Client~~~~0.0.1.0
        Write-Host "✅ OpenSSH client installed" -ForegroundColor Green
    }
    catch {
        Write-Host "❌ Failed to install OpenSSH. Please install manually:" -ForegroundColor Red
        Write-Host "   Settings → Apps → Optional Features → Add Feature → OpenSSH Client" -ForegroundColor Yellow
        Read-Host "Press Enter after installing OpenSSH Client"
    }
}

# Create .ssh directory if it doesn't exist
$sshDir = "$env:USERPROFILE\.ssh"
if (-not (Test-Path $sshDir)) {
    New-Item -ItemType Directory -Path $sshDir -Force
    Write-Host "✅ Created .ssh directory" -ForegroundColor Green
}

# Check if SSH key already exists
$keyPath = "$sshDir\id_rsa"
if (Test-Path $keyPath) {
    Write-Host "✅ SSH key already exists at $keyPath" -ForegroundColor Green
} else {
    Write-Host "🔑 Generating SSH key pair..." -ForegroundColor Yellow
    
    # Generate SSH key
    $email = Read-Host "Enter your email for SSH key (press Enter for default)"
    if (-not $email) {
        $email = "$env:USERNAME@ft2025"
    }
    
    ssh-keygen -t rsa -b 4096 -C $email -f $keyPath -N '""'
    
    if (Test-Path $keyPath) {
        Write-Host "✅ SSH key generated successfully" -ForegroundColor Green
    } else {
        Write-Host "❌ Failed to generate SSH key" -ForegroundColor Red
        exit 1
    }
}

# Create SSH config if it doesn't exist
$configPath = "$sshDir\config"
$configContent = @"
# FT_2025 Field Trainer Device 0
Host device0
    HostName 192.168.99.100
    User pi
    IdentityFile ~/.ssh/id_rsa
    StrictHostKeyChecking no
    UserKnownHostsFile /dev/null

# Alternative connection methods
Host device0-direct
    HostName 192.168.99.100
    User pi
    IdentityFile ~/.ssh/id_rsa
    Port 22

"@

if (Test-Path $configPath) {
    $existingConfig = Get-Content $configPath -Raw
    if ($existingConfig -notmatch "Host device0") {
        Add-Content -Path $configPath -Value "`n$configContent"
        Write-Host "✅ Added Device 0 configuration to existing SSH config" -ForegroundColor Green
    } else {
        Write-Host "✅ Device 0 already configured in SSH config" -ForegroundColor Green
    }
} else {
    Set-Content -Path $configPath -Value $configContent
    Write-Host "✅ Created SSH config with Device 0 settings" -ForegroundColor Green
}

# Get the public key content
$pubKeyPath = "$keyPath.pub"
if (Test-Path $pubKeyPath) {
    $pubKey = Get-Content $pubKeyPath
    Write-Host "`n📋 Your public key:" -ForegroundColor Cyan
    Write-Host $pubKey -ForegroundColor White
    
    # Copy to clipboard if possible
    try {
        $pubKey | Set-Clipboard
        Write-Host "✅ Public key copied to clipboard" -ForegroundColor Green
    } catch {
        Write-Host "⚠️  Could not copy to clipboard automatically" -ForegroundColor Yellow
    }
} else {
    Write-Host "❌ Public key file not found" -ForegroundColor Red
    exit 1
}

Write-Host "`n🚀 Next Steps:" -ForegroundColor Cyan
Write-Host "1. Connect to Device 0 and add your public key:" -ForegroundColor White
Write-Host "   ssh pi@192.168.99.100" -ForegroundColor Yellow
Write-Host "   mkdir -p ~/.ssh" -ForegroundColor Yellow
Write-Host "   echo '$pubKey' >> ~/.ssh/authorized_keys" -ForegroundColor Yellow
Write-Host "   chmod 600 ~/.ssh/authorized_keys" -ForegroundColor Yellow
Write-Host "   exit" -ForegroundColor Yellow

Write-Host "`n2. Test the connection:" -ForegroundColor White
Write-Host "   ssh device0" -ForegroundColor Yellow

Write-Host "`n3. If connection works, you can use VS Code tasks:" -ForegroundColor White
Write-Host "   - Deploy to Device 0" -ForegroundColor Yellow
Write-Host "   - Check Device 0 Status" -ForegroundColor Yellow
Write-Host "   - View Device 0 Logs" -ForegroundColor Yellow

# Ask if user wants to test connection now
$testConnection = Read-Host "`nWould you like to test the SSH connection now? (y/N)"
if ($testConnection -eq "y" -or $testConnection -eq "Y") {
    Write-Host "`n🔗 Testing SSH connection to Device 0..." -ForegroundColor Yellow
    
    try {
        ssh -o ConnectTimeout=10 device0 "echo 'SSH connection successful!'"
        Write-Host "✅ SSH connection to Device 0 working!" -ForegroundColor Green
    } catch {
        Write-Host "❌ SSH connection failed. Please check:" -ForegroundColor Red
        Write-Host "   - Device 0 is powered on and connected to network" -ForegroundColor Yellow
        Write-Host "   - IP address 192.168.99.100 is correct" -ForegroundColor Yellow
        Write-Host "   - SSH service is running on Device 0" -ForegroundColor Yellow
        Write-Host "   - Your public key is added to Device 0 authorized_keys" -ForegroundColor Yellow
    }
}

Write-Host "`n=== SSH Setup Complete ===" -ForegroundColor Cyan
Write-Host "📁 SSH files location: $sshDir" -ForegroundColor White
Write-Host "🔧 You can now use VS Code tasks to manage Device 0" -ForegroundColor White
Write-Host "📖 See WINDOWS_DEVELOPMENT.md for detailed usage instructions" -ForegroundColor White

Read-Host "`nPress Enter to continue"
