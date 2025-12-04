#!/usr/bin/env python3
"""
dxcam Diagnostic Tool
Diagnoses dxcam compatibility issues and provides troubleshooting steps
"""
import sys
import os
import platform

def check_system_requirements():
    """Check if system meets dxcam requirements"""
    print("🔍 System Requirements Check")
    print("=" * 40)

    # Check Windows
    if platform.system() != "Windows":
        print("❌ Not running on Windows")
        print("   dxcam requires Windows OS")
        return False

    print(f"✅ Running on {platform.system()} {platform.release()}")

    # Check Python version
    python_version = sys.version_info
    if python_version < (3, 7):
        print(f"❌ Python {python_version.major}.{python_version.minor} is too old")
        print("   dxcam requires Python 3.7+")
        return False

    print(f"✅ Python {python_version.major}.{python_version.minor}.{python_version.micro}")

    return True

def test_dxcam_import():
    """Test dxcam import and basic functionality"""
    print("\n🧪 Testing dxcam Import")
    print("=" * 40)

    try:
        import dxcam
        print("✅ dxcam imported successfully")

        # Check dxcam version
        if hasattr(dxcam, '__version__'):
            print(f"   dxcam version: {dxcam.__version__}")
        else:
            print("   dxcam version: unknown")

        return True
    except ImportError as e:
        print(f"❌ dxcam import failed: {e}")
        print("   Try: pip install dxcam")
        return False
    except Exception as e:
        print(f"❌ dxcam error: {e}")
        return False

def test_directx_availability():
    """Test DirectX availability"""
    print("\n🎮 Testing DirectX Availability")
    print("=" * 40)

    try:
        import comtypes
        print("✅ comtypes available")
    except ImportError:
        print("❌ comtypes not available")
        print("   Try: pip install comtypes")
        return False

    try:
        # Test COM initialization
        import pythoncom
        pythoncom.CoInitialize()
        pythoncom.CoUninitialize()
        print("✅ COM subsystem available")
    except Exception as e:
        print(f"❌ COM subsystem error: {e}")
        return False

    return True

def test_dxcam_functionality():
    """Test dxcam basic functionality"""
    print("\n📸 Testing dxcam Functionality")
    print("=" * 40)

    try:
        import dxcam
        import win32gui

        # Get a window handle
        try:
            hwnd = win32gui.GetForegroundWindow()
            title = win32gui.GetWindowText(hwnd)
            print(f"   Test window: {title[:50]}...")
        except:
            hwnd = None
            print("   Using mock window handle")

        # Create dxcam instance
        try:
            camera = dxcam.create()
            print("✅ dxcam.create() successful")
        except Exception as e:
            print(f"❌ dxcam.create() failed: {e}")
            return False

        # Test screen grab
        try:
            frame = camera.grab()
            if frame is not None:
                print(f"✅ Screen grab successful: {frame.shape}")
                print(f"   Frame type: {frame.dtype}")
                print(f"   Frame size: {frame.nbytes} bytes")
            else:
                print("❌ Screen grab returned None")
                return False
        except Exception as e:
            print(f"❌ Screen grab failed: {e}")
            return False

        # Test region capture
        try:
            frame = camera.grab(region=(0, 0, 640, 480))
            if frame is not None:
                print(f"✅ Region grab successful: {frame.shape}")
            else:
                print("❌ Region grab returned None")
        except Exception as e:
            print(f"❌ Region grab failed: {e}")

        # Cleanup
        try:
            del camera
            print("✅ dxcam cleanup successful")
        except Exception as e:
            print(f"⚠️ dxcam cleanup warning: {e}")

        return True

    except Exception as e:
        print(f"❌ dxcam functionality test failed: {e}")
        return False

def check_directx_debug_info():
    """Get DirectX debug information"""
    print("\n🔧 DirectX Debug Information")
    print("=" * 40)

    try:
        import wmi
        c = wmi.WMI()

        # Check graphics cards
        for gpu in c.Win32_VideoController():
            print(f"🎮 GPU: {gpu.Name}")
            print(f"   Driver: {gpu.DriverVersion}")
            print(f"   RAM: {gpu.AdapterRAM // (1024*1024)} MB")

        return True
    except ImportError:
        print("❌ WMI not available - pip install WMI for GPU info")
        return False
    except Exception as e:
        print(f"❌ GPU info failed: {e}")
        return False

def generate_troubleshooting_guide():
    """Generate troubleshooting guide based on test results"""
    print("\n💡 Troubleshooting Guide")
    print("=" * 40)

    print("📋 Common dxcam Issues and Solutions:")
    print()
    print("1. ❌ 'dxcam not available':")
    print("   • Ensure you're running Windows 10/11")
    print("   • Install: pip install dxcam comtypes")
    print("   • Check: python -c 'import dxcam; print(dxcam.__version__)'")
    print()

    print("2. ❌ 'COM technology not available':")
    print("   • Must be running on Windows")
    print("   • Try: pip install comtypes pywin32")
    print("   • Restart Python/IDE after installation")
    print()

    print("3. ❌ 'dxcam returned None frame':")
    print("   • Check Windows display settings")
    print("   • Try running as administrator")
    print("   • Close other DirectX applications")
    print("   • Update graphics drivers")
    print("   • Disable hardware acceleration in other apps")
    print()

    print("4. ❌ 'Access denied':")
    print("   • Run as administrator")
    print("   • Check Windows privacy settings")
    print("   • Add Python to Windows Defender exclusions")
    print()

    print("🚀 Recommended dxcam Usage Pattern:")
    print("   ```python")
    print("   import dxcam")
    print("   ")
    print("   camera = dxcam.create(output_idx=0, output_color='RGB')")
    print("   frame = camera.grab()  # or camera.grab(region=(x,y,w,h))")
    print("   ")
    print("   # Always check for None")
    print("   if frame is not None:")
    print("       # Use frame")
    print("   ```")
    print()

def main():
    """Main diagnostic function"""
    print("🎯 dxcam Diagnostic Tool")
    print("=" * 60)

    # Run all tests
    all_tests_passed = True

    # Test 1: System requirements
    if not check_system_requirements():
        all_tests_passed = False

    # Test 2: Import test
    if not test_dxcam_import():
        all_tests_passed = False

    # Test 3: DirectX availability (Windows only)
    if all_tests_passed and platform.system() == "Windows":
        if not test_directx_availability():
            all_tests_passed = False

    # Test 4: Functionality test
    if all_tests_passed and platform.system() == "Windows":
        if not test_dxcam_functionality():
            all_tests_passed = False

        # Test 5: Debug info
        check_directx_debug_info()

    # Generate troubleshooting guide
    generate_troubleshooting_guide()

    # Final verdict
    print(f"\n{'🎉' if all_tests_passed else '⚠️'} Diagnostic Results")
    print("=" * 60)

    if all_tests_passed:
        print("✅ All tests passed! dxcam should work properly.")
        print("📈 Expected performance: 1-3ms capture time (10-40x faster than PrintWindow)")
        print("🎮 Your system is ready for high-performance capture!")
    else:
        print("❌ Some tests failed. See troubleshooting guide above.")
        print("💡 Most issues are fixable with proper configuration.")

    print(f"\n📞 If problems persist:")
    print("   1. Run this script as administrator")
    print("   2. Update graphics drivers")
    print("   3. Close all DirectX applications")
    print("   4. Check Windows Event Viewer for dxcam errors")

if __name__ == "__main__":
    main()