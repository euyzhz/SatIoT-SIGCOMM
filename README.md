# **[Towards Next-Generation Global IoT: Empowering Massive Connectivity with Harmonious Multi-Network Coexistence](https://a1phawan.github.io/)**

## Overview

AlphaWAN addresses the decoder contention problem in LoRaWANs, enhancing capacity and coexistence among networks. This repository contains the key components, deployment instructions, and evaluation scripts to implement AlphaWAN and reproduce the results presented in our SIGCOMM 2025 paper.

We include setup guides for the **network server**, **gateways**, and **nodes**. Operators can follow the example provided to generate and apply optimized channel configurations suitable for their network devices.

## Repository Structure

```graphql
AlphaWAN/
├── Network_server/        # ChirpStack deployment and example for channel planning
├── Gateway_cfg/           # Instructions for configuring RAK7268 gateways
├── Node_cfg/              # End-node codes and setup guide
├── Evaluation/            # Scripts and data for results reproduction
└── README.md              # This file
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
@inproceedings{Zhang2025AlphaWAN,
 title      = {Towards Next-Generation Global IoT: Empowering Massive Connectivity with Harmonious Multi-Network Coexistence},
 author     = {Ziyue Zhang, Xianjin Xia, Ruonan Li, and Yuanqing Zheng},
 booktitle  = {Proceedings of the ACM SIGCOMM 2025 Conference},
 year       = {2025},
 doi        = {https://doi.org/10.1145/3718958.3750504}
 }
```
