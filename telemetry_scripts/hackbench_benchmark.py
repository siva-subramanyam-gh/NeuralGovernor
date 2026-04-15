import subprocess
import time

# ==========================================
# CONFIGURATION
# ==========================================
govs = ["walt", "neural"]
runs = 10

def send_cmd(cmd_str):
    try:
        res = subprocess.run(cmd_str, shell=True, capture_output=True, text=True, check=True)
        return res.stdout.strip()
    except subprocess.CalledProcessError:
        return ""

def change_gov(g_name):
    print(f"\n--- Switching CPU to {g_name.upper()} ---")
    cmd = [
        "adb", "shell", 
        f"su -c 'for p in /sys/devices/system/cpu/cpufreq/policy*; do chmod 644 $p/scaling_governor; echo {g_name} > $p/scaling_governor; chmod 444 $p/scaling_governor; done'"
    ]
    subprocess.run(cmd, capture_output=True)
    time.sleep(2) 

def run_stress_test(g_name):
    total_time = 0.0
    valid_runs = 0
    
    for i in range(1, runs + 1):
        print(f"  -> Crunching run {i}/{runs}... (Please wait)")
        test_cmd = "adb shell \"su -c 'LD_LIBRARY_PATH=/data/data/com.termux/files/usr/lib /data/local/tmp/hackbench 10 thread 1000'\""
        out_text = send_cmd(test_cmd)
        
        if "Time:" in out_text:
            time_str = out_text.split("Time:")[1].strip()
            time_val = float(time_str)
            print(f"     Result: {time_val} seconds")
            
            total_time = total_time + time_val
            valid_runs = valid_runs + 1
        else:
            print(f"     Failed: Could not parse output.")
            
        time.sleep(1) 
        
    if valid_runs > 0:
        avg = total_time / valid_runs
        print(f"\n[WIN] {g_name.upper()} Average Overhead: {round(avg, 3)} seconds")
    else:
        print("\n[!] Error: Could not calculate average.")

def main():
    print("Starting Kernel Scheduler Stress Test...")
    send_cmd("adb shell input keyevent 224")
    
    for g in govs:
        change_gov(g)
        run_stress_test(g)
        
        print("\nLetting the phone cool down for 15 seconds...")
        time.sleep(15)
        
    print("\nStress test complete!")

if __name__ == "__main__":
    try:
        main()
    except KeyboardInterrupt:
        print("\nTest aborted.")