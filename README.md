# Neural Governor: RL-Based CPU Scheduling for ARM big.LITTLE 

![License](https://img.shields.io/badge/License-GPLv2-blue.svg)
![Architecture](https://img.shields.io/badge/Architecture-ARM64-orange.svg)
![Platform](https://img.shields.io/badge/Platform-Android%20%2F%20Linux-green.svg)

**Neural Governor** is a dynamic, machine-learning-driven CPU governor natively implemented as a Linux Loadable Kernel Module (LKM). By formulating Dynamic Voltage and Frequency Scaling (DVFS) as a Markov Decision Process, it utilizes Q-learning to anticipate workload requirements and maintain thermal equilibrium, replacing outdated, reactive heuristic schedulers like WALT.

**[Read the full IEEE Research Paper here](./docs/Neural_Governor_IEEE_Paper.pdf)**

## Key Results (Snapdragon 8s Gen 3)
Tested natively on a Xiaomi Poco F6, Neural Governor drastically outperformed the stock WALT kernel scheduler:
* **17.7% Power Reduction** during sustained 720p 60fps media playback.
* **Absolute Thermal Equilibrium** achieved under heavy hardware decoding loads.
* **37.0% Faster Context Switching** overhead reduction during massive multi-threaded IPC workloads.
* **O(1) Time Complexity** lookup ensuring zero kernel-scheduler blocking.

## Repository Architecture

```text
NeuralGovernor/
├── kernel_module/           # C source code for the Loadable Kernel Module
│   ├── Makefile             # Build instructions for the kernel headers
│   ├── neural_gov.c         # Main RL governor and state-space evaluation logic
│   └── q_table_matrix.h     # Pre-trained, quantized Q-table weights
│
├── telemetry_scripts/       # Python ADB automation and stress-testing suite
│   ├── hackbench_benchmark.py  # Automated IPC thread context-switching test
│   ├── skynet_benchmark.py     # Sustained array-computation thermal test
│   └── youtube_benchmark.py     # Quick Race-to-Idle thermal test
│
├── data_and_results/        # Empirical evidence and visualizations
│   ├── raw_csv_logs/        # Raw PMIC telemetry data (Power, Temp, Memory)
│   └── benchmark_graphs/    # High-resolution performance and thermal charts
│
└── docs/                    # Academic publications
```

## Compilation & Injection

*Note: Compiling and injecting this module requires an unlocked bootloader, a rooted Android environment (su), and the clang toolchain installed via a terminal emulator like Termux.*

### 1. Build the Module
Pull the repository to your local Android environment, navigate to the `kernel_module` directory, and run the make command to build against your device's kernel headers:

```bash
cd NeuralGovernor/kernel_module
make
```

### 2. Inject into the Kernel
Drop into a root shell and use `insmod` to inject the newly compiled `.ko` file into the live kernel environment:

```bash
su
insmod neural_gov.ko
```

### 3. Verify Registration
Ensure the governor has successfully hooked into the Linux `cpufreq` subsystem without panicking the kernel:

```bash
cat /sys/devices/system/cpu/cpufreq/policy0/scaling_available_governors
```
*(You should see `neural` listed alongside standard governors like `walt`, `performance`, or `schedutil`)*.

## Acknowledgments & Credits
While the Neural Governor is an independent, custom-built Loadable Kernel Module, compiling it natively for the Poco F6 (Snapdragon 8s Gen 3) requires specific hardware configurations. 

Massive thanks to the **Peridot Dev** open-source community for maintaining the device tree and kernel source that made the compilation and deployment of this research possible.

---
*Developed by Siva Subramanyam Ghanta *