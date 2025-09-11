# Marstek Energy Storage Integration

A lightweight local integration for Marstek energy storage systems using UDP-JSON protocol.

## Features
- Real-time monitoring of battery SoC, power flows, and energy counters
- Control operating modes (Auto, AI, Manual, Passive)
- Local polling - no cloud dependency
- Easy UI configuration

## Compatibility
- Tested with Marstek Venus v2, Firmware V154
- Requires API enabled on port 30000

## Installation
This integration can be installed through HACS or manually by copying the files to your `custom_components/marstek/` directory.
```

## 4. Verify manifest.json

Ensure your `manifest.json` includes required fields:

```json:custom_components/marstek/manifest.json
{
  "domain": "marstek",
  "name": "Marstek Energy Storage",
  "version": "0.6.11",
  "documentation": "https://github.com/nbesseghir/ha-marstek",
  "issue_tracker": "https://github.com/nbesseghir/ha-marstek/issues",
  "dependencies": [],
  "config_flow": true,
  "codeowners": ["@nbesseghir"],
  "requirements": [],
  "iot_class": "local_polling"
}