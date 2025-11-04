"""
MQTT Bot Controller with Face/Hand Tracking
Integrates MediaPipe tracking with MQTT commands for robot control
Uses simple proportional control for smooth and stable tracking
"""

import json
import time
import logging
from typing import Optional, Literal
import paho.mqtt.client as mqtt

# Import configuration
try:
    from bot_config import (
        DEAD_ZONE_X, DEAD_ZONE_Y,
        ROTATION_GAIN, SERVO_GAIN,
        MAX_SERVO_CHANGE_PER_FRAME,
        MAX_TURN_SPEED,
        FORWARD_SPEED, BACKWARD_SPEED,
        OPTIMAL_TARGET_SIZE, SIZE_TOLERANCE,
        TARGET_LOST_TIMEOUT,
        SERVO_MIN, SERVO_MAX, SERVO_START
    )
except ImportError:
    # Default values if config file not found
    DEAD_ZONE_X = 150
    DEAD_ZONE_Y = 100
    ROTATION_GAIN = 0.3
    SERVO_GAIN = 0.05
    MAX_SERVO_CHANGE_PER_FRAME = 3
    MAX_TURN_SPEED = 60
    FORWARD_SPEED = 25
    BACKWARD_SPEED = 20
    OPTIMAL_TARGET_SIZE = 0.12
    SIZE_TOLERANCE = 0.03
    TARGET_LOST_TIMEOUT = 1.0
    SERVO_MIN = 0
    SERVO_MAX = 110
    SERVO_START = 90

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)


class MQTTBotController:
    """MQTT Bot Controller with tracking capabilities"""
    
    def __init__(self, 
                 broker: str = "broker.emqx.io",
                 topic: str = "LDrago_windows/ducky_script",
                 password: str = "E1s2t3e4r5",
                 frame_width: int = 1280,
                 frame_height: int = 720):
        
        self.broker = broker
        self.topic = topic
        self.password = password
        self.frame_width = frame_width
        self.frame_height = frame_height
        
        # Frame center (target position)
        self.center_x = frame_width / 2
        self.center_y = frame_height / 2  # Middle of screen (50%)
        
        # Mirror mode for phone front cameras (flips left/right)
        self.mirror_mode = True  # Set to True for phone front cameras
        
        # Dead zone (pixels) - no movement if target is within this zone
        self.dead_zone_x = DEAD_ZONE_X
        self.dead_zone_y = DEAD_ZONE_Y
        
        # Current servo positions
        self.current_s1 = 90  # Horizontal servo (always 90 as per requirement)
        self.current_s2 = SERVO_START  # Vertical servo (0-110 range)
        
        # Servo time-based control: 1° every 200ms (slower to reduce oscillation)
        self.last_servo_time = time.time()
        self.servo_interval = 0.2  # 200ms (was 150ms)
        self.servo_step = 1  # 1 degree per step
        self.servo_direction = 0  # -1=up, 0=none, 1=down
        
        # Current motor speeds
        self.current_left = 0
        self.current_right = 0
        
        # MQTT Client
        self.client = mqtt.Client()
        self.client.on_connect = self._on_connect
        self.client.on_disconnect = self._on_disconnect
        self.connected = False
        
        # Tracking state
        self.tracking_enabled = False
        self.tracking_mode: Literal["face", "hand"] = "face"
        self.last_target_time = 0
        self.target_lost_timeout = TARGET_LOST_TIMEOUT  # Stop after timeout of no target
        
    def _on_connect(self, client, userdata, flags, rc):
        """MQTT connection callback"""
        if rc == 0:
            logger.info(f"✅ Connected to MQTT broker: {self.broker}")
            self.connected = True
        else:
            logger.error(f"❌ Failed to connect to MQTT broker. Return code: {rc}")
            self.connected = False
    
    def _on_disconnect(self, client, userdata, rc):
        """MQTT disconnection callback"""
        logger.warning(f"⚠️ Disconnected from MQTT broker. Return code: {rc}")
        self.connected = False
    
    def connect(self):
        """Connect to MQTT broker"""
        try:
            logger.info(f"🔌 Connecting to MQTT broker: {self.broker}")
            self.client.connect(self.broker, 1883, 60)
            self.client.loop_start()
            
            # Wait for connection
            timeout = 5
            start_time = time.time()
            while not self.connected and (time.time() - start_time) < timeout:
                time.sleep(0.1)
            
            if not self.connected:
                logger.error("❌ Connection timeout")
                return False
            
            return True
            
        except Exception as e:
            logger.error(f"❌ MQTT connection error: {e}")
            return False
    
    def disconnect(self):
        """Disconnect from MQTT broker"""
        self.stop_bot()  # Stop bot before disconnecting
        self.client.loop_stop()
        self.client.disconnect()
        logger.info("🔌 Disconnected from MQTT broker")
    
    def send_command(self, left: int, right: int, s1: int = 90, s2: int = 90):
        """
        Send command to bot via MQTT
        
        Args:
            left: Left motor speed (-100 to 100)
            right: Right motor speed (-100 to 100)
            s1: Servo 1 angle (always 90 as per requirement)
            s2: Servo 2 angle (0 to 110, with safety limits)
        """
        if not self.connected:
            logger.warning("⚠️ Not connected to MQTT broker")
            return False
        
        # Clamp motor values
        left = max(-100, min(100, int(left)))
        right = max(-100, min(100, int(right)))
        
        # Safety limits for servos
        s1 = 90  # Always 90 as per requirement
        s2 = max(0, min(110, int(s2)))  # Strict 0-110 limit
        
        # Create command payload
        payload = {
            "password": self.password,
            "L": left,
            "R": right,
            "S1": s1,
            "S2": s2
        }
        
        try:
            # Publish to MQTT
            result = self.client.publish(self.topic, json.dumps(payload))
            
            if result.rc == mqtt.MQTT_ERR_SUCCESS:
                # Update current state
                self.current_left = left
                self.current_right = right
                self.current_s1 = s1
                self.current_s2 = s2
                
                logger.debug(f"📤 Command sent: L={left}, R={right}, S1={s1}, S2={s2}")
                return True
            else:
                logger.error(f"❌ Failed to publish command. Error code: {result.rc}")
                return False
                
        except Exception as e:
            logger.error(f"❌ Error sending command: {e}")
            return False
    
    def stop_bot(self):
        """Stop all bot movement and reset servos"""
        logger.info("🛑 Stopping bot")
        self.send_command(left=0, right=0, s1=90, s2=SERVO_START)
    
    def start_tracking(self, mode: Literal["face", "hand"] = "face"):
        """Start tracking mode"""
        self.tracking_enabled = True
        self.tracking_mode = mode
        self.last_target_time = time.time()
        logger.info(f"🎯 Tracking started: {mode} mode")
    
    def stop_tracking(self):
        """Stop tracking mode"""
        self.tracking_enabled = False
        self.stop_bot()
        logger.info("🎯 Tracking stopped")
    
    def get_target_position(self, detection_data: dict) -> Optional[tuple]:
        """
        Extract target position from detection data using POSE landmarks (yellow skeleton)
        This is more stable than face detection box
        
        Returns:
            (x, y, size) or None if no target found
        """
        if self.tracking_mode == "face":
            # Priority 1: Use POSE face landmarks (more stable than face detector)
            poses = detection_data.get("poses", [])
            if poses and len(poses) > 0:
                pose = poses[0]
                landmarks = pose.get("landmarks", [])
                
                # Face landmarks in pose: 0=nose, 1=left_eye_inner, 2=left_eye, 
                # 3=left_eye_outer, 4=right_eye_inner, 5=right_eye, 6=right_eye_outer,
                # 7=left_ear, 8=right_ear, 9=mouth_left, 10=mouth_right
                if len(landmarks) >= 11:
                    # Get key face points that are usually visible
                    nose = landmarks[0]
                    left_eye = landmarks[2]
                    right_eye = landmarks[5]
                    
                    # Check visibility
                    visible_points = []
                    if nose.get("visibility", 0) > 0.3:
                        visible_points.append((nose["x"], nose["y"]))
                    if left_eye.get("visibility", 0) > 0.3:
                        visible_points.append((left_eye["x"], left_eye["y"]))
                    if right_eye.get("visibility", 0) > 0.3:
                        visible_points.append((right_eye["x"], right_eye["y"]))
                    
                    if len(visible_points) >= 2:
                        # Calculate center of visible face points
                        avg_x = sum(p[0] for p in visible_points) / len(visible_points)
                        avg_y = sum(p[1] for p in visible_points) / len(visible_points)
                        
                        x = avg_x * self.frame_width
                        y = avg_y * self.frame_height
                        
                        # Calculate size from face width
                        if left_eye.get("visibility", 0) > 0.3 and right_eye.get("visibility", 0) > 0.3:
                            face_width = abs(left_eye["x"] - right_eye["x"])
                            size = face_width * 3  # Approximate face area
                        else:
                            size = 0.15  # Default size
                        
                        logger.debug(f"📍 Using POSE face tracking: ({x:.0f}, {y:.0f})")
                        return (x, y, size)
            
            # Priority 2: Fallback to face detection box if pose fails
            faces = detection_data.get("faces", [])
            if faces and len(faces) > 0:
                largest_face = max(faces, key=lambda f: f["width"] * f["height"])
                
                x = (largest_face["x"] + largest_face["width"] / 2) * self.frame_width
                y = (largest_face["y"] + largest_face["height"] / 2) * self.frame_height
                size = largest_face["width"] * largest_face["height"]
                
                logger.debug(f"📦 Using FACE box tracking: ({x:.0f}, {y:.0f})")
                return (x, y, size)
            
            # Priority 3: Use upper body center if face not detected but body is
            if poses and len(poses) > 0:
                pose = poses[0]
                landmarks = pose.get("landmarks", [])
                
                # Use shoulders as reference (11=left_shoulder, 12=right_shoulder)
                if len(landmarks) >= 13:
                    left_shoulder = landmarks[11]
                    right_shoulder = landmarks[12]
                    
                    if (left_shoulder.get("visibility", 0) > 0.3 and 
                        right_shoulder.get("visibility", 0) > 0.3):
                        # Face should be above shoulders
                        center_x = (left_shoulder["x"] + right_shoulder["x"]) / 2
                        # Estimate face position above shoulders
                        shoulder_y = (left_shoulder["y"] + right_shoulder["y"]) / 2
                        estimated_face_y = shoulder_y - 0.15  # Face is ~15% above shoulders
                        
                        x = center_x * self.frame_width
                        y = estimated_face_y * self.frame_height
                        
                        # Estimate size from shoulder width
                        shoulder_width = abs(left_shoulder["x"] - right_shoulder["x"])
                        size = shoulder_width * 2  # Approximate
                        
                        logger.warning(f"⚠️ Face lost! Using BODY estimation, tilting UP")
                        # Signal that we should tilt UP quickly
                        return (x, y - 150, size)  # Bias upward
        
        elif self.tracking_mode == "hand":
            # Hand tracking - use palm center
            hands = detection_data.get("hands", [])
            if hands and len(hands) > 0:
                hand = hands[0]
                landmarks = hand.get("landmarks", [])
                
                if len(landmarks) >= 9:
                    wrist = landmarks[0]
                    middle_base = landmarks[9]
                    
                    x = ((wrist["x"] + middle_base["x"]) / 2) * self.frame_width
                    y = ((wrist["y"] + middle_base["y"]) / 2) * self.frame_height
                    size = 0.1
                    
                    return (x, y, size)
        
        return None
    
    def update_tracking(self, detection_data: dict):
        """
        Update bot position based on detection data
        
        Args:
            detection_data: Detection results from MediaPipe
        """
        if not self.tracking_enabled:
            return
        
        # Get target position
        target = self.get_target_position(detection_data)
        
        if target is None:
            # No target detected - STOP IMMEDIATELY (don't keep spinning!)
            logger.warning("⚠️ No target detected, stopping bot")
            self.send_command(left=0, right=0, s1=90, s2=self.current_s2)
            return
        
        # Target found
        self.last_target_time = time.time()
        target_x, target_y, target_size = target
        
        # Calculate errors (distance from center)
        # Positive error_x = target is to the RIGHT
        # Negative error_x = target is to the LEFT
        # Positive error_y = target is BELOW center
        # Negative error_y = target is ABOVE center
        error_x = target_x - self.center_x
        error_y = target_y - self.center_y
        
        # Mirror mode: flip X-axis for front-facing phone cameras
        if self.mirror_mode:
            error_x = -error_x
        
        logger.debug(f"🎯 Target at ({target_x:.0f}, {target_y:.0f}), "
                    f"Error: X={error_x:.0f}, Y={error_y:.0f}")
        
        # Check if target is within dead zone
        if abs(error_x) < self.dead_zone_x and abs(error_y) < self.dead_zone_y:
            # Target is centered, stop movement
            logger.debug("✅ Target centered - stopping")
            self.send_command(left=0, right=0, s1=90, s2=self.current_s2)
            return
        
        # Initialize speeds
        left_speed = 0
        right_speed = 0
        
        # --- HORIZONTAL MOVEMENT (Left/Right Rotation) ---
        # ASYMMETRIC SPEED - Smoother turning with different wheel speeds
        if abs(error_x) > self.dead_zone_x:
            fast_wheel_speed = 20  # Outer wheel (faster)
            slow_wheel_speed = 12  # Inner wheel (slower) - creates gentler turn
            
            if error_x > 0:
                # Target is to the RIGHT - need to turn RIGHT
                # Right turn = left motor forward (fast), right motor backward (slow)
                left_speed = fast_wheel_speed    # Left wheel forward at 20
                right_speed = -slow_wheel_speed  # Right wheel backward at -12
                logger.debug(f"↪️ Turning RIGHT: L=20, R=-12")
            else:
                # Target is to the LEFT - need to turn LEFT
                # Left turn = left motor backward (slow), right motor forward (fast)
                left_speed = -slow_wheel_speed   # Left wheel backward at -12
                right_speed = fast_wheel_speed   # Right wheel forward at 20
                logger.debug(f"↩️ Turning LEFT: L=-12, R=20")
        
        # --- VERTICAL MOVEMENT (Servo S2) ---
        # Determine servo direction based on error with velocity protection
        current_time = time.time()
        
        if abs(error_y) > self.dead_zone_y:
            # Determine direction
            if error_y > 0:
                self.servo_direction = 1  # Target below, tilt down
            else:
                self.servo_direction = -1  # Target above, tilt up
            
            # Move servo every 150ms
            if (current_time - self.last_servo_time) >= self.servo_interval:
                new_angle = self.current_s2 + (self.servo_direction * self.servo_step)
                
                # Apply strict safety limits with velocity-based protection
                SAFE_MIN = SERVO_MIN + 5
                SAFE_MAX = SERVO_MAX - 5
                
                # If approaching edge, slow down or stop based on velocity
                approaching_bottom = (new_angle >= SAFE_MAX - 10) and self.servo_direction > 0
                approaching_top = (new_angle <= SAFE_MIN + 10) and self.servo_direction < 0
                
                if approaching_bottom or approaching_top:
                    # Stop movement and pull back slightly
                    if approaching_bottom:
                        self.current_s2 = min(self.current_s2, SAFE_MAX - 2)  # Stay 2° away from edge
                        logger.debug(f"🛑 Servo at bottom edge, retreating to {self.current_s2:.0f}°")
                    else:
                        self.current_s2 = max(self.current_s2, SAFE_MIN + 2)  # Stay 2° away from edge
                        logger.debug(f"🛑 Servo at top edge, retreating to {self.current_s2:.0f}°")
                    self.servo_direction = 0  # Stop movement
                else:
                    self.current_s2 = max(SAFE_MIN, min(SAFE_MAX, new_angle))
                
                self.last_servo_time = current_time
                
                if self.servo_direction > 0:
                    logger.debug(f"⬇️ Servo DOWN: {new_angle:.0f}°")
                elif self.servo_direction < 0:
                    logger.debug(f"⬆️ Servo UP: {new_angle:.0f}°")
        else:
            self.servo_direction = 0  # Centered, stop servo
        
        # Use current servo position for command
        new_s2 = self.current_s2
        
        # --- FORWARD/BACKWARD MOVEMENT (Based on target size) ---
        # Only move forward/backward if horizontally centered
        if abs(error_x) < self.dead_zone_x * 1.5:
            # Target size thresholds
            optimal_size = OPTIMAL_TARGET_SIZE
            size_tolerance = SIZE_TOLERANCE
            
            if target_size < (optimal_size - size_tolerance):
                # Target too small (too far), move forward
                forward_speed = FORWARD_SPEED
                left_speed += forward_speed
                right_speed += forward_speed
                logger.debug(f"⬆️ Moving FORWARD (target too small: {target_size:.3f})")
                
            elif target_size > (optimal_size + size_tolerance):
                # Target too large (too close), move backward
                backward_speed = -BACKWARD_SPEED
                left_speed += backward_speed
                right_speed += backward_speed
                logger.debug(f"⬇️ Moving BACKWARD (target too large: {target_size:.3f})")
        
        # Final clamping to safe ranges
        left_speed = max(-100, min(100, int(left_speed)))
        right_speed = max(-100, min(100, int(right_speed)))
        
        # Send command to bot
        self.send_command(
            left=left_speed,
            right=right_speed,
            s1=90,
            s2=int(new_s2)
        )
        
        logger.info(f"📤 Command: L={left_speed}, R={right_speed}, S2={int(new_s2)}")


# Example usage and testing
if __name__ == "__main__":
    # Create controller
    controller = MQTTBotController(
        broker="broker.emqx.io",
        topic="LDrago_windows/ducky_script",
        password="E1s2t3e4r5"
    )
    
    # Connect to MQTT
    if controller.connect():
        print("✅ Connected successfully!")
        
        # Test commands
        print("\n🧪 Testing bot commands...\n")
        
        # Stop
        print("1. Stop bot")
        controller.send_command(0, 0, 90, 90)
        time.sleep(2)
        
        # Move forward
        print("2. Move forward")
        controller.send_command(50, 50, 90, 90)
        time.sleep(2)
        
        # Stop
        print("3. Stop")
        controller.send_command(0, 0, 90, 90)
        time.sleep(1)
        
        # Turn right
        print("4. Turn right")
        controller.send_command(50, -50, 90, 90)
        time.sleep(2)
        
        # Stop
        print("5. Stop")
        controller.send_command(0, 0, 90, 90)
        time.sleep(1)
        
        # Tilt servo down
        print("6. Tilt camera down")
        for angle in range(90, 111, 5):
            controller.send_command(0, 0, 90, angle)
            time.sleep(0.5)
        
        # Tilt servo up
        print("7. Tilt camera up")
        for angle in range(110, -1, -5):
            controller.send_command(0, 0, 90, angle)
            time.sleep(0.5)
        
        # Center servo
        print("8. Center camera")
        controller.send_command(0, 0, 90, 90)
        time.sleep(1)
        
        # Disconnect
        controller.disconnect()
        print("\n✅ Test complete!")
    else:
        print("❌ Failed to connect to MQTT broker")
