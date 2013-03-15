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

import ConfigParser # Parse the exclude hosts file
import string       # Spliting agains ',' delimiter

from nova.scheduler import filters
from nova.openstack.common import log as logging
from nova.openstack.common import cfg # Read nova.conf file
from nova import flags                # Access nova.conf variable

FLAGS = flags.FLAGS
LOG = logging.getLogger(__name__)
CONF = cfg.CONF

exclude_hosts_file_opts = [
    cfg.StrOpt('exclude_hosts_file',
                    default=None,
                    help='File that contains list of hosts to be excluded')
]

CONF.register_opts(exclude_hosts_file_opts)

class AllHostsFilter(filters.BaseHostFilter):
    """Filter hosts bases on the file contents of the file
       specified in nova.conf"""

    def host_passes(self, host_state, filter_properties):
        exclude_hosts_file = FLAGS.exclude_hosts_file; # Read from nova.conf
        exclude_hosts_list = []
        if not exclude_hosts_file is None:
            exclude_hosts = ConfigParser.ConfigParser()
            exclude_hosts.read(exclude_hosts_file)
            try:
                hosts_str = exclude_hosts.get("DEFAULT", "hostnames")
                hosts_list = [string.strip(s) for s in hosts_str.split(',')]
                exclude_hosts_list.extend(hosts_list);
            except:
                LOG.error("Exclude hosts file (%s) invalid format or empty. Ignored" % exclude_hosts_file)

        if host_state.host in exclude_hosts_list:
            LOG.info(_("Excluded hosts from %s: " % exclude_hosts_file))
            for h in exclude_hosts_list:
                LOG.info(_("EXCLUDED HOST: %s" % h))
            LOG.info(_("%s in exclude list. Host EXCLUDED" % host_state.host))
            return False;
        return True
