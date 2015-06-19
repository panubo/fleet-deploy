#!/usr/bin/env python

from time import sleep
import math
from subprocess import Popen, PIPE

import click
import fleet.v1 as fleet
from ordered_set import OrderedSet

try:
    # For Python 3.0 and later
    from http.client import ResponseNotReady
except ImportError:
    # Fall back to Python 2
    from httplib import ResponseNotReady

FLEET_ENDPOINT_DEFAULT = 'http+unix://%2Fvar%2Frun%2Ffleet.sock'


class FleetConnection(object):
    """ Connection / client """

    def __new__(cls, fleet_uri):
        try:
            return fleet.Client(fleet_uri)
        except (ValueError, ResponseNotReady) as e:
            raise SystemExit('Unable to connect to Fleet: {0}'.format(e))


class Instance(object):
    """ Unit Instance """

    def __init__(self, name, state, required_action='redeploy'):
        self.name = name
        self.state = state
        self.required_action = required_action

        if state not in ('inactive', 'launched', 'uncreated'):
            raise Exception('Invalid state')

        if required_action not in ('redeploy', 'spawn', 'destroy'):
            raise Exception('Invalid required_action')

    def __str__(self):
        return self.name

    def __repr__(self):
        return "'%s'" % self.name

    @property
    def details(self):
        return "%s %s" % (self, self.state)


class Step(object):
    """ Single Step in a Deployment Plan """

    def __init__(self, name, action):
        self.name = name
        self.action = action

        if action not in ('start', 'stop', 'spawn', 'destroy', 'external_script'):
            raise Exception('Invalid action')

    def __str__(self):
        return "%s %s" % (self.action, self.name)

    def __repr__(self):
        return "'%s'" % self.name


class Plan(object):
    """ Collection of deployment steps and execution methods """

    def __init__(self, fleet_client, unit_template):
        self.fleet = fleet_client
        self.unit_template = unit_template
        self.steps = OrderedSet()

    def __str__(self):
        return "Plan %s" % len(self.steps)

    def get_by_action(self, action):
        result = list()
        for step in self.steps:
            if step.action == action:
                result.append(step)
        return result

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

        if step.action == 'external_script':
            click.echo("Executing %s with data: " % step.name, nl=False)
            data = self.get_external_script_payload()
            click.echo(data)
            self.execute_external_script(step.name, data)

    @staticmethod
    def execute_external_script(script, data):
        # run the script as a subprocess:
        p = Popen([script], stdin=PIPE, stdout=PIPE, stderr=PIPE, shell=False)
        # pass the data
        p.stdin.write(str(data))
        p.stdin.close()

    def get_external_script_payload(self):
        return {
            'add': self.get_by_action('spawn'),
            'remove': self.get_by_action('destroy')
        }


class BaseDeployment(object):

    name = 'Base Deployment'

    def __init__(self, fleet_client, service_name, tag):

        self.fleet = fleet_client
        self.service_name = service_name
        self.tag = tag

        self.plans = list() # Plan(fleet_client=fleet_client, unit_template=None)
        self.units = OrderedSet()
        self.chunking_count = 1  # default
        self.unit_template = None

    def load(self, instances):
        """ Run logic and API calls to setup Units """
        # find relevant units that exist in the cluster
        for u in self.fleet.list_units():
            if u['name'].startswith(self.service_name + '-'):
                if u['name'] != "%s@.service" % self.service_name:  # Exclude service templates
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
            self.units[i].required_action = 'destroy'
            i -= 1

        # define the creation of new units here
        i = 0
        spawn = list()
        while i < self.unit_count_difference:
            i += 1
            spawn.append(Instance(self.get_service_name(self.current_unit_count+i), 'uncreated', 'spawn'))
        for s in spawn:
            self.units.append(s)

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

    def create_plans(self):
        i = 0
        while i < self.current_unit_count:
            plan = Plan(self.fleet, self.unit_template)
            from_idx = i
            to_idx = i + self.chunking_count
            if to_idx > self.current_unit_count:
                to_idx = self.current_unit_count

            for unit in self.units[from_idx:to_idx]:
                if unit.required_action == 'spawn':
                    plan.steps.append(Step(unit.name, 'spawn'))
                if unit.required_action == 'redeploy':
                    plan.steps.append(Step(unit.name, 'stop'))
            for unit in self.units[from_idx:to_idx]:
                if unit.required_action == 'redeploy':
                    plan.steps.append(Step(unit.name, 'start'))
                if unit.required_action == 'destroy':
                    plan.steps.append(Step(unit.name, 'destroy'))
            i = to_idx
            self.plans.append(plan)

    def describe_plans(self):
        # # let us know what will be done, if anything
        # if self.unit_count_difference > 0:
        #     click.echo("Insufficient units found. %s will be spawned." % self.unit_count_difference)
        # if self.unit_count_difference < 0:
        #     click.echo("Excess units found. %s will be destroyed." % abs(self.unit_count_difference))

        click.echo("*** %s Deployment Plan ***" % self.name)

        click.echo("==> Details")
        for u in self.units:
            click.echo("Unit: %s (%s)." % (u.name, u.state))
        click.echo("Chunking: %s units" % self.chunking_count)

        click.echo("==> Deployment Plan")
        stage_idx = 1
        step_idx = 1
        for plan in self.plans:
            click.echo("==> Stage %s" % stage_idx)
            stage_idx += 1
            for step in plan.steps:
                click.echo("Step %s: %s" % (step_idx, step))
                step_idx += 1

    def run_plans(self):
        for plan in self.plans:
            plan.run()
        click.echo("Finished.")

    def load_unit_template(self):
        # load service template from fleet
        self.unit_template = self.fleet.get_unit("%s@.service" % self.service_name)
        return self.unit_template

    def set_unit_template(self, template):
        self.unit_template = template
        return self.unit_template


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

    def __init__(self, atomic_handler, *args, **kwargs):
        super(AtomicRollingDeployment, self).__init__(*args, **kwargs)
        self.handler = atomic_handler
        if atomic_handler is None:
            raise Exception('atomic_handler must be set')

    def generate_steps(self, from_idx, to_idx):
        steps = list()
        idx = from_idx + 1
        for unit in self.units[from_idx:to_idx]:
            if unit.required_action in ('spawn', 'redeploy'):
                name = self.get_service_name(idx)
                steps.append(Step(name, 'spawn'))
            idx += 1

        # Do atomic script here
        steps.append(Step(self.handler, 'external_script'))

        for unit in self.units[from_idx:to_idx]:
            if unit.required_action in ('destroy', 'redeploy'):
                steps.append(Step(unit.name, 'destroy'))
        return steps

    def create_plans(self):

        i = 0
        while i < self.current_unit_count:
            plan = Plan(self.fleet, self.unit_template)
            from_idx = i
            to_idx = i + self.chunking_count
            if to_idx > self.current_unit_count:
                to_idx = self.current_unit_count
            for step in self.generate_steps(from_idx, to_idx):
                plan.steps.append(step)
            i = to_idx
            self.plans.append(plan)


@click.command()
@click.option('--fleet-endpoint', default=FLEET_ENDPOINT_DEFAULT, help="Fleet URI / socket", envvar='FLEETCTL_ENDPOINT')
@click.option('--name', required=True, help="Name of service to deploy")
@click.option('--tag', required=False, type=click.STRING, help="Tag label. eg Git tag")
@click.option('--method', default='stopstart', type=click.Choice(['stopstart', 'rolling', 'atomic']), help="Deployment method")
@click.option('--instances', type=click.INT, help="Desired number of instances")
@click.option('--unit-file', type=click.File(), help="Unit template file")
@click.option('--atomic-handler', type=click.Path(exists=True), help="Program to handle atomic operations")
@click.option('--chunking', type=click.INT, help="Number of containers to act on each pass. Eg 2")
@click.option('--chunking-percent', type=click.INT, help="Percentage of containers to act on each pass. Eg 50")
@click.option('--delay', default=5, type=click.INT, help="Startup delay")
def main(fleet_endpoint, name, tag, method, instances, unit_file, atomic_handler, chunking, chunking_percent, delay):
    """Main function"""

    # Validation
    if chunking is not None and chunking_percent is not None:
        raise click.UsageError('Cannot use --chunking and --chunking-percent together.')

    if chunking_percent is not None and not 0 <= chunking_percent <= 100:
        raise click.UsageError('Invalid --chunking-percent. Valid values 0 - 100.')

    # atomic validation
    if method != 'atomic' and atomic_handler is not None:
        raise click.UsageError('--atomic-handler is only valid for atomic deployment')

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
    if method == 'atomic':
        deployment = method_obj(atomic_handler, connection, name, tag)
    else:
        deployment = method_obj(connection, name, tag)
    deployment.load(instances)
    if unit_file is None:
        deployment.load_unit_template()
    else:
        deployment.set_unit_template(unit_file.read())
    deployment.update_chunking(chunking, chunking_percent)
    deployment.create_plans()
    deployment.describe_plans()  # Print planned execution

    # Give chance to abort
    click.echo("==> Run")
    click.echo('Starting in %s seconds...' % delay, nl=False)
    for i in range(0, delay):
        sleep(1)
        click.echo(' %s' % (delay-i), nl=False)
    click.echo('... Starting.')
    deployment.run_plans()

if __name__ == '__main__':
    main()