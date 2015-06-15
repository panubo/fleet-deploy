#!/usr/bin/env python

from __future__ import print_function

from time import sleep
import math
import sys

import click
import fleet.v1 as fleet


class FleetConnection(object):
    """ Connection / client """

    def __new__(cls, fleet_uri):
        try:
            return fleet.Client(fleet_uri)
        except ValueError as e:
            print('Unable to connect to Fleet: {0}'.format(e))
            raise SystemExit


class Instance(object):
    """ Unit Instance """

    def __init__(self, fleet_client, name):
        self.fleet = fleet_client
        self.name = name

    def __str__(self):
        return self.name

    @property
    def details(self):
        return "%s %s" % (self, self.get_state())

    def start(self):
        return self.fleet.set_unit_desired_state(self.name, 'launched')

    def stop(self):
        return self.fleet.set_unit_desired_state(self.name, 'inactive')

    def get_state(self):
        """ Return current state """
        for unit in self.fleet.list_unit_states():
            if unit.name == self.name:
                return unit.systemdSubState

    @property
    def is_running(self):
        if self.get_state() == 'running':
            return True
        else:
            return False


class BaseDeploymentManager(object):

    name = 'Base Deployment'

    def __init__(self, fleet_client, service_name, *args, **kwargs):
        self.fleet = fleet_client
        self.service_name = service_name
        # find list of relevant units
        self.units = list()
        for u in self.fleet.list_units():
            if u['name'].startswith(service_name):
                unit = Instance(fleet_client, u['name'])
                self.units.append(unit)
        if len(self.units) == 0:
            raise Exception('No units found')


class SimpleDeployment(BaseDeploymentManager):
    """ Simple Deployment: just stop and start all units """

    name = 'Simple'

    def stop_wait_start(self, from_idx=0, to_idx=None):
        """ Stop and Wait for unit to start """
        print("%s Deploy of Unit Ranges: %s-%s" % (self.name, from_idx, to_idx))
        for unit in self.units[from_idx:to_idx]:
            unit.stop()

        for unit in self.units[from_idx:to_idx]:
            print("Stopping %s..." % unit.name, end='')
            while unit.is_running is True:
                print('.', end='')
                sys.stdout.flush()
                sleep(1)
            print("Done.")

        for unit in self.units[from_idx:to_idx]:
            unit.start()

        for unit in self.units[from_idx:to_idx]:
            print("Starting %s..." % unit.name, end='')
            while unit.is_running is False:
                print('.', end='')
                sys.stdout.flush()
                sleep(1)
            print("Done.")

    def run(self):
        # Stop, Wait, Start all...
        self.stop_wait_start()


class FiftyFiftyDeployment(SimpleDeployment):
    """ 50/50: stop and restart half, then the other half """

    name = 'Fifty Fifty'

    def run(self):
        count = len(self.units)
        fifty = int(math.ceil(len(self.units)/2))
        # print("Count: %s, Half:%s" % (count, fifty))
        self.stop_wait_start(0, fifty)
        self.stop_wait_start(fifty, count)


class SpawnDeployment(SimpleDeployment):
    """ Spawn: spawn new units, then destroy the old. """

    name = 'Spawning'

    def __init__(self, *args, **kwargs):
        raise NotImplementedError('Not yet Implemented')
        super(SpawnDeployment, self).__init__(*args, **kwargs)


@click.command()
@click.option('--fleet-endpoint', default='http+unix://%2Fvar%2Frun%2Ffleet.sock', help="Fleet URI / socket", envvar='FLEETCTL_ENDPOINT')
@click.option('--name', required=True, help="Name of service to deploy")
@click.option('--method', default='simple', type=click.Choice(['simple', 'fiftyfifty', 'spawn']), help="Deployment method")
def main(fleet_endpoint, name, method):
    """Main function"""
    deployment_method_map = {
        'simple': SimpleDeployment,
        'fiftyfifty':  FiftyFiftyDeployment,
        'spawn': SpawnDeployment,
    }
    connection = FleetConnection(fleet_endpoint)
    method_obj = deployment_method_map[method]
    deployment = method_obj(connection, name)
    deployment.run()

if __name__ == '__main__':
    main()
