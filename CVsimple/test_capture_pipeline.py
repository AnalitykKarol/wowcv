#!/usr/bin/env python3
"""
Image Capture Pipeline Bottleneck Analysis
Tests each stage of the image capture and preprocessing pipeline to identify bottlenecks
"""
import time
import numpy as np
import threading
from typing import Dict, List, Optional, Tuple, Any
from collections import deque
import sys
import os

# Add project path for imports
sys.path.append(os.path.dirname(os.path.abspath(__file__)))

# Mock Windows API for cross-platform testing
class MockWindowsAPI:
    """Mock Windows API for testing image capture operations"""

    def __init__(self, width=1920, height=1080):
        self.width = width
        self.height = height
        self.frame_count = 0

    def get_window_rect(self, hwnd):
        """Mock window rect"""
        return (0, 0, self.width, self.height)

    def GetWindowDC(self, hwnd):
        """Mock DC"""
        return f"mock_dc_{hwnd}"

    def ReleaseDC(self, hwnd, dc):
        """Mock DC release"""
        pass

    def CreateCompatibleDC(self, dc):
        """Mock compatible DC"""
        return f"mock_compatible_dc_{dc}"

    def DeleteDC(self, dc):
        """Mock DC deletion"""
        pass

    def CreateCompatibleBitmap(self, dc, width, height):
        """Mock bitmap creation"""
        return f"mock_bitmap_{width}x{height}"

    def SelectObject(self, dc, bitmap):
        """Mock object selection"""
        return f"mock_selected_{bitmap}"

    def DeleteObject(self, obj):
        """Mock object deletion"""
        pass

    def PrintWindow(self, hwnd, dc, flags):
        """Mock PrintWindow - simulates actual screen capture time"""
        # Simulate variable capture time (15-40ms)
        capture_time = np.random.uniform(0.015, 0.040)
        time.sleep(capture_time)
        self.frame_count += 1
        return True  # Success

    def GetBitmapBits(self, bitmap, size, buffer):
        """Mock bitmap bits - simulates memory copy time"""
        # Simulate memory copy time based on image size
        image_size = self.width * self.height * 4  # BGRX
        copy_time = image_size / (1024 * 1024 * 1024) * 0.001  # ~1ms per GB
        time.sleep(max(0.001, copy_time))

        # Generate mock bitmap data
        mock_data = np.random.randint(0, 255, image_size, dtype=np.uint8)
        return len(mock_data)

# Import actual modules if available (fallback to mock)
try:
    import win32gui
    import win32ui
    import win32con
    import ctypes
    from ctypes import wintypes
    WINDOWS_API_AVAILABLE = True
except ImportError:
    print("⚠️ Windows API not available - using mock implementation")
    WINDOWS_API_AVAILABLE = False

# Mock the Windows API if not available
if not WINDOWS_API_AVAILABLE:
    win32gui = MockWindowsAPI()
    win32ui = MockWindowsAPI()
    win32con = type('MockConstants', (), {})()
    ctypes = type('MockCtypes', (), {'wintypes': MockWindowsAPI()})()

class ImageCapturePipelineAnalyzer:
    """Analyzes each stage of image capture pipeline"""

    def __init__(self, target_width=1920, target_height=1080):
        self.target_width = target_width
        self.target_height = target_height
        self.results = {
            'total_tests': 0,
            'stage_timings': {},
            'memory_usage': []
        }

        # Performance stages to test
        self.stages = [
            'windows_api_capture',
            'bitmap_extraction',
            'pil_conversion',
            'numpy_conversion',
            'color_space_conversion',
            'array_reshaping',
            'validation',
            'total_pipeline'
        ]

        # Initialize timing storage
        for stage in self.stages:
            self.results['stage_timings'][stage] = {
                'times': deque(maxlen=100),
                'total_time': 0,
                'avg_time': 0,
                'max_time': 0,
                'min_time': float('inf')
            }

    def capture_window_mock(self, hwnd: int) -> Optional[np.ndarray]:
        """Mock window capture with detailed timing"""
        timings = {}

        try:
            # Stage 1: Windows API Setup
            start_time = time.perf_counter()
            rect = win32gui.get_window_rect(hwnd)
            width = rect[2] - rect[0]
            height = rect[3] - rect[1]
            timings['windows_setup'] = (time.perf_counter() - start_time) * 1000

            # Stage 2: DC Operations
            start_time = time.perf_counter()
            hwnd_dc = win32gui.GetWindowDC(hwnd)
            mfc_dc = win32ui.CreateCompatibleDC(hwnd_dc)
            save_dc = mfc_dc.SaveDC()
            h_bitmap = win32ui.CreateCompatibleBitmap(hwnd_dc, width, height)
            mfc_dc.SelectObject(h_bitmap)
            timings['dc_operations'] = (time.perf_counter() - start_time) * 1000

            # Stage 3: PrintWindow (Actual screen capture)
            start_time = time.perf_counter()
            result = win32gui.PrintWindow(hwnd, mfc_dc.GetSafeHdc(), 2)
            timings['windows_capture'] = (time.perf_counter() - start_time) * 1000

            if not result:
                raise Exception("PrintWindow failed")

            # Stage 4: Bitmap info preparation
            start_time = time.perf_counter()
            bmpinfo = mfc_dc.GetBitmapBits(h_bitmap)
            bmpstr = bmpinfo['bmBits']
            timings['bitmap_info'] = (time.perf_counter() - start_time) * 1000

            # Cleanup Windows resources
            mfc_dc.RestoreDC(save_dc)
            win32gui.DeleteObject(h_bitmap.GetSafeHdc())
            mfc_dc.DeleteDC()
            win32gui.ReleaseDC(hwnd, hwnd_dc)

            # Stage 5: PIL Conversion (BGRX -> RGB)
            start_time = time.perf_counter()
            from PIL import Image
            img = Image.frombuffer(
                'RGB',
                (bmpinfo['bmWidth'], bmpinfo['bmHeight']),
                bmpstr, 'raw', 'BGRX', 0, 1
            )
            timings['pil_conversion'] = (time.perf_counter() - start_time) * 1000

            # Stage 6: Numpy conversion
            start_time = time.perf_counter()
            img_array = np.array(img)
            timings['numpy_conversion'] = (time.perf_counter() - start_time) * 1000

            # Store all timings
            for stage_name, stage_time in timings.items():
                if stage_name not in self.results['stage_timings']:
                    self.results['stage_timings'][stage_name] = {
                        'times': deque(maxlen=100),
                        'total_time': 0,
                        'avg_time': 0,
                        'max_time': 0,
                        'min_time': float('inf')
                    }

                self.results['stage_timings'][stage_name]['times'].append(stage_time)
                self.results['stage_timings'][stage_name]['total_time'] += stage_time
                self.results['stage_timings'][stage_name]['max_time'] = max(
                    self.results['stage_timings'][stage_name]['max_time'], stage_time
                )
                self.results['stage_timings'][stage_name]['min_time'] = min(
                    self.results['stage_timings'][stage_name]['min_time'], stage_time
                )

            return img_array

        except Exception as e:
            print(f"❌ Capture error: {e}")
            return None

    def test_optimized_pipeline(self, hwnd: int) -> Optional[np.ndarray]:
        """Test optimized pipeline without PIL"""
        try:
            timings = {}

            # Stage 1: Windows API operations
            start_time = time.perf_counter()
            rect = win32gui.get_window_rect(hwnd)
            width = rect[2] - rect[0]
            height = rect[3] - rect[1]
            timings['windows_api_capture'] = (time.perf_counter() - start_time) * 1000

            # Stage 2: Direct bitmap extraction and numpy conversion
            start_time = time.perf_counter()
            # Simulate direct numpy conversion (this would be the optimized version)
            image_size = width * height * 4  # BGRX
            mock_data = np.random.randint(0, 255, image_size, dtype=np.uint8)
            img_array = mock_data.reshape((height, width, 4))[:,:,:3]  # BGR
            timings['bitmap_extraction'] = (time.perf_counter() - start_time) * 1000

            # Stage 3: Color space conversion (BGR -> RGB)
            start_time = time.perf_counter()
            img_rgb = img_array[:, :, ::-1]  # BGR to RGB
            timings['color_space_conversion'] = (time.perf_counter() - start_time) * 1000

            # Stage 4: Validation
            start_time = time.perf_counter()
            # Basic validation
            if img_rgb.size == 0:
                raise Exception("Empty image")
            timings['validation'] = (time.perf_counter() - start_time) * 1000

            # Record optimized pipeline timings
            total_time = sum(timings.values())
            timings['total_pipeline'] = total_time

            for stage_name, stage_time in timings.items():
                self.results['stage_timings'][stage_name]['times'].append(stage_time)
                self.results['stage_timings'][stage_name]['total_time'] += stage_time
                self.results['stage_timings'][stage_name]['max_time'] = max(
                    self.results['stage_timings'][stage_name]['max_time'], stage_time
                )
                self.results['stage_timings'][stage_name]['min_time'] = min(
                    self.results['stage_timings'][stage_name]['min_time'], stage_time
                )

            return img_rgb

        except Exception as e:
            print(f"❌ Optimized capture error: {e}")
            return None

    def test_yolo_preprocessing(self, image: np.ndarray, target_size=(640, 640)) -> Tuple[np.ndarray, Dict]:
        """Test YOLO preprocessing stages"""
        timings = {}

        try:
            # Stage 1: Resize for YOLO
            start_time = time.perf_counter()
            try:
                import cv2
                resized = cv2.resize(image, target_size)
            except ImportError:
                # Mock resize
                resized = np.random.randint(0, 255, (*target_size, 3), dtype=np.uint8)
            timings['yolo_resize'] = (time.perf_counter() - start_time) * 1000

            # Stage 2: Normalization
            start_time = time.perf_counter()
            normalized = resized.astype(np.float32) / 255.0
            timings['normalization'] = (time.perf_counter() - start_time) * 1000

            # Stage 3: Transpose (HWC -> CHW for PyTorch)
            start_time = time.perf_counter()
            transposed = normalized.transpose(2, 0, 1)
            timings['transpose'] = (time.perf_counter() - start_time) * 1000

            # Stage 4: Add batch dimension
            start_time = time.perf_counter()
            batched = np.expand_dims(transposed, axis=0)
            timings['batch_dimension'] = (time.perf_counter() - start_time) * 1000

            total_time = sum(timings.values())

            return batched, {
                'timings': timings,
                'total_time': total_time,
                'input_shape': image.shape,
                'output_shape': batched.shape
            }

        except Exception as e:
            print(f"❌ YOLO preprocessing error: {e}")
            return None, {'error': str(e)}

    def run_comprehensive_test(self, num_iterations: int = 50):
        """Run comprehensive pipeline test"""
        print(f"🚀 Starting Image Capture Pipeline Analysis")
        print(f"📊 Target: {num_iterations} iterations")
        print(f"🖼️  Image size: {self.target_width}x{self.target_height}")
        print("=" * 70)

        mock_hwnd = 12345  # Mock window handle

        print("\n📋 Testing Current Pipeline (with PIL)")
        print("-" * 40)

        # Test current pipeline
        successful_captures = 0
        start_total = time.perf_counter()

        for i in range(num_iterations):
            if i % 10 == 0:
                print(f"   Progress: {i}/{num_iterations}")

            result = self.capture_window_mock(mock_hwnd)
            if result is not None:
                successful_captures += 1

        total_pipeline_time = (time.perf_counter() - start_total) * 1000
        avg_pipeline_time = total_pipeline_time / num_iterations

        print(f"✅ Current pipeline completed")
        print(f"   Success rate: {successful_captures}/{num_iterations} ({successful_captures/num_iterations*100:.1f}%)")
        print(f"   Average time: {avg_pipeline_time:.2f}ms")
        print(f"   Theoretical FPS: {1000/avg_pipeline_time:.1f}")

        print("\n📋 Testing Optimized Pipeline (without PIL)")
        print("-" * 40)

        # Test optimized pipeline
        successful_optimized = 0
        start_optimized = time.perf_counter()

        for i in range(num_iterations):
            result = self.test_optimized_pipeline(mock_hwnd)
            if result is not None:
                successful_optimized += 1

        total_optimized_time = (time.perf_counter() - start_optimized) * 1000
        avg_optimized_time = total_optimized_time / num_iterations

        print(f"✅ Optimized pipeline completed")
        print(f"   Success rate: {successful_optimized}/{num_iterations} ({successful_optimized/num_iterations*100:.1f}%)")
        print(f"   Average time: {avg_optimized_time:.2f}ms")
        print(f"   Theoretical FPS: {1000/avg_optimized_time:.1f}")

        print(f"\n📋 Testing YOLO Preprocessing")
        print("-" * 40)

        # Test YOLO preprocessing
        test_image = np.random.randint(0, 255, (self.target_height, self.target_width, 3), dtype=np.uint8)

        yolo_times = []
        for i in range(num_iterations):
            _, yolo_result = self.test_yolo_preprocessing(test_image)
            if 'total_time' in yolo_result:
                yolo_times.append(yolo_result['total_time'])

        if yolo_times:
            avg_yolo_time = np.mean(yolo_times)
            print(f"✅ YOLO preprocessing completed")
            print(f"   Average time: {avg_yolo_time:.2f}ms")
            print(f"   Theoretical FPS: {1000/avg_yolo_time:.1f}")

        # Calculate improvement
        if avg_optimized_time > 0:
            improvement = (avg_pipeline_time - avg_optimized_time) / avg_pipeline_time * 100
            speedup = avg_pipeline_time / avg_optimized_time
            print(f"\n🚀 OPTIMIZATION RESULTS:")
            print(f"   Time reduction: {improvement:.1f}%")
            print(f"   Speedup factor: {speedup:.1f}x")

        return self.generate_detailed_report()

    def generate_detailed_report(self) -> Dict:
        """Generate detailed performance report"""
        print("\n" + "=" * 70)
        print("📊 DETAILED PIPELINE ANALYSIS REPORT")
        print("=" * 70)

        report = {
            'bottlenecks': [],
            'recommendations': [],
            'stage_analysis': {}
        }

        for stage_name, stage_data in self.results['stage_timings'].items():
            times = list(stage_data['times'])
            if not times:
                continue

            avg_time = np.mean(times)
            max_time = np.max(times)
            min_time = np.min(times)
            std_time = np.std(times)

            stage_analysis = {
                'avg_ms': avg_time,
                'max_ms': max_time,
                'min_ms': min_time,
                'std_ms': std_time,
                'avg_fps': 1000 / avg_time if avg_time > 0 else 0
            }

            report['stage_analysis'][stage_name] = stage_analysis

            print(f"\n🔍 {stage_name.upper().replace('_', ' ')}:")
            print(f"   Average: {avg_time:7.2f}ms  ({1000/avg_time:6.1f} FPS)")
            print(f"   Max:     {max_time:7.2f}ms  ({1000/max_time:6.1f} FPS)")
            print(f"   Min:     {min_time:7.2f}ms  ({1000/min_time:6.1f} FPS)")
            print(f"   Std Dev: {std_time:7.2f}ms")

            # Identify bottlenecks
            if avg_time > 20:  # More than 20ms is a bottleneck
                report['bottlenecks'].append({
                    'stage': stage_name,
                    'avg_time_ms': avg_time,
                    'impact': f"Reduces theoretical max FPS to {1000/avg_time:.1f}"
                })

                if avg_time > 50:
                    print(f"   🚨 CRITICAL BOTTLENECK!")
                elif avg_time > 30:
                    print(f"   ⚠️  SIGNIFICANT BOTTLENECK!")

        # Recommendations
        print(f"\n💡 RECOMMENDATIONS:")

        if 'windows_capture' in report['stage_analysis']:
            capture_time = report['stage_analysis']['windows_capture']['avg_ms']
            if capture_time > 20:
                print(f"   1️⃣ Windows PrintWindow is slow ({capture_time:.1f}ms)")
                print(f"      - Consider DirectX/Desktop Duplication API")
                print(f"      - Lower capture resolution")
                report['recommendations'].append("Use DirectX instead of PrintWindow")

        if 'pil_conversion' in report['stage_analysis']:
            pil_time = report['stage_analysis']['pil_conversion']['avg_ms']
            if pil_time > 5:
                print(f"   2️⃣ PIL conversion is slow ({pil_time:.1f}ms)")
                print(f"      - Use direct numpy conversion")
                print(f"      - Pre-allocate buffers")
                report['recommendations'].append("Replace PIL with direct numpy conversion")

        if 'numpy_conversion' in report['stage_analysis']:
            numpy_time = report['stage_analysis']['numpy_conversion']['avg_ms']
            if numpy_time > 3:
                print(f"   3️⃣ Numpy conversion overhead ({numpy_time:.1f}ms)")
                print(f"      - Use in-place operations")
                print(f"      - Avoid unnecessary copies")
                report['recommendations'].append("Optimize numpy operations")

        # Calculate total pipeline time
        if 'total_pipeline' in report['stage_analysis']:
            total_time = report['stage_analysis']['total_pipeline']['avg_ms']
            max_fps = 1000 / total_time

            print(f"\n🎯 PIPELINE SUMMARY:")
            print(f"   Total pipeline time: {total_time:.2f}ms")
            print(f"   Theoretical max FPS: {max_fps:.1f}")

            if max_fps < 30:
                print(f"   🚨 PIPELINE TOO SLOW FOR 60 FPS TARGET!")
            elif max_fps < 60:
                print(f"   ⚠️  Pipeline needs optimization for 60 FPS")
            else:
                print(f"   ✅ Pipeline can handle 60 FPS")

        return report

def main():
    """Main test function"""
    print("🎯 Image Capture Pipeline Bottleneck Analysis")
    print("=" * 70)

    # Check for dependencies
    dependencies = {
        'numpy': np,
        'PIL': None,
        'OpenCV': None,
        'Windows API': WINDOWS_API_AVAILABLE
    }

    try:
        from PIL import Image
        dependencies['PIL'] = True
        print("✅ PIL available")
    except ImportError:
        print("❌ PIL not available")

    try:
        import cv2
        dependencies['OpenCV'] = True
        print("✅ OpenCV available")
    except ImportError:
        print("❌ OpenCV not available")

    print(f"✅ NumPy available")
    print(f"✅ Windows API: {'Available' if WINDOWS_API_AVAILABLE else 'Mock mode'}")

    # Run analysis
    analyzer = ImageCapturePipelineAnalyzer()

    # Test with different image sizes
    test_configs = [
        {'width': 1920, 'height': 1080, 'name': 'Full HD (1920x1080)'},
        {'width': 1280, 'height': 720, 'name': 'HD (1280x720)'},
        {'width': 640, 'height': 480, 'name': 'VGA (640x480)'}
    ]

    for config in test_configs:
        print(f"\n🖥️  Testing with {config['name']}")
        print("=" * 50)

        analyzer.target_width = config['width']
        analyzer.target_height = config['height']

        # Fewer iterations for larger images
        iterations = 20 if config['width'] >= 1920 else 30
        report = analyzer.run_comprehensive_test(iterations)

        # Store results for comparison
        config['report'] = report

    # Final comparison
    print(f"\n🏁 FINAL COMPARISON")
    print("=" * 70)

    for config in test_configs:
        if 'total_pipeline' in config['report']['stage_analysis']:
            stage_data = config['report']['stage_analysis']['total_pipeline']
            fps = stage_data['avg_fps']
            time_ms = stage_data['avg_ms']

            print(f"{config['name']:20s}: {time_ms:6.1f}ms ({fps:5.1f} FPS)")

    print(f"\n🎯 BOTTLENECK SUMMARY:")

    all_bottlenecks = []
    for config in test_configs:
        if config['report']['bottlenecks']:
            print(f"\n{config['name']}:")
            for bottleneck in config['report']['bottlenecks']:
                print(f"   - {bottleneck['stage']}: {bottleneck['avg_time_ms']:.1f}ms")
                print(f"     {bottleneck['impact']}")
                all_bottlenecks.append((config['name'], bottleneck))

    if all_bottlenecks:
        print(f"\n💡 TOP RECOMMENDATIONS:")
        recommendations = set()
        for config in test_configs:
            recommendations.update(config['report']['recommendations'])

        for i, rec in enumerate(recommendations, 1):
            print(f"   {i}. {rec}")
    else:
        print(f"\n✅ No critical bottlenecks detected!")

    print(f"\n🚀 Analysis completed!")

if __name__ == "__main__":
    main()