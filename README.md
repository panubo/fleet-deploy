# Panubo Fleet Deploy

A Python CLI tool to facilitate Fleet unit deployments.

## Usage
```
Usage: deploy.py [OPTIONS]

  Main function

Options:
  --fleet-endpoint TEXT           Fleet URI / socket
  --name TEXT                     Name of service to deploy  [required]
  --method [simple|fiftyfifty|spawn]
                                  Deployment method
  --help                          Show this message and exit.
```

## Methods

The following deployment methods are supported:

- Simple - Simple Deployment: just stop and start all units
- FiftyFifty - stop and restart half, then the other half
- Spawn (not yet implemented)

## Status

Under active development. Alpha status.
