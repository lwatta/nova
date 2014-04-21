__author__ = 'nalle'

from nova.scheduler import filters
from nova.scheduler.neutron_scheduler_agent import NeutronScheduler

class NeutronFilter(filters.BaseHostFilter):

    def filter_all(self, filter_obj_list, filter_properties):

        chain_id = CHAIN.ID
        weights = None
        router_id = Instance.ID

        return NeutronScheduler.neutron_scheduler(filter_obj_list, chain_id, weights, router_id)
