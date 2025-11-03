"""
Simple Hardware Monitor
Checks if system can handle parallel processing
"""

import psutil
import os

def get_simple_hardware_info():
    """
    Get basic hardware information
    Simple and easy to understand
    
    Returns:
        Dictionary with hardware info
    """
    try:
        # CPU information
        cpu_count = os.cpu_count()
        cpu_percent = psutil.cpu_percent(interval=1)
        
        # Memory information
        memory = psutil.virtual_memory()
        memory_available_gb = memory.available / (1024**3)  # Convert to GB
        memory_percent_used = memory.percent
        
        # Disk information (for the current directory)
        disk = psutil.disk_usage('.')
        disk_free_gb = disk.free / (1024**3)  # Convert to GB
        
        # Check Python environment type
        import sys
        python_executable = sys.executable
        is_windows_store_python = 'WindowsApps' in python_executable
        
        return {
            'cpu_cores': cpu_count,
            'cpu_usage_percent': cpu_percent,
            'memory_available_gb': round(memory_available_gb, 1),
            'memory_used_percent': memory_percent_used,
            'disk_free_gb': round(disk_free_gb, 1),
            'python_type': 'Windows Store Python' if is_windows_store_python else 'Regular Python',
            'playwright_compatible': not is_windows_store_python
        }
        
    except Exception as e:
        print(f"❌ Error getting hardware info: {e}")
        return {
            'cpu_cores': 1,
            'cpu_usage_percent': 50,
            'memory_available_gb': 1.0,
            'memory_used_percent': 50,
            'disk_free_gb': 1.0,
            'python_type': 'Unknown',
            'playwright_compatible': False
        }

def can_handle_parallel(hardware_info):
    """
    Simple check - can we handle parallel processing?
    
    Args:
        hardware_info: Result from get_simple_hardware_info()
    
    Returns:
        True if system can handle parallel processing, False otherwise
    """
    # Simple rules for parallel processing
    
    # Need at least 2 CPU cores
    if hardware_info['cpu_cores'] < 2:
        print("🔄 Single core detected - using sequential processing")
        return False
    
    # CPU shouldn't be too busy
    if hardware_info['cpu_usage_percent'] > 80:
        print("🔄 CPU usage high - using sequential processing")
        return False
    
    # Need at least 1GB available memory
    if hardware_info['memory_available_gb'] < 1.0:
        print("🔄 Low memory - using sequential processing")
        return False
    
    # Memory shouldn't be too full
    if hardware_info['memory_used_percent'] > 90:
        print("🔄 Memory usage high - using sequential processing")
        return False
    
    print("🚀 System can handle parallel processing")
    return True

def get_optimal_parallel_count(hardware_info):
    """
    Simple calculation - how many parallel operations can we handle?
    
    Args:
        hardware_info: Result from get_simple_hardware_info()
    
    Returns:
        Number of parallel operations (1-8)
    """
    if not can_handle_parallel(hardware_info):
        return 1
    
    # Start with CPU cores
    parallel_count = hardware_info['cpu_cores']
    
    # Reduce if memory is limited
    if hardware_info['memory_available_gb'] < 2:
        parallel_count = min(parallel_count, 2)
    elif hardware_info['memory_available_gb'] < 4:
        parallel_count = min(parallel_count, 3)
    
    # Reduce if CPU is busy
    if hardware_info['cpu_usage_percent'] > 50:
        parallel_count = max(1, parallel_count - 1)
    
    # Cap at reasonable maximum
    parallel_count = min(parallel_count, 8)
    
    print(f"🎯 Optimal parallel operations: {parallel_count}")
    return parallel_count

def print_hardware_status():
    """
    Print current hardware status in a human-readable way
    """
    info = get_simple_hardware_info()
    
    print("\n🖥️ Hardware Status:")
    print(f"   CPU Cores: {info['cpu_cores']}")
    print(f"   CPU Usage: {info['cpu_usage_percent']}%")
    print(f"   Available Memory: {info['memory_available_gb']} GB")
    print(f"   Memory Usage: {info['memory_used_percent']}%")
    print(f"   Free Disk Space: {info['disk_free_gb']} GB")
    
    if can_handle_parallel(info):
        parallel_count = get_optimal_parallel_count(info)
        print(f"   ✅ Can handle {parallel_count} parallel operations")
    else:
        print(f"   ⚠️ Sequential processing recommended")
    print()