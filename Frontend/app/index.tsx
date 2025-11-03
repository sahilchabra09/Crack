import { useState, useEffect, useRef } from 'react';
import { Text, TouchableOpacity, View } from 'react-native';
import { DeviceMotion } from 'expo-sensors';
import type { Subscription } from 'expo-sensors/build/DeviceSensor';

export default function Index() {
  const [angles, setAngles] = useState({
    roll: 0,
    pitch: 0,
    yaw: 0,
  });
  const [subscription, setSubscription] = useState<Subscription | null>(null);
  const initialAngles = useRef<{ roll: number; pitch: number; yaw: number } | null>(null);

  const radToDeg = (rad: number) => (rad * 180) / Math.PI;

  const _slow = () => DeviceMotion.setUpdateInterval(1000);
  const _fast = () => DeviceMotion.setUpdateInterval(16);

  const _subscribe = () => {
    initialAngles.current = null;
    
    setSubscription(
      DeviceMotion.addListener(data => {
        if (data.rotation) {
          const currentRoll = radToDeg(data.rotation.beta);  // Roll (X-axis)
          const currentPitch = radToDeg(data.rotation.gamma); // Pitch (Y-axis)
          const currentYaw = radToDeg(data.rotation.alpha);   // Yaw (Z-axis)
          
          // Set initial angles on first reading
          if (!initialAngles.current) {
            initialAngles.current = {
              roll: currentRoll,
              pitch: currentPitch,
              yaw: currentYaw,
            };
          }
          
          // Calculate relative angles from initial position
          let relativeRoll = currentRoll - initialAngles.current.roll;
          let relativePitch = currentPitch - initialAngles.current.pitch;
          let relativeYaw = currentYaw - initialAngles.current.yaw;
          
          // Handle wrap-around for yaw (0-360 degrees)
          if (relativeYaw > 180) relativeYaw -= 360;
          if (relativeYaw < -180) relativeYaw += 360;
          
          setAngles({
            roll: relativeRoll,
            pitch: relativePitch,
            yaw: relativeYaw,
          });
        }
      })
    );
  };

  const _unsubscribe = () => {
    subscription && subscription.remove();
    setSubscription(null);
    // Reset angles when stopping
    initialAngles.current = null;
    setAngles({ roll: 0, pitch: 0, yaw: 0 });
  };

  const _reset = () => {
    // Reset angles to zero without stopping
    initialAngles.current = null;
    setAngles({ roll: 0, pitch: 0, yaw: 0 });
  };

  useEffect(() => {
    _subscribe();
    return () => _unsubscribe();
  }, []);

  return (
    <View className="flex-1 justify-center px-10 bg-gray-900">
      <Text className="text-4xl font-bold text-center mb-8 text-white">
        Gyroscope Angles
      </Text>
      
      <View className="bg-gray-800 rounded-2xl p-6 mb-6 shadow-lg">
        <View className="mb-4">
          <Text className="text-gray-400 text-sm uppercase tracking-wide mb-1">Roll (X-axis)</Text>
          <Text className="text-white text-3xl font-bold">
            {angles.roll.toFixed(2)}°
          </Text>
        </View>
        
        <View className="mb-4">
          <Text className="text-gray-400 text-sm uppercase tracking-wide mb-1">Pitch (Y-axis)</Text>
          <Text className="text-white text-3xl font-bold">
            {angles.pitch.toFixed(2)}°
          </Text>
        </View>
        
        <View className="mb-0">
          <Text className="text-gray-400 text-sm uppercase tracking-wide mb-1">Yaw (Z-axis)</Text>
          <Text className="text-white text-3xl font-bold">
            {angles.yaw.toFixed(2)}°
          </Text>
        </View>
      </View>
      
      <View className="flex-row mt-4 mb-4">
        <TouchableOpacity 
          onPress={subscription ? _unsubscribe : _subscribe} 
          className={`flex-1 justify-center items-center py-4 rounded-lg ${subscription ? 'bg-green-600' : 'bg-gray-600'}`}
        >
          <Text className="text-white font-semibold text-lg">
            {subscription ? 'On' : 'Off'}
          </Text>
        </TouchableOpacity>
        
        <TouchableOpacity 
          onPress={_reset} 
          className="flex-1 justify-center items-center bg-red-600 py-4 rounded-lg ml-2"
        >
          <Text className="text-white font-semibold text-lg">Reset</Text>
        </TouchableOpacity>
      </View>
      
      <View className="flex-row">
        <TouchableOpacity 
          onPress={_slow} 
          className="flex-1 justify-center items-center bg-blue-600 py-4 rounded-lg mr-2"
        >
          <Text className="text-white font-semibold text-lg">Slow</Text>
        </TouchableOpacity>
        
        <TouchableOpacity 
          onPress={_fast} 
          className="flex-1 justify-center items-center bg-purple-600 py-4 rounded-lg"
        >
          <Text className="text-white font-semibold text-lg">Fast</Text>
        </TouchableOpacity>
      </View>
    </View>
  );
}

