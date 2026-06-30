import multiprocessing
import threading
import time
import os

# 0 = No Lag, 50 = Heavy Lag, 100 = 100% CPU Spiked Max
CURRENT_THROTTLE_PERCENTAGE = 50

_SHUTDOWN_SIGNAL = False
_SHARED_VALUE = None
_WORKER_PROCESSES = []

def _core_stress_loop(shared_target):
    """Max-throughput process loop designed to force 100% hardware saturation."""
    while True:
        target = shared_target.value
        if target <= 0:
            time.sleep(0.05)
            continue
            
        # Linear raw scaling to guarantee 100% target fills the entire timeline
        factor = target / 100.0
        
        slice_start = time.perf_counter()
        run_duration = 0.02 * factor
        rest_duration = 0.02 * (1.0 - factor)
        
        # Raw, mathematical operation to completely blind the CPU execution units
        while time.perf_counter() - slice_start < run_duration:
            # Shift bits in an infinite memory loop to bypass OS throttling logic
            _ = 1 << 30
            
        if rest_duration > 0:
            time.sleep(rest_duration)

def _manager_background_thread():
    """Background thread that synchronizes the global variable and spawns 2x oversubscribed workers."""
    global CURRENT_THROTTLE_PERCENTAGE, _SHUTDOWN_SIGNAL, _SHARED_VALUE, _WORKER_PROCESSES
    
    # Detect cores and double them to completely overwhelm the OS scheduler
    num_cores = os.cpu_count() or 10
    total_workers = num_cores * 2 
    
    _SHARED_VALUE = multiprocessing.Value('d', float(CURRENT_THROTTLE_PERCENTAGE))
    
    # Flood the system with twice as many processes as physical cores
    for _ in range(total_workers):
        p = multiprocessing.Process(target=_core_stress_loop, args=(_SHARED_VALUE,))
        p.daemon = True
        p.start()
        _WORKER_PROCESSES.append(p)
        
    while not _SHUTDOWN_SIGNAL:
        if _SHARED_VALUE.value != float(CURRENT_THROTTLE_PERCENTAGE):
            _SHARED_VALUE.value = float(CURRENT_THROTTLE_PERCENTAGE)
        time.sleep(0.01)
        
    for p in _WORKER_PROCESSES:
        p.terminate()

def start_pc_throttle():
    """Call this once to activate the 100% max capacity background engines."""
    t = threading.Thread(target=_manager_background_thread)
    t.daemon = True
    t.start()

def stop_pc_throttle():
    """Instantly kills all worker processes and returns CPU to idle state."""
    global _SHUTDOWN_SIGNAL
    _SHUTDOWN_SIGNAL = True

if __name__ == "__main__":
    print("Initializing heavy multi-process overload engine...")
    start_pc_throttle()
    print("Overload engine active. Main thread is completely responsive.")
    
    try:
        while True:
            print(f"\n[Main Thread] CURRENT_THROTTLE_PERCENTAGE: {CURRENT_THROTTLE_PERCENTAGE}%")
            print("Type a number (0-100) to adjust lag, or 'exit':")
            
            user_input = input("> ")
            if user_input.strip().lower() == 'exit':
                break
                
            try:
                val = int(user_input)
                if 0 <= val <= 100:
                    CURRENT_THROTTLE_PERCENTAGE = val
                else:
                    print("Enter a number between 0 and 100.")
            except ValueError:
                print("Please enter a valid integer.")
                
    except KeyboardInterrupt:
        print("\nAborting...")
        
    stop_pc_throttle()
    print("System restored to normal performance.")
