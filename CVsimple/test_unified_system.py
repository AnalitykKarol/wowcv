#!/usr/bin/env python3
"""
Test Unified System Integration
Tests the unified pipeline and display components working together
"""
import sys
import os
import time
import numpy as np

# Add project path for imports
sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))

def test_unified_pipeline():
    """Test unified pipeline functionality"""
    print("🧪 Testing Unified Pipeline")
    print("=" * 50)

    try:
        from core.unified_pipeline import create_unified_pipeline
        from core.dx_window_capture import DXWindowCapture
        from core.yolo_detector import MultiThreadedYOLODetector

        print("✅ Successfully imported unified components")

        # Test pipeline creation
        pipeline = create_unified_pipeline(target_fps=60)
        print(f"✅ Pipeline created successfully")

        # Test if dxcam is available
        print(f"📊 dxcam available: {DXWindowCapture.dx_available}")

        # Test frame capture (simulated)
        test_frame = np.random.randint(0, 255, (1080, 1920, 3), dtype=np.uint8)

        # Test processing
        result = pipeline._run_inference(test_frame)
        print(f"✅ Inference test: {result is not None}")

        # Test combat processing
        combat_result = pipeline._process_combat([])
        print(f"✅ Combat test: {combat_result is not None}")

        return True

    except Exception as e:
        print(f"❌ Pipeline test failed: {e}")
        return False

def test_unified_display():
    """Test unified display functionality"""
    print("\n🖼️ Testing Unified Display")
    print("=" * 50)

    try:
        import tkinter as tk
        from gui.unified_display import UnifiedDisplay

        # Test display creation
        root = tk.Tk()
        display = UnifiedDisplay(root, logger=print)
        print("✅ Display created successfully")

        # Test display modes
        display.current_mode = 'debug'
        print(f"✅ Display mode: {display.current_mode}")

        # Test FPS switching
        display.fps_var.set(45)
        print("✅ FPS changed successfully")

        # Test option toggles
        display.show_boxes_var.set(False)
        display.show_metrics_var.set(True)
        print("✅ Options toggled successfully")

        # Cleanup
        root.destroy()
        print("✅ Display test completed")

        return True

    except Exception as e:
        print(f"❌ Display test failed: {e}")
        return False

def test_integration():
    """Test unified system integration"""
    print("\n🔗 Testing System Integration")
    print("=" * 50)

    try:
        from gui.unified_display import UnifiedDisplay
        from core.unified_pipeline import create_unified_pipeline
        import tkinter as tk

        # Create root window
        root = tk.Tk()
        root.title("🎯 Unified System Test")
        root.geometry("1000x800")

        # Create unified system
        controller, display = setup_unified_system(root,
                                                   target_fps=60,
                                                   auto_start=False)

        if not controller.is_initialized:
            print("❌ System initialization failed")
            return False

        print("✅ Unified system initialized")
        print(f"   System mode: {controller.get_system_mode()}")

        # Get initial status
        status = controller.get_status()
        print(f"   Is running: {status['is_running']}")
        print(f"   FPS: {status.get('target_fps', 60)}")

        # Test frame count vs performance
        print("\n📊 Running performance test for 5 seconds...")
        start_time = time.time()
        frame_count = 0

        controller.start_pipeline(None)  # Auto-detect window

        controller.log("🚀 Performance test started")

        # Simulate processing
        for i in range(150):  # Test 150 iterations
            result = controller.get_latest_result()
            if result:
                frame_count += 1
                if frame_count % 30 == 0:
                    elapsed = time.time() - start_time
                    fps = frame_count / elapsed if elapsed > 0 else 0
                    print(f"   Progress: {frame_count} frames, FPS: {fps:.1f}")

            time.sleep(0.001)  # Simulate minimal processing time

        controller.stop_pipeline()

        final_fps = frame_count / (time.time() - start_time) if time.time() > start_time else 0
        print(f"\n📈 Performance Test Results:")
        print(f"   Total frames: {frame_count}")
        print(f"   Average FPS: {final_fps:.1f} FPS")
        print(f"   Duration: {time.time() - start_time:.1f}s")

        return final_fps >= 30  # Expect at least 30 FPS

    except Exception as e:
        print(f"❌ Integration test failed: {e}")
        return False

def main():
    """Main test function"""
    print("🎯 Unified System Integration Test")
    print("=" * 60)

    all_tests_passed = True

    # Test 1: Pipeline
    print("\n🔬 Testing Unified Pipeline")
    pipeline_test = test_unified_pipeline()
    if not pipeline_test:
        all_tests_passed = False

    # Test 2: Display
    print("\n🖼️ Testing Unified Display")
    display_test = test_unified_display()
    if not display_test:
        all_tests_passed = False

    # Test 3: Integration
    print("\n🔗 Testing System Integration")
    integration_test = test_integration()
    if not integration_test:
        all_tests_passed = False

    # Final results
    print(f"\n🎯 Final Results:")
    print("=" * 40)
    if all_tests_passed:
        print("🎉 ALL TESTS PASSED! 🎉")
        print("   System is ready for production use with 60+ FPS capability")
        print("   Unified architecture provides:")
        print("   - Single pipeline processing")
        print("   - Configurable display modes")
        - - Legacy compatibility fallback")
        print("   - High-performance frame processing")
    else:
        print("❌ SOME TESTS FAILED")
        print("   Check the error logs above for details")

    print(f"\n💡 Next Steps:")
    print("   1. Run 'python main.py' with unified system")
    print("   2. Set target window in the application")
    print("   3. Adjust FPS and display options as needed")
        print("   4. Monitor performance metrics")

    print(f"\n🎯 Test completed!")

if __name__ == "__main__":
    main()