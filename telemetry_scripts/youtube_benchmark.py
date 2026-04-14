import subprocess
import time
import csv
import sys
import os

# ==========================================
# CONFIGURATION
# ==========================================
GOVERNORS = ["neural", "walt"]
RUN_DURATION = 1800  # 30 Minutes
POLL_RATE = 2.0      # 2-second polling to reduce overhead
BRIGHTNESS = 100     
VOLUME = 0           
VIDEO_ID = "LXb3EKWsInQ" 
APP_PACKAGE = "com.google.android.youtube"

def run_cmd(cmd):
    try:
        result = subprocess.run(cmd, shell=True, capture_output=True, text=True, check=True)
        return result.stdout.strip()
    except subprocess.CalledProcessError:
        return ""

def setup_device():
    print(f"[PRE-FLIGHT] Normalizing device: Brightness={BRIGHTNESS}, Volume={VOLUME}")
    run_cmd(f"adb shell settings put system screen_brightness {BRIGHTNESS}")
    run_cmd(f"adb shell media volume --set {VOLUME}")
    run_cmd("adb shell svc power stayon usb")
    run_cmd("adb shell input keyevent 224") 
    run_cmd("adb shell input keyevent 82")  
    time.sleep(1)

def set_gov(gov_name):
    print(f"\n[SYSTEM] Transitioning CPU governor to: {gov_name.upper()}")
    cmd = [
        "adb", "shell", 
        f"su -c 'for p in /sys/devices/system/cpu/cpufreq/policy*; do chmod 644 $p/scaling_governor; echo {gov_name} > $p/scaling_governor; chmod 444 $p/scaling_governor; done'"
    ]
    subprocess.run(cmd, capture_output=True)
    
    current = run_cmd("adb shell cat /sys/devices/system/cpu/cpufreq/policy0/scaling_governor")
    if current != gov_name:
        print(f"[!] FATAL: Failed to lock governor. Expected {gov_name}, got {current}")
        sys.exit(1)
    print(f"[SYSTEM] Successfully locked to {current}")

def get_cpu_freq():
    # Scans the specific cluster policies for Snapdragon 8s Gen 3
    # 0 = Small, 4 = Big, 7 = Prime
    freqs = []
    for policy in [0, 3, 7]:
        raw_output = run_cmd(f"adb shell \"su -c 'cat /sys/devices/system/cpu/cpufreq/policy{policy}/scaling_cur_freq'\"")
        try:
            freqs.append(round(int(raw_output.strip()) / 1000.0, 1)) # Convert to MHz
        except ValueError:
            # If the core is offline/sleeping, it won't return an integer
            freqs.append(0.0) 
            
    return freqs[0], freqs[1], freqs[2]

def get_sensors():
    v_str = run_cmd("adb shell \"su -c 'cat /sys/class/power_supply/battery/voltage_now'\"")
    i_str = run_cmd("adb shell \"su -c 'cat /sys/class/power_supply/battery/current_now'\"")
    t_str = run_cmd("adb shell \"su -c 'cat /sys/class/power_supply/battery/temp'\"")
    
    f0, f4, f7 = get_cpu_freq()
    
    try:
        volts = float(v_str) / 1000000.0
        amps = abs(float(i_str)) / 1000000.0 
        watts = volts * amps
        temp_c = float(t_str) / 10.0
        return temp_c, round(watts, 3), f0, f4, f7
    except ValueError:
        return 0.0, 0.0, 0.0, 0.0, 0.0

def run_test(gov_name):
    print(f"\n==================================================")
    print(f"  STARTING 30-MIN YOUTUBE TEST: {gov_name.upper()}")
    print(f"==================================================")
    
    print(f"[TEST] Waking YouTube app...")
    run_cmd(f"adb shell monkey -p {APP_PACKAGE} -c android.intent.category.LAUNCHER 1")
    time.sleep(3) 
    
    print(f"[TEST] Injecting native video stream intent...")
    run_cmd(f'adb shell am start -a android.intent.action.VIEW -d "vnd.youtube:{VIDEO_ID}" {APP_PACKAGE}')
    time.sleep(8) 
    
    run_cmd("adb shell input tap 540 1200")
    time.sleep(1)
    run_cmd("adb shell input tap 540 1200")

    start_t = time.perf_counter()
    end_t = start_t + RUN_DURATION
    
    file_name = f"youtube_drain_{gov_name}.csv"
    with open(file_name, mode='w', newline='') as f:
        csv_writer = csv.writer(f)
        # Added distinct columns for each cluster
        csv_writer.writerow(["Time(s)", "Temp(C)", "Power(W)", "Freq0(MHz)", "Freq4(MHz)", "Freq7(MHz)"])
        f.flush()

        print(f"[TEST] Telemetry running. Live-writing to {file_name}...")

        while True:
            now = time.perf_counter()
            elapsed_sec = now - start_t
            
            if elapsed_sec >= RUN_DURATION:
                break
                
            temp, pwr, f0, f4, f7 = get_sensors()
            
            csv_writer.writerow([round(elapsed_sec, 2), temp, pwr, f0, f4, f7])
            f.flush()
            os.fsync(f.fileno()) 
            
            if int(elapsed_sec) % 60 == 0:
                print(f"   -> {int(elapsed_sec)//60} min / 30 min | Pwr: {pwr}W | F0: {f0} F4: {f4} F7: {f7} | Temp: {temp}°C")
                
            if int(elapsed_sec) > 0 and int(elapsed_sec) % 60 == 0:
                run_cmd("adb shell input tap 10 10")
            
            time_left = POLL_RATE - (time.perf_counter() - now)
            if time_left > 0:
                time.sleep(time_left)

    print(f"\n[TEST] 30 minutes elapsed. Force killing YouTube.")
    run_cmd(f"adb shell am force-stop {APP_PACKAGE}")

def main():
    print("Initializing NextGenRL Race-to-Idle Video Test...")
    run_cmd(f"adb shell am force-stop {APP_PACKAGE}")
    setup_device()
    
    for gov in GOVERNORS:
        set_gov(gov)
        run_test(gov)
        print("\n[SYSTEM] Run complete. Cooling/Settling for 2 minutes...")
        time.sleep(120) 

    run_cmd("adb shell svc power stayon false")
    print("\n[SYSTEM] All cycles successfully completed.")

if __name__ == "__main__":
    try:
        main()
    except KeyboardInterrupt:
        print("\n[!] Test aborted by user.")
        run_cmd(f"adb shell am force-stop {APP_PACKAGE}")
        run_cmd("adb shell svc power stayon false")
        sys.exit(0)