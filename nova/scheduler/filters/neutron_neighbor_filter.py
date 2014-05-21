__author__ = 'nalle'

from nova.scheduler import filters
from nova.scheduler.neutron_scheduler_agent import NeutronScheduler
from nova.scheduler.host_manager import HostState
from nova import exception
from nova.db.sqlalchemy.models import Instance
from nova.db.sqlalchemy import api

class HostS(HostState):
    def __init__(self, adict):
        self.__dict__.update(adict)


def to_object(adict):
    return HostS(adict)


class NeutronNeighborFilter(filters.BaseHostFilter):

    def get_physical_host(self, context, vm):
        query = api._build_instance_get(context)
        hostname = query.filter_by(hostname=vm).first()

        return hostname.host

    def filter_all(self, filter_obj_list, filter_properties):

        neighbor_vm = 'all'
        chain_name = 'neighbor_filter'
        weights = None
        instance = filter_properties
        topic = 'topic.filter_scheduler'
        ns = NeutronScheduler(topic)
        physical_host = self.get_physical_host(instance.get('context'), neighbor_vm)
        kwargs = {
        'neighbor_physical_host': physical_host,
                 }
        hosts = ns.neutron_scheduler(filter_obj_list, chain_name, weights, instance, **kwargs)

        if hosts == 'No valid host':
            raise exception.NoValidHost(reason="")

        neutron_filtered_hosts = []

        for h in hosts:
            neutron_filtered_hosts.append(to_object(h))

        return neutron_filtered_hosts
