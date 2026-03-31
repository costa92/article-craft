#!/usr/bin/env python3
"""
Auto-detect and install missing dependencies for article-craft skill
Includes Python packages and Node.js tools (picgo)
"""
import subprocess
import sys
import os
import shutil

def check_command_exists(cmd):
    """Check if a command exists in PATH"""
    return shutil.which(cmd) is not None

def check_python_dependencies():
    """Check if required Python packages are installed, install if missing"""

    required_packages = {
        'google.genai': 'google-genai>=0.1.0',
        'PIL': 'Pillow>=10.0.0',
        'dotenv': 'python-dotenv>=1.0.0',
        'markdown': 'markdown>=3.5.0',
        'premailer': 'premailer>=3.10.0',
        'pygments': 'Pygments>=2.17.0'
    }

    missing_packages = []

    print("🔍 Checking Python dependencies...")

    # Check each required package
    for import_name, pip_name in required_packages.items():
        try:
            if import_name == 'google.genai':
                from google import genai
            elif import_name == 'PIL':
                import PIL
            elif import_name == 'dotenv':
                import dotenv
            print(f"  ✅ {pip_name.split('>=')[0]} is installed")
        except ImportError:
            print(f"  ❌ {pip_name.split('>=')[0]} is missing")
            missing_packages.append(pip_name)

    # Install missing packages
    if missing_packages:
        print(f"\n📦 Installing {len(missing_packages)} missing Python package(s)...")

        # Get the skill directory
        skill_dir = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
        requirements_file = os.path.join(skill_dir, 'requirements.txt')

        try:
            subprocess.check_call([
                sys.executable, '-m', 'pip', 'install', '-q',
                '-r', requirements_file
            ])
            print("✅ All Python dependencies installed successfully!\n")
            return True
        except subprocess.CalledProcessError as e:
            print(f"❌ Failed to install Python dependencies: {e}")
            print(f"Please manually run: pip install -r {requirements_file}")
            return False
    else:
        print("✅ All Python dependencies are already installed!\n")
        return True

def check_and_install_picgo():
    """Check if picgo is installed, auto-install if npm is available"""

    print("🔍 Checking PicGo CLI...")

    # Check if picgo is already installed
    if check_command_exists('picgo'):
        try:
            result = subprocess.run(
                ['picgo', '--version'],
                capture_output=True,
                text=True,
                timeout=5
            )
            if result.returncode == 0:
                version = result.stdout.strip()
                print(f"  ✅ PicGo CLI is installed (version {version})\n")
                return True
        except (subprocess.CalledProcessError, subprocess.TimeoutExpired, FileNotFoundError, OSError):
            pass

    print("  ❌ PicGo CLI is not installed")

    # Check if npm is available
    if not check_command_exists('npm'):
        print("\n⚠️  npm is not available - cannot auto-install picgo")
        print("📝 Manual installation instructions:")
        print("   1. Install Node.js and npm from https://nodejs.org/")
        print("   2. Run: npm install -g picgo")
        print("   3. Configure picgo: picgo set uploader\n")
        return False

    # Check if node is available
    if not check_command_exists('node'):
        print("\n⚠️  Node.js is not available - cannot auto-install picgo")
        print("📝 Please install Node.js from https://nodejs.org/\n")
        return False

    # Auto-install picgo
    print("\n📦 npm is available - auto-installing PicGo CLI...")
    print("   (This may take 10-30 seconds)")

    try:
        result = subprocess.run(
            ['npm', 'install', '-g', 'picgo'],
            capture_output=True,
            text=True,
            timeout=120
        )

        if result.returncode == 0:
            print("✅ PicGo CLI installed successfully!")

            # Verify installation by directly running picgo command
            # Note: Don't rely on check_command_exists() as PATH may not be refreshed
            try:
                version_result = subprocess.run(
                    ['picgo', '--version'],
                    capture_output=True,
                    text=True,
                    timeout=5
                )
                if version_result.returncode == 0:
                    version = version_result.stdout.strip()
                    print(f"✅ Verified: PicGo CLI version {version}")
                    print("\n📝 Next step: Configure picgo with your image hosting service")
                    print("   Run: picgo set uploader")
                    print("   Supported: GitHub, Aliyun OSS, Tencent COS, Qiniu, SM.MS, etc.\n")
                    return True
                else:
                    print("⚠️  Installation completed but verification failed")
                    print("   You may need to restart your terminal or reload your shell\n")
                    return False
            except (subprocess.CalledProcessError, FileNotFoundError, subprocess.TimeoutExpired):
                # If direct command fails, try to get npm bin path
                try:
                    npm_bin_result = subprocess.run(
                        ['npm', 'bin', '-g'],
                        capture_output=True,
                        text=True,
                        timeout=5
                    )
                    if npm_bin_result.returncode == 0:
                        npm_bin = npm_bin_result.stdout.strip()
                        picgo_path = os.path.join(npm_bin, 'picgo')
                        print(f"ℹ️  PicGo installed at: {picgo_path}")
                        print("   You may need to restart your terminal or add to PATH\n")
                        return True
                except:
                    pass

                print("⚠️  Installation completed but picgo command not found in PATH")
                print("   You may need to restart your terminal or reload your shell\n")
                return False
        else:
            print(f"❌ Failed to install PicGo CLI")
            if result.stderr:
                print(f"   Error: {result.stderr[:200]}")
            print("\n📝 Manual installation:")
            print("   Run: npm install -g picgo\n")
            return False

    except subprocess.TimeoutExpired:
        print("❌ Installation timeout (120s)")
        print("📝 Please try manually: npm install -g picgo\n")
        return False
    except Exception as e:
        print(f"❌ Installation failed: {str(e)}")
        print("📝 Please try manually: npm install -g picgo\n")
        return False

def check_gemini_api_key():
    """Check if GEMINI_API_KEY is configured"""

    print("🔍 Checking Gemini API Key...")

    # Check environment variable
    if os.getenv("GEMINI_API_KEY"):
        print("  ✅ GEMINI_API_KEY is set in environment\n")
        return True

    # Check ~/.claude/env.json (unified config)
    env_json = os.path.expanduser("~/.claude/env.json")
    if os.path.exists(env_json):
        try:
            import json
            with open(env_json) as f:
                data = json.load(f)
            val = data.get("gemini_api_key", "")
            if val and not str(val).startswith("your-"):
                print(f"  ✅ GEMINI_API_KEY is configured in {env_json}\n")
                return True
        except Exception:
            pass

    # Check legacy .env file
    env_file = os.path.expanduser("~/.nanobanana.env")
    if os.path.exists(env_file):
        with open(env_file, 'r') as f:
            content = f.read()
            if 'GEMINI_API_KEY=' in content and not content.split('GEMINI_API_KEY=')[1].split('\n')[0].strip() == '':
                print(f"  ✅ GEMINI_API_KEY is configured in {env_file} (legacy)\n")
                return True

    print(f"  ❌ GEMINI_API_KEY is not configured")
    print(f"\n📝 Setup instructions:")
    print(f"   1. Get your API key from: https://aistudio.google.com/app/apikey")
    print(f"   2. Edit ~/.claude/env.json and set gemini_api_key (recommended)")
    print(f"      Template: cp ~/.claude/env.example.json ~/.claude/env.json")
    print(f"   3. Or: export GEMINI_API_KEY=your_api_key_here\n")
    return False

def main():
    """Main dependency check and installation"""

    print("=" * 70)
    print("🚀 article-craft Dependency Check")
    print("=" * 70)
    print()

    all_ok = True

    # 1. Check Python dependencies
    if not check_python_dependencies():
        all_ok = False

    # 2. Check and install PicGo
    if not check_and_install_picgo():
        all_ok = False

    # 3. Check Gemini API Key
    if not check_gemini_api_key():
        all_ok = False

    # Summary
    print("=" * 70)
    if all_ok:
        print("✅ All dependencies are ready!")
        print("=" * 70)
        print("\n🎉 You can now use article-craft skill")
        print("   Example: /article-craft 写一篇关于Python的技术文章\n")
        return True
    else:
        print("⚠️  Some dependencies are missing or not configured")
        print("=" * 70)
        print("\n📝 Please follow the instructions above to complete setup")
        print("   Run this script again after setup: python3 setup_dependencies.py\n")
        return False

if __name__ == '__main__':
    success = main()
    sys.exit(0 if success else 1)
