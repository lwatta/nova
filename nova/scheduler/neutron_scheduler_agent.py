__author__ = 'nalle'

from oslo import messaging
from nova.openstack.common import jsonutils
from nova import rpc
import copy

class NeutronScheduler(object):
    def __init__(self):
        super(NeutronScheduler, self).__init__()
        target = messaging.Target(topic='topic.filter_scheduler', version='3.0')
        self.client = rpc.get_client(target)
        self.host_dict = []

    def neutron_scheduler(self, hosts, chain_name, weights, instance):
        """Make a remote process call to use Neutron's filter scheduler."""
        client = self.client.prepare()
        context = instance.pop('context')
        new_hosts = copy.deepcopy(hosts)

        for i in new_hosts:
            i.__dict__.pop('updated')
            i.__dict__.pop('service')
            self.host_dict.append(i.__dict__)

        return client.call(context, 'neutron_filter_scheduler',
                           instance=jsonutils.to_primitive(instance),
                           hosts=jsonutils.to_primitive(self.host_dict),
                           chain_name=chain_name,
                           weight_functions=weights)
