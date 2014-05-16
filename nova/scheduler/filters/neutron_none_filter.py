__author__ = 'nalle'

from nova.scheduler import filters
from nova.scheduler.neutron_scheduler_agent import NeutronScheduler
from nova.scheduler.host_manager import HostState
from nova import exception

class HostS(HostState):
    def __init__(self, adict):
        self.__dict__.update(adict)

def to_object(adict):
    return HostS(adict)


class NeutronFilter(filters.BaseHostFilter):

    def filter_all(self, filter_obj_list, filter_properties):

        chain_name = 'no_filter'
        weights = None
        instance = filter_properties
        exchange = 'neutron'
        topic = 'topic.filter_scheduler'
        ns = NeutronScheduler(topic)
        hosts = ns.neutron_scheduler(filter_obj_list, chain_name, weights, instance)

        if hosts == 'No valid host':
            raise exception.NoValidHost(reason="")

        neutron_filtered_hosts = []

        for h in hosts:
            neutron_filtered_hosts.append(to_object(h))

        return neutron_filtered_hosts
