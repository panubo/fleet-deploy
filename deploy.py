#!/usr/bin/env python

from time import sleep
import math

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

    def __init__(self, name, state):
        self.name = name
        self.state = state  # inactive, launched

    def __str__(self):
        return self.name

    @property
    def details(self):
        return "%s %s" % (self, self.state)


class Step(object):
    """ Single Step in a Deployment Plan """

    def __init__(self, action, name):
        self.action = action
        self.name = name

    def __str__(self):
        return "%s %s" % (self.action, self.name)


class PlanManager(object):

    def __init__(self, fleet_client, steps):
        self.fleet = fleet_client
        self.steps = steps

    def __str__(self):
        return "StepManager %s" % len(self.steps)

    def run(self):
        click.echo("==> Executing")
        for i in range(0, len(self.steps)):
            self.execute(i)

    def execute(self, step_number):

        step = self.steps[step_number]

        def get_state(step):
            """ Return current state """
            for unit in self.fleet.list_unit_states():
                if unit.name == step.name:
                    return unit.systemdSubState

        def is_running():
            return get_state(step) == 'running'

        # run appropriate action
        if step.action == 'stop':
            click.echo("Stopping %s..." % step.name, nl=False)
            self.fleet.set_unit_desired_state(step.name, 'inactive')
            while is_running() is True:
                click.echo('.', nl=False)
                sleep(1)
            click.echo("Done.")

        if step.action == 'start':
            click.echo("Starting %s..." % step.name, nl=False)
            self.fleet.set_unit_desired_state(step.name, 'launched')
            while is_running() is False:
                click.echo('.', nl=False)
                sleep(1)
            click.echo("Done.")


class BaseDeploymentManager(object):

    name = 'Base Deployment'
    plan = object()
    units = list()

    def __init__(self, fleet_client, service_name, tag, instances, chunk, chunk_percent):

        self.fleet = fleet_client

        # find relevant units
        for u in self.fleet.list_units():
            if u['name'].startswith(service_name):
                unit = Instance(u['name'], u['currentState'])
                self.units.append(unit)
        if len(self.units) == 0:
            raise Exception('No units found')

        self.service_name = service_name
        self.tag = tag

        # update chunk_count based on our parameters and the number of units
        if chunk_percent is not None:
            count = len(self.units)
            self.chunk_count = int(math.ceil((float(len(self.units))*(float(chunk_percent)/float(100)))))
        else:
            if chunk is None:
                self.chunk_count = len(self.units)  # default to all
            else:
                self.chunk_count = chunk

        if instances is None:
            # assume desired is current state
            self.desired_instances = len(self.units)
        else:
            self.desired_instances = instances
            if len(self.units) != instances:
                raise NotImplementedError("Changing the number of instances is not implemented %s found" % len(self.units))
                # TODO: add or remove the units, and update self.units.

    def create_plan(self):
        raise NotImplementedError('Method must be implemented in subclass')

    def describe_plan(self):
        # let us know what will be done, if anything
        unit_difference = self.desired_instances - len(self.units)
        if unit_difference > 0:
            click.echo("Insufficient units found. %s will be spawned." % unit_difference)
        if unit_difference < 0:
            click.echo("Excess units found. %s will be destroyed." % unit_difference)

        click.echo("*** %s Deployment Plan ***" % self.name)

        click.echo("==> Details")
        for u in self.units:
            click.echo("Found unit: %s (%s)." % (u.name, u.state))
        click.echo("Chunking: %s units" % self.chunk_count)

        click.echo("==> Steps")
        i = 0
        for step in self.plan.steps:
            i += 1
            click.echo("Step %s: %s" % (i, step))

    def run(self):
        self.plan.run()
        click.echo("Finished.")


class SimpleDeployment(BaseDeploymentManager):
    """ Simple Deployment: just stop and start all units """

    name = 'Stop Start'

    def __init__(self, *args, **kwargs):
        super(SimpleDeployment, self).__init__(*args, **kwargs)

    def create_plan(self):
        steps = list()
        for unit in self.units:
            steps.append(Step('stop', unit.name))
        for unit in self.units:
            steps.append(Step('start', unit.name))
        self.plan = PlanManager(self.fleet, steps)


class RollingDeployment(BaseDeploymentManager):
    """ Rolling Deployment: Start and Stop units by chunking """

    name = 'Rolling'

    def create_plan(self):
        steps = list()
        i = 0
        while i < len(self.units):
            from_idx = i
            to_idx = i + self.chunk_count
            if to_idx > len(self.units):
                to_idx = len(self.units)
            for unit in self.units[from_idx:to_idx]:
                steps.append(Step('stop', unit.name))
            for unit in self.units[from_idx:to_idx]:
                steps.append(Step('start', unit.name))
            i = to_idx
        self.plan = PlanManager(self.fleet, steps)


class AtomicRollingDeployment(RollingDeployment):
    """ Atomic Deployment: Start new units and destroy old units by chunking """

    name = 'Atomic'

    # configurable by number of containers or %age.
    def __init__(self, *args, **kwargs):
        raise NotImplementedError('Atomic deployment not yet implemented')
        super(SimpleDeployment, self).__init__(*args, **kwargs)


@click.command()
@click.option('--fleet-endpoint', default='http+unix://%2Fvar%2Frun%2Ffleet.sock', help="Fleet URI / socket", envvar='FLEETCTL_ENDPOINT')
@click.option('--name', required=True, help="Name of service to deploy")
@click.option('--tag', required=False, type=click.STRING, help="Tag label. eg Git tag")
@click.option('--method', default='stopstart', type=click.Choice(['stopstart', 'rolling', 'atomic']), help="Deployment method")
@click.option('--instances', type=click.INT, help="Desired number of instances")
@click.option('--unit-file', type=click.File(), help="Unit template file")
@click.option('--chunk', type=click.INT, help="Number of containers to act on each pass. Eg 2")
@click.option('--chunk-percent', type=click.INT, help="Percentage of containers to act on each pass. Eg 50")
@click.option('--delay', default=5, type=click.INT, help="Startup delay")
def main(fleet_endpoint, name, tag, method, instances, unit_file, chunk, chunk_percent, delay):
    """Main function"""

    # Validation
    if chunk is not None and chunk_percent is not None:
        raise click.UsageError('Cannot use --chunk and --chuck-percent together.')

    if chunk_percent is not None and not 0 <= chunk_percent <= 100:
        raise click.UsageError('Invalid --chuck-percent. Valid values 0 - 100.')

    if chunk is not None and chunk > instances:
        raise click.UsageError('--chunk cannot be greater than --instances.')

    # stopstart validation
    if method is 'stopstart' and unit_file is not None:
        raise click.UsageError('--unit-file is not valid for stopstart deployment')

    if method is 'stopstart' and chunk is not None:
        raise click.UsageError('--chunk is not valid for stopstart deployment')

    if method is 'stopstart' and chunk_percent is not None:
        raise click.UsageError('--chunk-percent is not valid for stopstart deployment')

    if method is 'stopstart' and instances is not None:
        raise click.UsageError('--instances is not valid for stopstart deployment')

    if method is 'stopstart' and tag is not None:
        raise click.UsageError('--tag is not valid for stopstart deployment')

    deployment_map = {
        'stopstart': SimpleDeployment,
        'rolling':  RollingDeployment,
        'atomic': AtomicRollingDeployment,
    }
    connection = FleetConnection(fleet_endpoint)
    method_obj = deployment_map[method]
    deployment = method_obj(connection, name, tag, instances, chunk, chunk_percent)
    deployment.create_plan()
    deployment.describe_plan()  # Print planned execution

    # Give chance to abort
    click.echo("==> Run")
    click.echo('Starting in %s seconds...' % delay, nl=False)
    for i in range(0, delay):
        sleep(1)
        click.echo(' %s' % (delay-i), nl=False)
    click.echo('... Starting.')

    if method is not 'stopstart':
        deployment.run() #unit_file
    else:
        deployment.run()

if __name__ == '__main__':
    main()