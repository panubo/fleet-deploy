# Panubo Fleet Deploy

[![Build Status](https://travis-ci.org/panubo/fleet-deploy.svg?branch=master)](https://travis-ci.org/panubo/fleet-deploy)

A CLI tool to facilitate Fleet unit deployments.

## Deployment Methods

The following deployment methods are supported:

- Simple Stop-Start: just stop and start all units in one go
- Rolling Stop-Start: Start and stop units in succession by chunking quantity
- Atomic Switchover: Spawn new units, execute atomic-handler script, then destroy the old units. The atomic-handler
is responsible for service discovery updates to make the deployment seamless.

## Usage

```
Usage: deploy.py [OPTIONS]

  Main function

Options:
  --fleet-endpoint TEXT           Fleet URI / socket
  --name TEXT                     Name of service to deploy  [required]
  --tag TEXT                      Tag label. eg Git tag
  --method [stopstart|rolling|atomic]
                                  Deployment method
  --instances INTEGER             Desired number of instances
  --unit-file FILENAME            Unit template file
  --atomic-handler PATH           Program to handle atomic operations
  --chunking INTEGER              Number of containers to act on each pass. Eg
                                  2
  --chunking-percent INTEGER      Percentage of containers to act on each
                                  pass. Eg 50
  --delay INTEGER                 Startup delay
  --help                          Show this message and exit.
```

## Example

```
$ ./deploy.py --name docs --method rolling --chunking-percent 50
*** Rolling Deployment Plan ***
==> Details
Found unit: docs-a.service (launched).
Found unit: docs-b.service (launched).
Chunking: 1 units
==> Steps
Step 1: stop docs-a.service
Step 2: start docs-a.service
Step 3: stop docs-b.service
Step 4: start docs-b.service
==> Run
Starting in 5 seconds... 5 4 3 2 1... Starting.
==> Executing
Stopping docs-a.service.....Done.
Starting docs-a.service..................Done.
Stopping docs-b.service.....Done.
Starting docs-b.service.................Done.
Finished.
```

## TODO

- Add wait timeouts for Fleet operations 
- Exception handling
- Test coverage

## Status

Under active development. Consider it Alpha status.
