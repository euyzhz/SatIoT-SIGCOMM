# **Dataset: [Planet-Scale IoT Connectivity via LEO Satellites](https://conferences.sigcomm.org/sigcomm/2026/)**

## Overview

This repository releases measurement traces collected from an operational LEO satellite IoT network and reproduces the results presented in our SIGCOMM 2026 paper.

## Repository Structure

```graphql
SatIoT-SIGCOMM26/
├── Constellation-calendar/      # This data describes the orbital position and motion state of a satellite over time, helping predict satellite passes, visibility windows, and potential communication opportunities.
├── Energy profile/              # xxx
├── Evaluation/                  # xxx
├── Link-testing-data/           # xxx
├── PHY-trace/                   # xxx
├── Satellite-signaling/         # xxx
└── README.md                    # This file
```

## Getting Started

If you're new, follow the manual in each directory:

1. [Set up ChirpStack and run channel planning](https://github.com/A1phaWAN/AlphaWAN/blob/main/Network_server/README.md)
2. [Configure your gateways](https://github.com/A1phaWAN/AlphaWAN/blob/main/Gateway/README.md)
3. [Deploy end devices](https://github.com/A1phaWAN/AlphaWAN/blob/main/Node_config/README.md)
4. [Evaluate with trace or hardware](https://github.com/A1phaWAN/AlphaWAN/blob/main/Evaluation/README.md)

## Requirements
### 🔩 Hardware

- **Server**: A workstation or cloud server for receiving satellite backhaul data.
- **Satellite IoT devices**: COTS satellite IoT terminals, eg, TQZD-10.
    
    *Minimum: 3 devices.*
    
- **Host machine**: A device that can be used for serial communication (computer recommended).
    

### 💻 Software

- **Operating System**: Windows 10 or Ubuntu 22.04 LTS.
- **Python**: Python 3.8 or later.
- **MATLAB**: Required only for MATLAB-based analysis scripts.
- **Serial tools**：Required only if users want to reproduce hardware experiments with satellite IoT devices.

## Reproducing Results

xxx.

## Dataset Description

The released data covers multiple aspects of commercial LEO satellite IoT connectivity:

- **Constellation-level opportunities**: satellite passes, visibility windows, and potential contact opportunities.
- **Link-level performance**: message delivery success, latency, reliability, and backhaul behavior.
- **Physical-layer behavior**: beacon reception, signal quality, and contact dynamics.
- **Energy profile**: device energy consumption under different operating states.
- **Signaling behavior**: serial-command interaction and satellite IoT protocol logs.
- **Evaluation traces**: processed traces used for trace-driven replay and performance analysis.


## Contact

For questions, issues, or requests, please contact:

Ziyue Zhang - ziyue.zhang@connect.polyu.hk

Ruonan Li - ruo-nan.li@connect.polyu.hk

## Citation

```bibtex
@inproceedings{Zhang2026SatIoT,
 title      = {Planet-Scale IoT Connectivity via LEO Satellites},
 author     = {Ziyue Zhang, Xianjin Xia, Ruonan Li, Jinhong Liu, Yuanqing Zheng, Congcong Miao, Mo Li},
 booktitle  = {Proceedings of the ACM SIGCOMM 2026 Conference},
 year       = {2026},
 doi        = {https://doi.org/10.1145/xxxxxxx.xxxxxxx}
 }
```
