__author__ = 'nalle'

from nova.scheduler import filters
from nova.scheduler.neutron_scheduler_agent import NeutronScheduler


class NeutronFilter(filters.BaseHostFilter):

    def filter_all(self, filter_obj_list, filter_properties):

        chain_name = 'all_filter'
        weights = None
        resource = filter_properties

        return NeutronScheduler.neutron_scheduler(filter_obj_list, chain_name, weights, resource)
