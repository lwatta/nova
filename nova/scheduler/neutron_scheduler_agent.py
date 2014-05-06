__author__ = 'nalle'

from oslo import messaging
from nova.objects import base as objects_base
from nova import rpc


class NeutronScheduler(messaging.RPCClient):

    def __init__(self, transport):
        target = messaging.Target(topic='filter_scheduler', version='3.0')
        super(NeutronScheduler, self).__init__(transport, target)

    def neutron_scheduler(self, hosts, chain_name, weights, resource):
        """Make a remote process call to use Neutron's filter scheduler."""
        cctxt = self.prepare()
        return cctxt.call('neutron_filter_scheduler',
                                               resource=resource,
                                               hosts=hosts,
                                               chain_name=chain_name,
                                               weight_functions = weights)