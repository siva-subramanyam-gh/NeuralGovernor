import subprocess
import time
import csv
import sys

# ==========================================
# CONFIGURATION
# ==========================================
GOVERNORS = ["walt", "neural"]
RUNS_PER_GOV = 5
COOLDOWN_TEMP = 38.0       # Celsius
POLL_RATE = 1.0            # Telemetry polling interval (seconds)
TEST_DURATION = 300        # Fixed test length (300 seconds = 5 minutes)

# Skynet CPU Throttling Test "START TEST" button coordinates.
# Update these using the 'Pointer Location' tool in Developer Options!
TAP_X = 540
TAP_Y = 1200 

APP_PACKAGE = "skynet.cputhrottlingtest"

def run_cmd(cmd):
    try:
        result = subprocess.run(cmd, shell=True, capture_output=True, text=True, check=True)
        return result.stdout.strip()
    except subprocess.CalledProcessError:
        return ""

def set_governor(gov):
    print(f"\n[SYSTEM] Transitioning CPU governor to: {gov.upper()}")
    cmd = [
        "adb", "shell", 
        f"su -c 'for p in /sys/devices/system/cpu/cpufreq/policy*; do chmod 644 $p/scaling_governor; echo {gov} > $p/scaling_governor; chmod 444 $p/scaling_governor; done'"
    ]
    subprocess.run(cmd, capture_output=True)
        
    current = run_cmd("adb shell cat /sys/devices/system/cpu/cpufreq/policy0/scaling_governor")
    if current != gov:
        print(f"[!] FATAL: Failed to lock governor. Expected {gov}, got {current}")
        sys.exit(1)
    print(f"[SYSTEM] Successfully locked to {current}")

def get_battery_temp():
    raw = run_cmd("adb shell \"su -c 'cat /sys/class/power_supply/battery/temp'\"")
    try:
        return float(raw) / 10.0
    except ValueError:
        return 99.0 

def wait_for_cooldown():
    print(f"\n[SYSTEM] Purging {APP_PACKAGE} for clean cooldown...")
    run_cmd(f"adb shell am force-stop {APP_PACKAGE}")
    time.sleep(2)
    
    print(f"[THERMAL] Waiting for device to cool to {COOLDOWN_TEMP}°C...")
    while True:
        temp = get_battery_temp()
        if temp <= COOLDOWN_TEMP:
            print(f"\n[THERMAL] Target reached. Current temp: {temp}°C. Proceeding.")
            break
        sys.stdout.write(f"\r[THERMAL] Current temp: {temp}°C... cooling.")
        sys.stdout.flush()
        time.sleep(5)

def get_gov_memory(gov):
    if gov == "neural":
        raw = run_cmd("adb shell \"su -c 'lsmod | grep cpufreq_nextgenrl'\"")
        if raw:
            try:
                size_bytes = int(raw.split()[1])
                return round(size_bytes / 1024.0, 2)
            except (IndexError, ValueError):
                pass
        return 0.0
    else:
        return 0.0

def get_telemetry():
    volts_raw = run_cmd("adb shell \"su -c 'cat /sys/class/power_supply/battery/voltage_now'\"")
    amps_raw = run_cmd("adb shell \"su -c 'cat /sys/class/power_supply/battery/current_now'\"")
    temp = get_battery_temp()
    
    try:
        v = float(volts_raw) / 1000000.0
        i = abs(float(amps_raw)) / 1000000.0 
        watts = v * i
        return temp, round(v, 3), round(i, 3), round(watts, 3)
    except ValueError:
        return temp, 0.0, 0.0, 0.0

def take_screenshot(gov, run_num):
    filename = f"skynet_gips_{gov}_run{run_num}.png"
    print(f"\n[TEST] Snapping screenshot of live GIPS graph: {filename}")
    run_cmd("adb shell screencap -p /data/local/tmp/sc.png")
    run_cmd(f"adb pull /data/local/tmp/sc.png {filename} > /dev/null 2>&1")
    run_cmd("adb shell rm /data/local/tmp/sc.png")

def run_benchmark(gov, run_num):
    print(f"\n==================================================")
    print(f"  STARTING SKYNET THROTTLE TEST: {gov.upper()} (Run {run_num}/{RUNS_PER_GOV})")
    print(f"  Target Duration: {TEST_DURATION} seconds")
    print(f"==================================================")

    # Wake and Launch
    run_cmd("adb shell svc power stayon usb")
    run_cmd("adb shell input keyevent 224")
    time.sleep(1)

    print(f"[TEST] Launching {APP_PACKAGE}...")
    run_cmd(f"adb shell monkey -p {APP_PACKAGE} -c android.intent.category.LAUNCHER 1 > /dev/null 2>&1")
    time.sleep(5)

    print(f"[TEST] Tapping 'START TEST'...")
    run_cmd(f"adb shell input tap {TAP_X} {TAP_Y}")

    # --- WALL CLOCK TIMER START ---
    start_time = time.perf_counter()
    end_time = start_time + TEST_DURATION
    
    csv_filename = f"skynet_telemetry_{gov}_run{run_num}.csv"
    with open(csv_filename, mode='w', newline='') as f:
        writer = csv.writer(f)
        writer.writerow(["Time(s)", "Temp(C)", "Power(W)", "Gov_Memory(KB)"])

        print(f"[TEST] Collecting telemetry based on Wall-Clock time...")

        while True:
            current_time = time.perf_counter()
            elapsed = current_time - start_time
            
            if elapsed >= TEST_DURATION:
                break # Exit loop exactly at 180s

            t, v, i, w = get_telemetry()
            gov_mem_kb = get_gov_memory(gov)

            # Log the ACTUAL elapsed time, not just a counter
            writer.writerow([round(elapsed, 2), t, w, gov_mem_kb])

            if int(elapsed) % 10 == 0:
                print(f"   -> {int(elapsed)}s / {TEST_DURATION}s | Temp: {t}°C | Pwr: {w}W")

            # Anti-dimming tap
            if int(elapsed) > 0 and int(elapsed) % 60 == 0:
                run_cmd("adb shell input tap 10 10")

            # Smart Sleep: Adjust sleep to stay on track with POLL_RATE
            # This accounts for the time it took to run get_telemetry()
            time_to_next_poll = POLL_RATE - (time.perf_counter() - current_time)
            if time_to_next_poll > 0:
                time.sleep(time_to_next_poll)

    # --- TEST FINISHED ---
    take_screenshot(gov, run_num)
    print("[TEST] Run complete. Killing Skynet...")
    run_cmd(f"adb shell am force-stop {APP_PACKAGE}")
    print(f"\n==================================================")
    print(f"  STARTING SKYNET THROTTLE TEST: {gov.upper()} (Run {run_num}/{RUNS_PER_GOV})")
    print(f"==================================================")
    
    run_cmd("adb shell svc power stayon usb")
    run_cmd("adb shell input keyevent 224")
    time.sleep(1)
    
    print(f"[TEST] Launching {APP_PACKAGE}...")
    run_cmd(f"adb shell monkey -p {APP_PACKAGE} -c android.intent.category.LAUNCHER 1 > /dev/null 2>&1")
    time.sleep(5) 
    
    print(f"[TEST] Tapping 'START TEST' button at X:{TAP_X} Y:{TAP_Y}...")
    run_cmd(f"adb shell input tap {TAP_X} {TAP_Y}")
    
    csv_filename = f"skynet_telemetry_{gov}_run{run_num}.csv"
    with open(csv_filename, mode='w', newline='') as f:
        writer = csv.writer(f)
        writer.writerow(["Time(s)", "Temp(C)", "Power(W)", "Gov_Memory(KB)"])
        
        print(f"[TEST] CPU at 100%. Collecting telemetry for {TEST_DURATION} seconds...")
        
        # Rigid, fixed-time loop for exactly 5 minutes
        for elapsed in range(0, TEST_DURATION + 1, int(POLL_RATE)):
            t, v, i, w = get_telemetry()
            gov_mem_kb = get_gov_memory(gov)
            
            writer.writerow([elapsed, t, w, gov_mem_kb])
            
            if elapsed % 10 == 0:
                print(f"       -> {elapsed}s | Temp: {t}°C | Pwr: {w}W | Gov Mem: {gov_mem_kb} KB")
                
            # Prevent screen dimming
            if elapsed > 0 and elapsed % 60 == 0:
                run_cmd("adb shell input tap 10 10")
            
            time.sleep(POLL_RATE)
    take_screenshot(gov, run_num)
    
    print("[TEST] Run complete. Force killing Skynet to halt CPU load...")
    run_cmd(f"adb shell am force-stop {APP_PACKAGE}")

def main():
    print("Initializing Skynet Throttle Automation Lab...")
    # Ensure app is dead before we start
    run_cmd(f"adb shell am force-stop {APP_PACKAGE}")
    
    for gov in GOVERNORS:
        set_governor(gov)
        for run_num in range(1, RUNS_PER_GOV + 1):
            wait_for_cooldown()
            run_benchmark(gov, run_num)
            
    run_cmd("adb shell svc power stayon false")
    print("\n[SYSTEM] All Skynet throttle cycles successfully completed.")

if __name__ == "__main__":
    try:
        main()
    except KeyboardInterrupt:
        run_cmd(f"adb shell am force-stop {APP_PACKAGE}")
        run_cmd("adb shell svc power stayon false")
        print("\n\n[!] Test aborted by user. Skynet killed and screen locks released.")
        sys.exit(0)