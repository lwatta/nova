__author__ = 'nalle'

from oslo import messaging
from nova.openstack.common import jsonutils
from nova import rpc


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

        for i in hosts:
            i_dict = i.__dict__
            i_dict.pop('updated')
            i_dict.pop('service')
            self.host_dict.append(i_dict)

        return client.call(context, 'neutron_filter_scheduler',
                           instance=jsonutils.to_primitive(instance),
                           hosts=jsonutils.to_primitive(self.host_dict),
                           chain_name=chain_name,
                           weight_functions=weights)
