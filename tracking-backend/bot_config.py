"""
Bot Tracking Configuration
Adjust these values to tune the bot's tracking behavior
"""

# ====================
# TRACKING SENSITIVITY
# ====================

# Dead zones (pixels) - No movement within this zone
DEAD_ZONE_X = 250  # Horizontal (increased for more stability)
DEAD_ZONE_Y = 100  # Vertical (increased to reduce oscillation)

# Rotation sensitivity (0.1 to 1.0)
# Higher = faster rotation, Lower = slower/smoother rotation
ROTATION_GAIN = 0.15  # Reduced for smoother, more controlled rotation

# Servo sensitivity (0.01 to 0.2)
# Higher = faster servo movement, Lower = slower/smoother
SERVO_GAIN = 0.08  # How much to adjust target based on error (degrees per pixel)

# Maximum servo change per frame (degrees)
# NOT USED ANYMORE - using smooth interpolation instead
MAX_SERVO_CHANGE_PER_FRAME = 10  # Not limiting target calculation

# ====================
# MOVEMENT SPEEDS
# ====================

# Asymmetric turning speeds for smoother turns
FAST_WHEEL_SPEED = 20  # Outer wheel speed
SLOW_WHEEL_SPEED = 12  # Inner wheel speed (gentler turn)

# Forward/backward speeds when adjusting distance
FORWARD_SPEED = 30   # Forward speed (faster for better tracking)
BACKWARD_SPEED = 15  # Backward speed (slower, more careful)

# Starting position (middle, not downward)
SERVO_START = 55  # Middle position (50% of 110)

# ====================
# DISTANCE CONTROL
# ====================

# Optimal target size as percentage of frame (0.0 to 1.0)
# 0.18 = target should occupy 18% of frame (much closer!)
OPTIMAL_TARGET_SIZE = 0.18

# Size tolerance - won't move forward/back within this range
SIZE_TOLERANCE = 0.03

# ====================
# TIMING
# ====================

# How long to wait before stopping when target is lost (seconds)
TARGET_LOST_TIMEOUT = 1.0

# ====================
# SERVO LIMITS
# ====================

# Servo S2 range (DO NOT EXCEED 0-110 or bot may damage itself!)
SERVO_MIN = 0   # Up
SERVO_MAX = 110 # Down

# Starting position (middle, not downward)
SERVO_START = 55  # Middle position (50% of 110)

# ====================
# TUNING GUIDE
# ====================
"""
PROBLEM: Bot oscillates/jitters when tracking
SOLUTION: Increase DEAD_ZONE_X and DEAD_ZONE_Y

PROBLEM: Bot responds too slowly
SOLUTION: Decrease DEAD_ZONE_X/Y, increase ROTATION_GAIN

PROBLEM: Servo moves too fast/jerky
SOLUTION: Decrease SERVO_GAIN and MAX_SERVO_CHANGE_PER_FRAME

PROBLEM: Bot turns in wrong direction
SOLUTION: This is fixed in the code - should work correctly now!

PROBLEM: Bot moves too far forward/backward
SOLUTION: Adjust OPTIMAL_TARGET_SIZE (larger = bot stays farther away)

PROBLEM: Servo randomly jumps
SOLUTION: Decrease SERVO_GAIN to 0.03 or lower

PROBLEM: Bot too aggressive
SOLUTION: 
  - Decrease ROTATION_GAIN to 0.2
  - Decrease MAX_TURN_SPEED to 40
  - Increase DEAD_ZONE_X to 200

PROBLEM: Bot too passive/slow
SOLUTION:
  - Increase ROTATION_GAIN to 0.5
  - Increase MAX_TURN_SPEED to 80
  - Decrease DEAD_ZONE_X to 100
"""

# ====================
# PRESET CONFIGURATIONS
# ====================

# Smooth & Stable (Recommended for beginners)
PRESET_SMOOTH = {
    'DEAD_ZONE_X': 180,
    'DEAD_ZONE_Y': 120,
    'ROTATION_GAIN': 0.25,
    'SERVO_GAIN': 0.04,
    'MAX_SERVO_CHANGE_PER_FRAME': 2,
    'MAX_TURN_SPEED': 50,
}

# Responsive & Fast (For experienced users)
PRESET_FAST = {
    'DEAD_ZONE_X': 100,
    'DEAD_ZONE_Y': 80,
    'ROTATION_GAIN': 0.5,
    'SERVO_GAIN': 0.08,
    'MAX_SERVO_CHANGE_PER_FRAME': 5,
    'MAX_TURN_SPEED': 80,
}

# Aggressive (For demos/testing)
PRESET_AGGRESSIVE = {
    'DEAD_ZONE_X': 80,
    'DEAD_ZONE_Y': 60,
    'ROTATION_GAIN': 0.7,
    'SERVO_GAIN': 0.1,
    'MAX_SERVO_CHANGE_PER_FRAME': 7,
    'MAX_TURN_SPEED': 100,
}

# Very Smooth (For precise applications)
PRESET_VERY_SMOOTH = {
    'DEAD_ZONE_X': 200,
    'DEAD_ZONE_Y': 150,
    'ROTATION_GAIN': 0.15,
    'SERVO_GAIN': 0.03,
    'MAX_SERVO_CHANGE_PER_FRAME': 1,
    'MAX_TURN_SPEED': 35,
}
