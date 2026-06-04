# **Dataset: [Planet-Scale IoT Connectivity via LEO Satellites](https://conferences.sigcomm.org/sigcomm/2026/)**

## Overview

This repository releases measurement traces collected from an operational LEO satellite IoT network and reproduces the results presented in our SIGCOMM 2026 paper.

## Repository Structure

```graphql
AlphaWAN/
├── Constellation-calender/      # This data describes the orbital position and motion state of a satellite over time, helping predict satellite passes, visibility windows, and potential communication opportunities.
├── Energy profile/              # xxx
├── Evaluation/                  # xxx
├── Link-testing-data/           # xxx
├── PHY-=trace/                  # xxx
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

- **Server**: A workstation with Ethernet/WiFi connectivity for gateway backhaul and ChirpStack hosting.
- **Gateways**: COTS LoRaWAN gateways (e.g., WisGate RAK7268CV2).
    
    *Minimum: 3 gateways.*
    
- **LoRa Nodes**: SX1276 radios (e.g., Dragino LoRa Shield) with Arduino Uno boards.
    
    *Recommended: ≥ 48 nodes for full-scale evaluation.*
    

### 💻 Software

- **MATLAB**: R2023b
- **Arduino IDE**: v1.8.X
- **Docker Desktop**: v4.35.X (for Windows OS)
- **Operating System**: Windows 10 or Ubuntu 22.04 LTS

## Reproducing Results

If you don’t have enough experimental devices, you can evaluate AlphaWAN through our provided data traces and experiment scripts under `Evaluation/`. Refer to readme in the corresponding folders for details.

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
