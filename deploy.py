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

    def __init__(self, name, state, intended_action='redeploy'):
        self.name = name
        self.state = state  # inactive, launched, uncreated
        self.intended_action = intended_action  # redeploy, create, destroy

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

        if action not in ('start', 'stop', 'spawn', 'destroy'):
            raise Exception('Invalid action')

    def __str__(self):
        return "%s %s" % (self.action, self.name)


class Plan(object):
    """ Collection of deployment steps and execution methods """

    def __init__(self, fleet_client, steps, unit_template):
        self.fleet = fleet_client
        self.steps = steps
        self.unit_template = unit_template

    def __str__(self):
        return "Plan %s" % len(self.steps)

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

        if step.action == 'spawn':
            click.echo("Spawning %s..." % step.name, nl=False)
            self.fleet.create_unit(step.name, fleet.Unit(from_string=self.unit_template))
            while is_running() is False:
                click.echo('.', nl=False)
                sleep(1)
            click.echo("Done.")

        if step.action == 'destroy':
            click.echo("Destroying %s..." % step.name, nl=False)
            self.fleet.set_unit_desired_state(step.name, 'inactive')
            while is_running() is True:
                click.echo('.', nl=False)
                sleep(1)
            self.fleet.destroy_unit(step.name)
            click.echo("Done.")


class BaseDeployment(object):

    name = 'Base Deployment'
    plan = object()
    units = list()
    chunking_count = 1
    unit_template = None

    def __init__(self, fleet_client, service_name, tag, instances):

        self.fleet = fleet_client
        self.service_name = service_name
        self.tag = tag

        # find relevant units that exist in the cluster
        for u in self.fleet.list_units():
            if u['name'].startswith(service_name + '-'):
                if u['name'] != "%s@.service" % service_name:  # Exclude service templates
                    unit = Instance(u['name'], u['currentState'])
                    self.units.append(unit)

        if instances is None:
            # assume desired is current state
            self.desired_units = self.current_unit_count
        else:
            self.desired_units = instances

        # mark excess units for destruction
        i = 0
        while i > self.unit_count_difference:
            self.units[i].intended_action = 'destroy'
            i -= 1

        # define the creation of new units here
        i = 0
        spawn = list()
        while i < self.unit_count_difference:
            spawn.append(Instance(self.get_service_name(self.current_unit_count+i+1), 'uncreated', 'spawn'))
            i += 1
        self.units.extend(spawn)

        if self.current_unit_count == 0:
            raise Exception('No units found')

    def get_service_name(self, idx):
        return "%s-%s@%s.service" % (self.service_name, self.tag, idx)

    def update_chunking(self, chunking, chunking_percent):
        # update chunking_count based on our parameters and the number of units
        if chunking_percent is not None:
            if self.unit_count_difference < 0:
                # we are destroying some, exclude from the chunking calculation
                units_to_deploy = self.current_unit_count + self.unit_count_difference
            else:
                units_to_deploy = self.current_unit_count
            self.chunking_count = int(math.ceil((float(units_to_deploy)*(float(chunking_percent)/float(100)))))
        else:
            if chunking is not None:
                self.chunking_count = chunking

        if chunking > self.current_unit_count:
            raise click.UsageError('--chunking cannot be greater than --instances.')

    @property
    def current_unit_count(self):
        return len(self.units)

    @property
    def unit_count_difference(self):
        return self.desired_units - self.current_unit_count

    def create_plan(self):
        steps = list()
        i = 0
        while i < self.current_unit_count:
            from_idx = i
            to_idx = i + self.chunking_count
            if to_idx > self.current_unit_count:
                to_idx = self.current_unit_count

            for unit in self.units[from_idx:to_idx]:
                if unit.intended_action == 'spawn':
                    steps.insert(0, Step('spawn', unit.name))
                if unit.intended_action == 'redeploy':
                    steps.append(Step('stop', unit.name))
            for unit in self.units[from_idx:to_idx]:
                if unit.intended_action == 'redeploy':
                    steps.append(Step('start', unit.name))
                if unit.intended_action == 'destroy':
                    steps.append(Step('destroy', unit.name))
            i = to_idx
        self.plan = Plan(self.fleet, steps, self.unit_template)

    def load_unit_template(self):
        # load service template from fleet
        self.unit_template = self.fleet.get_unit("%s@.service" % self.service_name)
        return self.unit_template

    def set_unit_template(self, template):
        self.unit_template = template
        return self.unit_template

    def describe_plan(self):
        # let us know what will be done, if anything
        if self.unit_count_difference > 0:
            click.echo("Insufficient units found. %s will be spawned." % self.unit_count_difference)
        if self.unit_count_difference < 0:
            click.echo("Excess units found. %s will be destroyed." % abs(self.unit_count_difference))

        click.echo("*** %s Deployment Plan ***" % self.name)

        click.echo("==> Details")
        for u in self.units:
            click.echo("Unit: %s (%s)." % (u.name, u.state))
        click.echo("Chunking: %s units" % self.chunking_count)

        click.echo("==> Steps")
        i = 0
        for step in self.plan.steps:
            i += 1
            click.echo("Step %s: %s" % (i, step))

    def run(self):
        self.plan.run()
        click.echo("Finished.")


class SimpleDeployment(BaseDeployment):
    """ Simple Deployment: just stop and start all units """

    name = 'Stop Start'

    def __init__(self, *args, **kwargs):
        super(SimpleDeployment, self).__init__(*args, **kwargs)
        self.chunking_count = self.current_unit_count


class RollingDeployment(BaseDeployment):
    """ Rolling Deployment: Start and Stop units by chunking """

    name = 'Rolling'


class AtomicRollingDeployment(BaseDeployment):
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
@click.option('--chunking', type=click.INT, help="Number of containers to act on each pass. Eg 2")
@click.option('--chunking-percent', type=click.INT, help="Percentage of containers to act on each pass. Eg 50")
@click.option('--delay', default=5, type=click.INT, help="Startup delay")
def main(fleet_endpoint, name, tag, method, instances, unit_file, chunking, chunking_percent, delay):
    """Main function"""

    # Validation
    if chunking is not None and chunking_percent is not None:
        raise click.UsageError('Cannot use --chunking and --chunking-percent together.')

    if chunking_percent is not None and not 0 <= chunking_percent <= 100:
        raise click.UsageError('Invalid --chunking-percent. Valid values 0 - 100.')

    # stopstart validation
    if method == 'stopstart' and unit_file is not None:
        raise click.UsageError('--unit-file is not valid for stopstart deployment')

    if method == 'stopstart' and chunking is not None:
        raise click.UsageError('--chunking is not valid for stopstart deployment')

    if method == 'stopstart' and chunking_percent is not None:
        raise click.UsageError('--chunking-percent is not valid for stopstart deployment')

    if method == 'stopstart' and instances is not None:
        raise click.UsageError('--instances is not valid for stopstart deployment')

    if method == 'stopstart' and tag is not None:
        raise click.UsageError('--tag is not valid for stopstart deployment')

    deployment_map = {
        'stopstart': SimpleDeployment,
        'rolling':  RollingDeployment,
        'atomic': AtomicRollingDeployment,
    }
    connection = FleetConnection(fleet_endpoint)
    method_obj = deployment_map[method]
    deployment = method_obj(connection, name, tag, instances)
    if unit_file is None:
        deployment.load_unit_template()
    else:
        deployment.set_unit_template(unit_file.read())
    deployment.update_chunking(chunking, chunking_percent)
    deployment.create_plan()
    deployment.describe_plan()  # Print planned execution

    # Give chance to abort
    click.echo("==> Run")
    click.echo('Starting in %s seconds...' % delay, nl=False)
    for i in range(0, delay):
        sleep(1)
        click.echo(' %s' % (delay-i), nl=False)
    click.echo('... Starting.')
    deployment.run()

if __name__ == '__main__':
    main()