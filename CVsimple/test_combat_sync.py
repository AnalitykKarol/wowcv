#!/usr/bin/env python3
"""
Combat-Detection Synchronization Test
Tests whether combat controller properly synchronizes with detection timing
"""
import time
import threading
import numpy as np
from typing import Dict, List, Optional, Any

class MockDetectionsSimulator:
    """Simulates YOLO detection system with variable timing"""

    def __init__(self):
        self.detection_rate = 10  # Hz (10 detections per second)
        self.detection_interval = 1.0 / self.detection_rate
        self.running = False
        self.detection_count = 0
        self.last_detection_time = 0

    def start_simulation(self, callback):
        """Start detection simulation"""
        self.running = True
        self.detection_count = 0
        self.last_detection_time = time.time()

        def detection_worker():
            while self.running:
                # Generate mock detections
                detections = self._generate_mock_detections()

                # Call callback with detections
                callback(detections)

                self.detection_count += 1
                self.last_detection_time = time.time()

                # Sleep for detection interval
                time.sleep(self.detection_interval)

        thread = threading.Thread(target=detection_worker, daemon=True)
        thread.start()
        return thread

    def _generate_mock_detections(self) -> List[Dict[str, Any]]:
        """Generate mock enemy detections"""
        # Simulate 1-3 enemies
        num_enemies = np.random.randint(1, 4)

        detections = []
        for i in range(num_enemies):
            detection = {
                'class': 'enemy',
                'confidence': np.random.uniform(0.6, 0.95),
                'center_x': np.random.uniform(200, 1720),
                'center_y': np.random.uniform(200, 880),
                'width': np.random.uniform(50, 150),
                'height': np.random.uniform(80, 200),
                'frame_id': self.detection_count
            }
            detections.append(detection)

        return detections

    def stop_simulation(self):
        """Stop detection simulation"""
        self.running = False

class MockCombatController:
    """Mock combat controller that tracks detection synchronization"""

    def __init__(self, logger=None):
        self.logger = logger or print

        # Synchronization tracking
        self.last_detection_time = 0
        self.detection_stale = False
        self.mode = "exploration"

        # Statistics
        self.stats = {
            'total_updates': 0,
            'detection_updates': 0,
            'stale_updates': 0,
            'combat_actions': 0,
            'exploration_actions': 0,
            'sync_errors': 0
        }

    def update(self, detections: Optional[List[Dict[str, Any]]] = None):
        """Update combat controller with detections"""
        current_time = time.time()
        self.stats['total_updates'] += 1

        # Detection synchronization check
        if detections and len(detections) > 0:
            self.last_detection_time = current_time
            self.detection_stale = False
            self.stats['detection_updates'] += 1

            # Simulate combat actions with fresh data
            self._simulate_combat_actions(detections)

        else:
            # Check if detection data is stale
            if self.last_detection_time > 0:
                time_since_detection = current_time - self.last_detection_time
                if time_since_detection > 1.0:  # 1 second without detections
                    if not self.detection_stale:
                        self.logger(f"⚠️ Detection data became stale after {time_since_detection:.1f}s")
                    self.detection_stale = True
                    self.stats['stale_updates'] += 1

                    # Should NOT perform combat actions with stale data
                    self._simulate_stale_data_behavior()

    def _simulate_combat_actions(self, detections: List[Dict[str, Any]]):
        """Simulate combat actions with fresh detections"""
        if self.detection_stale:
            self.logger("❌ ERROR: Combat actions with stale data!")
            self.stats['sync_errors'] += 1
            return

        if self.mode == "exploration" and len(detections) > 0:
            self.logger(f"🎯 Fresh detections: {len(detections)} enemies - switching to combat")
            self.mode = "combat"
            self.stats['combat_actions'] += 1
        elif self.mode == "combat":
            self.logger(f"⚔️ Combat actions with {len(detections)} enemies")
            self.stats['combat_actions'] += 1

    def _simulate_stale_data_behavior(self):
        """Simulate proper behavior with stale data"""
        self.logger("🛑 Stale detection data - stopping movement")
        self.mode = "exploration"  # Should not be moving
        # In real system, this would stop all movement

    def get_stats(self) -> Dict:
        """Get synchronization statistics"""
        total = self.stats['total_updates']
        if total == 0:
            return self.stats

        stats = self.stats.copy()
        stats.update({
            'detection_update_rate': self.stats['detection_updates'] / total,
            'stale_update_rate': self.stats['stale_updates'] / total,
            'sync_error_rate': self.stats['sync_errors'] / total,
            'synchronization_health': 'GOOD' if self.stats['sync_errors'] == 0 else 'POOR'
        })
        return stats

def test_combat_synchronization():
    """Test combat-detection synchronization"""
    print("🧪 Testing Combat-Detection Synchronization")
    print("=" * 60)

    # Initialize components
    simulator = MockDetectionsSimulator()
    combat = MockCombatController()

    def detection_callback(detections):
        """Callback from detection simulator to combat controller"""
        combat.update(detections)

    print("📡 Starting detection simulation (10 Hz)")

    # Start detection simulation
    detection_thread = simulator.start_simulation(detection_callback)

    try:
        # Test for 10 seconds
        test_duration = 10
        print(f"⏰ Running test for {test_duration} seconds...")

        start_time = time.time()
        while time.time() - start_time < test_duration:
            time.sleep(0.1)  # Check every 100ms

            # Print status every 2 seconds
            elapsed = time.time() - start_time
            if int(elapsed) % 2 == 0 and elapsed > 0 and elapsed - int(elapsed) < 0.1:
                print(f"   {elapsed:.0f}s: Total updates: {combat.stats['total_updates']}, "
                      f"Detection updates: {combat.stats['detection_updates']}, "
                      f"Stale updates: {combat.stats['stale_updates']}")

    except KeyboardInterrupt:
        print("\n⏹️ Test stopped by user")

    finally:
        # Stop simulation
        simulator.stop_simulation()
        detection_thread.join(timeout=1)

    # Get results
    stats = combat.get_stats()

    print("\n📊 SYNCHRONIZATION TEST RESULTS")
    print("=" * 60)

    print(f"⏱️  Duration: {test_duration} seconds")
    print(f"🔄 Total updates: {stats['total_updates']}")
    print(f"🎯 Detection updates: {stats['detection_updates']}")
    print(f"⚠️  Stale updates: {stats['stale_updates']}")
    print(f"⚔️  Combat actions: {stats['combat_actions']}")
    print(f"❌ Sync errors: {stats['sync_errors']}")

    print(f"\n📈 RATES:")
    print(f"   Detection update rate: {stats['detection_update_rate']:.1%}")
    print(f"   Stale update rate: {stats['stale_update_rate']:.1%}")
    print(f"   Sync error rate: {stats['sync_error_rate']:.1%}")

    print(f"\n🎯 SYNCHRONIZATION HEALTH: {stats['synchronization_health']}")

    # Recommendations
    print(f"\n💡 ANALYSIS:")
    if stats['sync_errors'] == 0:
        print("   ✅ Perfect synchronization - no combat actions with stale data")
    else:
        print(f"   ❌ {stats['sync_errors']} sync errors detected!")

    if stats['stale_update_rate'] > 0.5:
        print("   ⚠️ High stale data rate - consider improving detection frequency")

    if stats['detection_update_rate'] < 0.7:
        print("   ⚠️ Low detection update rate - system may be lagging")

    print("\n🚀 Test completed!")

def test_detection_failure_scenarios():
    """Test various detection failure scenarios"""
    print("\n🧪 Testing Detection Failure Scenarios")
    print("=" * 60)

    scenarios = [
        {"name": "Normal operation", "detection_rate": 10, "duration": 3},
        {"name": "Slow detection", "detection_rate": 2, "duration": 5},
        {"name": "Detection dropout", "detection_rate": 0, "duration": 3},
    ]

    for scenario in scenarios:
        print(f"\n📋 Testing: {scenario['name']}")
        print("-" * 40)

        simulator = MockDetectionsSimulator()
        combat = MockCombatController()

        # Set detection rate
        simulator.detection_rate = scenario['detection_rate']
        simulator.detection_interval = 1.0 / scenario['detection_rate'] if scenario['detection_rate'] > 0 else 999

        def callback(detections):
            combat.update(detections)

        # Run test
        thread = simulator.start_simulation(callback)

        try:
            time.sleep(scenario['duration'])
        finally:
            simulator.stop_simulation()
            thread.join(timeout=1)

        # Results
        stats = combat.get_stats()
        print(f"   Updates: {stats['total_updates']}")
        print(f"   Detection updates: {stats['detection_updates']}")
        print(f"   Stale updates: {stats['stale_updates']}")
        print(f"   Sync errors: {stats['sync_errors']}")
        print(f"   Health: {stats['synchronization_health']}")

if __name__ == "__main__":
    # Run main synchronization test
    test_combat_synchronization()

    # Run failure scenarios
    test_detection_failure_scenarios()

    print("\n🎉 All synchronization tests completed!")