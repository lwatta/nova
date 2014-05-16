__author__ = 'nalle'

from nova.scheduler import filters
from nova.scheduler.neutron_scheduler_agent import NeutronScheduler


class Host(object):
    def __init__(self, **entries):
        return self.__dict__.update(entries)


class NeutronFilter(filters.BaseHostFilter):

    def filter_all(self, filter_obj_list, filter_properties):

        chain_name = 'all_filter'
        weights = None
        instance = filter_properties
        exchange = 'neutron'
        topic = 'topic.filter_scheduler'
        ns = NeutronScheduler(topic)
        hosts = ns.neutron_scheduler(filter_obj_list, chain_name, weights, instance)
        for h in hosts:
            Host(**h)

        print ('sd')
        return hosts
