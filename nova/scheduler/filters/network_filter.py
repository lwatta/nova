# Copyright (c) 2011-2012 OpenStack, LLC.
# All Rights Reserved.
#
#    Licensed under the Apache License, Version 2.0 (the "License"); you may
#    not use this file except in compliance with the License. You may obtain
#    a copy of the License at
#
#         http://www.apache.org/licenses/LICENSE-2.0
#
#    Unless required by applicable law or agreed to in writing, software
#    distributed under the License is distributed on an "AS IS" BASIS, WITHOUT
#    WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied. See the
#    License for the specific language governing permissions and limitations
#    under the License.

import json
import string       # Spliting agains ',' delimiter
from nova.scheduler import filters
from nova.openstack.common import log as logging
from oslo.config import cfg # Read nova.conf file
from nova import db                   # Get compute node capabilities

LOG = logging.getLogger(__name__)
CONF = cfg.CONF

pci_passthru_networks = [
    cfg.StrOpt('pci_passthru_networks',
                    default=None,
                    help='Networks to which direct pci devices are attached')
]

CONF.register_opts(pci_passthru_networks)

class NetworkFilter(filters.BaseHostFilter):
    """ Filter the host pased on the net pci devices available
        for direct mapping. This is currently specified in extra_specs
        If requested for one, then check filter the host based on its
        capabilities. """
    def __init__(self):
        self.passthru_networks = CONF.pci_passthru_networks;
        if not self.passthru_networks: # If it is not specified in the conf file
	    self.passthru_networks = list(); # Empty list
        elif not isinstance(self.passthru_networks, (list, tuple)):
            self.passthru_networks = \
                [string.strip(s) for s in self.passthru_networks.split(',')]

    def host_passes(self, host_state, filter_properties):
        LOG.debug('##### NetworkHostsFilter for %s #####' % host_state.host);
#        LOG.debug('##### NetworkHostsFilter for %s #####' % filter_properties);

        context = filter_properties['context']

        for n in self.passthru_networks:
            LOG.debug(_('ALL Passthru networks: %s') % n)

        extra_specs = filter_properties['instance_type']['extra_specs']
        if len(extra_specs) == 0: # No PCI passthru requested for this instance
            LOG.debug('No PCI passthru requested for this instance')
            return True;

        if not extra_specs.has_key('pci_devices'):
            # No PCI devices listed. Extra specs may be for something else
            LOG.debug('No PCI devices listed. Extra specs may be for something else')
            return True;

        # Compute node updates the DB with pci information in compute_node DB
        # when the instance is created or deleted. Use that information directly.
        host_dev_list = []
        compute_nodes = db.compute_node_get_all(context)
        for compute in compute_nodes:
            if compute['hypervisor_hostname'] == host_state.nodename:
                host_dev_list = json.loads(compute['net_pci_passthru']);
                break;

        if len(host_dev_list) == 0:
            # PCI passthru requested for this instance,
            # but host has not advertised it
            LOG.error('PCI passthru requested for this instance, '
                'but host %s does not have the capability' % host_state.host);
            return False; # Do not select this host

        pci_dev_string = extra_specs['pci_devices'];
        pci_devices = json.loads(pci_dev_string)

        # If specific network ID is not specified then choose all that are
        # specified in the conf file.
        for pci_dev in pci_devices:
            if pci_dev.has_key('network_id'):
                netids = [pci_dev['network_id']]
            else:
                netids = self.passthru_networks;

            satisfy_score = len(netids);
            LOG.error('satisfy_score %s' % satisfy_score);
            assert(satisfy_score > 0);

            pci_class = pci_dev['pci_class']
            count = pci_dev['count']

            for network_id in netids:
                for hdev in host_dev_list:
                    if hdev['network_id'] == network_id and \
                        hdev['pci_class'] == pci_class and \
                        hdev['avail'] >= count:
                            satisfy_score = satisfy_score - 1;

            if satisfy_score != 0:
            	start_score = len(netids);
                LOG.error('##### NetworkHostsFilter for %s #####' % host_state.host);
                LOG.error('satisfy_score > 0: %d (%d)' % (satisfy_score, start_score));
                LOG.error('REQUESTED: pci_class: %s, netid: %s, count: %d' %
                    (pci_class, network_id, count))
                LOG.error('AVAILABLE: %s' % host_dev_list)
                LOG.error('#############################')
                return False;

        LOG.debug("NetworkFilter return Success for %s" % host_state.host);
        return True
